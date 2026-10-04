#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Needle-in-a-haystack test for the *token context window* of a Sparkrun recipe.

Why this file exists
--------------------
The registry ships recipes that advertise long context (the go-live DS4 recipe
serves 1,048,576 tokens), but nothing in `tools/` or `benchmarking/` actually
*exercises* a long context.  `quality-battery.py` plants one needle inside a
~3k-word haystack, which is a reasoning probe, not a context-window probe, and
`sparkrun benchmark` profiles only measure speed.  A context window can be
mis-sized, silently truncated, or served correctly and still retrieve nothing --
none of which shows up in a token/s number.

This tool builds a haystack that hits a requested context length, plants a
needle at each requested depth, and asks for it.  The default depth grid is
every 10% of the window (10, 20, ..., 90, 100), which is the standard
needle-in-a-haystack shape and the one the DSPARK/mod work cites
("needle correct at 799K", attic/ds4/AGENTS.md §7.5).

Why it is not just `curl`
-------------------------
A server that ignores `max_model_len`, truncates the prompt, or answers from a
cached prefix all return HTTP 200 with plausible text.  So the tool checks the
things a 200 cannot tell you:

* the **actual** `prompt_tokens` the server reports for each request (a window
  smaller than requested shows up here, or as a 400 -- not as a wrong answer);
* whether that count reached the requested length (silent truncation is a
  finding, not a pass);
* `temperature=0` and a per-depth-unique haystack, so a radix/prefix cache
  cannot flatter a run and the needle cannot be guessed from the question;
* the raw answer is kept and printed for every depth, pass or fail, so a
  scoring bug is visible rather than trusted.

The haystack is sized by reading the served `max_model_len` from `/v1/models`
and measuring the endpoint's chars-per-token across a small size sweep (see
`calibrate()`).  A single small probe is biased -- chars/token drifts with prompt
size -- and even the ~4.6 estimate overshoots this fleet's tokenizer by ~15%, so
the tool probes several sizes, largest-first, and uses the largest usable one.
The window is never filled exactly: a 1,048,576-token request always arrives a
little over and is rejected, so the tool targets `max_model_len` minus a small
headroom.

Stdlib only, on purpose.  This has to run on a head node, inside a container,
and on a laptop with no venv.  The only way a target gets here is
`--api-endpoint`; nothing in this file knows about any machine or cluster.

Exit codes
----------
0  every depth retrieved its needle and reached the requested context
1  transport failure / endpoint unreachable / every request errored
2  bad flags
3  a check failed: a miss, or a silently truncated (short) prompt

`--selftest` runs the whole ladder against an in-process HTTP mock with three
deliberately different behaviours (correct, always-wrong, truncating) and
asserts each is classified the way it must be.  A guard that has only ever
passed is not a guard, so the selftest is a required part of this tool.

Usage
-----
    python3 tools/needle-haystack.py \\
        --model deepseek-ai/DeepSeek-V4.1-Flash \\
        --context-length 1000000 \\
        --api-endpoint http://10.0.4.30:8000 \\
        --json needle-1m.json

    # watch it work: progress on stderr, report and --json stay on stdout
    python3 tools/needle-haystack.py --model auto --context-length 1m \\
        --api-endpoint http://10.0.4.30:8000 --verbose

    python3 tools/needle-haystack.py --selftest        # offline, no GPU

    # cheaper smoke: 64k window, depths every 25%
    python3 tools/needle-haystack.py --model auto \
        --context-length 65536 --api-endpoint http://10.0.4.30:8000 \\
        --depths 25,50,75,100

As a library, the same test takes model / context length / API endpoint as
keyword arguments:

    import needle_haystack as nh            # tools/needle-haystack.py, dash-named
    result = nh.run_needle_test(
        model="deepseek-ai/DeepSeek-V4.1-Flash",
        context_length="1m",
        api_endpoint="http://10.0.4.30:8000",
    )
    print(result["verdict"])                # PASS / FAIL / TRUNCATED / ...
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request

VERSION = "0.1"


def _vlog(verbose: bool, msg: str) -> None:
    """Progress line for ``--verbose``, timestamped.

    Goes to **stderr** and is flushed, for two reasons: the report and the
    ``--json`` artifact are on stdout and must stay clean and parseable, and a
    1M-token prefill runs for minutes, so a line buffered until exit would tell
    the user nothing while they wait -- which is exactly when they want it.

    The timestamp is local time to the second and self-contained (a fixed
    offset, no OS locale), matching the convention the log parsers in this repo
    expect rather than a bare relative offset.
    """
    if verbose:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{ts}] [nh] {msg}", file=sys.stderr, flush=True)

#: Fraction of the requested context that the server must actually report for a
#: request to count as having reached the window.  Below this, the prompt was
#: silently truncated -- which is worse than an error, because the answer can
#: still be right (or plausibly wrong) and nothing else flags it.  0.95 rather
#: than 1.0 because a real tokenizer differs from the character estimate by a
#: few percent; a genuine short window (a 128k server asked for 1M) is far below.
REACHED_FRACTION = 0.95

#: The standard needle-in-a-haystack grid: every 10% of the window.
DEFAULT_DEPTHS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

#: Used to size the haystack before the server's real tokenization is known.
#: A live 32k run measured this endpoint at ~4.0 chars/token, not the 4.6 the
#: estimate assumes, which overshoots the prompt ~15% -- at a 1M target that
#: exceeds max_model_len and the request 400s.  So the ladder calibrates once
#: (calibrate(), below) instead of trusting this value.
DEFAULT_CHARS_PER_TOKEN = 4.6

#: Token targets for the calibration sweep, largest first.  A *single* small
#: probe is noisy: each probe size builds a different haystack, so the measured
#: chars/token has a content spread that shrinks with size -- measured on this
#: fleet, ~0.65% at 8k, ~0.31% at 65k, ~0.09% at 128k -- against a true value of
#: ~4.014 (1M).  65k reads within ~0.055% of truth, which at a 1M target is a few
#: hundred tokens against a 2% (~20k) headroom, so 128k buys precision that
#: cannot change the outcome and costs ~15 s more prefill.  The smaller sizes are
#: fallbacks for narrow-window servers, where a large probe would itself 400.
CALIBRATION_TOKENS = (65536, 32768, 8192)

#: Stop sweeping once the two largest usable ratios agree this closely (the
#: remaining sizes are unlikely to move it).
CALIBRATION_AGREE_FRACTION = 0.01

#: A probe is built from the *estimate* (chars_per_token may be up to ~4.6),
#: so its real token count overshoots its target by est/true (~15%).  A probe
#: target must therefore stay this far below the window, or the probe itself is
#: the request that fills (and 400s on) the window -- the waste this whole
#: mechanism exists to avoid.
PROBE_SAFETY = 1.4

#: A sweep probe's reported tokens must be within this band of its target to be
#: trusted -- a truncated probe (a small server asked for 64k) would otherwise
#: derive a nonsensical ratio and build an even larger prompt.
CALIBRATION_BAND = 0.30

#: Character budget reserved for the wrapper (system prompt, question, tags) when
#: pacing a prompt by a *measured* token count, so the final prompt lands a hair
#: under the target instead of a hair over it.
TOKEN_HEADROOM = 24

#: Blind shrink factor, used only when the engine's too-long body carries no
#: parseable token counts.  When it does, the retry corrects the ratio from them
#: instead of shrinking blind (see run_depth).
SHRINK_FACTOR = 0.85

#: Fraction of the served window left unused, so a prompt paced from a
#: slightly-wrong chars/token ratio does not land over `max_model_len`.  Must
#: exceed that ratio error; this fleet measured ~1% on the 1M prompt, so 2%.
HEADROOM_FRACTION = 0.02

#: How many times to shrink-and-retry when the server says the prompt is too
#: long.  The calibration normally prevents this; the retry is the safety net.
SHRINK_RETRIES = 3

#: Calibration is trusted only if the probe's reported tokens are within this
#: band of the target -- a truncated calibration probe would otherwise derive a
#: nonsensical chars/token and build an even larger prompt.
CALIBRATION_BAND = 0.30

#: Filler vocabulary.  Deliberately lowercase and distinct from the uppercase
#: codewords, so a needle can never be spelled by the filler generator and the
#: containment score cannot be satisfied by accident.
FILLER_WORDS = (
    "harbor lantern granite meadow copper orchard willow quarry ember thistle "
    "saddle canvas ledger anvil compass furrow tallow gable mortar plinth "
    "cistern spindle rafter tether kiln bramble fathom marrow pewter ballast "
    "juniper lattice cobble fennel gossip heather ironwood jetty kettle linden "
    "mallow nettle oatgrass pebble quillon rushes sorrel trellis umber vellum "
    "wicket yarrow zephyr alder birch cedar dogwood elm fir grove hazel ivy"
).split()

#: Answer keys.  Kept uppercase with a digit group so a hit is unambiguous and
#: the raw reply is easy to eyeball.
CODEWORDS = (
    "KESTREL", "NARWHAL", "ORCHID", "PUMICE", "QUARTZ", "RAVEN", "SORREL",
    "TAMARIND", "UMBRA", "VIOLET", "WALRUS", "XENON", "YARROW", "ZEPHYR",
    "ALBATROSS", "BRAMBLE", "CINNABAR", "DUNLIN", "ELMWOOD", "FENNEL",
)

SYSTEM_PROMPT = (
    "You are reading a long document. Answer the question using only the "
    "document. Reply with just the requested value, nothing else."
)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def parse_context_length(value: str | int) -> int:
    """Accept ``1000000``, ``1m``, ``1M``, ``512k``, ``1_000_000``."""
    if isinstance(value, int):
        return value
    s = str(value).strip().replace("_", "").replace(",", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([kKmM]?)", s)
    if not m:
        raise ValueError(f"cannot parse context length {value!r}")
    n = float(m.group(1))
    mult = {"": 1, "k": 1000, "K": 1000, "m": 1000000, "M": 1000000}[m.group(2)]
    out = int(n * mult)
    if out <= 0:
        raise ValueError(f"context length must be positive, got {value!r}")
    return out


def build_haystack(n_chars: int, rng: random.Random) -> str:
    """Deterministic prose of roughly ``n_chars`` characters.

    Prose rather than one repeated token, because a repeated filler token is
    *easier* for a speculative decoder and hits one Engram row
    (.scratch/ds4/knapcio/docs/history.md notes the inflation).  Sentence
    boundaries are inserted so a needle can be spliced in without splitting a
    word.
    """
    out: list[str] = []
    n = 0
    while n < n_chars:
        k = rng.randint(9, 17)
        s = " ".join(rng.choice(FILLER_WORDS) for _ in range(k)).capitalize() + "."
        out.append(s)
        n += len(s) + 1
        if rng.random() < 0.07:
            out.append("\n")
            n += 1
    return " ".join(out)


def _seed(*parts: int) -> int:
    """Deterministic integer mix.

    NOT ``hash((...))``: Python randomises ``str`` hashing per process
    (PYTHONHASHSEED), so a tuple containing a string hashes differently on every
    run and the "seeded by depth" guarantee -- which both reproducibility and the
    radix-cache-avoidance argument depend on -- would be false.
    """
    h = 2166136261
    for p in parts:
        h = ((h ^ (int(p) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h


def make_needles(count: int, depth: int, seed: int) -> list[tuple[str, str, str]]:
    """Return ``(fact_sentence, question, answer_key)`` tuples for one depth.

    Seeded by depth so every depth is a different document: a shared prefix
    across depths would let a radix cache (this fleet runs one) serve the
    deeper request from the shallower one and hide a real retrieval failure.
    """
    rng = random.Random(_seed(seed, 1, depth))
    out = []
    for i in range(count):
        codeword = rng.choice(CODEWORDS)
        number = rng.randint(1000, 9999)
        key = f"{number}-{codeword}"
        fact = f"The vault access code for record {depth}-{i} is {key}."
        question = (
            f"What is the vault access code for record {depth}-{i}? "
            "Reply with only the code."
        )
        out.append((fact, question, key))
    return out


def plant(haystack: str, needles: list[tuple[str, str, str]], depth: int) -> tuple[str, list[int]]:
    """Splice each fact into ``haystack`` near ``depth`` percent, return positions.

    A single needle per depth sits at that depth.  With N needles they fan out
    symmetrically around it (so depth=10, N=3 plants at ~2/10/18%) -- the depths
    asked for stay the same, the needle just has neighbours.
    """
    if not needles:
        return haystack, []
    half = (len(needles) - 1) / 2
    spread = 8.0 / max(1, len(needles) - 1) if len(needles) > 1 else 0.0
    parts: list[str] = []
    positions: list[int] = []
    last = 0
    for idx, (fact, _q, _k) in enumerate(needles):
        frac = max(0.0, min(1.0, (depth + (idx - half) * spread) / 100.0))
        cut = haystack.find(". ", int(len(haystack) * frac))
        cut = len(haystack) if cut < 0 else cut + 2
        parts.append(haystack[last:cut])
        positions.append(sum(len(p) for p in parts))
        parts.append(fact + " ")
        last = cut
    parts.append(haystack[last:])
    return "".join(parts), positions


def build_prompt(
    target_tokens: int,
    depth: int,
    needle_count: int,
    seed: int,
    chars_per_token: float | None = None,
    token_headroom: int = 24,
) -> tuple[str, list[str], list[tuple[str, str, str]]]:
    """Build the full user prompt for one depth.

    Returns ``(prompt, question_lines, needles)``.  The haystack is sized from
    the chars-per-token ratio; the real token count comes back from the server's
    usage and is what run_depth() reports.  ``chars_per_token=None`` falls back
    to the module estimate.
    """
    cpt = chars_per_token or DEFAULT_CHARS_PER_TOKEN
    needles = make_needles(needle_count, depth, seed)
    overhead_chars = len(SYSTEM_PROMPT) + sum(len(q) for _f, q, _k in needles) + 64
    hay_chars = max(200, int(target_tokens * cpt) - overhead_chars - token_headroom)
    rng = random.Random(_seed(seed, 2, depth, target_tokens))
    haystack = build_haystack(hay_chars, rng)
    body, _positions = plant(haystack, needles, depth)
    questions = [q for _f, q, _k in needles]
    prompt = "<document>\n" + body + "\n</document>\n\n" + "\n".join(questions)
    return prompt, questions, needles


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def chat_completions_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def models_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/v1"):
        return base + "/models"
    return base + "/v1/models"


def resolve_model(endpoint: str, model: str, api_key: str | None, timeout: int) -> str:
    """``--model auto`` asks the server what it is serving."""
    if model != "auto":
        return model
    req = urllib.request.Request(models_url(endpoint), headers=_headers(api_key))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["data"][0]["id"]


def fetch_max_model_len(
    endpoint: str, model: str, api_key: str | None, timeout: int
) -> int | None:
    """Read the served ``max_model_len`` from /v1/models, so the tool does not
    build a prompt the server will reject.

    Returns the entry's ``max_model_len`` (or ``max_context_length``) for
    ``model``, else the first entry's, else ``None`` if the server does not
    report one.  ``None`` means "pace the request by measured token counts
    instead" -- the caller handles both.
    """
    try:
        req = urllib.request.Request(models_url(endpoint), headers=_headers(api_key))
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        entries = data.get("data") or []
        if not entries:
            return None
        for e in entries:
            if e.get("id") == model:
                break
        else:
            e = entries[0]
        for key in ("max_model_len", "max_context_length", "context_length"):
            v = e.get(key)
            if isinstance(v, int) and v > 0:
                return v
    except Exception:
        return None
    return None


def _headers(api_key: str | None) -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def ask(
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    api_key: str | None,
    extra_body: dict | None = None,
) -> tuple[str, dict, float]:
    """One completion.  Returns ``(reply_text, usage, elapsed_s)``.

    Raises on transport error.  The caller distinguishes a *server* error
    (HTTP 4xx/5xx, e.g. "context length exceeded") from a *miss* by catching
    ``urllib.error.HTTPError`` and keeping the body.
    """
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if extra_body:
        body.update(extra_body)
    req = urllib.request.Request(
        chat_completions_url(endpoint),
        data=json.dumps(body).encode(),
        headers=_headers(api_key),
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    elapsed = time.time() - t0
    text = ""
    try:
        text = out["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        text = ""
    return text, out.get("usage", {}) or {}, elapsed


#: Substrings that mean "the prompt was longer than the window", across SGLang
#: and vLLM.  The SGLang/sglang wording observed live is
#: "The input (1066900 tokens) is longer than the model's context length
#: (1048576 tokens)." -- so BOTH "longer than" and "context length" must appear
#: together; "context length" alone would also match a benign warning.
LENGTH_ERROR_MARKERS = (
    "longer than the maximum model length",
    "longer than the model's context length",
    "longer than the model context length",
    "maximum context length",
    "max_model_len",
    "input length",
    "too long",
)


def length_error(detail: str) -> bool:
    """True when the body is a real too-long rejection (not a benign mention)."""
    d = (detail or "").lower()
    if "longer than" in d and "context length" in d:
        return True
    return any(m in d for m in LENGTH_ERROR_MARKERS)


def parse_length_error(detail: str) -> tuple[int | None, int | None]:
    """Pull ``(input_tokens, window_tokens)`` out of an engine's too-long body.

    SGLang's wording: "The input (1066900 tokens) is longer than the model's
    context length (1048576 tokens)."  The input count lets the caller correct
    its chars-per-token ratio to the real one and size the retry exactly, instead
    of shrinking blind.
    """
    nums = [int(n) for n in re.findall(r"\((\d+)\s+tokens?\)", detail or "")]
    if not nums:
        nums = [int(n) for n in re.findall(r"(\d+)\s+tokens?\)", detail or "")]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], None
    return None, None


def calibrate(
    endpoint: str,
    model: str,
    api_key: str | None,
    timeout: int,
    chars_per_token: float,
    extra_body: dict | None = None,
    targets: tuple[int, ...] = CALIBRATION_TOKENS,
    agree_fraction: float = CALIBRATION_AGREE_FRACTION,
    max_model_len: int | None = None,
) -> tuple[float, dict]:
    """Measure the server's chars-per-token from a size sweep.

    chars/token is not perfectly constant: on this fleet it read 4.037 at an 8k
    prompt, 4.006 at 64k, and ~4.01 at 1M.  A single small probe therefore
    biases the ratio and sizes the deep prompt ~0.7% too long -- one wasted
    multi-minute prefill ending in a 400.  This sweeps several sizes, largest
    first, and returns the ratio from the **largest usable probe** (nearest the
    scale that matters) rather than extrapolating a fit, which on real data
    produced an unphysical negative overhead.  Smaller probes are fallbacks if a
    larger one is rejected or out of band, and their spread is recorded.

    Probes larger than ``max_model_len`` (minus headroom) are skipped so a probe
    is never itself the request that overfills the window.  Sizes stop early
    once the two largest usable ratios agree, and the result is sanity-bounded
    against the single-probe ratio.  Returns ``(ratio, record)``; on any failure
    the input value is returned unchanged and the record says why.
    """
    rec: dict = {
        "method": "sweep",
        "requested_targets": list(targets),
        "probes": [],
        "chars_per_token": chars_per_token,
    }
    cap = None
    if max_model_len:
        cap = max_model_len - max(1024, int(max_model_len * HEADROOM_FRACTION))
    safe_cap = None if cap is None else cap / PROBE_SAFETY
    usable_targets = [t for t in targets if safe_cap is None or t <= safe_cap]
    if not usable_targets:
        usable_targets = [min(targets)]
    rec["targets"] = usable_targets

    good: list[tuple[int, int]] = []          # (chars, tokens), largest first
    for target in usable_targets:
        try:
            prompt, _q, _n = build_prompt(target, 50, 1, 20261003, chars_per_token)
            _reply, usage, _elapsed = ask(endpoint, model, prompt, 8, timeout,
                                          api_key, extra_body)
            pt = usage.get("prompt_tokens")
        except Exception as e:
            rec["probes"].append({"target": target, "error": f"{type(e).__name__}: {e}"})
            continue
        entry = {"target": target, "chars": len(prompt), "tokens": pt}
        if not pt:
            entry["note"] = "no usage.prompt_tokens"
            rec["probes"].append(entry)
            continue
        if abs(pt - target) > target * CALIBRATION_BAND:
            entry["note"] = (f"reported {pt} tokens for a ~{target} target; "
                             "outside the trusted band, dropped")
            rec["probes"].append(entry)
            continue
        entry["ratio"] = round(len(prompt) / pt, 4)
        rec["probes"].append(entry)
        good.append((len(prompt), pt))
        if len(good) >= 2:
            c_new, t_new = good[-1]
            c_prev, t_prev = good[-2]
            if t_new and t_prev:
                r_new = c_new / t_new
                r_prev = c_prev / t_prev
                if abs(r_new - r_prev) <= max(r_prev, 1e-9) * agree_fraction:
                    rec["note"] = "largest two probes agreed; sweep stopped early"
                    break

    if not good:
        rec["note"] = ("no probe produced a usable token count; keeping the "
                       f"{chars_per_token} estimate")
        return chars_per_token, rec

    c, t = good[0]                            # largest usable probe
    ratio = c / t
    rec["basis"] = f"largest usable probe (~{rec['targets'][0]} target, {t} tokens)"
    if len(good) >= 2:
        r_small = good[-1][0] / good[-1][1]
        rec["spread"] = round(ratio - r_small, 4)
    rec.setdefault("note", "swept largest-first; ratio from the largest usable probe")
    rec["chars_per_token"] = round(ratio, 4)
    return ratio, rec


# ---------------------------------------------------------------------------
# Scoring and the ladder
# ---------------------------------------------------------------------------

def score(reply: str, key: str) -> bool:
    """Exact containment of the answer key, case-insensitive, punctuation-blind.

    Normalised by stripping non-alphanumerics from both sides because models
    punctuate codes inconsistently ("7391-KESTREL", "7391 KESTREL", "`7391-KESTREL`")
    and none of those differences is a retrieval failure.
    """
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    k = norm(key)
    return bool(k) and k in norm(reply)


def run_depth(
    endpoint: str,
    model: str,
    context_length: int,
    depth: int,
    needle_count: int,
    seed: int,
    max_tokens: int,
    timeout: int,
    api_key: str | None,
    chars_per_token: float | None,
    extra_body: dict | None = None,
    max_model_len: int | None = None,
    verbose: bool = False,
) -> dict:
    """Exercise one depth.  Never raises: a failure is recorded as a status.

    The request is paced two ways:

    * ``chars_per_token`` from calibration (or the estimate when calibration
      could not run) sizes the prompt in characters;
    * after the first response, the server's *measured* token/char ratio takes
      over, so the prompt lands on the requested count rather than ~15% over it.

    If the server still rejects the prompt as too long, the token *target* is
    shrunk and the request retried -- never the chars-per-token ratio, which is a
    tokenizer property and would rebuild an equally-long prompt.  A prompt the
    server *accepts* but reports as short is NOT retried: that is a truncation
    finding, and hiding it would defeat the tool.
    """
    # Cap to the advertised window, minus a headroom so a paced prompt that lands a
    # hair long is not rejected.  The headroom must exceed the chars-per-token
    # error (this fleet measured ~1% on the 1M prompt), so 2%; without it the
    # request is a full multi-minute prefill that ends in a 400.
    if max_model_len:
        headroom = min(max(1024, int(max_model_len * HEADROOM_FRACTION)),
                       max_model_len // 2)
        target = min(context_length, max_model_len - headroom)
    else:
        target = context_length
    rec: dict = {"depth": depth, "status": "ERROR", "hits": 0, "of": needle_count}
    last_error = None
    ratio = chars_per_token  # may be corrected from an engine too-long message
    for attempt in range(SHRINK_RETRIES + 1):
        prompt, questions, needles = build_prompt(
            target, depth, needle_count, seed, ratio, token_headroom=TOKEN_HEADROOM
        )
        _vlog(verbose, f"depth {depth}%: attempt {attempt + 1}, "
                       f"{len(prompt)} chars, ~{target} tokens to send "
                       f"(ratio {(ratio if ratio is not None else DEFAULT_CHARS_PER_TOKEN):.4f} chars/token)")
        rec = {
            "depth": depth,
            "target_tokens": context_length,
            "paced_target": target,
            "estimated_tokens": int(len(prompt) / (ratio or DEFAULT_CHARS_PER_TOKEN)),
            "chars_per_token": None if ratio is None else round(ratio, 4),
            "prompt_tokens": None,
            "status": "ERROR",
            "hits": 0,
            "of": len(needles),
            "latency_s": None,
            "answers": [],
            "error": None,
            "attempts": attempt + 1,
        }
        try:
            reply, usage, elapsed = ask(
                endpoint, model, prompt, max_tokens, timeout, api_key, extra_body
            )
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {detail}"
            rec["error"] = last_error
            _vlog(verbose, f"depth {depth}%: HTTP {e.code}: {detail[:160]}")
            if length_error(detail) and attempt < SHRINK_RETRIES:
                # Correct the ratio from the engine's own count, then size the
                # retry to land under the window instead of shrinking blind.
                input_tokens, window_tokens = parse_length_error(detail)
                if input_tokens and input_tokens > 0:
                    ratio = len(prompt) / input_tokens
                    cap = window_tokens or max_model_len or target
                    target = int(cap - max(1024, int(cap * HEADROOM_FRACTION)))
                    rec["note"] = (f"prompt rejected as too long ({input_tokens} tokens "
                                   f"> window {cap}); corrected ratio to {ratio:.4f} "
                                   f"chars/token and retrying a {target}-token target")
                else:
                    target = int(target * SHRINK_FACTOR)
                    rec["note"] = (f"prompt rejected as too long; retrying a "
                                   f"{target}-token target")
                continue
            rec["status"] = "ERROR"
            return rec
        except Exception as e:  # transport, timeout, parse
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["status"] = "ERROR"
            return rec

        rec["latency_s"] = round(elapsed, 2)
        pt = usage.get("prompt_tokens")
        rec["prompt_tokens"] = pt
        rec["usage"] = usage
        if pt:
            # Measured ratio: use it to pace the *next* depth exactly.
            rec["measured_chars_per_token"] = round(len(prompt) / pt, 4)

        # One reply answers all questions at a depth; score each key it contains.
        # (needle_count defaults to 1, which is the objective's "a needle at every
        # 10%" shape; >1 is for a multi-key retry and is reported as hits/of.)
        hits = 0
        for (_f, question, key) in needles:
            ok = score(reply, key)
            hits += ok
            rec["answers"].append(
                {"question": question, "key": key, "reply": reply.strip()[:300],
                 "ok": bool(ok)}
            )
        rec["hits"] = hits

        # A short prompt_tokens means the window was not actually reached -- a
        # truncating server, a smaller-than-asked window, or a client bug.  This
        # is a failure even if the needle was retrieved, because the run did not
        # test the context it claims to test.
        if pt is None:
            rec["status"] = "PASS" if hits == len(needles) else "FAIL"
            rec["note"] = "server reported no usage.prompt_tokens; token count unverified"
        elif pt < context_length * REACHED_FRACTION:
            rec["status"] = "TRUNCATED"
            rec["note"] = (f"server counted {pt} tokens for a {context_length}-token "
                           "request; the window was not reached")
        else:
            rec["status"] = "PASS" if hits == len(needles) else "FAIL"
        _vlog(verbose, f"depth {depth}%: {rec['status']} "
                       f"({hits}/{len(needles)} needles, prompt_tokens {pt}, "
                       f"{rec['latency_s']}s)")
        return rec

    rec["status"] = "ERROR"
    rec["error"] = last_error or "exhausted shrink retries"
    return rec


def run_ladder(cfg: dict) -> dict:
    """Run every requested depth.  One owner of the result set: this function."""
    assert cfg.get("depths"), "run_ladder needs at least one depth"
    verbose = bool(cfg.get("verbose"))
    model = resolve_model(cfg["endpoint"], cfg["model"], cfg.get("api_key"),
                          cfg.get("timeout", 3600))
    _vlog(verbose, f"endpoint {cfg['endpoint']}, model {model}")
    window = fetch_max_model_len(cfg["endpoint"], model, cfg.get("api_key"),
                                 min(60, cfg.get("timeout", 3600)))
    _vlog(verbose, f"server max_model_len: {window if window else 'not advertised'}")
    cpt = cfg.get("chars_per_token")
    calibration = None
    if cpt is None:
        cpt, calibration = calibrate(
            cfg["endpoint"], model, cfg.get("api_key"), cfg.get("timeout", 3600),
            DEFAULT_CHARS_PER_TOKEN, cfg.get("extra_body"), max_model_len=window,
        )
        probes = "; ".join(
            f"~{p.get('target')}→{p.get('tokens')}tok"
            for p in calibration.get("probes", []) if p.get("tokens")
        )
        _vlog(verbose, f"calibration: {calibration.get('note')}"
                       + (f" [{probes}]" if probes else "")
                       + (f"; using {cpt:.4f} chars/token" if cpt else ""))
    _vlog(verbose, f"depths: {cfg['depths']}  ({len(cfg['depths'])} prefill(s))")
    depths = []
    for depth in cfg["depths"]:
        rec = run_depth(
            cfg["endpoint"], model, cfg["context_length"], depth,
            cfg.get("needle_count", 1), cfg.get("seed", 1234),
            cfg.get("max_tokens", 64), cfg.get("timeout", 3600),
            cfg.get("api_key"), cpt, cfg.get("extra_body"), max_model_len=window,
            verbose=verbose,
        )
        depths.append(rec)
    out = {"model": model, "endpoint": cfg["endpoint"],
           "context_length": cfg["context_length"],
           "max_model_len": window, "depths": depths}
    if calibration is not None:
        out["calibration"] = calibration
        out["chars_per_token"] = None if cpt is None else round(cpt, 4)
    return out


def run_needle_test(
    model: str,
    context_length: int | str,
    api_endpoint: str,
    *,
    depths: list[int] | None = None,
    needles_per_depth: int = 1,
    seed: int = 1234,
    max_tokens: int = 64,
    timeout: int = 3600,
    api_key: str | None = None,
    chars_per_token: float | None = None,
    extra_body: dict | None = None,
    verbose: bool = False,
) -> dict:
    """Run a needle-haystack test.  The keyword-argument entry point.

    ``model``, ``context_length``, and ``api_endpoint`` are the three required
    parameters; everything else is optional.  ``context_length`` accepts an int
    or a string like ``"1m"``.  ``verbose=True`` prints live progress to
    **stderr** (stdout is left for the caller).  Returns the full ladder result
    (the same structure the CLI writes to ``--json``), and does NOT raise on a
    miss/truncation -- call ``classify()`` on the result for the verdict, or use
    the CLI, whose exit code carries it.
    """
    cfg = {
        "endpoint": api_endpoint,
        "model": model,
        "context_length": parse_context_length(context_length),
        "depths": depths or list(DEFAULT_DEPTHS),
        "needle_count": needles_per_depth,
        "seed": seed,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "api_key": api_key,
        "chars_per_token": chars_per_token,
        "extra_body": extra_body,
        "verbose": verbose,
    }
    results = run_ladder(cfg)
    results["tool_version"] = VERSION
    results["verdict"] = classify(results)[0]
    return results


def classify(results: dict) -> tuple[str, int]:
    """Map a ladder result to a verdict + exit code.  Order matters: an empty
    result is a failure, not a vacuous pass."""
    depths = results.get("depths") or []
    if not depths:
        return "EMPTY", 1
    if all(d["status"] == "ERROR" for d in depths):
        return "ERROR", 1
    if any(d["status"] == "ERROR" for d in depths):
        return "PARTIAL-ERROR", 1
    if any(d["status"] == "TRUNCATED" for d in depths):
        return "TRUNCATED", 3
    if any(d["status"] == "FAIL" for d in depths):
        return "FAIL", 3
    return "PASS", 0


def print_report(results: dict, verdict: str) -> None:
    print(f"model:   {results['model']}")
    print(f"endpoint:{results['endpoint']}")
    window = results.get("max_model_len")
    print(f"context: {results['context_length']} tokens requested"
          + (f"  (server max_model_len {window})" if window else ""))
    cal = results.get("calibration")
    if cal:
        print(f"sizing:  {results.get('chars_per_token')} chars/token "
              f"(calibrated: {cal.get('note')})")
    print()
    header = f"{'depth':>6} {'requested':>10} {'prompt_tok':>11} {'hits':>6} {'latency_s':>10}  verdict"
    print(header)
    print("-" * len(header))
    for d in results["depths"]:
        pt = d["prompt_tokens"] if d["prompt_tokens"] is not None else "n/a"
        lat = f"{d['latency_s']:.1f}" if d["latency_s"] is not None else "n/a"
        print(f"{d['depth']:>5}% {d['target_tokens']:>10} {str(pt):>11} "
              f"{d['hits']}/{d['of']:>4} {lat:>10}  {d['status']}")
    print()
    for d in results["depths"]:
        if d["status"] == "ERROR":
            print(f"  depth {d['depth']}% ERROR: {d['error']}")
        elif d.get("note"):
            print(f"  depth {d['depth']}% note: {d['note']}")
        for a in d["answers"]:
            if not a["ok"]:
                print(f"  depth {d['depth']}% MISS: {a['question']!r} -> {a['reply']!r}")
    total = sum(d["hits"] for d in results["depths"])
    of = sum(d["of"] for d in results["depths"])
    print(f"\nTOTAL: {total}/{of} needles retrieved; verdict {verdict}")


# ---------------------------------------------------------------------------
# Selftest: an in-process mock with three behaviours
# ---------------------------------------------------------------------------

def _make_handler(mode: dict):
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a):  # silence
            pass

        def do_GET(self):
            if self.path.rstrip("/").endswith("/models"):
                ml = mode.get("window", 1000000)
                body = json.dumps(
                    {"object": "list", "data": [{"id": "mock-model", "max_model_len": ml}]}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = payload["messages"][-1]["content"]
            keys = re.findall(r"is (\d{4}-[A-Z]+)\.", text)
            # ratio lets a test emulate a server whose real tokenizer differs
            # from the client's estimate (the overshoot the retry exists for).
            n_tokens = int(len(text) / mode.get("ratio", 4.6))
            # Optional hard window: reject with the engine's too-long wording, so
            # the shrink-retry path can be exercised without a real engine.
            if mode.get("window") and n_tokens > mode["window"]:
                err = json.dumps({
                    "error": {"message": f"The input ({n_tokens} tokens) is longer "
                                         f"than the model's context length ({mode['window']} tokens)."}}
                ).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
                return
            m = mode["mode"]
            if m == "truncate":
                n_tokens = min(n_tokens, 512)  # silently claim a tiny window
                reply = "I could not find the access code."
            elif m == "wrong":
                reply = "The access code is 0000-WRONG."
            else:  # correct: echo the first planted key if one is present
                reply = f"The access code is {keys[-1]}." if keys else "none found"
            out = {
                "choices": [{"message": {"role": "assistant", "content": reply}}],
                "usage": {"prompt_tokens": n_tokens, "completion_tokens": 8,
                          "total_tokens": n_tokens + 8},
            }
            body = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def selftest() -> int:
    """Run the ladder against three mocks and assert each is classified right.

    This is the negative control the repo requires: the same code path is shown
    to PASS a correct server, FAIL a wrong-answer server, and detect a
    truncating one.  A guard that has only ever passed proves nothing.
    """
    from http.server import ThreadingHTTPServer

    mode = {"mode": "correct"}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(mode))
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    endpoint = f"http://127.0.0.1:{port}"
    cfg = {"endpoint": endpoint, "model": "mock-model", "context_length": 2000,
           "depths": [10, 50, 100], "seed": 1234, "max_tokens": 32,
           "timeout": 30, "needle_count": 1, "chars_per_token": DEFAULT_CHARS_PER_TOKEN}

    failures = []
    try:
        mode["mode"] = "correct"
        good = run_ladder(cfg)
        gv, gcode = classify(good)
        print(f"[selftest] correct mock   -> verdict {gv} (exit {gcode}), "
              f"hits {sum(d['hits'] for d in good['depths'])}/"
              f"{sum(d['of'] for d in good['depths'])}")
        if gv != "PASS" or gcode != 0:
            failures.append(f"correct mock should PASS, got {gv}/{gcode}")

        mode["mode"] = "wrong"
        bad = run_ladder(cfg)
        bv, bcode = classify(bad)
        print(f"[selftest] wrong mock     -> verdict {bv} (exit {bcode}), "
              f"hits {sum(d['hits'] for d in bad['depths'])}/"
              f"{sum(d['of'] for d in bad['depths'])}")
        if bv != "FAIL" or bcode != 3:
            failures.append(f"wrong mock should FAIL, got {bv}/{bcode}")

        mode["mode"] = "truncate"
        trunc = run_ladder(cfg)
        tv, tcode = classify(trunc)
        print(f"[selftest] truncating mock-> verdict {tv} (exit {tcode}), "
              f"prompt_tokens {[d['prompt_tokens'] for d in trunc['depths']]}")
        if tv != "TRUNCATED" or tcode != 3:
            failures.append(f"truncating mock should TRUNCATE, got {tv}/{tcode}")
    finally:
        server.shutdown()
        server.server_close()

    if failures:
        print("\nSELFTEST FAILED:")
        for f in failures:
            print("  - " + f)
        return 1
    print("\nSELFTEST PASSED (3/3 controls behaved as required)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="needle-haystack.py",
        description="Needle-in-a-haystack test over an OpenAI-compatible chat endpoint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--model", help="served model name, or 'auto' to query /v1/models")
    p.add_argument("--context-length", help="tokens to fill, e.g. 1000000 or 1m")
    p.add_argument("--api-endpoint", help="base URL, e.g. http://HOST:8000")
    p.add_argument("--api-key", default=None,
                   help="bearer token; falls back to $NEEDLE_API_KEY; never printed")
    p.add_argument("--depths", default=",".join(str(d) for d in DEFAULT_DEPTHS),
                   help="comma-separated depth percentages (default: every 10%%)")
    p.add_argument("--needles-per-depth", type=int, default=1,
                   help="needles planted per depth (default 1)")
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--max-tokens", type=int, default=64)
    p.add_argument("--timeout", type=int, default=3600,
                   help="per-request timeout s (a 1M-token prefill can take 20+ min)")
    p.add_argument("--chars-per-token", type=float, default=None,
                   help="haystack sizing ratio; default: measure it with one small "
                        "probe request (the estimate alone overshoots ~15%% on this "
                        "fleet's tokenizer and a 1M prompt then 400s)")
    p.add_argument("--verbose", action="store_true",
                   help="print live progress (endpoint, window, calibration, and per-depth "
                        "attempt/result) to stderr; stdout stays clean for the report")
    p.add_argument("--json", default=None, help="write the full result (with raw replies) here")
    p.add_argument("--dry-run", action="store_true",
                   help="build prompts and report estimated sizes, send nothing")
    p.add_argument("--selftest", action="store_true",
                   help="run offline against an in-process mock; requires no other flags")
    p.add_argument("--version", action="version", version=f"needle-haystack {VERSION}")
    return p


def parse_depths(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        v = int(part)
        if not 0 < v <= 100:
            raise ValueError(f"depth must be in 1..100, got {v}")
        out.append(v)
    if not out:
        raise ValueError("no depths given")
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest:
        return selftest()

    missing = [n for n, v in (("--model", args.model),
                              ("--context-length", args.context_length),
                              ("--api-endpoint", args.api_endpoint)) if not v]
    if missing:
        print(f"error: required: {', '.join(missing)} (or --selftest)", file=sys.stderr)
        return 2
    try:
        context_length = parse_context_length(args.context_length)
        depths = parse_depths(args.depths)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.needles_per_depth < 1:
        print("error: --needles-per-depth must be >= 1", file=sys.stderr)
        return 2

    api_key = args.api_key if args.api_key is not None else os.environ.get("NEEDLE_API_KEY")

    if args.dry_run:
        chars = args.chars_per_token or DEFAULT_CHARS_PER_TOKEN
        for depth in depths:
            prompt, questions, needles = build_prompt(
                context_length, depth, args.needles_per_depth, args.seed,
                chars,
            )
            est = int(len(prompt) / chars)
            print(f"depth {depth:>3}%: prompt chars {len(prompt):>10} "
                  f"~{est:>9} tokens, {len(needles)} needle(s), "
                  f"questions: {len(questions)}")
        return 0

    cfg = {
        "endpoint": args.api_endpoint,
        "model": args.model,
        "context_length": context_length,
        "depths": depths,
        "needle_count": args.needles_per_depth,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "timeout": args.timeout,
        "api_key": api_key,
        "chars_per_token": args.chars_per_token,
        "verbose": args.verbose,
    }
    _vlog(args.verbose, f"running a {context_length}-token ladder at depths {depths}")
    try:
        results = run_ladder(cfg)
    except urllib.error.URLError as e:
        print(f"error: endpoint unreachable: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    results["tool_version"] = VERSION
    verdict, code = classify(results)
    results["verdict"] = verdict
    print_report(results, verdict)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=1)
        print(f"wrote {args.json}")
    return code


if __name__ == "__main__":
    sys.exit(main())