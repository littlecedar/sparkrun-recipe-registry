#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Little Cedar Group <sparkrun@littlecedar.net>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Flatten the LTX-2.5 UI-format workflow to the API prompt `POST /prompt` takes.

Provenance: verbatim from `~/benchmarks/ltx25-20261018/expand2.py` on the head
(the fixed copy), itself `recipes/explore/ltx-2.5-runbook/expand_subgraph.py`
with the subgraph-instance widget alignment fixed:

    widgets_values on a subgraph instance consumes a value only for
    widget-typed slots, in instance input order.  The runbook copy indexed
    widgets_values by the promoted-input index over ALL slots, which is
    silently correct only for T2V (where every slot is a widget) and shifts
    every model path by one on I2V/FLF2V (receipt REPORT.md defect 1).

ComfyUI's subgraph support lives in the frontend; the backend `/prompt` route
only takes flat API graphs. Widget names come from the running server's
`/object_info` (the authoritative INPUT_TYPES declaration order).
"""
import json
import sys
import urllib.request

WIDGET_PRIMITIVES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def is_widget(spec):
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
        allspec = dict(info["input"].get("required", {}))
        allspec.update(info["input"].get("optional", {}))
        return [n for n in names if n in allspec and is_widget(allspec[n])]
    req = info["input"].get("required", {})
    opt = info["input"].get("optional", {})
    return [k for k, v in list(req.items()) + list(opt.items()) if is_widget(v)]


def main(workflow_path, base_url):
    tpl = json.load(open(workflow_path))
    obj_info = json.load(urllib.request.urlopen(base_url.rstrip("/") + "/object_info"))
    subgraphs = tpl.get("definitions", {}).get("subgraphs", [])
    assert len(subgraphs) == 1, f"expected exactly 1 subgraph, got {len(subgraphs)}"
    sg = subgraphs[0]
    inst = [n for n in tpl["nodes"] if n["type"] == sg["id"]]
    assert len(inst) == 1, f"expected 1 instance of subgraph, got {len(inst)}"
    inst = inst[0]
    sg_inputs = sg["inputs"]
    iws = inst.get("widgets_values", [])
    promoted = {i["name"]: i for i in inst.get("inputs", [])}
    # widgets_values aligns with the subgraph input slots in order, consuming a
    # value only for widget-typed slots (IMAGE/LATENT slots are links only).
    binding = {}
    j = 0
    for si in sg_inputs:
        p = promoted.get(si["name"])
        t = si["type"]
        isw = isinstance(t, list) or any(
            x in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO")
            for x in str(t).split(","))
        v = None
        if isw:
            v = iws[j] if j < len(iws) else None
            j += 1
        if p is not None and p.get("link") is not None:
            binding[si["name"]] = ("link", p["link"])
        else:
            binding[si["name"]] = ("value", v)
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
        return l[1], l[2]

    def resolve_inner_link(lid):
        link = sg_links[lid]
        oid, oslot = link["origin_id"], link["origin_slot"]
        if oid in inner_nodes:
            return [str(oid), oslot]
        slot = link_to_slot[lid]
        b = binding[slot]
        if b[0] == "link":
            oid, oslot = outer_origin(b[1])
            return [str(oid), oslot]
        return b[1]

    prompt = {}
    skipped = []
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
        for i in n.get("inputs", []):
            lid = i.get("link")
            if lid is None:
                continue
            inputs[i["name"]] = resolve_inner_link(lid)
        prompt[str(nid)] = {"class_type": ntype, "inputs": inputs, "_meta": {}}
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
                out_slot = sg["outputs"][oslot]
                inner_lids = out_slot.get("linkIds", [])
                assert inner_lids, f"subgraph output {out_slot['name']} has no inner link"
                il = sg_links[inner_lids[0]]
                inputs[i["name"]] = [str(il["origin_id"]), il["origin_slot"]]
            else:
                inputs[i["name"]] = [str(oid), oslot]
        prompt[str(n["id"])] = {"class_type": ntype, "inputs": inputs, "_meta": {}}
    if skipped:
        print(f"WARN skipped nodes with no /object_info entry: {skipped}", file=sys.stderr)
    return prompt