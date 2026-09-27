# mod: `drop-caches`

Drop the **host** kernel page cache from a privileged sparkrun mod — and refuse to
pretend when it cannot.

## Why this exists

Many recipes in this registry list `@eugr/mods/drop-caches` (qwen4, ds4, qwen3,
ornith). That mod is **inert**: its loop process starts and stays alive, so it
reads as success, but the cache is never dropped. Two independent reasons, both
reproduced 2026-09-27 (Docker 29.8.1, Linux 7.2.8, the same host the recipes run on):

1. **Rootless blocks the write.** sparkrun defaults `rootless=True`
   (`core/launcher.py:837`), and `DockerExecutor.apply_runtime_adjustments` then sets
   `privileged: false` + `no-new-privileges` (`orchestration/executors/docker.py:311-313`).
   Docker mounts `/proc/sys` **`ro`**, so `echo 3 > /proc/sys/vm/drop_caches` returns
   `Read-only file system`.
2. **Its command has a redirection-order bug.** eugr's line is
   `echo 3 > /proc/sys/vm/drop_caches >> /tmp/drop_caches.log 2>&1`. Bash applies
   redirects left-to-right and the **last stdout redirect wins**, so `3` is written to
   the *log* and `drop_caches` gets nothing. Reproduced with a stand-in target:
   `target 0 bytes, log "3"`.

This mod fixes both: one redirect to the target, and a **fail-closed** gate.

## What it does

1. Reads `Cached:` from `/proc/meminfo` (un-namespaced, so it is the host's number).
2. `sync`, then writes `MOD_DROP_CACHES_LEVEL` (default `3`) to
   `/proc/sys/vm/drop_caches` — exactly once, with a single stdout redirect.
3. Re-reads `Cached:` and logs before → after.
4. **If the write fails, it `die`s** (exit 1). A cache drop that did not happen must
   not look like success — that is the entire failure mode this mod exists to avoid.

### The mechanism (why a privileged mod can drop the host cache)

`/proc/sys` is **not namespaced**. A write from inside a `--privileged` container
reaches the host kernel's `drop_caches`. VERIFIED on this host:

| container | `/proc/sys` | write | observed host `Cached:` |
|---|---|---|---|
| default (unprivileged) | mounted `ro` | `Read-only file system` | unchanged |
| `--privileged` | writable | rc 0 | **17.93 GB → 3.16 GB** |

So the drop is a **whole-node** effect, not per-container. On a shared cluster it
evicts every tenant's page cache — see the warning below.

### Requirement: a trusted, rootful launch

`privileged` is **trust-gated** (`core/launcher.py:_TRUST_GATED_EXECUTOR_KEYS`): an
untrusted recipe cannot set it. To actually drop the cache, launch rootful:

```bash
sparkrun run <recipe> --rootful          # or: -o privileged=true
```

`--rootful` is a hidden flag (`cli/_run.py:271`); a recipe's `executor_config:
{privileged: true}` works too, but only for a trusted recipe. Under the default
rootless launch this mod will (correctly) fail the launch.

## Usage

```yaml
mods:
  - "@littlecedar/mods/drop-caches"       # scoped form, once committed
defaults:
  privileged: true                        # rootful launch, trusted recipe only
```

While iterating on the cluster, the bare form `mods/drop-caches` resolves against
`${WOPR_SRC_DIR}/mods` without a commit.

## Knobs

| Env | Default | Meaning |
|---|---|---|
| `MOD_DROP_CACHES_MODE` | `once` | `once` (single drop at launch) or `loop` (periodic, eugr parity) |
| `MOD_DROP_CACHES_INTERVAL` | `60` | seconds between drops in `loop` mode |
| `MOD_DROP_CACHES_LEVEL` | `3` | value written to `drop_caches` (`1` page, `2` dentries+inodes, `3` both) |
| `MOD_DROP_CACHES_TARGET` | `/proc/sys/vm/drop_caches` | override the drop path; **test hook** |

`loop` mode keeps dropping for the life of the container. Prefer `once` unless a long
weight load genuinely needs repeated drops.

## Verification

The write is proven at the point of use, not inferred from a live process:

- the write's exit status is checked and the mod `die`s on non-zero;
- the host `Cached:` figure is printed before and after;
- `tests/test_drop_caches_mod.py` executes the mod against a **stand-in target file**
  (via `MOD_DROP_CACHES_TARGET`) to prove both directions: a writable target yields
  `3` and rc 0; an unwritable one yields rc 1 and no silent success. The stand-in is
  necessary because the test host is a non-root laptop where the real
  `/proc/sys/vm/drop_caches` is root-only — but the code path under test (single
  redirect, last-redirect-wins, fail-closed) is identical.

## Warning

Dropping the page cache frees memory but **discards warm filesystem cache** for the
whole node — other workloads on that node re-read from disk and can slow down. This
is a node-wide action issued from one container. Use it deliberately.
