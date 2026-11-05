#!/usr/bin/env python3
"""Deterministic layout engine — coordinates, group boxes, orthogonal routing.

The model only decides content (nodes/groups/edges); every pixel here follows
the constants from the skill's references/geometry.md:
  node box ~132x100 (tile 60, name at +68, role at +86)
  >=140px between centers in a row; row spacing grows with how many routed
  lines share the gap (30px per extra line); group boxes padded 24/60/150 and
  clipped above the next row's tiles.
Edges spanning several rows route through an x-corridor verified free of node
boxes in every intermediate row. Horizontal segments keep clear of group-label
corners (geometry.md: "keep edges out of that corner"). Foreign nodes caught
inside a group box are re-packed to whichever side has room (polish: no more
always-right exile), and same-row members of a group are made contiguous so
boxes stay narrow in the first place.
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


def _label_rects(gboxes):
    """Top-left corner label zone of each group box (geometry.md keeps edges
    out of it). Width estimate: icon 14 + gap + 12px display text, padded —
    underestimating here would let an entry edge drop through the label."""
    rects = []
    for gb in gboxes:
        w = (20 if gb.get("icon") else 0) + _txt_w(gb["name"]) * 1.1 + 16
        rects.append({"x0": gb["x"] + 12, "x1": gb["x"] + 12 + w,
                      "y0": gb["y"] + 12, "y1": gb["y"] + 32, "name": gb["name"]})
    return rects


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


def _make_contiguous(order, rows, groups, up_entries):
    """Post-pass: same-row members of a group become one block, so group boxes
    stay narrow and foreign nodes between members (the classic push-out
    trigger) disappear. Foreign nodes caught between move to the nearer end.
    Inside a block, members WITHOUT an entering edge from above go leftmost:
    the group label lives in the top-left corner, and a member with an entry
    edge under it would drop a vertical segment straight through the label."""
    gid = {}
    for gi, g in enumerate(groups):
        for m in g["members"]:
            gid[m] = gi
    for r in rows:
        row = order[r]
        by_group = {}
        for k, i in enumerate(row):
            if i in gid:
                by_group.setdefault(gid[i], []).append(k)
        for gi, ks in by_group.items():
            if len(ks) < 2:
                continue
            lo, hi = min(ks), max(ks)
            inside = row[lo:hi + 1]
            foreigners = [i for i in inside if gid.get(i) != gi]
            if not foreigners:
                # still reorder the block itself (label-safe leftmost)
                block = sorted((i for i in inside if gid.get(i) == gi),
                               key=lambda i: 1 if i in up_entries else 0)
                if block != inside:
                    order[r] = row[:lo] + block + row[hi + 1:]
                    row = order[r]
                continue
            block = sorted((i for i in inside if gid.get(i) == gi),
                           key=lambda i: 1 if i in up_entries else 0)
            rest_head, rest_tail = row[:lo], row[hi + 1:]
            left_load = sum(1 for _ in rest_head)
            right_load = sum(1 for _ in rest_tail)
            newrow = (rest_head + block + foreigners + rest_tail if left_load <= right_load
                      else rest_head + foreigners + block + rest_tail)
            order[r] = newrow
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

    def next_row_top(g):
        idx = rows.index(g)
        return row_top[rows[idx + 1]] if idx + 1 < len(rows) else None

    order = _order(rows, layer, edges, groups)
    up_entries = {e["to"] for e in edges if layer[e["to"]] - layer[e["from"]] >= 1}
    order = _make_contiguous(order, rows, groups, up_entries)

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
    labels = _label_rects(gboxes)

    # ---- foreign nodes caught in a group box: repack to the roomier side ----
    members = {m for gb in gboxes for m in gb["members"]}
    for n in nodes:
        i = n["id"]
        if i in members:
            continue
        for gb in gboxes:
            if not (gb["x"] - 4 < cx[i] < gb["x"] + gb["w"] + 4
                    and gb["y"] < top[i] + BOX_H / 2 < gb["y"] + gb["h"]):
                continue
            need = max(60, bw[i] / 2 + 30)
            # left side: squeeze into the gap between the box edge and the
            # nearest node to the left on this row
            left_prev = max((cx[j] + bw[j] / 2 for j in order[layer[i]]
                             if cx[j] < cx[i] and j not in members), default=MARGIN_X * 0.2)
            left_room = gb["x"] - 8 - left_prev
            # right side: nearest node to the right
            right_next = min((cx[j] - bw[j] / 2 for j in order[layer[i]]
                              if cx[j] > cx[i]), default=None)
            right_room = None if right_next is None else right_next - (gb["x"] + gb["w"]) - 8
            placed = False
            if left_room >= bw[i] + 24:
                cx[i] = left_prev + 12 + bw[i] / 2
                placed = True
            elif right_room is None or right_room >= bw[i] + 24:
                cx[i] = gb["x"] + gb["w"] + need
                W = max(W, int(cx[i] + bw[i] / 2 + MARGIN_X))
                placed = True
            else:
                cx[i] = gb["x"] + gb["w"] + need
                W = max(W, int(cx[i] + bw[i] / 2 + MARGIN_X))
                placed = True
            if placed:
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
                            new.append((ca, cb))
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

    def dodge_group_label(x0, x1, ly, ceiling, drop_x=None):
        """Push a horizontal segment below any group-label corner it crosses —
        either because the segment itself runs through the label zone, or
        because its final vertical drop (at drop_x) would fall through the
        label on the way to the target tile. ceiling: y the segment must stay
        above (target tile top - 12)."""
        for rect in labels:
            h_hit = rect["x0"] - 2 <= x1 and rect["x1"] + 2 >= x0 \
                and rect["y0"] - 2 <= ly <= rect["y1"] + 2
            v_hit = (drop_x is not None and rect["x0"] - 2 <= drop_x <= rect["x1"] + 2
                     and ly < rect["y0"] and rect["y1"] < ceiling)
            if h_hit or v_hit:
                cand = rect["y1"] + 8
                if cand < ceiling:
                    return cand
        return ly

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
                ntop = next_row_top(layer[s])
                if ntop is not None:
                    ly = min(ly, ntop - 46)
                x0, x1 = sorted((cx[s], cx[t]))
                ly = dodge_group_label(x0, x1, ly, (ntop - 12) if ntop is not None else ly + 1)
                d = f"M{cx[s]:.0f} {top[s] + BOX_H + 6} V{ly} H{cx[t]:.0f} V{top[t] + BOX_H + 12}"
                below_label = ly + 16
                if ntop is not None and below_label + 10 > ntop - 4:
                    lab = ((cx[s] + cx[t]) / 2, ly - 8, "middle")
                else:
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
            ntop = next_row_top(layer[s])
            x0, x1 = sorted((sx, cx[t]))
            if ntop is not None:
                ly = dodge_group_label(x0, x1, ly, ntop - 12, drop_x=cx[t])
            d = f"M{sx:.0f} {top[s] + BOX_H + 6} V{ly} H{cx[t]:.0f} V{top[t] - 6}"
            if abs(cx[t] - sx) < 8:
                lab = (sx + 10, (top[s] + BOX_H + top[t]) / 2 + 4, "start")
            else:
                below_label = ly + 16
                if ntop is not None and below_label + 10 > ntop - 4:
                    lab = ((x0 + x1) / 2, ly - 8, "middle")
                else:
                    lab = ((x0 + x1) / 2, ly + 16, "middle")
                max_line_y = max(max_line_y, ly + 26)
        elif diff == -1:
            ly = line_map[(id(e), "adj")]
            sx = sx_for(e, s, "up")
            x0, x1 = sorted((sx, cx[t]))
            # the gap above layer[t]'s row: its ceiling is row_top of s minus 12
            ly = dodge_group_label(x0, x1, ly, top[s] - 12)
            d = f"M{sx:.0f} {top[s] - 6} V{ly} H{cx[t]:.0f} V{top[t] + BOX_H + 12}"
            if abs(cx[t] - sx) < 8:
                lab = (sx + 10, (top[s] + top[t] + BOX_H) / 2 + 4, "start")
            else:
                lab = ((x0 + x1) / 2, ly + 16, "middle")
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
                x0, x1 = sorted((cor, cx[t]))
                ly_out = dodge_group_label(x0, x1, ly_out, top[t] - 12, drop_x=cx[t])
                d = (f"M{sx:.0f} {top[s] + BOX_H + 6} V{ly_in} H{cor:.0f} V{ly_out} "
                     f"H{cx[t]:.0f} V{top[t] - 6}")
            else:
                x0, x1 = sorted((cor, cx[t]))
                ly_out = dodge_group_label(x0, x1, ly_out, top[t] + BOX_H + 12 + 1)
                d = (f"M{sx:.0f} {top[s] - 6} V{ly_in} H{cor:.0f} V{ly_out} "
                     f"H{cx[t]:.0f} V{top[t] + BOX_H + 12}")
            lab = ((x0 + x1) / 2, ly_out + 16, "middle")
            max_line_y = max(max_line_y, ly_out + 26)
        routed.append({"d": d, "kind": e["kind"], "label": e["label"], "label_pos": lab})

    # ---- label placement: grid search for a spot hitting no line and no label rect ----
    def _segs(d):
        toks = re.findall(r"[MHVL]|-?\d+(?:\.\d+)?", d)
        x = y = 0.0
        pts = []
        i = 0
        while i < len(toks):
            tok = toks[i]
            if tok == "M":
                x, y = float(toks[i + 1]), float(toks[i + 2])
                i += 3
                pts = [(x, y)]
            elif tok == "V":
                y = float(toks[i + 1]); i += 2; pts.append((x, y))
            elif tok == "H":
                x = float(toks[i + 1]); i += 2; pts.append((x, y))
            elif tok == "L":
                x, y = float(toks[i + 1]), float(toks[i + 2]); i += 3; pts.append((x, y))
            else:
                i += 1
        return list(zip(pts[:-1], pts[1:]))

    all_segs = [(i, _segs(e["d"])) for i, e in enumerate(routed)]

    def spot_hits(idx, x, y, txt):
        w = _txt_w(txt) / 2 + 4
        l, rr, t, b = x - w, x + w, y - 10, y + 3
        for j, segs in all_segs:
            for (x1, y1), (x2, y2) in segs:
                if min(x1, x2) - 1.5 <= rr and max(x1, x2) + 1.5 >= l \
                        and min(y1, y2) - 1.5 <= b and max(y1, y2) + 1.5 >= t:
                    return True
        for rect in labels:
            if rect["x0"] - 2 <= rr and rect["x1"] + 2 >= l \
                    and rect["y0"] - 2 <= b and rect["y1"] + 2 >= t:
                return True
        return False

    placed = []
    for idx, e in enumerate(routed):
        if not e["label"]:
            continue
        x, y, anchor = e["label_pos"]
        if anchor != "start":
            for (px, py) in placed:
                if abs(py - y) < 13 and abs(px - x) < (_txt_w(e["label"]) / 2 + 34):
                    y += LINE_STEP
                    break
        if spot_hits(idx, x, y, e["label"]):
            found = False
            for dy in (16, -14, 30, -28, 46, -42, 60, 76):
                for dx in (0, 18, -18, 36, -36, 54, -54, 72, -72):
                    if y + dy > 0 and not spot_hits(idx, x + dx, y + dy, e["label"]):
                        x, y = x + dx, y + dy
                        found = True
                        break
                if found:
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
