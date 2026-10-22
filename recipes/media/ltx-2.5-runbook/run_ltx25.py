#!/usr/bin/env python3
"""Expand the LTX-2.5 T2V subgraph template to an API prompt and run it on a
local ComfyUI server, then wait for the history entry and report wall-clock.

Stage split + peak memory come from server.log (timestamped wrapper) and a
1 Hz /proc/meminfo sampler started by run.sh -- this script only owns the
prompt round trip.
"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, "/<home-dir>/ltx25")
from expand_subgraph import main as expand  # noqa: E402


def post(base, prompt):
    body = json.dumps({"prompt": prompt, "client_id": "ltx25-runner"}).encode()
    req = urllib.request.Request(base + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def history(base, pid):
    return json.load(urllib.request.urlopen(base + f"/history/{pid}", timeout=60))

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--base-url", default="http://127.0.0.1:8188")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--width", type=int, default=1344)
    ap.add_argument("--height", type=int, default=768)
    ap.add_argument("--duration", type=int, default=5)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--transformer")
    ap.add_argument("--api-out", default="/<home-dir>/ltx25/api_prompt.json")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    tpl = json.load(open(a.workflow))
    work = a.workflow
    if a.transformer:
        inst = [n for n in tpl["nodes"]
                if n["type"] == tpl["definitions"]["subgraphs"][0]["id"]][0]
        # widgets_values index 7 is the unet_name slot (subgraph input order)
        inst["widgets_values"][7] = a.transformer
        work = "/<home-dir>/ltx25/ltx_t2v_nvfp4.json"
        json.dump(tpl, open(work, "w"))
        print(f"transformer -> {a.transformer}", file=sys.stderr)

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        expand(work, a.base_url, a.seed, a.width, a.height, a.duration,
               a.fps, None)
    prompt = json.loads(buf.getvalue())
    # Prompt-enhancer branch (380 TextGenerateLTX2Prompt + 393 CLIPLoader) is
    # dead when switch=False, but ComfyUI still validates its inputs: prune it
    # and alias on_true to on_false (ComfySwitchNode is lazy, never evaluated).
    if not prompt["383"]["inputs"]["value"]:
        for dead in ("380", "393"):
            prompt.pop(dead, None)
        prompt["382"]["inputs"]["on_true"] = prompt["382"]["inputs"]["on_false"]
        print("pruned prompt-enhancer branch (380, 393); on_true aliased", file=sys.stderr)
    json.dump(prompt, open(a.api_out, "w"), indent=1)
    print(f"API prompt: {len(prompt)} nodes -> {a.api_out}", file=sys.stderr)

    t0 = time.time()
    sub = post(a.base_url, prompt)
    pid = sub["prompt_id"]
    print(f"queued prompt_id={pid}", file=sys.stderr)
    while time.time() - t0 < a.timeout:
        time.sleep(2)
        h = history(a.base_url, pid)
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed") or st.get("status_str") == "error":
                break
    dt = time.time() - t0
    entry = h.get(pid, {})
    status = entry.get("status", {})
    print(json.dumps({"prompt_id": pid, "wall_s": round(dt, 2),
                      "status": status.get("status_str"),
                      "completed": status.get("completed"),
                      "outputs": entry.get("outputs", {})}, indent=1))


if __name__ == "__main__":
    main()
