"""Campaign director for multi-arm sparkrun measurement campaigns.

One director owns the plan and decides what "done" means; workers are subprocesses it spawns,
each polling the director for an assignment and reporting a return code back. The per-arm
executor is `tools/run-arm.sh`, unchanged. `DESIGN.md` carries the component split, the wire
protocol, the persisted state and the acceptance-item map.
"""