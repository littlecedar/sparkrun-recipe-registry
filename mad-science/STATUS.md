# Board
_Generated 2026-11-22 22:07 ET_

## In flight
| where | owner | what |
|---|---|---|
| census | read-only in tick — booted nothing, claimed nothing, stopped nothing, evicted nothing | read `2026-11-23T03:07:46Z`–`2026-11-23T03:07:48Z` (each node's own `date -u`) on the base census `2026-11-23T02:43:06Z`, **0 h 24 min 40 s** after it: **4 containers, 0 volumes** fleet-wide; **no research rank**; the fenced hosts hold running containers on `.31`, `.32`, `.33`, `.34`, excluded from research accounting; `/v1/models` **200**, `/health` **200** on `.31` |
| pool | — (nobody drives it; head units re-proved each tick) | head: `beegfs-mgmtd` **active** (Result success, NRestarts 0, **+0** on the base) · `beegfs-meta` **active** (Result success, NRestarts 0, **+0** on the base) · `beegfs-storage` **active** (Result success, NRestarts 0, **+0** on the base); worker unit states and the pool's through-mount reads are not part of this census |
| queue | register snapshot `892c492b…`; both blocks below rendered from it | `origin/main:mad-science/queue.json` sha256 **`892c492b7bfc77a4210ab99e56fe9eb954ad32354956b6b22341ff5361759333`** read locally: **253 tasks: 244 done, 1 queued, 7 blocked, 0 running, 1 ask — 9 open**; the head clone reads **`cf531900…`**, **differs** |
| window | **no manual lock** at this read | `.local/fleet-window.lock` is **absent** on the head (read `2026-11-23T03:07:49Z`) |
| campaign | `sparkrun-campaign` — active, no lease | head user unit `sparkrun-campaign` reads **`active`** / **`running`** (`MainPID` **3,930,275**, `NRestarts` **0**, **+0** on the base); the lease ledger holds **0 lease(s)** and fence(s) `tp-le2-20261120` |
| lease | **1 fence(s), 0 lease(s)** | the head's repo ledger `.local/fleet-leases.json` (389 B, sha **`ec09509d…`**, mtime **`2026-11-21 03:04:12.907935197 -0500`** local) holds fence **`tp-le2-20261120`** on `.31`, `.32`, `.33`, `.34` (`fenced_at` `2026-11-20T07:25:27Z`, owner directive 2026-11-20: production serve protected, serve `58cddf1c62ba6578_b8865cad5863` / image `986795bcd7f4`) and **0 lease(s)** |
| publication | tick | fresh census (`2026-11-23T03:07:46Z`–`2026-11-23T03:07:48Z`) written to `2026-11-23T030745Z.json` and composed on the base census `2026-11-23T02:43:06Z`; the queue blocks are rendered from `origin/main:mad-science/queue.json` sha **`892c492b…`**, and the landed rows from `git log --since=2026-11-23T02:43:06Z` |
| .30 | **nothing live (no reservation)** — idle | `2026-11-23T03:07:46Z` (`spark-41e1`): `docker ps -aq` **0**, running **0**, volumes **0**, `:8000` listeners **0**<br>root **1,213,484,961,792 B avail** (-227,794,944, fell) · **2,613,545,857,024 B used** (+227,794,944, rose)<br>boot **`2026-11-19T20:06:40Z`** (`btime`), `uptime` **284,466 s**<br>`MemTotal` **127,598,704 kB** (+0), `MemAvailable` **122,106,972 kB** (+17,256), `Cached` **52,029,504 kB** (+623,520), `AnonPages` **897,248 kB** (-16,868)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **0** in-window `exec`, oldest `2026-11-22T21:19:19.549437425-05:00 container exec_create: s`, newest `2026-11-22T21:29:27.688470769-05:00 container destroy ce2ab1` |
| .31 | **fenced serve** — excluded from the research census | `2026-11-23T03:07:47Z` (`spark-d325`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **2**, `/v1/models` **200**, `/health` **200**<br>root **1,559,355,043,840 B avail** (-10,956,800, fell) · **2,267,675,774,976 B used** (+10,956,800, rose)<br>boot **`2026-11-19T20:11:15Z`** (`btime`), `uptime` **284,191 s**<br>`MemTotal` **127,598,700 kB** (+0), `MemAvailable` **8,649,716 kB** (-44,216), `Cached` **8,942,080 kB** (-94,808), `AnonPages` **6,740,620 kB** (+32,416)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **147** in-window `exec`, oldest `2026-11-22T21:24:48.879407594-05:00 container exec_die d9d79`, newest `2026-11-22T22:07:18.796173673-05:00 container exec_die d9d79` |
| .32 | **fenced serve** — excluded from the research census | `2026-11-23T03:07:47Z` (`spark-ec1d`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **0**<br>root **1,624,984,768,512 B avail** (-19,283,968, fell) · **2,202,045,935,616 B used** (+19,283,968, rose)<br>boot **`2026-11-19T20:14:21Z`** (`btime`), `uptime` **284,005 s**<br>`MemTotal` **127,598,640 kB** (+0), `MemAvailable` **11,734,008 kB** (+3,676), `Cached` **12,416,324 kB** (+9,072), `AnonPages` **5,328,292 kB** (+5,216)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **147** in-window `exec`, oldest `2026-11-22T21:24:49.260911611-05:00 container exec_die 7641b`, newest `2026-11-22T22:07:19.147684433-05:00 container exec_die 7641b` |
| .33 | **fenced serve** — excluded from the research census | `2026-11-23T03:07:47Z` (`spark-3578`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **0**<br>root **1,521,560,006,656 B avail** (-19,271,680, fell) · **2,305,470,697,472 B used** (+19,271,680, rose)<br>boot **`2026-11-19T20:12:55Z`** (`btime`), `uptime` **284,092 s**<br>`MemTotal` **127,598,636 kB** (+0), `MemAvailable` **11,610,224 kB** (-76,824), `Cached` **12,253,452 kB** (+8,772), `AnonPages` **5,321,124 kB** (+2,488)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **147** in-window `exec`, oldest `2026-11-22T21:24:49.624627277-05:00 container exec_die d98d0`, newest `2026-11-22T22:07:19.503273593-05:00 container exec_die d98d0` |
| .34 | **fenced serve** — excluded from the research census | `2026-11-23T03:07:48Z` (`spark-324e`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **0**<br>root **1,106,952,425,472 B avail** (-19,279,872, fell) · **2,720,078,393,344 B used** (+19,279,872, rose)<br>boot **`2026-11-19T20:09:04Z`** (`btime`), `uptime` **284,324 s**<br>`MemTotal` **127,598,704 kB** (+0), `MemAvailable` **11,672,360 kB** (+56,160), `Cached` **11,121,156 kB** (+8,644), `AnonPages` **5,306,272 kB** (+4,340)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **147** in-window `exec`, oldest `2026-11-22T21:24:50.201255914-05:00 container exec_die ff75e`, newest `2026-11-22T22:07:19.877271181-05:00 container exec_die ff75e` |
| .35 | **nothing live (no reservation)** — idle | `2026-11-23T03:07:48Z` (`spark-383f`): `docker ps -aq` **0**, running **0**, volumes **0**, `:8000` listeners **0**<br>root **1,040,835,936,256 B avail** (-10,469,376, fell) · **2,786,194,882,560 B used** (+10,469,376, rose)<br>boot **`2026-11-19T20:07:56Z`** (`btime`), `uptime` **284,391 s**<br>`MemTotal` **127,598,700 kB** (+0), `MemAvailable` **123,225,300 kB** (+100), `Cached` **1,808,708 kB** (+8,124), `AnonPages` **247,548 kB** (+228)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **0** in-window `exec`, oldest `2026-11-22T21:05:06.535546060-05:00 container exec_start: sh`, newest `2026-11-22T21:19:48.088204374-05:00 container destroy 8b4cc1` |

## Work Queue
```mermaid
flowchart LR
  %% 7 blocked, 7 blocker edge(s), 2 drained by owner (1), session director (1)
  r1["owner · owns 1"]
  r2["session director · owns 1"]
  t1["ask-tp4-window-declaration · ask"]
  t2["beegfs-meta-restart-loop-non-meta-hosts · blocked"]
  t3["beegfs-meta-window-scheduling · queued"]
  t4["campaign-leases-tp4-onto-30 · blocked"]
  t5["ds4-fp4-kv-layout-sm121-port · blocked"]
  t6["inkling-tp4-first-boot · blocked"]
  t7["repin-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang · blocked"]
  t8["repin-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2 · blocked"]
  t9["weightless-dsgb10-tp4-boot-gate · blocked"]
  t1 --> t4
  t1 --> t5
  t1 --> t6
  t1 --> t7
  t1 --> t8
  t1 --> t9
  t3 --> t2
  r1 -.-> t1
  r2 -.-> t3
  classDef no-recorded-edge stroke-dasharray: 4 3
```

| job | node cost | blockers | holds | status | summary |
|---|---|---|---|---|---|
| `ask-tp4-window-declaration` — Ask: declare the four-rank TP4 window that two blocked quartet boots wait on | — | — | weightless-dsgb10-tp4-boot-gate, inkling-tp4-first-boot, campaign-leases-tp4-onto-30, repin-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang, repin-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2, ds4-fp4-kv-layout-sm121-port | ask | — QUESTION FOR THE OWNER: when may a four-rank TP4 boot run? Two arms are otherwise ready — weightless-dsgb10-tp4-boot-gate (the alpha=0 golden hash must equal stock before any steered request is quoted) and inkling-tp4-first-boot (first boot… (full note: queue.json) |
| `beegfs-meta-window-scheduling` — Propose and declare the maintenance window for the beegfs-meta fix | — | — | beegfs-meta-restart-loop-non-meta-hosts | queued | — OWNER ANSWER 2026-11-22 (ViBoard thread t22): the beegfs-meta restart-loop fix is deferred — its own session, no window yet. This row is the step that makes a window possible without pushing one: propose one or two candidate maintenance win… (full note: queue.json) |
| `beegfs-meta-restart-loop-non-meta-hosts` — beegfs-meta restart-loops every 5 s on .31-.35, and the loop hides a failed state behind "activating" | single | ask-beegfs-meta-window, beegfs-meta-window-scheduling | — | blocked | — Measured 2026-11-09 07:03-07:05 ET, and it is the side effect of the fix beegfs-units-restart-no (done) blessed: /etc/systemd/system/beegfs-meta.service.d/oom.conf (mtime 2026-11-08 16:03 on .30, 16:05 on .31) sets OOMScoreAdjust plus Resta… (full note: queue.json) — evidence: `.scratch/infra-chores-20261122/beegfs-meta/RECEIPT.md` |
| `repin-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang` — Boot glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang with the refreshed pin and move its pins | quartet | ask-tp4-window-declaration | — | blocked | — PIN MOVE 2026-11-22 (owner rule, ViBoard thread t24): updated pins are boot-tested as soon as a window of the correct size is free for them, and the pin moves in that boot's commit — no carrier-lane ride-along. This row boots recipes/glm/gl… (full note: queue.json) |
| `repin-glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2` — Boot glm-5.3-flash-exl3-tp4-1m-tensorfold-sglang-boot2 with the refreshed pin and move its pins | quartet | ask-tp4-window-declaration | — | blocked | — PIN MOVE 2026-11-22 (owner rule, ViBoard thread t24): updated pins are boot-tested as soon as a window of the correct size is free for them, and the pin moves in that boot's commit — no carrier-lane ride-along. This row boots recipes/glm/gl… (full note: queue.json) |
| `campaign-leases-tp4-onto-30` — The campaign leases memory-heavy TP4 quartets onto .30, which the owner ruling excludes | quartet | ask-placement-policy-30, ask-tp4-window-declaration | — | blocked | — MECHANISM LANDED OFFLINE 2026-11-11 (commits `aa54000`, `ebf5c8e`, `298098d`, `08ff156`; no live lease and no live six-node boot has run, so the row stays open). One ledger, `<repo>/.local/fleet-leases.json` (flock + atomic write), and one … (full note: queue.json) |
| `inkling-tp4-first-boot` — Inkling-2-Small TP=4 first boot: nightly pull and the unproven sm_121 Triton path | quartet | ask-tp4-window-declaration | — | blocked | — No node holds the pinned nightly digest c17e9d88, so the first boot includes the pull. GB10 is sm_121 and the Blackwell path gates on capability family 100, so the engine runs the Hopper/Triton half (attention_sm90 plus the Humming expert G… (full note: queue.json) — evidence: `recipes/explore/README.md section zz-inkling-2-small-nvfp4-thinking-tools-tp4-vllm` |
| `weightless-dsgb10-tp4-boot-gate` — Boot the weightless-dsgb10 arm four-rank: the α=0 golden hash must equal stock bit-for-bit before any steered request is quoted | quartet | ask-tp4-window-declaration | — | blocked | — Boot gate for the image closed by weightless-image-build-publish-pin (1bc6b5cb). Image ghcr.io/littlecedar/dgx-picom-ds41f:ds41f-7c123ad4-pr15-pr7-weightless, digest sha256:305b6e5151a2cfd13b85f18c36bccf9062af83e28917fd11a0f151691c5e83df, p… (full note: queue.json) — evidence: `recipes/ds4/zz-deepseek-v4.1-flash-1017-weightless-dsgb10-tp4.yaml (container pinned by digest at line 30); recipes/ds4/README.md lines 2890-2911 (two-name contract, alpha=0 identity) and 2990-2996 (the boot gate)` |
| `ds4-fp4-kv-layout-sm121-port` — DS4 1017 SM121: port the V41/V41_FP4 KV layout so fp4 KV is admissible — dtype is not a lever today, and sizing lies about fp4 | quartet | ask-tp4-window-declaration, ds4-fp4-kv-layout-sm121-port-sglang, ds4-fp4-kv-layout-sm121-port-vllm | — | blocked | — RECIPE RETIRED 2026-11-18: the `zz-` arm this row booted is archived at `attic/ds4/zz-ds4-1017-sm121-indexer-scoring.yaml` (it was run or refused on record; see the lane attic index), so the row is no longer bootable. CORRECTION TO THE FP8-… (full note: queue.json) |

## Completed Work
Window: commits since `2026-11-23T02:43:06Z` — the base census stamp, later than the 24 h start `2026-11-22T03:07:45Z`; older rows are not shown.

| time ET | commit | one clause |
|---|---|---|
| 11-22 21:45 | `95df6276` | Merge origin before publishing, so a diverged replica can still ship a board |
| 11-22 21:45 | `78341d30` | Merge origin before publishing, so a diverged replica can still ship a board |
| 11-22 21:57 | `df773623` | Refresh the status board: a 2026-11-23T025754Z census |
| 11-22 22:04 | `5f002619` | Merge origin, keeping origin's board and count |
| 11-22 22:07 | `9409c7e8` | Resolve a board-only merge conflict by taking origin's board |
