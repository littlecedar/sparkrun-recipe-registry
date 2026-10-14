#!/usr/bin/env python3
"""Flatten a ComfyUI UI-format workflow whose sole graph lives in a subgraph
into the API prompt format accepted by POST /prompt.

ComfyUI's subgraph support lives in the frontend; the backend `/prompt` route
only takes flat API graphs. This does the frontend's expansion headlessly:
resolves subgraph-input bindings (widget value or outer link), remaps inner
node ids, and rewires the instance's inputs/outputs to the inner nodes.

Widget names come from the running server's /object_info (the authoritative
INPUT_TYPES order): widget_values[i] -> i-th widget-typed input.
"""
import json
import sys
import urllib.request

WIDGET_PRIMITIVES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def is_widget(spec):
    """True for inputs the frontend renders as widgets (consume a widget value).

    Connection types (MODEL, VAE, LATENT, ...) never consume one; primitives,
    combos, multi-type widgets ("FLOAT,INT") and dynamic combos do.
    """
    t = spec[0]
    if isinstance(t, list):
        return True
    s = str(t)
    return s in WIDGET_PRIMITIVES or "," in s or s.endswith("V3")


def widget_names(obj_info, ntype):
    info = obj_info.get(ntype)
    if not info:
        return None
    order = info.get("input", {}).get("input_order", {})
    if order:
        names = order.get("required", []) + order.get("optional", [])
        # widget order == declaration order; filter by type below
        req = info["input"].get("required", {})
        opt = info["input"].get("optional", {})
        allspec = {**req, **opt}
        return [n for n in names if n in allspec and is_widget(allspec[n])]
    req = info["input"].get("required", {})
    opt = info["input"].get("optional", {})
    return [k for k, v in list(req.items()) + list(opt.items()) if is_widget(v)]


def main(workflow_path, base_url, seed=None, width=None, height=None,
         frames=None, fps=None, out_path=None):
    tpl = json.load(open(workflow_path))
    obj_info = json.load(urllib.request.urlopen(base_url.rstrip("/") + "/object_info"))

    subgraphs = tpl.get("definitions", {}).get("subgraphs", [])
    assert len(subgraphs) == 1, f"expected exactly 1 subgraph, got {len(subgraphs)}"
    sg = subgraphs[0]
    inst = [n for n in tpl["nodes"] if n["type"] == sg["id"]]
    assert len(inst) == 1, f"expected 1 instance of subgraph, got {len(inst)}"
    inst = inst[0]

    # --- 1. bind each subgraph input slot to either an outer link or a widget value
    sg_inputs = sg["inputs"]
    iws = inst.get("widgets_values", [])
    promoted = {i["name"]: i for i in inst.get("inputs", [])}
    binding = {}          # slot name -> ("link", outer_link_id) | ("value", v)
    for idx, si in enumerate(sg_inputs):
        p = promoted.get(si["name"])
        if p is not None and p.get("link") is not None:
            binding[si["name"]] = ("link", p["link"])
        else:
            binding[si["name"]] = ("value", iws[idx] if idx < len(iws) else None)
        # subgraph output slots have no "inputs" list entry; guard above covers it

    # --- 2. internal link id -> which subgraph input slot fed it
    link_to_slot = {}
    for si in sg_inputs:
        for lid in si.get("linkIds", []):
            link_to_slot[lid] = si["name"]
    outer_links = {l["id"] if isinstance(l, dict) else l[0]: l for l in tpl["links"]}
    inner_nodes = {n["id"]: n for n in sg["nodes"]}
    sg_links = {l["id"]: l for l in sg.get("links", [])}

    def outer_origin(lid):
        l = outer_links[lid]
        if isinstance(l, dict):
            return l["origin_id"], l["origin_slot"]
        return l[1], l[2]  # array form: [id, origin_id, origin_slot, ...]
    # --- 3. resolve a subgraph-internal link to an API input reference
    def resolve_inner_link(lid):
        link = sg_links[lid]
        oid, oslot = link["origin_id"], link["origin_slot"]
        if oid in inner_nodes:
            return [str(oid), oslot]
        # origin is a subgraph input slot
        slot = link_to_slot[lid]
        b = binding[slot]
        if b[0] == "link":
            oid, oslot = outer_origin(b[1])
            return [str(oid), oslot]
        # constant-bound subgraph input consumed by an inner widget input:
        # the API format takes a literal value there
        return b[1]

    prompt = {}
    skipped = []

    # --- 4. flatten inner nodes
    for nid, n in inner_nodes.items():
        ntype = n["type"]
        names = widget_names(obj_info, ntype)
        if names is None:
            skipped.append((nid, ntype))
            continue
        inputs = {}
        for i, v in enumerate(n.get("widgets_values", [])):
            if i < len(names):
                inputs[names[i]] = v
        linked = set()
        for i in n.get("inputs", []):
            lid = i.get("link")
            if lid is None:
                continue
            name = i["name"]
            inputs[name] = resolve_inner_link(lid)
            linked.add(name)
        # a widget's own input ref must beat its inline widget value
        prompt[str(nid)] = {"class_type": ntype, "inputs": inputs, "_meta": {}}

    # --- 5. outer nodes (skip subgraph instance + notes), wire instance refs
    sg_input_link_ids = set(link_to_slot)
    for n in tpl["nodes"]:
        if n["type"] == sg["id"] or n["type"] in ("MarkdownNote", "Note"):
            continue
        ntype = n["type"]
        names = widget_names(obj_info, ntype)
        if names is None:
            skipped.append((n["id"], ntype))
            continue
        inputs = {}
        for i, v in enumerate(n.get("widgets_values", [])):
            if i < len(names):
                inputs[names[i]] = v
        for i in n.get("inputs", []):
            lid = i.get("link")
            if lid is None or lid not in outer_links:
                continue
            oid, oslot = outer_origin(lid)
            if oid == inst["id"]:
                # instance output -> the inner node that fed that subgraph output
                out_slot = sg["outputs"][oslot]
                inner_lids = out_slot.get("linkIds", [])
                assert inner_lids, f"subgraph output {out_slot['name']} has no inner link"
                il = sg_links[inner_lids[0]]
                inputs[i["name"]] = [str(il["origin_id"]), il["origin_slot"]]
            else:
                inputs[i["name"]] = [str(oid), oslot]
        prompt[str(n["id"])] = {"class_type": ntype, "inputs": inputs, "_meta": {}}

    if skipped:
        print(f"WARN skipped nodes with no /object_info entry: {skipped}",
              file=sys.stderr)

    # --- 6. deterministic overrides for the acceptance cell
    #     (nodes 372/360/362/361 are the Width/Height/Duration/Frame-Rate primitives)
    overrides = {}
    if width is not None:
        overrides["372"] = ("value", width)
    if height is not None:
        overrides["360"] = ("value", height)
    if frames is not None:
        overrides["362"] = ("value", frames)
    if fps is not None:
        overrides["361"] = ("value", fps)
    applied = []
    for nid, (k, v) in overrides.items():
        if nid in prompt and k in prompt[nid]["inputs"]:
            prompt[nid]["inputs"][k] = v
            applied.append((nid, k, v))
    print("overrides:", applied, file=sys.stderr)
    # seed: RandomNoise 338 (stage 1) is the one that drives the sampling noise
    if seed is not None:
        prompt["338"]["inputs"]["noise_seed"] = seed
        prompt["339"]["inputs"]["noise_seed"] = seed
        print(f"seed -> {seed}", file=sys.stderr)

    text = json.dumps({k: v for k, v in prompt.items()}, indent=1)
    if out_path:
        open(out_path, "w").write(text)
    else:
        print(text)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--base-url", default="http://127.0.0.1:8188")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--frames", type=int)
    ap.add_argument("--fps", type=int)
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    main(a.workflow, a.base_url, a.seed, a.width, a.height, a.frames, a.fps, a.out)
