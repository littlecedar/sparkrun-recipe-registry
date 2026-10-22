#!/usr/bin/env python3
"""Pin refresh sweep: which recipe pins have fallen behind, and by what.

Two hand surveys on 2026-10-22 answered this the expensive way: five model
revisions sat behind Hub heads, a floating `ARG BASE_IMAGE` made a rebuild
non-reproducible, and every llama.cpp arm was frozen because the publisher of
the one `scitrera` image stopped.  This tool is that survey as a command, and
it is what CI runs.

What it answers, per pin:

* **models** — recipe `model:` + top-level `model_revision:` (never `revision:`),
  `speculative_draft_model[_revision]:`, and the mod/launcher pins
  (`DEFAULT_REVISION =`, `*_REVISION` with its `*_REPO`/`*_MODEL` partner,
  `OVERLAY_REVISION`, `hf download … --revision`).  Stale is split into weights
  vs docs by the *unified diff* of `…/compare/{pin}..main`, because a template
  or README commit is not a reason to re-boot an arm.
* **containers** — recipe `container:` refs against Docker Hub and ghcr; a tag
  whose resolved digest moved is `container-newer-release` and is the only
  thing `--apply` will rewrite.  A tag without a digest is `container-floating`
  (the tie-break a re-push destroys) and is never auto-resolved.
* **build inputs** — Dockerfile `ARG BASE_IMAGE`, `FROM …@sha256:` / `FROM tag`,
  and `ARG <NAME>_REF` paired with `ARG <NAME>_REPO` (llama.cpp, TensorFold).
* **llama.cpp** — the dedicated section: our fork refs, upstream head + date,
  `behind_by`, whether the three fork features (`graph_mtp`, `kolibri1`,
  `vllm-decision2`) and `121a-real` are native upstream, and the publisher
  status of every llama-cpp image we ship.  That is the answer to "can a stock
  build replace this fork image?".

Fail closed.  A pin that cannot be checked is `*-unresolvable`, never silently
clean; an unparseable recipe is an error; an empty parse is an error.

Exit codes (with `--exit-code`): 0 no drift, 1 drift, 2 could not run.  A hard
failure (unparseable tree, no recipes matched, network down) is exit 2 with or
without the flag, so CI can never read a failed sweep as "all clean".

    tools/refresh-sweep.py [--json PATH] [--markdown PATH] [--exit-code]
                           [--only CLASS[,CLASS...]] [--lane LANE] [--recipe PATH]
                           [--apply] [--token-env HF_TOKEN]
                           [--timeout SECONDS] [--cache PATH]

Stdlib only — runs on a laptop, in a container, on a head node with no venv.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "sparkrun-refresh-sweep/1.0 (+https://github.com/littlecedar/sparkrun-recipe-registry)"
CACHE_TTL = 3600  # seconds; older entries are refetched, never reported as current

MODEL_CURRENT = "model-current"
MODEL_STALE_WEIGHTS = "model-stale-weights"
MODEL_STALE_DOCS = "model-stale-docs"
MODEL_UNPINNED = "model-unpinned"
MODEL_UNRESOLVABLE = "model-unresolvable"
CONTAINER_CURRENT = "container-current"
CONTAINER_NEWER_RELEASE = "container-newer-release"
CONTAINER_FLOATING = "container-floating"
CONTAINER_UNRESOLVABLE = "container-unresolvable"
BUILD_INPUT_FLOATING = "build-input-floating"
BUILD_INPUT_STALE = "build-input-stale"
BUILD_INPUT_UNRESOLVABLE = "build-input-unresolvable"

CLASSES = (
    MODEL_CURRENT, MODEL_STALE_WEIGHTS, MODEL_STALE_DOCS, MODEL_UNPINNED,
    MODEL_UNRESOLVABLE,
    CONTAINER_CURRENT, CONTAINER_NEWER_RELEASE, CONTAINER_FLOATING,
    CONTAINER_UNRESOLVABLE,
    BUILD_INPUT_FLOATING, BUILD_INPUT_STALE, BUILD_INPUT_UNRESOLVABLE,
)
#: `*-current` is the only non-drift suffix; build inputs have no current class
#: at all, so a clean build input is counted but emits no row.
DRIFT_CLASSES = frozenset(c for c in CLASSES if not c.endswith("-current"))

#: A changed file with one of these suffixes means the weights moved.
WEIGHTS_RE = re.compile(
    r"\.(safetensors|gguf|bin|pt|pth|ckpt|onnx|npz|h5|msgpack|mlmodel)$"
    r"|\.safetensors\.index\.json$",
    re.I,
)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SweepError(RuntimeError):
    """The sweep could not produce a trustworthy answer (exit 2)."""


class FetchError(RuntimeError):
    def __init__(self, url, reason, status=None):
        super().__init__(f"{reason}: {url}")
        self.url = url
        self.reason = reason
        self.status = status


# --------------------------------------------------------------------- fetch


def _urllib_fetch(url, headers, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, hdrs, body
    except urllib.error.HTTPError as exc:  # 404 is evidence for some callers
        raise FetchError(url, f"HTTP {exc.code}", exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(url, f"{type(exc).__name__}: {exc}") from None


class Fetcher:
    """HTTP with an on-disk cache; a stale entry is refetched, never reused."""

    def __init__(self, timeout=30, cache_path=None, token=None, fetch=None):
        self.timeout = int(timeout)
        self.cache_path = Path(cache_path) if cache_path else None
        self.token = token
        self._fetch = fetch or _urllib_fetch
        self.cache = {}
        self.memo = {}  # per-run: repo listings, default branches, model metadata
        if self.cache_path is not None and self.cache_path.exists():
            try:
                loaded = json.loads(self.cache_path.read_text())
            except (OSError, ValueError) as exc:
                raise SweepError(f"unreadable --cache {self.cache_path}: {exc}") from None
            if not isinstance(loaded, dict):
                raise SweepError(f"--cache {self.cache_path} is not a JSON object")
            self.cache = loaded

    def get(self, url, headers=None):
        """(status, headers, body, cached_at)."""
        cached = self.cache.get(url)
        if cached is not None:
            try:
                age = time.time() - float(cached["fetched_at"])
            except (KeyError, TypeError, ValueError):
                age = CACHE_TTL + 1  # malformed entry: refetch
            if age <= CACHE_TTL and isinstance(cached.get("body"), str):
                return (int(cached.get("status", 200)), dict(cached.get("headers") or {}),
                        cached["body"], cached.get("cached_at"))
        status, hdrs, body = self._fetch(url, headers or {}, self.timeout)
        now = time.time()
        self.cache[url] = {
            "fetched_at": now,
            "cached_at": _iso(now),
            "status": status,
            # only what a caller reads, so the cache stays small
            "headers": {k: v for k, v in hdrs.items()
                        if k.lower() == "docker-content-digest"},
            "body": body,
        }
        return status, self.cache[url]["headers"], body, self.cache[url]["cached_at"]

    def json(self, url, headers=None):
        status, _hdrs, body, cached_at = self.get(url, headers)
        try:
            return json.loads(body), cached_at
        except ValueError as exc:
            raise FetchError(url, f"not JSON ({exc})", status) from None

    def save(self):
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.cache, indent=1, sort_keys=True))
        os.replace(tmp, self.cache_path)


def _iso(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts if ts is not None else time.time()))


def _hf_token(env_name):
    token = os.environ.get(env_name or "") or os.environ.get("HF_TOKEN") or ""
    if token:
        return token.strip()
    node_token = Path.home() / ".cache" / "huggingface" / "token"
    if node_token.is_file():
        try:
            return node_token.read_text().strip()
        except OSError:
            return ""
    return ""


# ------------------------------------------------------------ text parsing


def _scalar(raw):
    """A YAML scalar enough for one-line pins (inline comments stripped)."""
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end > 0 else value[1:]
    if value.startswith((">", "|", "[")):  # block/list: not a pin
        return ""
    cut = value.find(" #")
    return (value[:cut] if cut > 0 else value).strip()


def parse_recipe(text, path="<recipe>"):
    """Top-level recipe keys as text.  A stray `revision:` is NOT a pin."""
    keys = {}
    for line in text.splitlines():
        if not line or line[0] in " \t#":
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        keys.setdefault(match.group(1), _scalar(match.group(2)))
    recipe = {
        "path": path,
        "model": keys.get("model", ""),
        "model_revision": keys.get("model_revision", ""),
        "draft_model": keys.get("speculative_draft_model", ""),
        "draft_revision": keys.get("speculative_draft_model_revision", ""),
        "container": keys.get("container", ""),
        "runtime": keys.get("runtime", ""),
    }
    if not (recipe["model"] or recipe["container"] or keys.get("command")):
        raise SweepError(f"{path}: no model:, container: or command: — cannot classify")
    recipe["stray_revision"] = keys.get("revision", "")
    return recipe


def model_repo_id(value):
    """`org/name:QUANT` → `org/name`; a template or a local path stays as-is."""
    if not value or "{" in value:
        return ""
    return value.split(":", 1)[0].strip()


def parse_container_ref(ref):
    """`[host/]ns/name[:tag][@sha256:…]` → parts; hosts are detected by a dot."""
    raw = (ref or "").strip()
    info = {"raw": raw, "host": "docker.io", "repo": "", "tag": "", "digest": "",
            "error": ""}
    if not raw or "{" in raw:
        info["error"] = f"not a literal ref: {raw!r}"
        return info
    body, _, digest = raw.partition("@")
    if digest:
        if not DIGEST_RE.match(digest.strip()):
            info["error"] = f"malformed digest: {digest!r}"
            return info
        info["digest"] = digest.strip()
    head, sep, rest = body.partition("/")
    if sep and ("." in head or ":" in head or head == "localhost"):
        info["host"] = {"index.docker.io": "docker.io",
                        "registry-1.docker.io": "docker.io"}.get(head, head)
        body = rest
    last = body.rsplit("/", 1)[-1]
    if ":" in last:
        body, _, tag = body.rpartition(":")
        info["tag"] = tag
    info["repo"] = body
    if info["host"] == "docker.io" and "/" not in info["repo"]:
        info["repo"] = f"library/{info['repo']}"
    if not info["repo"]:
        info["error"] = f"no repository in {raw!r}"
    return info


def parse_dockerfile(text):
    """FROM refs and ARG pins, plus the `ARG <X>_REPO` ↔ `<X>_REF` pairing."""
    froms, args = [], {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        match = re.match(r"^(?:FROM|from)\s+(?:--\S+\s+)*(.+)$", stripped)
        if match:
            tokens = match.group(1).split()
            if tokens:
                froms.append(tokens[0])
            continue
        match = re.match(r"^ARG\s+([A-Za-z_][A-Za-z0-9_]*)(?:=(.*))?$", stripped)
        if match:
            args.setdefault(match.group(1), _scalar(match.group(2) or ""))
    return {"froms": froms, "args": args}


def github_repo(url):
    """`https://github.com/owner/name.git` → `owner/name`."""
    match = re.search(r"github\.com[/:]([^/\s]+)/([^/\s#]+?)(?:\.git)?$", url.strip())
    return f"{match.group(1)}/{match.group(2)}" if match else ""


# --------------------------------------------------------------- providers


def _hub_tags_page(repo, fetcher):
    url = (f"https://hub.docker.com/v2/repositories/{repo}/tags"
           "?page_size=100&ordering=last_updated")
    return fetcher.json(url)


def hub_newest_tag(repo, fetcher):
    key = ("hub-newest", repo)
    if key in fetcher.memo:
        return fetcher.memo[key]
    tags, cached_at = _hub_tags_page(repo, fetcher)
    results = tags.get("results") or []
    if not results:
        raise FetchError(f"hub.docker.com/v2/repositories/{repo}/tags", "no tags listed")
    # `buildcache` is bumped by every CI build and says nothing about a release,
    # so the reported tag skips it while the date is the page's newest anywhere.
    releases = [r for r in results if r.get("name") != "buildcache"] or results
    newest = max(releases, key=lambda r: r.get("last_updated") or "")
    value = {"name": newest.get("name"),
             "last_updated": max((r.get("last_updated") or "") for r in results),
             "cached_at": cached_at}
    fetcher.memo[key] = value
    return value


def hub_tag_digest(repo, tag, fetcher):
    key = ("hub-tag", repo, tag)
    if key in fetcher.memo:
        return fetcher.memo[key]
    entry, cached_at = fetcher.json(
        f"https://hub.docker.com/v2/repositories/{repo}/tags/{urllib.parse.quote(tag, safe='')}")
    digest = entry.get("digest") or ""
    if not DIGEST_RE.match(digest):
        raise FetchError(f"hub tag {repo}:{tag}", f"no digest in listing ({digest!r})")
    value = {"digest": digest, "last_updated": entry.get("last_updated"), "cached_at": cached_at}
    fetcher.memo[key] = value
    return value


def ghcr_token(repo, fetcher):
    key = ("ghcr-token", repo)
    if key in fetcher.memo:
        return fetcher.memo[key]
    payload, _ = fetcher.json(f"https://ghcr.io/token?scope=repository:{repo}:pull")
    token = payload.get("token") or payload.get("access_token") or ""
    if not token:
        raise FetchError(f"ghcr token {repo}", "no token in response")
    fetcher.memo[key] = token
    return token


GHCR_ACCEPT = (", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)))


def ghcr_manifest_digest(repo, reference, fetcher):
    headers = {"Authorization": f"Bearer {ghcr_token(repo, fetcher)}",
               "Accept": GHCR_ACCEPT}
    status, hdrs, _body, cached_at = fetcher.get(
        f"https://ghcr.io/v2/{repo}/manifests/{urllib.parse.quote(reference, safe=':')}",
        headers)
    digest = (hdrs.get("docker-content-digest") or hdrs.get("Docker-Content-Digest") or "")
    if not DIGEST_RE.match(digest):
        raise FetchError(f"ghcr manifest {repo}@{reference}", f"no digest (status {status})")
    return {"digest": digest, "cached_at": cached_at}


def hf_get_model(repo, fetcher):
    key = ("hf-model", repo)
    if key in fetcher.memo:
        return fetcher.memo[key]
    headers = {}
    token = fetcher.token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload, cached_at = fetcher.json(
        f"https://huggingface.co/api/models/{urllib.parse.quote(repo, safe='/')}?blobs=false",
        headers)
    value = {"sha": payload.get("sha") or "", "lastModified": payload.get("lastModified") or "",
             "gated": payload.get("gated"), "cached_at": cached_at}
    if not value["sha"]:
        raise FetchError(f"huggingface model {repo}", "no sha in model metadata")
    fetcher.memo[key] = value
    return value


def hf_compare(repo, pin, head_branch, fetcher):
    headers = {}
    if fetcher.token:
        headers["Authorization"] = f"Bearer {fetcher.token}"
    _status, _hdrs, body, cached_at = fetcher.get(
        f"https://huggingface.co/api/models/{urllib.parse.quote(repo, safe='/')}"
        f"/compare/{urllib.parse.quote(pin, safe='')}..{urllib.parse.quote(head_branch, safe='')}",
        headers)
    return body, cached_at


def github_token():
    """`GITHUB_TOKEN`/`GH_TOKEN`, else the gh CLI's stored oauth token."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    hosts = Path.home() / ".config" / "gh" / "hosts.yml"
    try:
        text = hosts.read_text() if hosts.is_file() else ""
    except OSError:
        return ""
    match = re.search(r"^\s*oauth_token:\s*(\S+)", text, re.MULTILINE)
    return match.group(1).strip("'\"") if match else ""


def github_json(path, fetcher, retries=1):
    headers = {"Accept": "application/vnd.github+json"}
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/{path.lstrip('/')}"
    for attempt in range(retries + 1):
        try:
            return fetcher.json(url, headers)
        except FetchError as exc:
            if exc.status == 403:
                raise FetchError(url, "HTTP 403 (rate limited — set GITHUB_TOKEN)",
                                 403) from None
            if exc.status == 404 or attempt >= retries:
                raise
    raise FetchError(url, "unreachable")


def github_default_branch(repo, fetcher):
    key = ("gh-branch", repo)
    if key in fetcher.memo:
        return fetcher.memo[key]
    payload, _ = github_json(f"repos/{repo}", fetcher)
    branch = payload.get("default_branch") or ""
    if not branch:
        raise FetchError(f"github repo {repo}", "no default_branch")
    fetcher.memo[key] = branch
    return branch


def github_branch_at_head(repo, ref, fetcher):
    """The branch whose head is exactly `ref`, or None (a dangling commit)."""
    key = ("gh-head-branch", repo, ref)
    if key in fetcher.memo:
        return fetcher.memo[key]
    payload, _ = github_json(f"repos/{repo}/commits/{ref}/branches-where-head", fetcher)
    branch = payload[0]["name"] if payload else None
    fetcher.memo[key] = branch
    return branch


def github_compare(repo, ref, fetcher, upstream=None, upstream_branch="master"):
    """(payload, cached_at, base) for `ref`.

    Same-repo compare answers "has our build ref moved?" against the branch that
    holds it (or the default branch when the ref is a dangling commit); the
    cross-repo `owner:branch...ref` form (same fork network only) answers "how
    far is this ref behind upstream?", which is the stock-build decision.
    """
    if upstream:
        base = f"{upstream}@{upstream_branch}"
        path = (f"repos/{repo}/compare/{upstream}:{upstream_branch}"
                f"...{urllib.parse.quote(ref, safe='')}")
    else:
        ref_branch = github_branch_at_head(repo, ref, fetcher) or github_default_branch(repo, fetcher)
        base = f"{repo}@{ref_branch}"
        path = (f"repos/{repo}/compare/{urllib.parse.quote(ref, safe='')}"
                f"...{urllib.parse.quote(ref_branch, safe='')}")
    payload, cached_at = github_json(path, fetcher)
    return payload, cached_at, base


def github_file(repo, sha, path, fetcher):
    """File text at a commit, or None when the path does not exist there."""
    try:
        _status, _hdrs, body, _at = fetcher.get(
            f"https://raw.githubusercontent.com/{repo}/{sha}/{path}")
        return body
    except FetchError as exc:
        if exc.status == 404:
            return None
        raise


# -------------------------------------------------------------- classifiers


def _row(cls, scope, path, field, pinned, observed="", reason="", cached_at=None, **extra):
    row = {"class": cls, "scope": scope, "path": path, "field": field,
           "pinned": pinned or "", "observed": observed or "",
           "reason": reason or "", "cached_at": cached_at}
    row.update(extra)
    return row


def _pin_matches(pin, head):
    pin = pin.strip()
    return bool(pin) and (head == pin or (len(pin) >= 7 and len(pin) < 40
                                          and re.fullmatch(r"[0-9a-f]+", pin)
                                          and head.startswith(pin)))


def classify_model(repo, pin, scope, path, field, fetcher):
    """One row for one HF model pin.  Never returns an empty list."""
    if not repo:
        return _row(MODEL_UNRESOLVABLE, scope, path, field, pin,
                    reason="model value is not a resolvable repo id")
    if not pin:
        return _row(MODEL_UNPINNED, scope, path, field, "",
                    reason="no revision pin: main can move under the arm")
    try:
        meta = hf_get_model(repo, fetcher)
    except FetchError as exc:
        return _row(MODEL_UNRESOLVABLE, scope, path, field, pin, reason=exc.reason)
    head = meta["sha"]
    if _pin_matches(pin, head):
        return _row(MODEL_CURRENT, scope, path, field, pin, observed=head,
                    cached_at=meta["cached_at"])
    try:
        diff, cached_at = hf_compare(repo, pin, "main", fetcher)
    except FetchError as exc:
        return _row(MODEL_UNRESOLVABLE, scope, path, field, pin, observed=head,
                    reason=f"pin differs from head; compare failed: {exc.reason}")
    files = re.findall(r"^diff --git a/(\S+) b/", diff, re.M)
    if not files:
        # pin != head but no unified diff: a state the tool cannot adjudicate
        return _row(MODEL_UNRESOLVABLE, scope, path, field, pin, observed=head,
                    reason="pin differs from head but the compare diff is empty",
                    cached_at=cached_at)
    weights = [f for f in files if WEIGHTS_RE.search(f)]
    if weights:
        return _row(MODEL_STALE_WEIGHTS, scope, path, field, pin, observed=head,
                    reason=f"{len(weights)} weight file(s) changed since the pin: "
                           + ", ".join(weights[:3]),
                    cached_at=cached_at, files=files)
    return _row(MODEL_STALE_DOCS, scope, path, field, pin, observed=head,
                reason=f"only non-weight files changed since the pin: "
                       + ", ".join(files[:3]),
                cached_at=cached_at, files=files)


def classify_container(ref, fetcher, scope, path, field="container"):
    """One row for one image ref: current / newer-release / floating / unresolvable."""
    info = parse_container_ref(ref)
    if info["error"]:
        return _row(CONTAINER_UNRESOLVABLE, scope, path, field, ref, reason=info["error"])
    digest, tag, repo, host = info["digest"], info["tag"], info["repo"], info["host"]
    if not digest:
        return _row(CONTAINER_FLOATING, scope, path, field, ref, observed="",
                    reason="tag without a digest: a re-push silently moves the arm")
    try:
        if host == "docker.io":
            if not tag:
                return _row(CONTAINER_CURRENT, scope, path, field, ref,
                            reason="digest-only pin; no tag tracked, so no release "
                                   "comparison is possible")
            current = hub_tag_digest(repo, tag, fetcher)
            newest = hub_newest_tag(repo, fetcher)
            notes = {"newest_tag": newest["name"],
                     "newest_tag_at": newest["last_updated"]}
            if current["digest"] == digest:
                return _row(CONTAINER_CURRENT, scope, path, field, ref,
                            observed=current["digest"], cached_at=current["cached_at"],
                            **notes)
            return _row(CONTAINER_NEWER_RELEASE, scope, path, field, ref,
                        observed=current["digest"], cached_at=current["cached_at"],
                        reason=f"{repo}:{tag} resolved to a newer digest",
                        appliable=True, new_tag=tag, new_digest=current["digest"],
                        **notes)
        if host == "ghcr.io":
            if not tag:
                got = ghcr_manifest_digest(repo, digest, fetcher)
                return _row(CONTAINER_CURRENT, scope, path, field, ref,
                            observed=got["digest"], cached_at=got["cached_at"],
                            reason="digest-only pin; no tag tracked")
            got = ghcr_manifest_digest(repo, tag, fetcher)
            if got["digest"] == digest:
                return _row(CONTAINER_CURRENT, scope, path, field, ref,
                            observed=got["digest"], cached_at=got["cached_at"])
            return _row(CONTAINER_NEWER_RELEASE, scope, path, field, ref,
                        observed=got["digest"], cached_at=got["cached_at"],
                        reason=f"ghcr {repo}:{tag} resolved to a newer digest",
                        appliable=True, new_tag=tag, new_digest=got["digest"])
    except FetchError as exc:
        return _row(CONTAINER_UNRESOLVABLE, scope, path, field, ref, reason=exc.reason)
    return _row(CONTAINER_UNRESOLVABLE, scope, path, field, ref,
                reason=f"no adapter for registry host {host!r}")


BUILD_CLASS = {
    CONTAINER_CURRENT: "",
    CONTAINER_NEWER_RELEASE: BUILD_INPUT_STALE,
    CONTAINER_FLOATING: BUILD_INPUT_FLOATING,
    CONTAINER_UNRESOLVABLE: BUILD_INPUT_UNRESOLVABLE,
}


def classify_image_build_input(ref, fetcher, path, field):
    row = classify_container(ref, fetcher, "dockerfile", path, field)
    cls = BUILD_CLASS.get(row["class"], BUILD_INPUT_UNRESOLVABLE)
    if not cls:
        return None
    row["class"] = cls
    row.pop("appliable", None)
    row.pop("new_tag", None)
    row.pop("new_digest", None)
    return row


def classify_github_ref(repo, ref, fetcher, path, field):
    """`ARG <X>_REF` against its repo's default branch."""
    if not repo:
        return _row(BUILD_INPUT_UNRESOLVABLE, "dockerfile", path, field, ref,
                    reason="no paired ARG <NAME>_REPO, so the ref has no repository")
    if not ref:
        return _row(BUILD_INPUT_FLOATING, "dockerfile", path, field, "",
                    reason="ARG has no default: the tree cannot reproduce the build")
    try:
        payload, cached_at, base = github_compare(repo, ref, fetcher)
    except FetchError as exc:
        return _row(BUILD_INPUT_UNRESOLVABLE, "dockerfile", path, field, ref,
                    reason=exc.reason)
    behind = payload.get("behind_by")
    if not isinstance(behind, int):
        return _row(BUILD_INPUT_UNRESOLVABLE, "dockerfile", path, field, ref,
                    reason="compare response has no behind_by")
    if behind == 0:
        return None
    return _row(BUILD_INPUT_STALE, "dockerfile", path, field, ref, observed=base,
                reason=f"{behind} commit(s) behind {base}", cached_at=cached_at,
                behind_by=behind)


# ------------------------------------------------------------------ mod pins

MOD_REVISION_RE = re.compile(
    r"""^(?:
        export\s+)?(?P<name>[A-Z][A-Z0-9_]*REVISION)\s*=\s*["']?
        (?:\$\{[A-Z0-9_]+:-)?(?P<sha>[0-9a-f]{7,40})""",
    re.X)
MOD_REPO_RE = re.compile(r"""^(?:export\s+)?(?P<name>[A-Z][A-Z0-9_]*(?:_REPO)?)\s*=\s*"""
                         r"""["']?(?:\$\{[A-Z0-9_]+:-)?(?P<value>[^"'\s}]+)""")
HF_DOWNLOAD_RE = re.compile(
    r"""hf\s+download\s+["']?(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)["']?"""
    r"""(?:[^\n]*?--revision[= ]+["']?(?P<sha>[0-9a-f]{7,40}))?""")
DEFAULT_REPO_RE = re.compile(r"""^DEFAULT_REPO\s*=\s*["'](?P<value>[^"']+)""", re.M)


def _looks_like_hf_id(value):
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value or ""))


def find_mod_pins(text):
    """`(repo, pin, field)` for every pin a mod/launcher holds."""
    env = {}
    for line in text.splitlines():
        match = MOD_REPO_RE.match(line.strip())
        if match and _looks_like_hf_id(match.group("value")):
            env.setdefault(match.group("name"), match.group("value"))
    default_repo = DEFAULT_REPO_RE.search(text)
    pins = []
    for line in text.splitlines():
        match = MOD_REVISION_RE.match(line.strip())
        if not match:
            continue
        name, sha = match.group("name"), match.group("sha")
        prefix = name[: -len("_REVISION")] if name.endswith("_REVISION") else "DEFAULT"
        repo = (env.get(f"{prefix}_REPO") or env.get(prefix)
                or (default_repo.group("value") if prefix == "DEFAULT" and default_repo else "")
                or "")
        pins.append((repo, sha, name))
    for match in HF_DOWNLOAD_RE.finditer(text):
        if match.group("sha"):
            pins.append((match.group("repo"), match.group("sha"), "hf download --revision"))
    return pins


# ------------------------------------------------------------------- sweep


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=False)


def repo_root(explicit=None):
    if explicit:
        return Path(explicit).resolve()
    proc = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip())
    return Path.cwd().resolve()


def tracked_paths(root):
    """`git ls-files` when available, else a filesystem walk."""
    proc = _git(root, "ls-files", "-z")
    if proc.returncode == 0:
        names = [n for n in proc.stdout.split("\0") if n]
        if not names:
            raise SweepError(f"{root}: git ls-files returned nothing")
        return names
    names = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for name in files:
            names.append(str(Path(base, name).relative_to(root)))
    if not names:
        raise SweepError(f"{root}: no files found and git ls-files is unavailable")
    return names


def recipe_files(paths):
    out = []
    for name in paths:
        parts = name.split("/")
        if len(parts) == 3 and parts[0] == "recipes" and parts[1] != "mods" \
                and name.endswith((".yaml", ".yml")):
            out.append(name)
    return sorted(out)


def dockerfiles(paths):
    return sorted(n for n in paths if "Dockerfile" in n.rsplit("/", 1)[-1])


def mod_scripts(paths):
    out = []
    for name in paths:
        if not name.endswith((".py", ".sh")):
            continue
        if name.startswith("mods/") or (name.startswith("recipes/") and "/mods/" in name):
            out.append(name)
    return sorted(out)


def _read(root, rel):
    try:
        return (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SweepError(f"{rel}: unreadable ({exc})") from None


def sweep(root, fetcher, only_recipe=None, lane=None):
    """Classify every pin in the tracked tree.  Raises SweepError, never returns []."""
    paths = tracked_paths(root)
    recipes = recipe_files(paths)
    if lane:
        recipes = [r for r in recipes if r.split("/")[1] == lane]
    if only_recipe:
        wanted = Path(only_recipe)
        if wanted.is_absolute():
            try:
                rel = str(wanted.resolve().relative_to(root))
            except ValueError:
                raise SweepError(f"--recipe {only_recipe}: not under {root}") from None
        else:
            rel = str(wanted)
        if rel not in paths and not (root / rel).is_file():
            raise SweepError(f"--recipe {only_recipe}: not a tracked file")
        recipes = [rel]
    if not recipes:
        raise SweepError("no recipes matched the selection — refusing to report "
                         "an empty sweep as clean")

    rows, warnings, clean_build_inputs = [], [], 0
    models = 0
    for rel in recipes:
        recipe = parse_recipe(_read(root, rel), rel)
        if recipe["stray_revision"]:
            warnings.append(f"{rel}: top-level `revision:` is ignored — a model pin is "
                            f"`model_revision:` (the value {recipe['stray_revision']} is not applied)")
        if recipe["model"]:
            models += 1
            rows.append(classify_model(model_repo_id(recipe["model"]),
                                       recipe["model_revision"], "recipe", rel, "model",
                                       fetcher))
        if recipe["draft_model"]:
            models += 1
            rows.append(classify_model(model_repo_id(recipe["draft_model"]),
                                       recipe["draft_revision"], "recipe", rel,
                                       "speculative_draft_model", fetcher))
        if recipe["container"]:
            row = classify_container(recipe["container"], fetcher, "recipe", rel, "container")
            if recipe["runtime"]:
                row["runtime"] = recipe["runtime"]
            rows.append(row)

    if not only_recipe:
        for rel in mod_scripts(paths):
            for repo, pin, field in find_mod_pins(_read(root, rel)):
                models += 1
                rows.append(classify_model(repo, pin, "mod", rel, field, fetcher))

        for rel in dockerfiles(paths):
            parsed = parse_dockerfile(_read(root, rel))
            seen = set()
            for ref in parsed["froms"]:
                if "$" in ref or ref in seen:
                    continue
                seen.add(ref)
                row = classify_image_build_input(ref, fetcher, rel, "FROM")
                if row:
                    rows.append(row)
                else:
                    clean_build_inputs += 1
            base = parsed["args"].get("BASE_IMAGE", "")
            if base and base not in seen:
                seen.add(base)
                row = classify_image_build_input(base, fetcher, rel, "ARG BASE_IMAGE")
                if row:
                    rows.append(row)
                else:
                    clean_build_inputs += 1
            for name, value in parsed["args"].items():
                if not name.endswith("_REF"):
                    continue
                repo = github_repo(parsed["args"].get(f"{name[:-4]}_REPO", ""))
                row = classify_github_ref(repo, value, fetcher, rel, f"ARG {name}")
                if row:
                    rows.append(row)
                else:
                    clean_build_inputs += 1

    llama = collect_llama_cpp(root, paths, recipes, fetcher)
    llama_rows = llama.pop("rows")
    # The llama section re-classifies the same `ARG LLAMA_REF`; its row carries
    # the upstream gap, so it wins.  One row per (path, field) either way.
    for row in llama_rows if not only_recipe else []:  # --recipe: section stays informational
        key = (row["path"], row["field"])
        rows = [r for r in rows if (r["path"], r["field"]) != key]
        rows.append(row)

    for row in rows:
        if row["class"] not in CLASSES:
            raise SweepError(f"internal: unknown class {row['class']!r}")
    if not rows:
        raise SweepError("the sweep classified nothing — refusing to report that as clean")

    counts = {}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1

    return {
        "rows": rows,
        "counts": counts,
        "llama_cpp": llama,
        "warnings": warnings,
        "totals": {
            "recipes": len(recipes),
            "model_pins": models,
            "container_pins": sum(1 for r in rows if r["field"] == "container"),
            "build_inputs": sum(1 for r in rows if r["scope"] in ("dockerfile", "llama_cpp"))
                            + clean_build_inputs,
            "clean_build_inputs": clean_build_inputs,
        },
    }


LLAMA_UPSTREAM = "ggml-org/llama.cpp"
LLAMA_UPSTREAM_OWNER = "ggml-org"  # the cross-repo compare base is `owner:branch`
PIN_CURRENT = "pin-current"  # informational status of a llama.cpp ref
LLAMA_FEATURES = (
    ("graph_mtp", "src/models/mellum.cpp", "graph_mtp"),
    ("kolibri1", "src/models/kolibri1.cpp", None),
    ("vllm-decision2", "src/models/vllm-decision2.cpp", None),
    ("121a-real", "ggml/src/ggml-cuda/CMakeLists.txt", "121a-real"),
)


def collect_llama_cpp(root, paths, recipes, fetcher):
    """The dedicated section: our refs, upstream head, feature map, image publishers."""
    rows, refs, images = [], [], []
    for rel in dockerfiles(paths):
        parsed = parse_dockerfile(_read(root, rel))
        for name, value in parsed["args"].items():
            if not name.endswith("_REF"):
                continue
            repo = github_repo(parsed["args"].get(f"{name[:-4]}_REPO", ""))
            if "llama" not in repo.lower():
                continue
            refs.append({"source": rel, "repo": repo, "ref": value or "",
                         "field": f"ARG {name}"})

    for rel in recipes:
        recipe = parse_recipe(_read(root, rel), rel)
        info = parse_container_ref(recipe["container"])
        name = info["repo"].lower()
        if recipe.get("runtime") == "llama-cpp" or "llama-cpp" in name or "llamacpp" in name:
            images.append({"path": rel, "ref": recipe["container"],
                           "repo": info["repo"], "tag": info["tag"],
                           "digest": info["digest"], "host": info["host"]})

    upstream = {"repo": LLAMA_UPSTREAM, "branch": "master"}
    try:
        commits, _ = github_json(f"repos/{LLAMA_UPSTREAM}/commits?sha=master&per_page=1", fetcher)
        if not commits:
            raise FetchError(f"github commits {LLAMA_UPSTREAM}", "empty commit list")
        upstream["head"] = commits[0]["sha"]
        upstream["date"] = commits[0]["commit"]["committer"]["date"]
        release, _ = github_json(f"repos/{LLAMA_UPSTREAM}/releases/latest", fetcher)
        upstream["latest_release"] = release.get("tag_name") or ""
    except FetchError as exc:
        upstream["head"] = ""
        rows.append(_row(MODEL_UNRESOLVABLE, "llama_cpp", "upstream", "head", "",
                         reason=f"upstream head unresolvable: {exc.reason}"))

    resolved = []
    for entry in refs:
        record = dict(entry)
        if not entry["ref"]:
            record["status"] = BUILD_INPUT_FLOATING
            record["behind_by"] = None
            rows.append(_row(BUILD_INPUT_FLOATING, "llama_cpp", entry["source"],
                             entry["field"], "",
                             reason="no ref default: the caller must pin at build time"))
            resolved.append(record)
            continue
        try:
            own, cached_at, own_base = github_compare(entry["repo"], entry["ref"], fetcher)
            record["branch"] = own_base.rsplit("@", 1)[-1]
            record["branch_behind_by"] = own.get("behind_by")
            record["cached_at"] = cached_at
            if entry["repo"] != LLAMA_UPSTREAM:
                up_cmp, _at, _base = github_compare(
                    entry["repo"], entry["ref"], fetcher, upstream=LLAMA_UPSTREAM_OWNER)
                record["behind_by"] = up_cmp.get("behind_by")
                record["ahead_by"] = up_cmp.get("ahead_by")
            else:
                record["behind_by"] = record["branch_behind_by"]
                record["ahead_by"] = own.get("ahead_by")
            record["status"] = (BUILD_INPUT_STALE
                                if (record["branch_behind_by"] or 0) > 0
                                else PIN_CURRENT)
            if record["status"] == BUILD_INPUT_STALE:
                rows.append(_row(BUILD_INPUT_STALE, "llama_cpp", entry["source"],
                                 entry["field"], entry["ref"], observed=own_base,
                                 reason=f"{record['branch_behind_by']} commit(s) behind "
                                        f"{own_base}",
                                 cached_at=cached_at,
                                 behind_by=record["behind_by"]))
        except FetchError as exc:
            record["status"] = BUILD_INPUT_UNRESOLVABLE
            record["behind_by"] = None
            record["branch_behind_by"] = None
            rows.append(_row(BUILD_INPUT_UNRESOLVABLE, "llama_cpp", entry["source"],
                             entry["field"], entry["ref"], reason=exc.reason))
        resolved.append(record)
    refs = resolved

    supports, support_notes = {}, {}
    for feature, path, needle in LLAMA_FEATURES:
        if not upstream.get("head"):
            supports[feature] = None
            support_notes[feature] = "upstream head unknown"
            continue
        try:
            text = github_file(LLAMA_UPSTREAM, upstream["head"], path, fetcher)
        except FetchError as exc:
            supports[feature] = None
            support_notes[feature] = f"unresolvable: {exc.reason}"
            rows.append(_row(MODEL_UNRESOLVABLE, "llama_cpp", LLAMA_UPSTREAM, path,
                             upstream["head"], reason=f"feature probe failed: {exc.reason}"))
            continue
        if text is None:
            supports[feature] = False
            support_notes[feature] = f"{path} absent at HEAD"
        elif needle is None:
            supports[feature] = True
            support_notes[feature] = path
        else:
            found = needle in text
            supports[feature] = found
            support_notes[feature] = f"{needle!r} {'found' if found else 'absent'} in {path}"

    for image in images:
        try:
            info = parse_container_ref(image["ref"])
            if info["host"] == "docker.io":
                newest = hub_newest_tag(info["repo"], fetcher)
                image["publisher_latest_tag"] = newest["name"]
                image["publisher_latest_at"] = newest["last_updated"]
        except FetchError as exc:
            image["publisher_latest_tag"] = ""
            image["publisher_error"] = exc.reason

    return {
        "upstream": upstream,
        "refs": refs,
        "images": images,
        "upstream_supports": supports,
        "upstream_supports_notes": support_notes,
        "rows": rows,
    }


# ------------------------------------------------------------------- output


def _fmt_ts(value):
    return (value or "").replace("Z", "").replace("T", " ")[:16]


def summary(report, exit_code=None):
    totals = report["totals"]
    lines = [
        f"refresh sweep — {totals['recipes']} recipes, {totals['model_pins']} model pins, "
        f"{totals['container_pins']} container pins, {totals['build_inputs']} build inputs",
        "",
    ]
    counts = report["counts"]
    if counts:
        width = max(len(c) for c in counts)
        lines += [f"  {cls.ljust(width)}  {counts[cls]}" for cls in CLASSES if cls in counts]
    else:
        lines.append("  (nothing classified)")
    drift = [r for r in report["rows"] if r["class"] in DRIFT_CLASSES]
    unresolvable = [r for r in drift if r["class"].endswith("-unresolvable")]
    lines += ["", f"drift: {len(drift)} row(s); unresolvable: {len(unresolvable)}"]
    for row in drift:
        lines.append(f"  {row['class']:<22} {row['path']}:{row['field']}  "
                     f"{row['pinned'] or '-'} -> {row['observed'] or '-'}  {row['reason']}")
    if report["warnings"]:
        lines += ["", "warnings:"] + [f"  {w}" for w in report["warnings"]]

    llama = report["llama_cpp"]
    lines += ["", "llama.cpp"]
    up = llama["upstream"]
    lines.append(f"  upstream {up['repo']}@{up['branch']}: {up.get('head') or '?'} "
                 f"({_fmt_ts(up.get('date'))}), latest release {up.get('latest_release') or '?'}")
    for ref in llama["refs"]:
        lines.append(f"  {ref['source']}: {ref['repo']}@{ref['ref'] or '<none>'} — "
                     f"{ref['status']}, behind_by {ref.get('behind_by')}")
    lines.append("  upstream supports: " + ", ".join(
        f"{k}={'yes' if v else ('no' if v is False else '?')}"
        for k, v in llama["upstream_supports"].items()))
    for image in llama["images"]:
        lines.append(f"  image {image['path']}: {image['tag'] or '-'} "
                     f"(publisher newest {image.get('publisher_latest_tag') or '?'} "
                     f"{_fmt_ts(image.get('publisher_latest_at'))})")
    if exit_code is not None:
        lines += ["", f"exit {exit_code}"]
    return "\n".join(lines)


def markdown(report, exit_code=None):
    totals = report["totals"]
    drift = [r for r in report["rows"] if r["class"] in DRIFT_CLASSES]
    out = [f"# Pin refresh sweep — {_iso()}", "",
           f"{totals['recipes']} recipes, {totals['model_pins']} model pins, "
           f"{totals['container_pins']} container pins, {totals['build_inputs']} build inputs; "
           f"**{len(drift)} drift row(s)**"
           + (f", exit {exit_code}" if exit_code is not None else "") + ".", ""]
    if drift:
        out += ["| class | arm | field | pinned | observed | reason |", "|---|---|---|---|---|---|"]
        for row in drift:
            out.append(f"| `{row['class']}` | `{row['path']}` | `{row['field']}` | "
                       f"`{row['pinned'] or '-'}` | `{row['observed'] or '-'}` | "
                       f"{row['reason'].replace('|', '/')} |")
        out.append("")
    else:
        out += ["No drift class present.", ""]

    llama = report["llama_cpp"]
    up = llama["upstream"]
    out += ["## llama.cpp", "",
            f"Upstream `{up['repo']}@{up['branch']}` head `{up.get('head') or '?'}` "
            f"({up.get('date') or '?'}), latest release `{up.get('latest_release') or '?'}`.", "",
            "| need | upstream supports | evidence |", "|---|---|---|"]
    for feature, supported in llama["upstream_supports"].items():
        mark = "**yes**" if supported else ("no" if supported is False else "unknown")
        out.append(f"| `{feature}` | {mark} | {llama['upstream_supports_notes'].get(feature, '')} |")
    if llama["refs"] or llama["images"]:
        out += ["", "| source | repo | ref | status | behind_by |", "|---|---|---|---|---|"]
        for ref in llama["refs"]:
            out.append(f"| `{ref['source']}` | `{ref['repo']}` | `{ref['ref'] or '-'}` | "
                       f"{ref['status']} | {ref.get('behind_by')} |")
        for image in llama["images"]:
            out.append(f"| `{image['path']}` | `{image['repo']}` | `{image['tag'] or image['digest']}` | "
                       f"image pin (publisher newest `{image.get('publisher_latest_tag') or '?'}` "
                       f"{_fmt_ts(image.get('publisher_latest_at'))}) | - |")
    if report["warnings"]:
        out += ["", "## warnings", ""] + [f"- {w}" for w in report["warnings"]]
    return "\n".join(out) + "\n"


# -------------------------------------------------------------------- apply


def rewrite_ref(ref, tag, digest):
    """The same image ref with `tag@digest` replaced, keeping any host prefix."""
    body = ref.split("@", 1)[0]
    if body.endswith(f":{tag}"):
        body = body[: -(len(tag) + 1)]
    return f"{body}:{tag}@{digest}"


def apply_container_bumps(report, root):
    """Rewrite only `container:` lines classified container-newer-release.

    The dirty-worktree refusal lives in `run()`, before any registry call, so an
    `--apply` run can never mix a bump with someone else's in-flight edit.
    """
    appliable = [r for r in report["rows"]
                 if r["class"] == CONTAINER_NEWER_RELEASE and r.get("appliable")]
    skipped = [r for r in report["rows"]
               if r["class"] == CONTAINER_NEWER_RELEASE and not r.get("appliable")]
    applied, stamp = [], time.strftime("%Y%m%d")
    for row in appliable:
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        new_ref = rewrite_ref(row["pinned"], row["new_tag"], row["new_digest"])
        pattern = re.compile(r"^(container:[ \t]*)(\S+)(.*)$", re.MULTILINE)
        match = pattern.search(text)
        if not match or match.group(2) != row["pinned"]:
            raise SweepError(f"{row['path']}: container: line does not match the surveyed "
                             f"ref {row['pinned']!r} — refusing to guess")
        updated = text[:match.start(2)] + new_ref + text[match.end(2):]
        path.write_text(updated, encoding="utf-8")
        applied.append({"path": row["path"], "old": row["pinned"], "new": new_ref,
                        "boot": f"sparkrun run {row['path']} -H <node>",
                        "receipt": f"~/benchmarks/bump-{stamp}/{Path(row['path']).stem}/RECEIPT.md"})

    if applied:
        print(f"applied {len(applied)} container bump(s):")
        for item in applied:
            print(f"  {item['path']}\n    - {item['old']}\n    + {item['new']}")
            print(f"    boot: {item['boot']}")
            print(f"    receipt: {item['receipt']}")
            print("      needs: TTR to port-open, GET /v1/models, one smoke completion, "
                  "then the arm's own ladder/battery before the pin is claimed")
    else:
        print("applied 0 container bumps")
    if skipped:
        print(f"skipped {len(skipped)} newer-release row(s) with no resolved digest target:")
        for row in skipped:
            print(f"  {row['path']}: {row['pinned']} — {row['reason']}")
    return applied


# ---------------------------------------------------------------- entrypoint


def build_parser():
    parser = argparse.ArgumentParser(
        description="Survey recipe/model/container/build pins for staleness.")
    parser.add_argument("--json", metavar="PATH", help="write the full report as JSON")
    parser.add_argument("--markdown", metavar="PATH", help="write a markdown report")
    parser.add_argument("--exit-code", action="store_true",
                        help="0 no drift, 1 drift, 2 could not run")
    parser.add_argument("--only", metavar="CLASS[,CLASS...]",
                        help="report (and gate on) only these classes")
    parser.add_argument("--lane", metavar="LANE", help="restrict recipes to recipes/<LANE>/")
    parser.add_argument("--recipe", metavar="PATH", help="restrict to one recipe file")
    parser.add_argument("--apply", action="store_true",
                        help="rewrite container-newer-release lines (refuses a dirty tree)")
    parser.add_argument("--token-env", default="HF_TOKEN", metavar="NAME",
                        help="env var holding the HF token (default: HF_TOKEN)")
    parser.add_argument("--timeout", type=float, default=30, metavar="SECONDS",
                        help="per-request timeout (default: 30)")
    parser.add_argument("--cache", metavar="PATH",
                        help="JSON cache of registry responses (stale entries are refetched)")
    return parser


def run(argv, fetch=None, root=None):
    """Returns (exit code, report).  Raises SweepError for anything unrunable."""
    args = build_parser().parse_args(argv)
    only = None
    if args.only:
        only = [c.strip() for c in args.only.split(",") if c.strip()]
        unknown = [c for c in only if c not in CLASSES]
        if unknown:
            raise SweepError(f"--only: unknown class(es) {', '.join(unknown)}; "
                             f"known: {', '.join(CLASSES)}")
    repo = repo_root(root)

    if args.apply:
        status = _git(repo, "status", "--porcelain")
        if status.returncode != 0:
            raise SweepError(f"git status failed in {repo}: {status.stderr.strip()}")
        dirty = [line for line in status.stdout.splitlines() if line.strip()]
        if dirty:
            raise SweepError("--apply refuses to run on a dirty worktree:\n  "
                             + "\n  ".join(dirty[:20]))

    fetcher = Fetcher(timeout=args.timeout, cache_path=args.cache,
                      token=_hf_token(args.token_env), fetch=fetch)
    try:
        report = sweep(repo, fetcher, only_recipe=args.recipe, lane=args.lane)
        report["generated_at"] = _iso()
        report["root"] = str(repo)
        if only:
            report["rows"] = [r for r in report["rows"] if r["class"] in only]
            report["counts"] = {}
            for row in report["rows"]:
                report["counts"][row["class"]] = report["counts"].get(row["class"], 0) + 1
            report["only"] = only

        drift = [r for r in report["rows"] if r["class"] in DRIFT_CLASSES]
        unresolvable = [r for r in drift if r["class"].endswith("-unresolvable")]
        code = 0
        if unresolvable:
            code = 2
        elif drift and args.exit_code:
            code = 1
        report["exit_code"] = code

        if args.apply:
            applied = apply_container_bumps(report, repo)
            report["applied"] = applied
        print(summary(report, code if (args.exit_code or code) else None))
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=False))
        if args.markdown:
            Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
            Path(args.markdown).write_text(markdown(report, code if (args.exit_code or code) else None))
        return code, report
    finally:
        try:
            fetcher.save()
        except OSError as exc:
            print(f"warning: could not write --cache {args.cache}: {exc}", file=sys.stderr)


def main(argv=None):
    try:
        code, _report = run(sys.argv[1:] if argv is None else argv)
    except (SweepError, FetchError) as exc:
        print(f"refresh-sweep: {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
