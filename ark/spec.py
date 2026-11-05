#!/usr/bin/env python3
"""Diagram spec: schema, validation, repair, and the Ark call that produces it."""
import json, re

import ark_client
from prompts import SYSTEM_PROMPT

MODELS = {"lite": "doubao-seed-2-1-lite-260915", "pro": "doubao-seed-2-1-pro-260915"}
MAX_NODES = 14


class SpecError(ValueError):
    pass


def _ascii_slug(s):
    return re.sub(r"[^a-z0-9_-]", "", str(s or "").lower())[:16]


def extract_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise SpecError(f"no JSON object in model output: {t[:120]!r}")
    return json.loads(t[a:b + 1])


def validate(spec):
    """Return list of problems ([] = good)."""
    errs = []
    if not isinstance(spec, dict):
        return ["spec is not an object"]
    for k in ("title", "nodes", "edges"):
        if k not in spec:
            errs.append(f"missing key {k}")
    if errs:
        return errs
    ids = []
    for n in spec["nodes"]:
        if not isinstance(n, dict) or not n.get("id") or not n.get("name"):
            errs.append(f"bad node: {n!r}")
            continue
        ids.append(n["id"])
    if len(ids) != len(set(ids)):
        errs.append("duplicate node ids")
    if not (1 <= len(ids) <= MAX_NODES):
        errs.append(f"node count {len(ids)} out of 1..{MAX_NODES}")
    idset = set(ids)
    for e in spec["edges"]:
        if not isinstance(e, dict) or e.get("from") not in idset or e.get("to") not in idset:
            errs.append(f"edge refs unknown node: {e!r}")
        elif e.get("kind") not in ("primary", "internal", "dev"):
            errs.append(f"bad kind: {e.get('kind')!r}")
    seen = []
    for g in spec.get("groups", []):
        for m in (g or {}).get("members", []):
            if m not in idset:
                errs.append(f"group member unknown: {m!r}")
            elif m in seen:
                errs.append(f"node {m!r} in two groups")
            seen.append(m)
    return errs


def repair(spec):
    """Best-effort normalization so layout never crashes: coerce ids/kinds, drop
    broken entries, cap node count. Returns (spec, dropped_notes)."""
    notes = []
    nodes, ids = [], set()
    for n in spec.get("nodes", []):
        if not isinstance(n, dict):
            continue
        nid = _ascii_slug(n.get("id"))
        name = str(n.get("name") or "").strip()[:20]
        if not nid or not name or nid in ids:
            notes.append(f"dropped bad node {n.get('id')!r}")
            continue
        ids.add(nid)
        icon = _ascii_slug(n.get("icon"))
        nodes.append({"id": nid, "name": name, "role": str(n.get("role") or "")[:24], "icon": icon})
    if len(nodes) > MAX_NODES:
        notes.append(f"trimmed to {MAX_NODES} nodes")
        nodes = nodes[:MAX_NODES]
        ids = {n["id"] for n in nodes}
    edges, seen = [], set()
    for e in spec.get("edges", []):
        if not isinstance(e, dict):
            continue
        f, t = _ascii_slug(e.get("from")), _ascii_slug(e.get("to"))
        if f not in ids or t not in ids or f == t or (f, t) in seen:
            notes.append(f"dropped bad edge {e.get('from')!r}->{e.get('to')!r}")
            continue
        seen.add((f, t))
        kind = e.get("kind") if e.get("kind") in ("primary", "internal", "dev") else "internal"
        edges.append({"from": f, "to": t, "label": str(e.get("label") or "")[:14], "kind": kind})
    groups = []
    if len(nodes) > 2:
        for g in spec.get("groups", []):
            if not isinstance(g, dict) or not g.get("name"):
                continue
            members = [m for m in g.get("members", []) if m in ids]
            if len(members) >= 2:
                groups.append({"name": str(g["name"])[:20],
                               "icon": _ascii_slug(g.get("icon")), "members": members})
    out = {"title": str(spec.get("title") or "")[:40] or "技术栈架构图",
           "lede": str(spec.get("lede") or "")[:90],
           "nodes": nodes, "groups": groups, "edges": edges}
    if not out["edges"] and len(nodes) > 1:            # flat list still gets a chain
        for a, b in zip(nodes, nodes[1:]):
            out["edges"].append({"from": a["id"], "to": b["id"], "label": "", "kind": "internal"})
        notes.append("no edges given; chained nodes in order")
    return out, notes


def ask(sentence, quality="lite"):
    """One Ark call -> repaired spec. One retry with the validator's complaints
    appended. Returns (spec, notes, usage, latency)."""
    model = MODELS.get(quality, MODELS["lite"])
    feedback = ""
    last_usage, last_latency = {}, 0.0
    for attempt in range(2):
        content, last_usage, last_latency = ark_client.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": sentence + feedback}],
            model=model, temperature=0.2 if not feedback else 0.1, max_tokens=2000)
        raw = extract_json(content)
        errs = validate(raw)
        if not errs:
            spec, notes = repair(raw)
            return spec, notes, last_usage, last_latency
        if attempt == 0:
            feedback = (f"\n\nYour previous output had these problems: {'; '.join(errs[:5])}. "
                        f"Answer again with corrected JSON only.")
    spec, notes = repair(raw)                          # salvage what we have
    notes = [f"salvaged after retry: {'; '.join(errs[:3])}"] + notes
    return spec, notes, last_usage, last_latency
