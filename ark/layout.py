#!/usr/bin/env python3
"""Deterministic layout engine — coordinates, group boxes, orthogonal routing.

The model only decides content (nodes/groups/edges); every pixel here follows
the constants from the skill's references/geometry.md:
  node box ~132x100 (tile 60, name at +68, role at +86)
  >=140px between centers in a row; row spacing grows with how many routed
  lines share the gap (30px per extra line); group boxes padded 24/60/150 and
  clipped above the next row's tiles.
Edges spanning several rows route through an x-corridor verified free of node
boxes in every intermediate row. Labels sit below their line segment.
"""
import re

ROW_TOP0, BASE_DY, TILE, BOX_H, BOX_W = 120, 140, 60, 100, 132
GAP_X, MARGIN_X = 140, 92
LINE_STEP = 30
STAGGERS = (-24, 0, 24)
PAD_X, PAD_TOP, PAD_BOTTOM = 24, 60, 150


def _txt_w(s):
    """Rough text width at 13px: CJK ~13px, latin ~7.2px."""
    w = 0.0
    for ch in str(s):
        w += 13.0 if ord(ch) > 0x2E7F else 7.2
    return w


def _box_w(name):
    return min(176, max(BOX_W, int(_txt_w(name) + 34)))


def _layers(nodes, edges):
    """Longest-path layering with back-edge removal."""
    ids = [n["id"] for n in nodes]
    dropped = set()
    colour = {}
    for root in ids:
        if root in colour:
            continue
        colour[root] = 1
        stack = [(root, iter([e for e in edges if e["from"] == root]))]
        while stack:
            v, it = stack[-1]
            advanced = False
            for e in it:
                w = e["to"]
                if colour.get(w) == 1:
                    dropped.add(id(e))
                elif colour.get(w) is None:
                    colour[w] = 1
                    stack.append((w, iter([e2 for e2 in edges if e2["from"] == w])))
                    advanced = True
                    break
            if not advanced:
                colour[v] = 2
                stack.pop()
    preds = {i: set() for i in ids}
    sucs = {i: set() for i in ids}
    seen = set()
    for e in edges:
        if id(e) not in dropped and e["from"] != e["to"] and (e["from"], e["to"]) not in seen:
            seen.add((e["from"], e["to"]))
            preds[e["to"]].add(e["from"])
            sucs[e["from"]].add(e["to"])
    indeg = {i: len(preds[i]) for i in ids}
    layer = {i: 0 for i in ids}
    queue = [i for i in ids if indeg[i] == 0]
    while queue:
        v = queue.pop(0)
        for w in sucs[v]:
            layer[w] = max(layer[w], layer[v] + 1)
            indeg[w] -= 1
            if indeg[w] == 0:
                queue.append(w)
    for i in ids:
        if indeg[i] > 0:
            layer[i] = max([layer[p] for p in preds[i]] + [0]) + 1
    return layer


def _order(rows, layer, edges, groups):
    """Group-clustered barycenter ordering, a few sweeps."""
    gid = {}
    for gi, g in enumerate(groups):
        for m in g["members"]:
            gid[m] = gi
    order = {r: sorted([i for i in layer if layer[i] == r],
                       key=lambda i: (gid.get(i, 99), i)) for r in rows}
    pos = {i: k for r in rows for k, i in enumerate(order[r])}
    neighbours = {}
    for e in edges:
        neighbours.setdefault(e["from"], []).append(e["to"])
        neighbours.setdefault(e["to"], []).append(e["from"])

    def sweep(rowlist):
        for r in rowlist:
            bary = []
            for i in order[r]:
                ns = [pos[n] for n in neighbours.get(i, []) if n in pos]
                bary.append(((sum(ns) / len(ns)) if ns else pos[i], gid.get(i, 99), pos[i], i))
            order[r] = [t[3] for t in sorted(bary, key=lambda t: (t[0], t[1], t[2]))]
            for k, i in enumerate(order[r]):
                pos[i] = k

    for _ in range(3):
        sweep(rows)
        sweep(list(reversed(rows)))
    return order


def place(spec):
    """spec -> layout dict {canvas, nodes, groups, edges, warnings}."""
    warns = []
    nodes, edges, groups = spec["nodes"], spec["edges"], spec.get("groups", [])
    layer = _layers(nodes, edges)
    if max(layer.values()) >= 5:
        for i in list(layer):
            if layer[i] >= 4:
                layer[i] = 3
        warns.append("图较深，已压缩到 4 行以内")
    rows = sorted(set(layer.values()))

    def prev_row(r):
        cand = [x for x in rows if x < r]
        return cand[-1] if cand else rows[0]

    order = _order(rows, layer, edges, groups)

    # ---- x placement ----
    bw = {n["id"]: _box_w(n["name"]) for n in nodes}
    cx = {}
    for r in rows:
        x = 0.0
        first = True
        for i in order[r]:
            if not first:
                x += max(GAP_X, bw[prev] / 2 + bw[i] / 2 + 24)
            cx[i] = x
            prev = i
            first = False
    width = max((cx[order[r][-1]] if order[r] else 0) for r in rows) if any(order.values()) else 0
    for r in rows:
        shift = (width - (cx[order[r][-1]] if order[r] else 0)) / 2
        for i in order[r]:
            cx[i] += shift
    W = max(940, int(width + 2 * MARGIN_X))
    for i in cx:
        cx[i] += MARGIN_X

    # ---- which horizontal lines share each physical gap (key = row above) ----
    # roles: adj (one-elbow between adjacent rows), u (same-row U-elbow below),
    #        in (multi-row source band, no label), out (multi-row target band)
    buckets = {}
    blocked_same_row = set()

    def reg(anchor, e, role, ox):
        buckets.setdefault(anchor, []).append((e, role, ox))

    for e in edges:
        s, t = e["from"], e["to"]
        diff = layer[t] - layer[s]
        if diff == 0:
            rowi = order[layer[s]]
            a, b = rowi.index(s), rowi.index(t)
            if rowi[min(a, b) + 1:max(a, b)]:
                blocked_same_row.add(id(e))
                reg(layer[s], e, "u", min(cx[s], cx[t]))
        elif diff == 1:
            reg(layer[s], e, "adj", min(cx[s], cx[t]))
        elif diff > 1:
            reg(layer[s], e, "in", cx[s])
            reg(prev_row(layer[t]), e, "out", cx[t])
        elif diff == -1:
            reg(layer[t], e, "adj", min(cx[s], cx[t]))
        else:
            reg(prev_row(layer[s]), e, "in", cx[s])
            reg(layer[t], e, "out", cx[t])

    # ---- row tops with adaptive spacing, then line y per (edge, role) ----
    line_map = {}
    top = {}
    row_top = {}
    y = ROW_TOP0
    for ri, r in enumerate(rows):
        row_top[r] = y
        for i in order[r]:
            top[i] = y
        if ri + 1 < len(rows):
            y += BASE_DY + LINE_STEP * max(0, len(buckets.get(r, [])) - 1)
    for g, lst in buckets.items():
        lst = sorted(lst, key=lambda t: t[2])
        for k, (e, role, ox) in enumerate(lst):
            line_map[(id(e), role)] = row_top[g] + BOX_H + 14 + k * LINE_STEP

    # ---- groups (bottom clipped above the next row's tiles) ----
    gboxes = []
    for g in groups:
        ms = [m for m in g["members"] if m in cx]
        if len(ms) < 2:
            continue
        last_row = max(layer[m] for m in ms)
        last_row_top = min(top[m] for m in ms if layer[m] == last_row)
        gbot = last_row_top + PAD_BOTTOM
        below = [row_top[r] for r in rows if row_top[r] > last_row_top]
        if below:
            gbot = min(gbot, below[0] - 10)
        gtop = min(top[m] for m in ms)
        gboxes.append({"name": g["name"], "icon": g.get("icon", ""), "members": ms,
                       "x": min(cx[m] - bw[m] / 2 for m in ms) - PAD_X,
                       "y": gtop - PAD_TOP,
                       "w": (max(cx[m] + bw[m] / 2 for m in ms) + PAD_X)
                            - (min(cx[m] - bw[m] / 2 for m in ms) - PAD_X),
                       "h": gbot - (gtop - PAD_TOP)})

    members = {m for gb in gboxes for m in gb["members"]}
    for n in nodes:
        i = n["id"]
        if i in members:
            continue
        for gb in gboxes:
            if (gb["x"] - 4 < cx[i] < gb["x"] + gb["w"] + 4
                    and gb["y"] < top[i] + BOX_H / 2 < gb["y"] + gb["h"]):
                cx[i] = gb["x"] + gb["w"] + max(60, bw[i] / 2 + 30)
                W = max(W, int(cx[i] + bw[i] / 2 + MARGIN_X))
                warns.append(f"节点 {n['name']} 移出分组框")

    # ---- corridors ----
    def occupied(r, extra_pad=8):
        return [(cx[i] - bw[i] / 2 - extra_pad, cx[i] + bw[i] / 2 + extra_pad)
                for i in order.get(r, [])]

    def free_corridor(r_rows, want, lo, hi):
        ivs = [(lo, hi)]
        for r in r_rows:
            nxt = []
            for a, b in ivs:
                cur = [(a, b)]
                for x0, x1 in occupied(r):
                    new = []
                    for ca, cb in cur:
                        if x1 <= ca or x0 >= cb:
                            new.append((ca, cb))      # box misses this piece: keep it
                        else:
                            if x0 > ca:
                                new.append((ca, x0))
                            if x1 < cb:
                                new.append((x1, cb))
                    cur = new
                nxt.extend(cur)
            ivs = [(a, b) for a, b in nxt if b - a >= 4]
            if not ivs:
                return None
        best = None
        for a, b in ivs:
            c = min(max(want, a), b)
            if best is None or abs(c - want) < abs(best - want):
                best = c
        return best

    # ---- routing ----
    W_box = [W]
    routed = []
    out_edges = {}
    for e in edges:
        out_edges.setdefault((e["from"], "down"), []).append(e)
        out_edges.setdefault((e["from"], "up"), []).append(e)

    def sx_for(e, s, direction):
        lst = out_edges.get((s, direction), [])
        return (cx[s] + STAGGERS[lst.index(e) % 3]) if len(lst) > 1 else cx[s]

    max_line_y = 0
    for e in edges:
        s, t = e["from"], e["to"]
        diff = layer[t] - layer[s]
        if diff == 0:
            if id(e) in blocked_same_row:
                ly = line_map[(id(e), "u")]
                d = f"M{cx[s]:.0f} {top[s] + BOX_H + 6} V{ly} H{cx[t]:.0f} V{top[t] + BOX_H + 12}"
                lab = ((cx[s] + cx[t]) / 2, ly + 16, "middle")
                max_line_y = max(max_line_y, ly + 26)
            else:
                yy = top[s] + 30
                if cx[s] < cx[t]:
                    d = f"M{cx[s] + TILE / 2 + 6:.0f} {yy} H{cx[t] - TILE / 2 - 6:.0f}"
                else:
                    d = f"M{cx[s] - TILE / 2 - 6:.0f} {yy} H{cx[t] + TILE / 2 + 6:.0f}"
                lab = ((cx[s] + cx[t]) / 2, yy - 8, "middle")
        elif diff == 1:
            ly = line_map[(id(e), "adj")]
            sx = sx_for(e, s, "down")
            d = f"M{sx:.0f} {top[s] + BOX_H + 6} V{ly} H{cx[t]:.0f} V{top[t] - 6}"
            if abs(cx[t] - sx) < 8:                      # straight vertical: label beside
                lab = (sx + 10, (top[s] + BOX_H + top[t]) / 2 + 4, "start")
            else:
                lab = ((min(sx, cx[t]) + abs(cx[t] - sx) / 2), ly + 16, "middle")
                max_line_y = max(max_line_y, ly + 26)
        elif diff == -1:
            ly = line_map[(id(e), "adj")]
            sx = sx_for(e, s, "up")
            d = f"M{sx:.0f} {top[s] - 6} V{ly} H{cx[t]:.0f} V{top[t] + BOX_H + 12}"
            if abs(cx[t] - sx) < 8:
                lab = (sx + 10, (top[s] + top[t] + BOX_H) / 2 + 4, "start")
            else:
                lab = ((min(sx, cx[t]) + abs(cx[t] - sx) / 2), ly + 16, "middle")
                max_line_y = max(max_line_y, ly + 26)
        else:
            down = diff > 1
            ly_in = line_map[(id(e), "in")]
            ly_out = line_map[(id(e), "out")]
            mid_rows = range(layer[s] + 1, layer[t]) if down else range(layer[t] + 1, layer[s])
            cor = free_corridor(list(mid_rows), (cx[s] + cx[t]) / 2,
                                MARGIN_X - 40, W_box[0] - MARGIN_X + 40)
            if cor is None:
                cor = W_box[0] + 80
                W_box[0] = int(cor + MARGIN_X * 0.9)
                warns.append("长边走画布右侧绕行")
            sx = sx_for(e, s, "down" if down else "up")
            if down:
                d = (f"M{sx:.0f} {top[s] + BOX_H + 6} V{ly_in} H{cor:.0f} V{ly_out} "
                     f"H{cx[t]:.0f} V{top[t] - 6}")
            else:
                d = (f"M{sx:.0f} {top[s] - 6} V{ly_in} H{cor:.0f} V{ly_out} "
                     f"H{cx[t]:.0f} V{top[t] + BOX_H + 12}")
            lab = ((cx[t] + cor) / 2, ly_out + 16, "middle")
            max_line_y = max(max_line_y, ly_out + 26)
        routed.append({"d": d, "kind": e["kind"], "label": e["label"], "label_pos": lab})

    # label collision nudge: (a) label vs label, (b) label vs other edges' lines
    def _segs(d):
        toks = re.findall(r"[MHVL]|-?\d+(?:\.\d+)?", d)
        x = y = 0.0
        pts = []
        i = 0
        while i < len(toks):
            t = toks[i]
            if t == "M":
                x, y = float(toks[i + 1]), float(toks[i + 2]); i += 3; pts = [(x, y)]
            elif t == "V":
                y = float(toks[i + 1]); i += 2; pts.append((x, y))
            elif t == "H":
                x = float(toks[i + 1]); i += 2; pts.append((x, y))
            elif t == "L":
                x, y = float(toks[i + 1]), float(toks[i + 2]); i += 3; pts.append((x, y))
            else:
                i += 1
        return list(zip(pts[:-1], pts[1:]))

    all_segs = [(i, _segs(e["d"])) for i, e in enumerate(routed)]

    def label_hits(idx, x, y, txt):
        w = _txt_w(txt) / 2 + 4
        l, r, t, b = x - w, x + w, y - 10, y + 3
        for j, segs in all_segs:                         # own line included: never sit on it
            for (x1, y1), (x2, y2) in segs:
                if min(x1, x2) - 1.5 <= r and max(x1, x2) + 1.5 >= l \
                        and min(y1, y2) - 1.5 <= b and max(y1, y2) + 1.5 >= t:
                    return True
        return False

    placed = []
    for idx, e in enumerate(routed):
        if not e["label"]:
            continue
        x, y, anchor = e["label_pos"]
        for (px, py) in placed:
            if abs(py - y) < 13 and abs(px - x) < (_txt_w(e["label"]) / 2 + 34):
                y += LINE_STEP
                break
        if label_hits(idx, x, y, e["label"]):
            for dx, dy in ((0, -14), (0, 15), (18, -14), (-18, -14), (0, LINE_STEP * 2)):
                if not label_hits(idx, x + dx, y + dy, e["label"]) and y + dy > 0:
                    x, y = x + dx, y + dy
                    break
        placed.append((x, y))
        e["label_pos"] = (x, y, anchor)
        max_line_y = max(max_line_y, y + 10)

    W = max(W, W_box[0])
    H = max(max_line_y, max(top.values()) + BOX_H) + 40
    for gb in gboxes:
        H = max(H, gb["y"] + gb["h"] + 30)
    return {"canvas": {"w": W, "h": H},
            "nodes": {n["id"]: {"cx": round(cx[n["id"]], 1), "top": top[n["id"]], "w": bw[n["id"]]}
                      for n in nodes},
            "groups": gboxes, "edges": routed, "warnings": warns}
