# Aneda log records: a contract request to sparkrun

**Request, not a patch.** The Aneda stack does not modify sparkrun; this note states what it emits so a maintainer can write parser rules without reading our code. Facts cite **sparkrun 0.4.3**, `src/sparkrun/cli/_monitor_metrics.py` (line numbers from that release; AGENTS.md warns they drift — re-grep after an upgrade).

## 1. What emits it

TP=4 DeepSeek-V4.1-Flash engine (`dsgb10`, `src=engine`) and its Rust front (`dsfront`, `src=front`): one record per event, one line each, stdout only, one sink per node (`/tmp/sparkrun_serve.log` = the container's stdout, so `docker logs` reads it). Rank 0-3; the front carries the rank of the node it runs beside and is told apart by `src`.

## 2. Grammar

```
ts=<YYYY-MM-DDThh:mm:ss.sssZ> level=<debug|info|warn|error|fatal> node=<host> rank=<0-3> \
  src=<engine|front|vision|launcher|mod> event=<noun.verb> [key=value]... [msg="<text>"]
```

- `ts` is CLOCK_REALTIME UTC, milliseconds, literal `Z`; never local time.
- Keys match `[a-z0-9_.]+`; an unquoted value has no spaces or commas (`-`, `.`, `/`, `:` are fine: paths, served names, revisions).
- `msg=` is last, double-quoted, `\`-escaped for `"`, `\` and newline. A record never contains a raw newline, so a native multi-line block folds into one record.
- Additive only: new keys append before `msg=`; existing keys are never reordered or renamed.

## 3. Exact line shapes

`<ts>` is the timestamp above; `<r>` = 0-3; `<model>` = the served name, which is how a steered request is attributed downstream. Native per-rank reading, every `WEIGHTLESS_STATS_INTERVAL` (default 10 s):

```
ts=<ts> level=info node=<host> rank=<r> src=engine event=stats #running-req: <int>, #queue-req: <int>, Avg prompt throughput: <float> tokens/s, Avg generation throughput: <float> tokens/s, GPU KV cache usage: <float>%, Prefix cache hit rate: <float>%, engram_hit: <float>, engram_used: <int>, reqs_stock: <int>, reqs_steered: <int>, inflight: <int>, window_s: <float>
```

The normalized pair, same cadence. **These two spellings are frozen** — they are the only reason a shipped rule can read us:

```
ts=<ts> level=info node=<host> rank=<r> src=engine event=metrics #running-req: <int>, #queue-req: <int>, Avg prompt throughput: <float> tokens/s, Avg generation throughput: <float> tokens/s, GPU KV cache usage: <float>%, Prefix cache hit rate: <float>%
ts=<ts> level=info node=<host> rank=<r> src=engine event=metrics Avg Draft acceptance rate: <float>%
```

Two records because the engines printing these fields print them on two lines, and a rule anchors on text, not on a record. Per-request and lifecycle:

```
ts=<ts> level=info  node=<host> rank=<r> src=front  event=req.done model=<model> status=<int> prompt_tokens=<int> cached_tokens=<int> completion_tokens=<int> ttft_ms=<float> prefill_ms=<float> gen_tps=<float>
ts=<ts> level=debug node=<host> rank=<r> src=front  event=req.plan model=<model> inflight=<int> queued=<int> steered=<0|1>
ts=<ts> level=warn  node=<host> rank=<r> src=front  event=req.refused status=<int> reason=<word>
ts=<ts> level=info  node=<host> rank=<r> src=front  event=serve.listen bind=<addr:port> model=<model>
ts=<ts> level=info  node=<host> rank=<r> src=engine event=engine.start model=<model> tp=4 kv_dtype=<word> max_len=<int> rev=<sha>
ts=<ts> level=info  node=<host> rank=<r> src=engine event=glp.load bank=<name> experts=<int> bytes=<int> ms=<float>
ts=<ts> level=info  node=<host> rank=<r> src=engine event=spec.cfmlp draft_len=<int> topk=<int> accept_pct=<float>
ts=<ts> level=fatal node=<host> rank=<r> src=engine event=fatal code=<int> msg="<text>"
ts=<ts> level=debug node=<host> rank=<r> src=engine event=turn req=<id> tokens=<int> ms=<float>
ts=<ts> level=debug node=<host> rank=<r> src=engine event=batch reqs=<int> prompt_tokens=<int> decode_tokens=<int>
```

`req.done` is the only per-request record at `info`; `req.plan`, `turn` and `batch` are `debug`, off by default (`DSGB10_LOG_LEVEL`, `DSFRONT_LOG_LEVEL`, default `info`).

## 4. Cadence, types, traps

- `stats` and `metrics` every 10 s per source; `req.done` once per request.
- `#running-req`/`#queue-req` are integers, rounded before printing; throughputs and percentages are floats with one decimal.
- Never print a sign: `_NUM` is `\d+(?:\.\d+)?` (`:223`), so `-1.0` matches as `1.0` — a silent wrong value rather than a miss. No `+`, exponent or thousands separator.
- `stats` carries gated substrings too, so it feeds the same rules as `metrics`. Harmless: samples inside one window are averaged, not added.

## 5. What the shipped parser needs

`_GATES` (`:301-313`) is a **substring pre-filter over the whole line**: a line with none of the eleven gates is dropped before any regex runs (`:369`), so a record prefix and extra fields are free but a gated field must appear **verbatim**. Every `_RULES` entry (`:245-296`) is `pattern.search(text)` with **group 1** the value (`:374`) — ratio rules take groups 1 and 2 — so no line-start anchor is needed and no spelling, spacing or separator change survives.

```
label  key    gate               rule (group 1 = value)                    agg
tg     gen    "throughput"       Avg generation throughput: (NUM) tokens/s  sum
pp     prompt "throughput"       Avg prompt throughput: (NUM) tokens/s      sum
jobs   run    "#running-req"     #running-req: (\d+)                       sum
queue  queue  "#queue-req"       #queue-req: (\d+)                         sum
kv     kv     "KV cache usage"   GPU KV cache usage: (NUM)%                max
hit    hit    "hit rate"         Prefix cache hit rate: (NUM)%             max
spec   accept "accept"           Avg Draft acceptance rate: (NUM)%         max
```

`_METRICS` (`:195-203`) fixes that order and the label spellings; `_KINDS` (`:207`) fixes sum-vs-max. The vLLM-wording rules `Running: (\d+) reqs` and `Waiting: (\d+) reqs` (`:249-250`, plus `Pending:` at `:251`) fire only as passengers on a line that also carries a gate (the one-line vLLM form carries `throughput` and `KV cache usage`). No gate matches a bare `Running:` line, so they never fire for us: our counts use the `#running-req:`/`#queue-req:` spellings at `:259-260`, which are gated themselves.

## 6. What the monitor does with it

Sources are `(host, container)` pairs (`_monitor_tui.py:1090`, `:1118`): four rank containers are four sources, a front in its own container a fifth. One poll per 30 s (`METRICS_TRACK_INTERVAL_S`, `_monitor_tui.py:503`) reads a 500-line tail and commits **one ring point per source per metric** = the mean of that source's window samples (`commit()`, `:464-487`) — three samples per point at a 10 s cadence. `history()` (`:489-509`) then aggregates across sources: non-percentage metrics **sum**, percentage metrics take the **max**; 120 points default = one hour at 30 s.

So `tg`/`pp` are the fleet total over the four rank containers (right for throughput), `kv` is the **fullest** rank's occupancy (right for pressure), and `hit`/`spec` take the **best** rank, so they read optimistically. Two emitters in one container average into one point instead of adding: give the front its own container if its numbers should count separately.

## 7. Fields no shipped rule reads

`engram_hit`, `engram_used`, `reqs_stock`, `reqs_steered`, `inflight`, `window_s` on `stats`, and `prefill_ms`/`gen_tps` on `req.done`. All are `key=value`, so none can accidentally match a rule; each is inert until a consumer adds a gate spelling and a rule:

- `reqs_steered` + `reqs_stock`: one gate, two rules, a ratio kind (like `#new-token`/`#cached-token` at `:274`) → a sparkline of the steered fraction, the number that says whether the steering path is exercised at all.
- `engram_hit` (percent): `engram_hit: (NUM)%`, pct kind → bank hit rate beside `hit`. `engram_used` (count): bank occupancy, the only early signal that it is filling before it evicts.
- `inflight`: front-side depth, which `queue` cannot show — the engine queue sits behind the front's admission, so a stalled front reads `queue=0` while `inflight` climbs.
- `window_s`: not a metric; it states the averaging window of the rates beside it, so `tg × window_s` is tokens per sample. No rule needed.
- `prefill_ms`/`gen_tps`: not a sparkline. Needs a rule pair plus per-request state to plot prefill time against decode rate — a stacked prompt/generation chart, not a ring series.

## 8. Verifying the contract on a live serve

One grep per shape, on a node that has served a request:

```
docker logs <container> 2>&1 | grep -m1 'event=stats #running-req:'
docker logs <container> 2>&1 | grep -m1 'event=metrics #running-req:'
docker logs <container> 2>&1 | grep -m1 'Avg Draft acceptance rate:'
docker logs <container> 2>&1 | grep -m1 'event=req.done model='
```

A parser-level check needing no serve:

```
python3 -c 'from sparkrun.cli._monitor_metrics import RuntimeMetricsScraper as S; \
s=S(); s.observe(("h","c"), "<one metrics line>"); s.commit(); print(s.latest("tg"), s.latest("kv"))'
```

Then the live monitor: `sparkrun cluster monitor` (`_cluster.py:858`) shows all seven indicators in priority order (`jobs queue pp tg kv hit spec`) once a request has run. A missing indicator is either an absent field or a changed spelling; the map in §5 says which.

---

**If this changes:** the record grammar is additive only (fields appended, never reordered) and the two `event=metrics` spellings are frozen. Any change to either lands here first, with the sparkrun version it was verified against.
