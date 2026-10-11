#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Travis Wichert
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Correctness soak gate for sglang#37111 / #38319 silent decode corruption.

Why this file exists
--------------------
Two upstream SGLang bugs corrupt output *silently* on exactly the engine and
topology this lane ships (Qwen3.8-Flash-Next, QSA sparse attention + NEXTN
speculative decoding, GB10 / SM121, TP2):

  * sgl-project/sglang#37111 -- "QSA + NEXTN decode graph silently corrupts
    output on GB10 TP2" (opened 2026-08-30, still OPEN as of 2026-10-04).
  * sgl-project/sglang#38319 -- "Chunked Prefill + Radix Insert race corrupts
    KV pages (QSA, Qwen3.8-Flash-Next)" (opened 2026-09-07, still OPEN as of
    2026-10-04; the proposed fix, PR #38355, is open and unmerged).

Both return HTTP 200 with plausible-looking-but-wrong text, so a health check,
a throughput benchmark, and a `curl` smoke test all pass while the server is
emitting garbage.  The lane's rule (WORK doc section 14) is blunt: a config
that is 10% faster and occasionally emits garbage is a regression.  This is the
instrument that catches it, and nothing else in `tools/` does: `quality-battery`
is a score, `needle-haystack` is context retrieval, and neither soaks, neither
compares a warm prefix against a cold one, and neither detects degeneration.

The failure modes this tool is built to trip
--------------------------------------------
1. Repetition / ``!!!!`` degeneration -- the punctuation-collapse and
   repeated-fragment signature both upstream reports describe.
2. Truncation / mid-sentence stops -- a reply that ends mid-word or mid-clause
   while the engine reports it as finished.
3. Prefix-cache corruption -- the *key* discriminator (below).

The discriminator: warm-prefix vs cold-prefix disagreement
----------------------------------------------------------
#38319's mechanism is a radix-tree node that references KV pages a retract has
already freed.  Its defining observable, per the issue, is *prefix-specific and
persistent*: every request that shares the corrupted prefix reads the same
garbage.  So if the failure is present, the **same logical question, asked with
the prefix cache warm, disagrees with the same question asked after the prefix
cache has been emptied.**  That is a far stronger signal than "the answer looks
wrong" -- it is the bug's own fingerprint.  The tool therefore asks a fixed
canary twice: once at the end of the soak, with the long shared system prompt
already resident in the radix tree, and once after a cold re-ask (a
`/flush_cache`, or a salted fresh session if that endpoint is unavailable).
Agreement is a pass; disagreement is corruption.

Why it is not just `curl`
-------------------------
* `temperature=0` everywhere, so the model's own sampling contributes no noise
  to a warm/cold comparison.
* A single long system prompt is shared by every turn, so prefix reuse is
  genuinely exercised (this is the surface #38319 lives on).
* The raw reply of every request -- turn, probe, canary, pass or fail -- is kept
  in the report and printed, because a summarised verdict hides a scoring bug.
* Exit code distinguishes *the server errored* from *the server answered
  confidently and wrongly*, so a release runbook can gate on it.

Stdlib only, on purpose: this runs on a head node, inside a container, and on a
laptop with no venv, and the only thing that reaches a target is `--base-url`.

Usage
-----
    # default soak: 1 minute, temperature 0, tool loop, no depth padding
    python3 tools/gate-37111.py --base-url http://127.0.0.1:8000

    # a real release gate: 90 minutes at ~100k depth, JSON artifact
    python3 tools/gate-37111.py --base-url http://127.0.0.1:8000 \
        --depth-tokens 100000 --duration-min 90 --json gate-37111.json

    # a fast smoke before a long soak
    python3 tools/gate-37111.py --depth-tokens 8192 --turns 3

    python3 tools/gate-37111.py --selftest     # offline, in-process mock, ~2 s

Exit codes
----------
0  PASS -- no corruption detected across the soak
1  transport failure / endpoint unreachable / every request errored
2  bad flags / bad configuration
3  FAIL -- corruption detected, or a run too partial to certify
   (degeneration, truncation, warm/cold disagreement, or transport errors)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.1"

#: Upstream references, read 2026-10-04.  Kept in the artifact so a report is
#: self-describing and the URLs are not re-derived from memory later.
UPSTREAM = {
    "issue_37111": {
        "url": "https://github.com/sgl-project/sglang/issues/37111",
        "title": "[Bug] Qwen3.8-Flash-Next QSA + NEXTN decode graph silently "
                 "corrupts output on GB10 TP2",
        "state": "open",
        "opened": "2026-08-30",
        "last_updated": "2026-08-31",
    },
    "issue_38319": {
        "url": "https://github.com/sgl-project/sglang/issues/38319",
        "title": "[Bug] Chunked Prefill + Radix Insert race corrupts KV pages "
                 "(QSA, Qwen3.8-Flash-Next)",
        "state": "open",
        "opened": "2026-09-07",
        "last_updated": "2026-09-11",
    },
    "pr_38355": {
        "url": "https://github.com/sgl-project/sglang/pull/38355",
        "title": "fix(mem_cache): eliminate chunked-prefill radix-insert race "
                 "corrupting QSA KV pages (#38319)",
        "state": "open",
        "base_branch": "qwen4-main-squashed",
        "note": "open and unmerged as of 2026-10-04; 1 commit af27224.",
    },
}

#: Estimated chars/token before the server's own tokenizer is observed.  Only
#: used to *build* a prompt toward a token target; the report carries the
#: server's real `usage.prompt_tokens`, which is the number to trust.
DEFAULT_CHARS_PER_TOKEN = 4.0

#: A generation shorter than this is not prose and is suspicious on its own.
MIN_PROSE_CHARS = 40

#: Punctuation fraction above which a reply is the reported collapse, not text.
MAX_PUNCT_FRACTION = 0.30

#: A short fragment repeated at least this many times is degeneration.
REPEAT_MIN_RUNS = 6

#: Distinct-word ratio below this (for replies of >= MIN_WORDS_FOR_RATIO words)
#: is degenerate.
MIN_DISTINCT_RATIO = 0.15
MIN_WORDS_FOR_RATIO = 40

#: Sentence-final characters a finished generation should end on.
SENTENCE_END = '.!?")\u2026'

#: The canary question and its known-correct answer.  Asked twice (warm/cold);
#: it is short, arithmetic, and has a fixed answer so a wrong reply is a direct
#: correctness signal independent of the warm/cold comparison.
CANARY_Q = "What is 47 multiplied by 89? Reply with just the number."
CANARY_EXPECTED = "4183"


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------
def _vlog(verbose: bool, msg: str) -> None:
    """Progress line for ``--verbose``; stderr, timestamped, so the stdout
    report and the ``--json`` artifact stay clean and a 90-minute soak shows
    something while it runs."""
    if verbose:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{ts}] [g37111] {msg}", file=sys.stderr, flush=True)


def _normalize(text: str) -> str:
    """Whitespace/case/punctuation-insensitive form for warm-vs-cold compare."""
    text = (text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\n\r.,;:!?\"'`()[]{}*#-")


def _json_dumps(obj) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False)


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------
class Endpoint:
    def __init__(self, base_url: str, timeout: int = 900, api_key: str | None = None):
        self.base = base_url.rstrip("/")
        if self.base.endswith("/v1"):
            self.base = self.base[:-3]
        self.timeout = timeout
        self.api_key = api_key

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _get(self, path: str, timeout: int | None = None):
        req = urllib.request.Request(self.base + path, headers=self._headers())
        return urllib.request.urlopen(req, timeout=timeout or self.timeout)

    def _post(self, path: str, body: dict, timeout: int | None = None):
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=self._headers())
        return urllib.request.urlopen(req, timeout=timeout or self.timeout)

    def resolve_model(self, model: str | None) -> str:
        if model:
            return model
        with self._get("/v1/models", timeout=30) as r:
            data = json.load(r)
        return data["data"][0]["id"]

    def max_model_len(self) -> int | None:
        try:
            with self._get("/v1/models", timeout=30) as r:
                data = json.load(r)
            node = data["data"][0]
            return node.get("max_model_len") or node.get("context_length")
        except Exception:  # noqa: BLE001 -- a metadata gap is not a gate failure
            return None

    def flush_cache(self) -> tuple[bool, str]:
        """Empty the prefix/radix cache via SGLang's admin endpoint.  Returns
        (ok, detail).  Tries POST then GET so a server that gates one method
        still works."""
        detail = "not attempted"
        for method in ("POST", "GET"):
            try:
                if method == "POST":
                    req = urllib.request.Request(self.base + "/flush_cache",
                                                 data=b"", headers=self._headers())
                else:
                    req = urllib.request.Request(self.base + "/flush_cache",
                                                 headers=self._headers())
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.status == 200, r.read().decode(errors="replace").strip()
            except Exception as e:  # noqa: BLE001 -- report, never crash the gate
                detail = f"{method} failed: {type(e).__name__}: {e}"
        return False, detail

    def chat(self, messages: list, model: str, max_tokens: int,
             thinking: bool = False) -> dict:
        body = {"model": model, "messages": messages, "temperature": 0,
                "max_tokens": max_tokens}
        if thinking:
            body["chat_template_kwargs"] = {"enable_thinking": True}
        t0 = time.time()
        with self._post("/v1/chat/completions", body) as r:
            out = json.load(r)
        elapsed = time.time() - t0
        choice = out["choices"][0]
        msg = choice.get("message", {}) or {}
        return {
            "text": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls") or [],
            "finish_reason": choice.get("finish_reason"),
            "usage": out.get("usage", {}),
            "elapsed_s": round(elapsed, 3),
        }


# ---------------------------------------------------------------------------
# detectors -- each returns (is_bad: bool, reason: str)
# ---------------------------------------------------------------------------
def detect_degeneration(text: str) -> tuple[bool, str]:
    """Repetition / ``!!!!`` collapse (the #37111 / #38319 signature)."""
    s = (text or "").strip()
    if not s:
        return True, "empty reply"
    if len(s) < MIN_PROSE_CHARS:
        return True, f"shorter than {MIN_PROSE_CHARS} chars ({len(s)})"

    punct = sum(1 for c in s if c in "!?.,;:-*#") / len(s)
    if punct > MAX_PUNCT_FRACTION:
        return True, f"punctuation {punct:.0%} of characters"

    # A short fragment repeated 6+ times in a row ("!!!!", "ha ha ha", ...).
    for run in re.findall(r"(\S{1,20}?)\1{%d,}" % (REPEAT_MIN_RUNS - 1), s):
        return True, f"repeated fragment {run!r}"

    words = re.findall(r"[A-Za-z']+", s)
    if len(words) >= MIN_WORDS_FOR_RATIO:
        distinct = len({w.lower() for w in words})
        if distinct / len(words) < MIN_DISTINCT_RATIO:
            return True, f"only {distinct} distinct words in {len(words)}"
    return False, ""


def detect_truncation(text: str, finish_reason: str | None,
                      max_tokens: int) -> tuple[bool, str]:
    """Mid-sentence stop: the engine says it finished but the text stops dead
    mid-clause/mid-word, or it hit the cap without a terminator."""
    s = (text or "").strip()
    if not s:
        return True, "no content returned"
    if finish_reason == "length" and s[-1] not in SENTENCE_END:
        return True, f"hit max_tokens={max_tokens} mid-sentence"
    # A "stop" that ends on a bare alphanumeric with no terminal punctuation is
    # the other shape of a silent cut -- only flagged on long prose, because a
    # short factual answer may legitimately end on a letter.
    if finish_reason in ("stop", None) and len(s) > 80 \
            and s[-1] not in SENTENCE_END and re.search(r"[A-Za-z0-9]$", s) \
            and s.count(" ") > 15:
        return True, "prose ends mid-clause with no terminator"
    return False, ""


def parse_tool_call(result: dict) -> dict | None:
    """Extract a tool call from either native ``tool_calls`` or a JSON reply."""
    if result.get("tool_calls"):
        fn = result["tool_calls"][0].get("function", {})
        args = fn.get("arguments")
        try:
            args = json.loads(args) if isinstance(args, str) else args
        except Exception:  # noqa: BLE001
            args = None
        return {"tool": fn.get("name"), "args": args}
    text = (result.get("text") or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(obj, dict) and "tool" in obj:
        return {"tool": obj.get("tool"), "args": obj.get("args")}
    return None


def detect_tool_call(result: dict, expected_tool: str,
                     expected_args: dict) -> tuple[bool, str]:
    call = parse_tool_call(result)
    if call is None:
        return True, "no parseable tool call"
    if call.get("tool") != expected_tool:
        return True, f"tool {call.get('tool')!r} != {expected_tool!r}"
    args = call.get("args") or {}
    if not isinstance(args, dict):
        return True, f"args not an object: {args!r}"
    for k, v in expected_args.items():
        if args.get(k) != v:
            return True, f"arg {k}={args.get(k)!r} != {v!r}"
    return False, ""


# ---------------------------------------------------------------------------
# prompt construction
# ---------------------------------------------------------------------------
def build_system_prompt() -> str:
    """One long, stable system prompt shared by every request.  Length matters:
    it is the prefix a radix cache keeps resident, which is the surface #38319
    corrupts."""
    rules = "\n".join(
        f"  R{idx:02d}. {line}"
        for idx, line in enumerate([
            "You are the audit agent for a model-recipe registry.",
            "Every answer must be short, literal, and free of caveats.",
            "When asked for a tool call, emit exactly one JSON object and nothing else.",
            'The JSON object must have the shape {"tool": <name>, "args": {...}}.',
            "Never wrap the JSON in prose or markdown fences.",
            "Never repeat a word more than three times consecutively.",
            "Never emit a run of identical punctuation characters.",
            "Arithmetic must be exact; do not round unless told to.",
            "If a question asks for one word, reply with only that word.",
            "If a question asks for a number, reply with only that number.",
            "Do not add explanations, apologies, or sign-offs.",
            "Preserve the order of any list you are asked to repeat back.",
            "Stop generating the moment the requested answer is complete.",
        ], start=1))
    return (
        "REGISTRY-AUDIT SYSTEM PROMPT (stable prefix; shared by every request)\n"
        "===============================================================\n"
        "You run inside a strict, deterministic audit harness.  The harness "
        "sends many requests that all begin with this exact prompt, so it will "
        "be reused from the prefix cache; your behaviour must be identical "
        "whether the prefix is warm or freshly prefilled.\n\n"
        "Operating rules:\n" + rules + "\n\n"
        "The harness records every reply verbatim and fails the run if any of "
        "the following appear: a repeated-character or repeated-phrase loop, a "
        "reply that trails off mid-sentence, or two answers to the identical "
        "question that disagree with each other.  Behave so that none of those "
        "ever happen.\n"
    )


def pad_system_prompt(system: str, depth_tokens: int,
                      chars_per_token: float) -> tuple[str, int]:
    """Pad the shared system prompt toward ``depth_tokens`` estimated tokens.

    The padding is itself a stable, structured corpus (a fake registry dump),
    so it is a realistic prefix and not one repeated line -- a repeated line
    would let a degeneracy detector fire on the *prompt* and would not exercise
    the radix cache the way real traffic does.
    """
    overhead = int(len(system) / chars_per_token)
    if depth_tokens <= overhead:
        return system, overhead
    target_chars = int(depth_tokens * chars_per_token) - len(system)
    rows = []
    n = 0
    byte_count = 0
    while byte_count < target_chars:
        rows.append(
            f"ROW {n:06d} | entry {n*7 % 99991:05d} | status ok | "
            f"shard s{n % 37:02d} | checksum {n*2654435761 % 2**32:08x} | "
            f"note the registry ledger records shard {n % 37} entry {n*7 % 99991}")
        byte_count += len(rows[-1]) + 1
        n += 1
    padding = ("\nREGISTRY LEDGER (reference data, read-only):\n"
               + "\n".join(rows) + "\n")
    return system + padding, overhead


def build_tool_turn_spec(turn_index: int) -> tuple[str, str, dict]:
    """A deterministic tool-call request: (user_text, tool_name, args)."""
    tools = [
        ("get_shard_status", {"shard": 12, "verbose": False}),
        ("get_shard_status", {"shard": 27, "verbose": True}),
        ("verify_checksum", {"entry": 4096, "algorithm": "blake3"}),
        ("list_entries", {"shard": 3, "limit": 50}),
        ("get_shard_status", {"shard": 5, "verbose": False}),
    ]
    name, args = tools[turn_index % len(tools)]
    arg_txt = ", ".join(f"{k}={json.dumps(v)}" for k, v in args.items())
    user = (f"Call the tool {name} with arguments {arg_txt}. "
            f"Reply with the JSON object only.")
    return user, name, args


def build_essay_prompt() -> str:
    return ("Write a continuous, non-repetitive essay of about 600 words on how "
            "coastal lighthouses were built and maintained in the nineteenth "
            "century. Use ordinary prose paragraphs. Do not use lists or headings.")


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------
def run_gate(cfg: dict) -> dict:
    """Run the soak against ``cfg['base_url']``.  Returns a report dict whose
    ``exit_code`` is the process exit code and whose ``records`` hold every raw
    reply.  Corruption is a verdict, not a crash."""
    verbose = cfg.get("verbose", False)
    ep = Endpoint(cfg["base_url"], timeout=cfg.get("timeout", 900),
                  api_key=cfg.get("api_key"))
    report = {
        "tool": "gate-37111",
        "version": VERSION,
        "upstream": UPSTREAM,
        "config": {k: cfg.get(k) for k in
                   ("base_url", "depth_tokens", "duration_min", "turns",
                    "max_tokens", "essay_max_tokens", "chars_per_token",
                    "thinking", "seed")},
        "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "endpoint": {"model": None, "max_model_len": None},
        "records": [],
        "findings": [],          # corruption findings only -> FAIL
        "transport_errors": [],  # transport failures -> inconclusive
        "canary": {},
        "verdict": None,
        "exit_code": None,
    }

    # -- resolve the endpoint (transport failure -> exit 1) ------------------
    try:
        model = ep.resolve_model(cfg.get("model"))
        report["endpoint"]["model"] = model
    except Exception as e:  # noqa: BLE001
        report["verdict"] = "UNREACHABLE"
        report["findings"].append(f"cannot resolve model: {type(e).__name__}: {e}")
        report["exit_code"] = 1
        return report
    report["endpoint"]["max_model_len"] = ep.max_model_len()
    _vlog(verbose, f"model={model} max_model_len={report['endpoint']['max_model_len']}")

    # -- build the shared prefix --------------------------------------------
    chars_per_token = cfg.get("chars_per_token", DEFAULT_CHARS_PER_TOKEN)
    system = build_system_prompt()
    est_tokens = int(len(system) / chars_per_token)
    if cfg.get("depth_tokens"):
        system, est_tokens = pad_system_prompt(
            system, cfg["depth_tokens"], chars_per_token)
    report["endpoint"]["system_prompt_chars"] = len(system)
    report["endpoint"]["estimated_system_tokens"] = est_tokens
    _vlog(verbose, f"shared system prompt ~{est_tokens} est tokens "
                   f"({len(system)} chars)")

    max_tokens = cfg.get("max_tokens", 512)
    essay_max = cfg.get("essay_max_tokens", 2048)
    thinking = cfg.get("thinking", False)

    def do_ask(messages, mt):
        return ep.chat(messages, model, mt, thinking=thinking)

    def record(kind, result, detectors, extra=None):
        rec = {
            "kind": kind,
            "elapsed_s": result["elapsed_s"],
            "finish_reason": result["finish_reason"],
            "prompt_tokens": result["usage"].get("prompt_tokens"),
            "completion_tokens": result["usage"].get("completion_tokens"),
            "text": result["text"],
            "tool_calls": result["tool_calls"],
            "detectors": detectors,
        }
        if extra:
            rec.update(extra)
        report["records"].append(rec)
        for name, (bad, why) in detectors.items():
            if bad:
                report["findings"].append(f"{kind}: {name}: {why}")
        return rec

    # -- the soak loop -------------------------------------------------------
    deadline = time.time() + cfg["duration_min"] * 60
    turns = cfg.get("turns")
    n_iters = 0
    messages = [{"role": "system", "content": system}]
    i = 0
    while True:
        if turns is not None and n_iters >= turns:
            break
        if time.time() >= deadline:
            break
        # every third iteration is the long non-looping essay probe; the rest
        # are tool turns, so the tool loop dominates and the essay signature is
        # still sampled repeatedly.
        if i % 3 == 2:
            _vlog(verbose, f"iter {n_iters}: essay probe")
            try:
                r = do_ask([{"role": "system", "content": system},
                            {"role": "user", "content": build_essay_prompt()}],
                           essay_max)
            except Exception as e:  # noqa: BLE001
                report["transport_errors"].append(f"essay: {type(e).__name__}: {e}")
                i += 1
                n_iters += 1
                continue
            det = {
                "degeneration": detect_degeneration(r["text"]),
                "truncation": detect_truncation(r["text"], r["finish_reason"], essay_max),
            }
            record("essay", r, det)
        else:
            user, tool, args = build_tool_turn_spec(i)
            _vlog(verbose, f"iter {n_iters}: tool {tool}")
            turn_messages = messages + [{"role": "user", "content": user}]
            try:
                r = do_ask(turn_messages, max_tokens)
            except Exception as e:  # noqa: BLE001
                report["transport_errors"].append(f"tool: {type(e).__name__}: {e}")
                i += 1
                n_iters += 1
                continue
            det = {
                "degeneration": detect_degeneration(r["text"] or
                                                     json.dumps(r["tool_calls"])),
                "truncation": detect_truncation(r["text"] or "x",
                                                r["finish_reason"], max_tokens),
                "tool_call": detect_tool_call(r, tool, args),
            }
            record("tool", r, det, extra={"expected_tool": tool,
                                          "expected_args": args})
            # grow the conversation so prefix reuse is genuinely exercised
            call = parse_tool_call(r)
            if call is not None:
                messages = turn_messages + [
                    {"role": "assistant",
                     "content": r["text"] or json.dumps(call)},
                    {"role": "tool",
                     "content": json.dumps({"status": "ok",
                                            "echo": call.get("args")})},
                ]
            else:
                messages = turn_messages
        i += 1
        n_iters += 1

    report["iterations"] = n_iters
    report["transport_error_count"] = len(report["transport_errors"])
    if n_iters == 0:
        report["verdict"] = "ERROR"
        report["findings"].append("no iterations ran (duration too short or turns=0)")
        report["exit_code"] = 2 if not report["transport_errors"] else 1
        return report

    # -- warm/cold canary: the #38319 discriminator -------------------------
    canary_msgs = [{"role": "system", "content": system},
                   {"role": "user", "content": CANARY_Q}]
    _vlog(verbose, "canary: warm re-ask")
    warm = None
    try:
        warm = do_ask(canary_msgs, max_tokens)
    except Exception as e:  # noqa: BLE001
        report["transport_errors"].append(f"canary warm: {type(e).__name__}: {e}")

    cold = None
    cold_method = None
    if warm is not None:
        ok, detail = ep.flush_cache()
        if ok:
            cold_method = "flush_cache"
            _vlog(verbose, f"canary: cold re-ask (flush_cache ok: {detail[:60]!r})")
            cold_msgs = canary_msgs
        else:
            cold_method = "salted-fresh-session"
            _vlog(verbose, "canary: cold re-ask via salt "
                           f"(/flush_cache unavailable: {detail[:80]!r})")
            salt = f"\n[cold-probe nonce {cfg.get('seed', 0)}-{time.time_ns()}]\n"
            cold_msgs = [{"role": "system", "content": system + salt},
                         {"role": "user", "content": CANARY_Q}]
        try:
            cold = do_ask(cold_msgs, max_tokens)
        except Exception as e:  # noqa: BLE001
            report["transport_errors"].append(f"canary cold: {type(e).__name__}: {e}")

    if warm is not None and cold is not None:
        agree = _normalize(warm["text"]) == _normalize(cold["text"])
        report["canary"] = {
            "question": CANARY_Q,
            "cold_method": cold_method,
            "warm": {"text": warm["text"], "finish_reason": warm["finish_reason"],
                     "prompt_tokens": warm["usage"].get("prompt_tokens")},
            "cold": {"text": cold["text"], "finish_reason": cold["finish_reason"],
                     "prompt_tokens": cold["usage"].get("prompt_tokens")},
            "agree": agree,
        }
        if not agree:
            report["findings"].append(
                "canary: warm-prefix and cold-prefix answers DISAGREE "
                f"({warm['text'].strip()[:60]!r} vs {cold['text'].strip()[:60]!r}) "
                f"-- the #38319/#37111 prefix-corruption fingerprint")
        for label, ans in (("warm", warm["text"]), ("cold", cold["text"])):
            nums = re.findall(r"-?\d[\d,]*", ans)
            got = nums[-1].replace(",", "") if nums else None
            if got != CANARY_EXPECTED:
                report["findings"].append(
                    f"canary: {label} answer {got!r} != expected {CANARY_EXPECTED!r}")
    else:
        report["canary"] = {"question": CANARY_Q, "cold_method": cold_method,
                            "warm": warm and warm["text"],
                            "cold": cold and cold["text"],
                            "error": "canary incomplete"}
        report["findings"].append("canary: incomplete (warm or cold ask failed)")

    # -- verdict -------------------------------------------------------------
    if report["findings"]:
        report["verdict"] = "FAIL"
        report["exit_code"] = 3
    elif len(report["transport_errors"]) >= n_iters:
        report["verdict"] = "UNREACHABLE"
        report["exit_code"] = 1
    elif report["transport_errors"]:
        # No corruption seen, but the soak did not complete cleanly.  A gate
        # must not turn that into a pass.
        report["verdict"] = "PARTIAL"
        report["exit_code"] = 3
    else:
        report["verdict"] = "PASS"
        report["exit_code"] = 0
    return report


# ---------------------------------------------------------------------------
# offline self-test -- an in-process mock with deliberately different
# behaviours, asserted to classify the way each must.  A guard that has only
# ever passed is not a guard.
# ---------------------------------------------------------------------------
class _MockHandler(BaseHTTPRequestHandler):
    state: dict = {}

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            self._send(200, {"data": [{"id": "mock-model",
                                       "max_model_len": 262144}]})
        elif self.path.startswith("/flush_cache"):
            self.state["flushed"] = True
            self._send(200, {"status": "Cache flushed."})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        if self.path.startswith("/flush_cache"):
            if self.state.get("mode") == "radix-nosalt":
                self._send(404, {"error": "flush disabled"})
            else:
                self.state["flushed"] = True
                self._send(200, {"status": "Cache flushed."})
            return
        if self.path.startswith("/v1/chat/completions"):
            body = json.loads(raw) if raw else {}
            self._send(200, self._respond(body))
            return
        self._send(404, {"error": "not found"})

    def _respond(self, body):
        mode = self.state["mode"]
        msgs = body.get("messages", [])
        user = ""
        system = ""
        for m in msgs:
            if m.get("role") == "user":
                user = m.get("content") or ""
            if m.get("role") == "system":
                system = m.get("content") or ""

        def reply(content, finish="stop"):
            return {"choices": [{"message": {"content": content},
                                 "finish_reason": finish}],
                    "usage": {"prompt_tokens": 1234, "completion_tokens": 50}}

        # canary question
        if "47 multiplied by 89" in user:
            cold = self.state.get("flushed") or ("cold-probe nonce" in system)
            if mode in ("radix", "radix-nosalt") and not cold:
                return reply("9999")          # wrong while the prefix is warm
            return reply("4183")              # right when cold
        # essay probe
        if "lighthouse" in user:
            if mode == "degenerate":
                return reply("!" * 88)
            if mode == "truncate":
                return reply("The keepers of the coastal lights spent their "
                             "nights trimming wicks and recording the tide, and "
                             "then one evening the fog rolled in and the", "stop")
            return reply(" ".join(
                ["The careful keepers of the coastal lights maintained their "
                 "lamps through long nights of fog and storm across the "
                 "whole century."] * 4))
        # tool turn -- emit a clean JSON tool call echoing the request
        if "Call the tool" in user:
            m = re.search(r"Call the tool (\w+) with arguments (.+)\. Reply", user)
            name = m.group(1) if m else "get_shard_status"
            argtxt = m.group(2) if m else "shard=12, verbose=false"
            args = {}
            for pair in argtxt.split(", "):
                k, _, v = pair.partition("=")
                try:
                    args[k.strip()] = json.loads(v.strip())
                except Exception:  # noqa: BLE001
                    args[k.strip()] = v.strip()
            if mode == "degenerate":
                return reply("!")
            return reply(json.dumps({"tool": name, "args": args}))
        return reply("ok")


def _start_mock(mode: str):
    state = {"mode": mode, "flushed": False}
    _MockHandler.state = state
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _mock_cfg(url: str, turns: int) -> dict:
    return {"base_url": url, "duration_min": 1.0, "turns": turns,
            "depth_tokens": 0, "max_tokens": 256,
            "essay_max_tokens": 2048, "chars_per_token": 4.0,
            "thinking": False, "seed": 1, "verbose": False, "timeout": 30}


def selftest() -> int:
    """Run the gate against an in-process mock in five deliberately different
    behaviours and assert each is classified the way it must be."""
    cases = [
        ("clean", "PASS", 0, "clean server must pass"),
        ("degenerate", "FAIL", 3, "punctuation/repetition collapse must fail"),
        ("truncate", "FAIL", 3, "mid-sentence stop must fail"),
        ("radix", "FAIL", 3, "warm!=cold must fail (flush_cache route)"),
        ("radix-nosalt", "FAIL", 3, "warm!=cold must fail (salt fallback)"),
    ]
    failures = 0
    clean_ran = False
    for mode, v_expected, x_expected, note in cases:
        httpd, url = _start_mock(mode)
        try:
            rep = run_gate(_mock_cfg(url, turns=3))
            clean_findings = list(rep["findings"])
        finally:
            httpd.shutdown()
        ok = rep["verdict"] == v_expected and rep["exit_code"] == x_expected
        print(f"[selftest] {mode:14s} verdict={rep['verdict']:6s} "
              f"exit={rep['exit_code']} expected={v_expected}/{x_expected} "
              f"{'OK' if ok else 'MISMATCH'}  -- {note}")
        if not ok:
            failures += 1
            for f in clean_findings:
                print(f"             finding: {f}")
        # the clean case must be clean for the right reason: no detector fired
        if mode == "clean":
            clean_ran = True
            if rep["findings"]:
                print(f"[selftest] clean case produced findings: {rep['findings']}")
                failures += 1
            if rep["canary"].get("agree") is not True:
                print("[selftest] clean case canary did not agree")
                failures += 1
    if not clean_ran:
        failures += 1
    if failures:
        print(f"[selftest] FAILED ({failures} case(s))")
        return 1
    print("[selftest] all cases classified correctly")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Correctness soak gate for sglang#37111 / #38319 silent "
                    "decode corruption (temperature 0, multi-turn tool loop, "
                    "long shared prefix, warm/cold canary).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage\n-----")[-1].strip())
    p.add_argument("--base-url", default="http://127.0.0.1:8000",
                   help="OpenAI-compatible endpoint (default %(default)s)")
    p.add_argument("--model", default=None,
                   help="served model name (default: first from /v1/models)")
    p.add_argument("--depth-tokens", type=int, default=0,
                   help="pad the shared system prompt toward this many tokens "
                        "(0 = no padding). 100000 exercises the deep-context / "
                        "prefix-reuse path the upstream bugs live on.")
    p.add_argument("--duration-min", type=float, default=1.0,
                   help="soak duration in minutes (default %(default)s); the "
                        "loop stops at whichever of --duration-min/--turns "
                        "comes first")
    p.add_argument("--turns", type=int, default=None,
                   help="stop after this many iterations (default: until "
                        "--duration-min elapses)")
    p.add_argument("--max-tokens", type=int, default=512,
                   help="max_tokens for tool turns and the canary")
    p.add_argument("--essay-max-tokens", type=int, default=2048,
                   help="max_tokens for the long non-looping essay probe "
                        "(default %(default)s, comfortably above a 600-word "
                        "essay so a healthy server finishes naturally)")
    p.add_argument("--chars-per-token", type=float, default=DEFAULT_CHARS_PER_TOKEN,
                   help="chars/token estimate used only to *build* the padded "
                        "prompt; the report carries the server's real count")
    p.add_argument("--thinking", action="store_true",
                   help="enable the model's thinking template (default off)")
    p.add_argument("--seed", type=int, default=0,
                   help="salt seed for the cold re-ask when /flush_cache is "
                        "unavailable")
    p.add_argument("--api-key", default=None, help="bearer token, if required")
    p.add_argument("--timeout", type=int, default=900,
                   help="per-request timeout seconds (default %(default)s)")
    p.add_argument("--json", metavar="OUT", default=None,
                   help="write the full JSON report to this path")
    p.add_argument("--verbose", action="store_true",
                   help="timestamped progress on stderr")
    p.add_argument("--selftest", action="store_true",
                   help="run the offline mock ladder and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        return selftest()

    if args.depth_tokens and args.depth_tokens < 1024:
        print("error: --depth-tokens must be 0 or >= 1024", file=sys.stderr)
        return 2
    if args.duration_min <= 0 and args.turns is None:
        print("error: give a positive --duration-min or a --turns count",
              file=sys.stderr)
        return 2

    cfg = {
        "base_url": args.base_url,
        "model": args.model,
        "depth_tokens": args.depth_tokens,
        "duration_min": args.duration_min,
        "turns": args.turns,
        "max_tokens": args.max_tokens,
        "essay_max_tokens": args.essay_max_tokens,
        "chars_per_token": args.chars_per_token,
        "thinking": args.thinking,
        "seed": args.seed,
        "api_key": args.api_key,
        "timeout": args.timeout,
        "verbose": args.verbose,
    }

    print(f"gate-37111 v{VERSION} -> {args.base_url}")
    for key in ("issue_37111", "issue_38319"):
        u = UPSTREAM[key]
        print(f"  upstream {u['url']} [{u['state']}, opened {u['opened']}]")
    print(f"  model={args.model or 'auto'} depth={args.depth_tokens or 'unpadded'} "
          f"duration={args.duration_min}m turns={args.turns or 'until-duration'}")

    report = run_gate(cfg)

    # -- raw audit trail -----------------------------------------------------
    print("\n--- raw replies (audit these, do not trust the verdict alone) ---")
    for rec in report["records"]:
        snippet = (rec["text"] or json.dumps(rec["tool_calls"]))[:200]
        bad = [k for k, v in rec["detectors"].items() if v[0]]
        print(f"[{rec['kind']:5s}] ptok={rec['prompt_tokens']} "
              f"ctok={rec['completion_tokens']} fin={rec['finish_reason']} "
              f"{'BAD:' + ','.join(bad) if bad else 'ok'}")
        print(f"        {snippet!r}")
    if report.get("canary"):
        print("\n--- warm/cold canary (the #38319 discriminator) ---")
        for line in _json_dumps(report["canary"]).splitlines():
            print(f"  {line}")

    print("\n=== VERDICT:", report["verdict"], "===")
    for f in report["findings"]:
        print("  finding:", f)
    for t in report["transport_errors"]:
        print("  transport:", t)
    if report["verdict"] == "PASS":
        print("  clean run: no degeneration, no truncation, warm==cold.")
        print("  NOTE: a PASS is a negative result, not proof of absence -- see "
              "tools/gate-37111-design.md 'what a PASS proves'.")

    if args.json:
        with open(args.json, "w") as fh:
            fh.write(_json_dumps(report))
        print(f"wrote {args.json}")
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())