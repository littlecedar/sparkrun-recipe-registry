#!/usr/bin/env python3
# Report-only freshness probe for the llama.cpp engine pins (llamacpp-engine.yml `report` job).
#
# Stdlib only and never fails: every probe is wrapped and a failure is printed as an ERROR line.
# Prints markdown to stdout and appends it to $GITHUB_STEP_SUMMARY when set.
import json
import os
import pathlib
import re
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
API = "https://api.github.com"
UA = "sparkrun-recipe-registry-ci"


def fetch(url, raw=False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return body.decode("utf-8", "replace") if raw else json.loads(body)


def try_fetch(url, raw=False):
    try:
        return fetch(url, raw)
    except Exception as exc:  # report-only: a probe that fails is printed, never fatal
        return "ERROR: %s" % exc


def ok(text):
    return isinstance(text, str) and not text.startswith("ERROR:")


out = []


def say(line=""):
    out.append(line)
    print(line)


# Our pins, read from the Dockerfiles that carry them.
pins = []
for d in sorted(pathlib.Path("recipes").rglob("Dockerfile*")):
    try:
        text = d.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:          # report-only: an unreadable Dockerfile is a printed gap
        say("- could not read %s: %s" % (d, exc))
        continue
    repo = re.search(r"(?m)^ARG LLAMA_REPO=https://github\.com/(\S+?)\.git", text)
    ref = re.search(r"(?m)^ARG LLAMA_REF=(\S*)", text)
    if repo and ref and ref.group(1):
        pins.append((d.as_posix(), repo.group(1), ref.group(1)))
# The build inside the image sparkrun's llama-cpp runtime advertises for GB10
# (mad-science/LLAMACPP-GGUF.md; the shipped Mellum GGUF arm's container tag).
pins.append(("scitrera/dgx-spark-llama-cpp:b10549-cu131", "ggml-org/llama.cpp", "b2e5e9b"))

head = try_fetch(API + "/repos/ggml-org/llama.cpp/commits/master")
# An error body (rate limit, 403) is JSON and therefore a dict, so key presence — not type — decides.
if isinstance(head, dict) and "sha" in head:
    head_sha = head["sha"]
    date = (head.get("commit") or {}).get("committer", {}).get("date", "date unknown")
    say("upstream head: `%s` (%s)" % (head_sha[:12], date))
else:
    head_sha = ""
    say(head if isinstance(head, str) else "ERROR: unexpected upstream-head payload: %r" % (head,))
say()

say("| our ref | repo | ref | upstream commits we lack | `behind_by` |")
say("|---|---|---|---|---|")
for label, repo, ref in pins:
    ahead = behind = "?"
    base = try_fetch("%s/repos/%s/commits/%s" % (API, repo, ref))
    base_sha = base.get("sha", ref) if isinstance(base, dict) else ref
    if repo == "ggml-org/llama.cpp":
        cmp_url = "%s/repos/ggml-org/llama.cpp/compare/%s...master" % (API, base_sha)
    else:
        # Cross-fork compare: the base lives in the fork, the head is the upstream branch.
        cmp_url = "%s/repos/%s/compare/%s...ggml-org:master" % (API, repo, base_sha)
    cmp = try_fetch(cmp_url)
    if isinstance(cmp, dict):
        ahead = cmp.get("ahead_by", "?")
        behind = cmp.get("behind_by", "?")
    say("| `%s` | %s | `%s` | %s | %s |" % (label, repo, ref[:12], ahead, behind))
say()
say("`behind_by` is GitHub's field: commits our ref has that upstream head does not (fork-only "
    "work). The column before it is what we are *missing*.")
say()

releases = try_fetch(API + "/repos/ggml-org/llama.cpp/releases?per_page=3")
say("upstream releases (newest 3):")
if isinstance(releases, list) and releases:
    for r in releases:
        say("- `%s` — %s — target `%s`"
            % (r.get("tag_name"), (r.get("published_at") or "")[:10],
               (r.get("target_commitish") or "")[:12]))
else:
    say("- %s" % (releases if isinstance(releases, str) else "none published"))
say()

say("upstream feature gate at head `%s`:" % (head_sha[:12] or "(unresolved)"))
if head_sha:
    raw = "https://raw.githubusercontent.com/ggml-org/llama.cpp/" + head_sha + "/"
    mellum = try_fetch(raw + "src/models/mellum.cpp", raw=True)
    say("- Mellum MTP `graph_mtp` (src/models/mellum.cpp): %s"
        % ("present" if ok(mellum) and "graph_mtp" in mellum else "ABSENT"))
    say("- Kolibri-1 `src/models/kolibri1.cpp`: %s"
        % ("present" if ok(try_fetch(raw + "src/models/kolibri1.cpp", raw=True)) else "ABSENT"))
    say("- Decision-2 `src/models/vllm-decision2.cpp`: %s"
        % ("present" if ok(try_fetch(raw + "src/models/vllm-decision2.cpp", raw=True))
           else "ABSENT"))
    cuda = try_fetch(raw + "ggml/src/ggml-cuda/CMakeLists.txt", raw=True)
    say("- CUDA sm_121 `121a-real` (ggml/src/ggml-cuda/CMakeLists.txt): %s"
        % ("present" if ok(cuda) and "121a-real" in cuda else "ABSENT"))
say()

hub = try_fetch("https://hub.docker.com/v2/repositories/scitrera/dgx-spark-llama-cpp"
                "/tags?page_size=20&ordering=last_updated")
say("publisher — scitrera/dgx-spark-llama-cpp (newest tags by last_updated):")
if isinstance(hub, dict) and hub.get("results"):
    tags = hub["results"]
    engines = [t for t in tags if re.match(r"^b\d+", t.get("name") or "")]
    if engines:
        t = engines[0]
        say("- newest engine tag: `%s` — last updated %s"
            % (t.get("name"), t.get("last_updated")))
    else:
        say("- no engine tag (`bNNNNN-…`) in the newest 20 tags")
    say("- newest tag of any kind: `%s` — %s"
        % (tags[0].get("name"), tags[0].get("last_updated")))
else:
    say("- %s" % (hub if isinstance(hub, str) else "no tags returned"))

summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    try:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## llama.cpp engine report\n\n")
            fh.write("\n".join(out) + "\n")
    except OSError as exc:   # the report is already on stdout; a summary write must not fail the job
        print("could not write $GITHUB_STEP_SUMMARY: %s" % exc)
