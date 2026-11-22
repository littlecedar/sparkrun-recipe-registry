# Board — generated 2026-11-21 20:12 ET

## In flight
| where | owner | what |
|---|---|---|
| census | read-only in tick — booted nothing, claimed nothing, stopped nothing, evicted nothing | read `2026-11-22T01:12:34Z`–`2026-11-22T01:12:37Z` (each node's own `date -u`) on the base census `2026-11-22T00:13:43Z`, **0 h 58 min 51 s** after it: **4 containers, 0 volumes** fleet-wide; **no research rank**; the fenced hosts hold running containers on `.31`, `.32`, `.33`, `.34`, excluded from research accounting; `/v1/models` **200**, `/health` **200** on `.31` |
| pool | — (nobody drives it; head units re-proved each tick) | head: `beegfs-mgmtd` **active** (Result success, NRestarts 0, **+0** on the base) · `beegfs-meta` **activating** (Result exit-code, NRestarts 36,536, **+6** on the base) · `beegfs-storage` **active** (Result success, NRestarts 0, **+0** on the base); worker unit states and the pool's through-mount reads are not part of this census |
| queue | register snapshot `55ea2a14…`; both blocks below rendered from it | `mad-science/queue.json` sha256 **`55ea2a142b868f08444f2141cae6721ea972541a40d1ac527f41f955f6c2d74c`** read locally: **213 tasks: 181 done, 31 queued, 1 blocked, 0 running — 32 open**; the head clone reads **`55ea2a14…`**, identical |
| window | **no manual lock** at this read | `.local/fleet-window.lock` is **absent** on the head (read `2026-11-22T01:12:36Z`) |
| campaign | `sparkrun-campaign` — active, 2 lease(s) | head user unit `sparkrun-campaign` reads **`active`** / **`running`** (`MainPID` **3,930,275**, `NRestarts` **0**, **+0** on the base); the lease ledger holds **2 lease(s)** and fence(s) `tp-le2-20261120` |
| lease | **1 fence(s), 2 lease(s)** | the head's repo ledger `.local/fleet-leases.json` (737 B, sha **`ec09509d…`**, mtime **`2026-11-21 03:04:12.000000000 -0500`** local) holds fence **`tp-le2-20261120`** on `.31`, `.32`, `.33`, `.34` (`fenced_at` `2026-11-20T07:25:27Z`, owner directive 2026-11-20: production serve protected, serve `58cddf1c62ba6578_b8865cad5863` / image `986795bcd7f4`) and **2 lease(s)** |
| publication | tick | fresh census (`2026-11-22T01:12:34Z`–`2026-11-22T01:12:37Z`) written to `evidence-next.json` and composed on the base census `2026-11-22T00:13:43Z`; the queue blocks are rendered from `mad-science/queue.json` sha **`55ea2a14…`**, and the landed rows from `git log --since=2026-11-22T00:13:43Z` |
| .30 | **nothing live (no reservation)** — idle | `2026-11-22T01:12:34Z` (`node-thirty`): `docker ps -aq` **0**, running **0**, volumes **0**, `:8000` listeners **0**<br>root **1,371,101,020,160 B avail** (+283,648, rose) · **2,660,770,533,376 B used** (-283,648, fell)<br>boot **`2026-11-19T20:06:40Z`** (`btime`), `uptime` **191,154 s**<br>`MemTotal` **127,598,704 kB** (+0), `MemAvailable` **121,141,800 kB** (+228), `Cached` **24,799,356 kB** (+284,580), `AnonPages` **1,089,548 kB** (-37,304)<br>ring **256** events all-types (+6), **0** in-window lifecycle and **0** in-window `exec`, oldest `2026-11-21T01:06:26.326203501-05:00 container destroy 4db0fd`, newest `2026-11-21T03:05:54.712690080-05:00 image delete sha256:5c2b` |
| .31 | **fenced serve** — excluded from the research census | `2026-11-22T01:12:35Z` (`node-thirty-one`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **2**, `/v1/models` **200**, `/health` **200**<br>root **1,649,791,016,960 B avail** (-979,200, fell) · **2,382,080,536,576 B used** (+979,200, rose)<br>boot **`2026-11-19T20:11:15Z`** (`btime`), `uptime` **190,879 s**<br>`MemTotal` **127,598,700 kB** (+0), `MemAvailable` **7,890,732 kB** (+61,648), `Cached` **2,591,124 kB** (+13,736), `AnonPages` **7,553,776 kB** (+35,584)<br>ring **256** events all-types (+0), **0** in-window lifecycle and **80** in-window `exec`, oldest `2026-11-21T19:31:50.184285308-05:00 container exec_create: t`, newest `2026-11-21T20:12:20.333797911-05:00 container exec_die d9d79` |
| .32 | **fenced serve** — excluded from the research census | `2026-11-22T01:12:35Z` (`node-thirty-two`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **0**<br>root **1,709,870,497,792 B avail** (no base, unmeasured) · **2,117,160,206,336 B used** (no base, unmeasured)<br>boot **`2026-11-19T20:14:21Z`** (`btime`), `uptime` **190,693 s**<br>`MemTotal` **127,598,640 kB** (no base), `MemAvailable` **11,709,116 kB** (no base), `Cached` **10,639,800 kB** (no base), `AnonPages` **5,323,000 kB** (no base)<br>ring **256** events all-types (no base), **0** in-window lifecycle and **256** in-window `exec`, oldest `2026-11-21T19:31:20.870368005-05:00 container exec_die 7641b`, newest `2026-11-21T20:12:20.734829172-05:00 container exec_die 7641b` |
| .33 | **fenced serve** — excluded from the research census | `2026-11-22T01:12:35Z` (`node-thirty-three`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **0**<br>root **1,625,686,769,664 B avail** (no base, unmeasured) · **2,201,343,934,464 B used** (no base, unmeasured)<br>boot **`2026-11-19T20:12:55Z`** (`btime`), `uptime` **190,780 s**<br>`MemTotal` **127,598,636 kB** (no base), `MemAvailable` **11,654,168 kB** (no base), `Cached` **10,275,824 kB** (no base), `AnonPages` **5,313,616 kB** (no base)<br>ring **256** events all-types (no base), **0** in-window lifecycle and **256** in-window `exec`, oldest `2026-11-21T19:31:21.490895329-05:00 container exec_die d98d0`, newest `2026-11-21T20:12:21.157697616-05:00 container exec_die d98d0` |
| .34 | **fenced serve** — excluded from the research census | `2026-11-22T01:12:36Z` (`node-thirty-four`): `docker ps -aq` **1**, running **1**, volumes **0**, `:8000` listeners **0**<br>root **1,102,518,554,624 B avail** (no base, unmeasured) · **2,724,512,264,192 B used** (no base, unmeasured)<br>boot **`2026-11-19T20:09:04Z`** (`btime`), `uptime` **191,012 s**<br>`MemTotal` **127,598,704 kB** (no base), `MemAvailable` **11,678,784 kB** (no base), `Cached` **9,083,644 kB** (no base), `AnonPages` **5,307,380 kB** (no base)<br>ring **256** events all-types (no base), **0** in-window lifecycle and **256** in-window `exec`, oldest `2026-11-21T19:31:21.904745070-05:00 container exec_die ff75e`, newest `2026-11-21T20:12:21.531601696-05:00 container exec_die ff75e` |
| .35 | **nothing live (no reservation)** — idle | `2026-11-22T01:12:37Z` (`node-thirty-five`): `docker ps -aq` **0**, running **0**, volumes **0**, `:8000` listeners **0**<br>root **1,112,209,510,400 B avail** (no base, unmeasured) · **2,714,821,308,416 B used** (no base, unmeasured)<br>boot **`2026-11-19T20:07:56Z`** (`btime`), `uptime` **191,080 s**<br>`MemTotal` **127,598,700 kB** (no base), `MemAvailable` **123,088,408 kB** (no base), `Cached` **6,041,560 kB** (no base), `AnonPages` **253,996 kB** (no base)<br>ring **256** events all-types (no base), **0** in-window lifecycle and **0** in-window `exec`, oldest `2026-11-20T19:46:09.290987692-05:00 container exec_die 2f39b`, newest `2026-11-20T20:56:32.651557975-05:00 container destroy 26b0f5` |
| `lease-1` | campaign | `.30` leased for `tp1-window`; expires `2026-11-22T03:00:00Z` |

## Work queue
```mermaid
flowchart LR
  %% 1 blocked, 1 edges, 0 prose-gated, 0 question-gated, 0 question
  t1["board-census-tool · queued"]
  t2["board-render-tool · blocked"]
  t1 --> t2
  classDef no-recorded-edge stroke-dasharray: 4 3
```

| job | node cost | holds | state |
|---|---|---|---|
| `board-census-tool` — Consolidate the per-tick census probe into one stdlib tool | single | — | queued — The probe script and its parser were rewritten every tick; a transcription slip shipped a 60 000 B phantom delta on 2026-11-09. |
| `board-render-tool` — Render STATUS.md from the evidence document and the register | — | board-census-tool | blocked |

## Landed session
| time ET | commit | one clause |
|---|---|---|
| 11-21 19:40 | `e4f5a6b` | Add the census evidence schema |
| 11-21 20:05 | `a1b2c3d` | Ship the board renderer, derived from evidence |
