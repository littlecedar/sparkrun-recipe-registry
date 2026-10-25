#!/usr/bin/env python3
"""Enable the three io_uring syscalls for every container on one Docker node.

Why this exists.  The vLLM b12x parity route (`mad-science/DEEPSEEK.md` §17) puts the Engram table
on disk, and the fork's `DiskTable` uses io_uring — `io_uring_setup` (425), `io_uring_enter` (426),
`io_uring_register` (427).  Docker's built-in seccomp profile is an **allowlist**
(`defaultAction: SCMP_ACT_ERRNO`, `defaultErrnoRet: 1`) and those three names are not on it, so the
call returns `EPERM` inside any ordinary container (measured on this fleet 2026-10-26: `ret=-1
errno=1`, host `kernel.io_uring_disabled=0` — the denial is seccomp, not the kernel).  sparkrun's
`executor_config` cannot express a seccomp profile, so the only place the grants can live is the
daemon: `seccomp-profile` in `/etc/docker/daemon.json`.

What it does, per node, and in this order (every step fails closed):

1. Probe: run a `--rm` container that calls all three syscalls and report the result.  This is the
   before/after evidence and, with `--probe-only`, the whole job.
2. Idempotence: if `daemon.json` already names a profile that allows all three **and** the probe
   passes, print `already enabled` and change nothing.
3. Refuse to restart Docker while any container is running: a restart kills them (`live-restore`
   is off on this fleet).  The node is skipped, not forced.
4. Base profile: a bundled/copied `default.json` if one exists locally, else the exact engine
   version's vendored copy from moby (`v<server version>`), else the newest released moby tag's
   copy.  The source URL and sha256 are printed either way.
5. Modify **only** the three io_uring syscalls into one appended `SCMP_ACT_ALLOW` block; assert
   structurally that nothing else moved (same action/archMap/deny blocks, allow names = base + 3).
6. Pre-flight the profile against the *running* daemon with `--security-opt seccomp=<file>`: a
   container must run and the probe must pass before `daemon.json` is touched at all.
7. Back up `daemon.json`, merge `seccomp-profile` into it (never clobbering other keys), validate it
   with `dockerd --validate`, restart `docker`, then re-probe (that container is also the
   post-restart hello check).
8. On any failure after the restart starts, restore the backup, restart Docker again, and exit
   non-zero — a node is never left with Docker down.

Rollback by hand: restore the printed backup over `/etc/docker/daemon.json` and restart Docker.

Runs as root on the target node; the orchestrator is `tools/enable-io-uring.sh`.  Stdlib only.

    sudo python3 tools/enable-io-uring.py --probe-only      # inspect, change nothing
    sudo python3 tools/enable-io-uring.py                   # apply
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

#: The three syscalls the b12x Engram disk table needs, with their numbers on x86-64/arm64.
IO_URING_SYSCALLS = ("io_uring_setup", "io_uring_enter", "io_uring_register")

PROFILE_PATH = Path("/etc/docker/seccomp-profiles/io-uring.json")
DAEMON_JSON = Path("/etc/docker/daemon.json")
DEFAULT_PROBE_IMAGE = "python:3.12-slim"
PROFILE_COMMENT = "io_uring for the vLLM b12x Engram disk table; added by tools/enable-io-uring.py"

#: Where a distro/engine build may ship the profile it embeds, and the moby-tree paths that carry it.
LOCAL_PROFILE_GLOBS = (
    "/usr/share/docker/seccomp/default.json",
    "/usr/share/docker/seccomp-profiles/default.json",
    "/usr/libexec/docker/seccomp/default.json",
    "/usr/lib/docker/seccomp/default.json",
    "/usr/share/containerd/seccomp/default.json",
)
MOBY_PROFILE_PATHS = (
    "vendor/github.com/moby/profiles/seccomp/default.json",
    "profiles/seccomp/default.json",
)
MOBY_RAW = "https://raw.githubusercontent.com/moby/moby/{ref}/{path}"
MOBY_TAGS = "https://api.github.com/repos/moby/moby/tags?per_page=100"

#: Runs inside the container: syscall 425 with a legal 120-byte params struct, then 426/427 on the
#: ring it returns.  Anything but EPERM counts as allowed — an unblocked syscall may still reject
#: its arguments, and that rejection is the proof that seccomp let it through.
PROBE_CODE = """
import ctypes, os, sys
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
params = ctypes.create_string_buffer(120)
ctypes.set_errno(0)
fd = libc.syscall(425, 8, ctypes.byref(params))
err = ctypes.get_errno()
if fd < 0:
    print("io_uring_setup(425): ret=-1 errno=%d (%s)" % (err, os.strerror(err)))
    try:
        print("kernel.io_uring_disabled=" + open("/proc/sys/kernel/io_uring_disabled").read().strip())
    except OSError:
        pass
    sys.exit(1)
print("io_uring_setup(425): fd=%d allowed" % fd)
rc = 0
for nr, args, name in ((426, (fd, 0, 0, 0, 0, 0), "io_uring_enter"), (427, (fd, 0, 0, 0), "io_uring_register")):
    ctypes.set_errno(0)
    r = libc.syscall(nr, *args)
    e = ctypes.get_errno()
    if r < 0 and e == 1:
        print("%s(%d): ret=-1 errno=1 (Operation not permitted)" % (name, nr))
        rc = 1
    else:
        print("%s(%d): seccomp allowed (ret=%d errno=%d)" % (name, nr, r, e))
os.close(fd)
sys.exit(rc)
"""


# --------------------------------------------------------------------------- pure helpers (guarded)

def allow_names(profile: dict) -> set[str]:
    """Syscall names the profile grants, i.e. the names in its ``SCMP_ACT_ALLOW`` blocks."""
    return {
        name
        for block in profile.get("syscalls", [])
        if block.get("action") == "SCMP_ACT_ALLOW"
        for name in block.get("names", [])
    }


def profile_has_io_uring(profile: dict) -> bool:
    return set(IO_URING_SYSCALLS) <= allow_names(profile)


def add_io_uring_allows(profile: dict) -> dict:
    """Return a copy of ``profile`` with one appended allow block for the three io_uring syscalls.

    The default profile is an allowlist, so a grant is an addition, not a rewrite: nothing that is
    already in the profile is touched.  A profile that *denies* io_uring explicitly is refused —
    rule order between an allow block and a deny block naming the same syscall is not something to
    guess at.
    """
    if profile_has_io_uring(profile):
        return copy.deepcopy(profile)
    for block in profile.get("syscalls", []):
        if block.get("action") != "SCMP_ACT_ALLOW" and set(block.get("names", [])) & set(IO_URING_SYSCALLS):
            raise ValueError(
                f"base profile carries a non-allow rule for {sorted(set(block.get('names', [])) & set(IO_URING_SYSCALLS))}; "
                "refusing to add an allow that rule order might undo"
            )
    out = copy.deepcopy(profile)
    out.setdefault("syscalls", []).append(
        {"names": list(IO_URING_SYSCALLS), "action": "SCMP_ACT_ALLOW", "comment": PROFILE_COMMENT}
    )
    return out


def validate_modified_profile(base: dict, modified: dict) -> None:
    """Raise ``ValueError`` unless ``modified`` differs from ``base`` in exactly the three grants.

    This is the guard that keeps a whole-fleet seccomp replacement honest: the profile reaches
    every container on the node, so an accidental extra grant or a dropped rule is a security
    change nobody reviewed.
    """
    for key in ("defaultAction", "defaultErrnoRet", "archMap"):
        if base.get(key) != modified.get(key):
            raise ValueError(f"{key} changed: {base.get(key)!r} -> {modified.get(key)!r}")
    if set(base) != set(modified):
        raise ValueError(f"top-level keys changed: {sorted(set(modified) ^ set(base))}")
    gained = allow_names(modified) - allow_names(base)
    lost = allow_names(base) - allow_names(modified)
    if gained != set(IO_URING_SYSCALLS) or lost:
        raise ValueError(f"allow set drift: gained {sorted(gained)}, lost {sorted(lost)}")
    base_other = [b for b in base.get("syscalls", []) if b.get("action") != "SCMP_ACT_ALLOW"]
    mod_other = [b for b in modified.get("syscalls", []) if b.get("action") != "SCMP_ACT_ALLOW"]
    if base_other != mod_other:
        raise ValueError("a non-allow (deny) rule changed")
    if len(modified.get("syscalls", [])) != len(base.get("syscalls", [])) + (
        0 if profile_has_io_uring(base) else 1
    ):
        raise ValueError("unexpected number of syscall blocks")


def parse_container_ids(ps_output: str) -> list[str]:
    return [line.strip() for line in ps_output.splitlines() if line.strip()]


def require_idle(ids: list[str], node: str) -> None:
    """Fail closed: a Docker restart stops every container on the node (live-restore is off here)."""
    if ids:
        raise SystemExit(
            f"[{node}] abort: {len(ids)} container(s) running ({' '.join(i[:12] for i in ids)}); "
            "a daemon restart would stop them — refusing"
        )


def merge_daemon_json(existing: dict, profile_path: str) -> dict:
    """Set ``seccomp-profile`` and keep every other key the daemon config already had."""
    merged = dict(existing)
    merged["seccomp-profile"] = profile_path
    return merged


def newest_moby_tag(tags_payload) -> str | None:
    """First stable ``vX.Y.Z`` tag in a GitHub tags listing (newest first)."""
    entries = tags_payload if isinstance(tags_payload, list) else tags_payload.get("tags", [])
    for entry in entries:
        name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
        if re.fullmatch(r"v\d+\.\d+\.\d+", name):
            return name
    return None


# --------------------------------------------------------------------------------- node plumbing

def run(cmd: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def docker(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return run(["docker", *args], timeout=timeout)


def docker_server_version() -> str:
    out = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=60)
    if out.returncode != 0:
        raise SystemExit(f"docker daemon unreachable: {out.stderr.strip()}")
    return out.stdout.strip()


def ensure_probe_image(image: str) -> None:
    if run(["docker", "image", "inspect", image], timeout=120).returncode == 0:
        return
    print(f"  pulling probe image {image}")
    out = run(["docker", "pull", image], timeout=900)
    if out.returncode != 0:
        raise SystemExit(f"cannot pull probe image {image}: {out.stderr.strip()[:300]}")


def probe(image: str, seccomp_path: Path | None = None) -> tuple[bool, str]:
    """Run the syscall probe in a ``--rm`` container; the only container the node ever sees here."""
    cmd = ["docker", "run", "--rm", "--entrypoint", "python3"]
    if seccomp_path is not None:
        cmd += ["--security-opt", f"seccomp={seccomp_path}"]
    cmd += [image, "-c", PROBE_CODE]
    out = run(cmd, timeout=300)
    text = (out.stdout + out.stderr).strip()
    return out.returncode == 0, text


def wait_for_daemon(seconds: int = 120) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if docker("info", "--format", "{{.ServerVersion}}", timeout=30).returncode == 0:
            return True
        time.sleep(2)
    return False


def _http_get(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "enable-io-uring/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # GitHub hosts only
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None


def local_profile_source() -> Path | None:
    for pattern in LOCAL_PROFILE_GLOBS:
        if Path(pattern).is_file():
            return Path(pattern)
    return None


def fetch_profile(version: str) -> tuple[str, str]:
    """The engine's own default profile: exact version first, newest released moby tag second."""
    for ref in (f"v{version}", None):
        if ref is None:
            payload = _http_get(MOBY_TAGS)
            if payload is None:
                break
            try:
                ref = newest_moby_tag(json.loads(payload))
            except json.JSONDecodeError:
                ref = None
            if ref is None:
                break
        for path in MOBY_PROFILE_PATHS:
            url = MOBY_RAW.format(ref=ref, path=path)
            text = _http_get(url)
            if text is not None:
                return text, url
    raise SystemExit(f"no default seccomp profile available for engine {version} (bundled: none, moby: none)")


def base_profile_text(version: str, override: Path | None) -> tuple[str, str]:
    if override is not None:
        if not override.is_file():
            raise SystemExit(f"--profile-source {override} is not a file")
        return override.read_text(), f"file:{override}"
    local = local_profile_source()
    if local is not None:
        return local.read_text(), f"file:{local}"
    return fetch_profile(version)


# ------------------------------------------------------------------------------------ node logic

def report(node: str, status: str, detail: str = "") -> None:
    print(f"RESULT {node} {status} {detail}".rstrip(), flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--node", default=socket.gethostname(), help="label for the output (defaults to hostname)")
    ap.add_argument("--probe-only", action="store_true", help="report the probe result and change nothing")
    ap.add_argument("--probe-image", default=DEFAULT_PROBE_IMAGE, help=f"container image for the probe (default {DEFAULT_PROBE_IMAGE})")
    ap.add_argument("--profile-source", type=Path, default=None, help="use this default.json as the base profile")
    args = ap.parse_args(argv)
    node = args.node

    version = docker_server_version()
    ensure_probe_image(args.probe_image)
    print(f"[{node}] docker server {version}, probe image {args.probe_image}", flush=True)

    allowed, detail = probe(args.probe_image)
    before = "ALLOWED" if allowed else "DENIED"
    print(f"[{node}] before: io_uring {before}: {detail.splitlines()[0] if detail else 'no output'}", flush=True)

    if args.probe_only:
        report(node, "probe-allowed" if allowed else "probe-denied", before.lower())
        return 0 if allowed else 1

    # Already enabled: the daemon points at a profile that grants all three and the probe passes.
    configured = ""
    try:
        existing_cfg = json.loads(DAEMON_JSON.read_text()) if DAEMON_JSON.is_file() else {}
        configured = existing_cfg.get("seccomp-profile", "") if isinstance(existing_cfg, dict) else ""
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[{node}] abort: {DAEMON_JSON} is not valid JSON ({exc})")
    if configured and allowed and Path(configured).is_file():
        try:
            if profile_has_io_uring(json.loads(Path(configured).read_text())):
                print(f"[{node}] daemon.json seccomp-profile={configured} already grants io_uring; nothing to do", flush=True)
                report(node, "already-enabled", configured)
                return 0
        except json.JSONDecodeError:
            print(f"[{node}] {configured} is not valid JSON; replacing it", flush=True)

    if os.geteuid() != 0:
        raise SystemExit(f"[{node}] abort: applying changes needs root (run via sudo)")
    running = parse_container_ids(docker("ps", "-q", timeout=60).stdout)
    try:
        require_idle(running, node)
    except SystemExit as exc:
        print(exc, flush=True)
        report(node, "aborted-containers", f"{len(running)} running; nothing changed")
        return 3

    # 1. base profile + the three grants, structurally checked
    text, source = base_profile_text(version, args.profile_source)
    base = json.loads(text)
    modified = add_io_uring_allows(base)
    validate_modified_profile(base, modified)
    print(f"[{node}] base profile {source} sha256={hashlib.sha256(text.encode()).hexdigest()}", flush=True)

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_profile = PROFILE_PATH.with_suffix(".json.tmp")
    tmp_profile.write_text(json.dumps(modified, indent=2) + "\n")
    os.chmod(tmp_profile, 0o644)
    os.replace(tmp_profile, PROFILE_PATH)
    print(f"[{node}] wrote {PROFILE_PATH} (base + {len(IO_URING_SYSCALLS)} grants, nothing else changed)", flush=True)

    # 2. pre-flight against the *running* daemon: the profile must load and the probe must pass
    ok, detail = probe(args.probe_image, seccomp_path=PROFILE_PATH)
    if not ok:
        print(f"[{node}] pre-flight FAILED under {PROFILE_PATH}:\n{detail}", flush=True)
        report(node, "failed", "profile pre-flight denied the probe; daemon.json untouched")
        return 1
    print(f"[{node}] pre-flight OK under the new profile (daemon.json untouched so far)", flush=True)

    # 3. backup + merge + validate + restart
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(str(DAEMON_JSON) + f".bak-pre-io-uring-{stamp}")
    original = DAEMON_JSON.read_bytes() if DAEMON_JSON.is_file() else None
    if original is None:
        print(f"[{node}] {DAEMON_JSON} absent; creating it", flush=True)
    else:
        backup.write_bytes(original)
        print(f"[{node}] backed up {DAEMON_JSON} -> {backup}", flush=True)
    cfg = json.loads(original) if original else {}
    merged = merge_daemon_json(cfg, str(PROFILE_PATH))
    DAEMON_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp_cfg = DAEMON_JSON.with_suffix(".json.tmp")
    tmp_cfg.write_text(json.dumps(merged, indent=2) + "\n")
    os.chmod(tmp_cfg, 0o644)
    os.replace(tmp_cfg, DAEMON_JSON)

    valid = run(["dockerd", "--validate", "--config-file", str(DAEMON_JSON)], timeout=120)
    if valid.returncode != 0:
        restore(node, original, backup)
        print(f"[{node}] dockerd --validate rejected the merged config: {(valid.stdout + valid.stderr).strip()[:300]}", flush=True)
        report(node, "failed", "daemon.json rejected by dockerd --validate; backup restored")
        return 1

    restart = run(["systemctl", "restart", "docker.service"], timeout=300)
    if restart.returncode != 0 or not wait_for_daemon():
        restore(node, original, backup)
        print(f"[{node}] docker did not come back after the restart ({(restart.stdout + restart.stderr).strip()[:200]})", flush=True)
        report(node, "failed", "daemon did not restart; backup restored and docker restarted again")
        return 1

    ok, detail = probe(args.probe_image)
    after = "ALLOWED" if ok else "DENIED"
    sec = docker("info", "--format", "{{json .SecurityOptions}}", timeout=60).stdout.strip()
    print(f"[{node}] after: io_uring {after}: {detail}", flush=True)
    print(f"[{node}] docker info security options: {sec}", flush=True)
    if not ok:
        restore(node, original, backup)
        report(node, "failed", "probe still denied after restart; backup restored")
        return 1
    report(node, "enabled", f"before=denied after=allowed profile={PROFILE_PATH} backup={backup if original else 'none'}")
    return 0


def restore(node: str, original: bytes | None, backup: Path) -> None:
    """Put the previous daemon.json back and bring Docker up — a node is never left with no daemon."""
    if original is None:
        DAEMON_JSON.unlink(missing_ok=True)
    else:
        DAEMON_JSON.write_bytes(original)
    run(["systemctl", "restart", "docker.service"], timeout=300)
    wait_for_daemon()
    print(f"[{node}] rollback: daemon.json restored ({'from ' + str(backup) if original else 'removed'}) and docker restarted", flush=True)


if __name__ == "__main__":
    sys.exit(main())
