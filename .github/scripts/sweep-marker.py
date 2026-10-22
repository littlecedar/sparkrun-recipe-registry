#!/usr/bin/env python3
"""Print the one stable line a reader greps for in a refresh-sweep run's summary.

`$GITHUB_STEP_SUMMARY` is not a subscription, so the workflow also keeps the report as a retained
artifact; this marker is what makes the summary machine-readable anyway. It never fails: an
unreadable report prints a marker saying so and exits 0, because the run must stay green.
"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "sweep.json"
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except Exception as exc:                      # missing, truncated, not JSON
    print("pin-drift: report unreadable (%s)" % exc)
    raise SystemExit(0)

totals = data.get("totals") or {}
print("pin-drift: %d rows (%d accepted) | exit %s | %d recipes, %d model pins, %d container pins, "
      "%d build inputs | generated %s"
      % (len(data.get("gated") or []),
         totals.get("accepted", 0),
         data.get("exit_code"),
         totals.get("recipes", 0),
         totals.get("model_pins", 0),
         totals.get("container_pins", 0),
         totals.get("build_inputs", 0),
         data.get("generated_at", "unknown")))
