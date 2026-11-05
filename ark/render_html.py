#!/usr/bin/env python3
"""spec + layout -> diagram HTML (template.html based, %%ICON_%% tokens for build.py)."""
import html
import pathlib
import re

SKILL_ASSETS = pathlib.Path(__file__).resolve().parent.parent / "skills" / "stack-diagram" / "assets"
GENERIC = {"user", "browser", "internet", "device", "server"}

EXTRA_CSS = """
.mono-mark { font-family: var(--font-display); font-weight: 700; font-size: 22px;
  color: var(--color-ink-2); line-height: 60px; }
"""

CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def _clean_template(tpl):
    """Strip the template's sample groups/edges/nodes, keep skeleton + comments."""
    # sample edge paths + their labels (inside svg.edges, after </defs>)
    tpl = re.sub(r'[ \t]*<path class="(?:e|n(?: dash)?)" d="M\d[^"]*" marker-end="url\(#ar\)"/>\n?', "", tpl)
    tpl = re.sub(r'[ \t]*<text class="el(?: a)?" x="\d+" y="\d+" text-anchor="middle">[^<]*</text>\n?', "", tpl)
    # sample groups (between the GROUPS comment and the EDGES comment)
    tpl = re.sub(r"(    <!-- GROUPS [=a-z ]*-->).*?\n\n    <!-- EDGES",
                 r"\1\n\n    <!-- EDGES", tpl, flags=re.S)
    # sample nodes (between the NODES comment and the closing canvas/scroller)
    tpl = re.sub(r"(    <!-- NODES [=a-z ]*-->).*?\n  </div>\n  </div>",
                 r"\1\n  </div>\n  </div>", tpl, flags=re.S)
    return tpl


def render(spec, lay, icon_meta):
    """icon_meta: {slug: {"plate": bool, "dark": str|None, "credit": str}}."""
    zh = any(CJK.search(n["name"]) or CJK.search(n["role"]) for n in spec["nodes"])
    tpl = _clean_template((SKILL_ASSETS / "template.html").read_text(encoding="utf-8"))

    title = html.escape(spec["title"])
    lede = html.escape(spec["lede"]) or "一句话生成的技术栈架构图"
    kicker = "stack-diagram / ark / Seed 2.1"
    W, H = lay["canvas"]["w"], lay["canvas"]["h"]

    groups_html = []
    for i, g in enumerate(lay["groups"]):
        cls = "ga" if i % 2 == 0 else "gb"
        icon = g.get("icon") or ""
        im = ""
        if icon and icon in icon_meta:
            meta = icon_meta[icon]
            if meta.get("dark"):
                im = (f'<img class="lt" src="%%ICON_{icon}%%" alt="">'
                      f'<img class="dk" src="%%ICON_{meta["dark"]}%%" alt="">')
            else:
                c = ' class="plate"' if meta.get("plate") else ""
                im = f'<img{c} src="%%ICON_{icon}%%" alt="">'
        groups_html.append(
            f'    <div class="group {cls}" style="left:{g["x"]:.0f}px; top:{g["y"]:.0f}px; '
            f'width:{g["w"]:.0f}px; height:{g["h"]:.0f}px;">\n'
            f'      <div class="g-label">{im}{html.escape(g["name"])}</div>\n    </div>')

    edges_html = []
    for e in lay["edges"]:
        cls = {"primary": "e", "internal": "n", "dev": "n dash"}[e["kind"]]
        x, y, anchor = e["label_pos"]
        lab = ""
        if e["label"]:
            a = "a" if e["kind"] == "primary" else ""
            lab = (f'\n      <text class="el {a}" x="{x:.0f}" y="{y:.0f}" '
                   f'text-anchor="{anchor}">{html.escape(e["label"])}</text>')
        edges_html.append(f'      <path class="{cls}" d="{e["d"]}" marker-end="url(#ar)"/>{lab}')

    nodes_html = []
    for n in spec["nodes"]:
        p = lay["nodes"][n["id"]]
        w = p["w"]
        style = f'left:{p["cx"] - w / 2:.0f}px; top:{p["top"]}px; width:{w}px'
        icon = n["icon"]
        if icon in GENERIC:
            tile = f'<div class="tile"><img src="%%ICON_{icon}%%" alt=""></div>'
        elif icon and icon in icon_meta:
            tile = f'<div class="tile"><img src="%%ICON_{icon}%%" alt=""></div>'
        else:
            mark = html.escape((n["name"] or "?").strip()[:1].upper())
            tile = f'<div class="tile"><div class="mono-mark">{mark}</div></div>'
        nodes_html.append(
            f'    <div class="node" style="{style}">\n      {tile}\n'
            f'      <div class="name"><span>{html.escape(n["name"])}</span></div>'
            f'<div class="role"><span>{html.escape(n["role"])}</span></div>\n    </div>')

    legend = ([("请求链路", ""), ("内部调用", "n"), ("构建 / 部署", "n dash")] if zh else
              [("request path", ""), ("internal", "n"), ("dev / deploy", "n dash")])
    legend_html = "".join(
        f'<span><span class="sw {c}"></span>{t}</span>' for t, c in legend)
    foot_left = "made with Ark Seed 2.1 + stack-diagram (MIT, ark fork)"
    icons_credit = " · ".join(sorted({m.get("credit", "svgl") for m in icon_meta.values()})) or "generic"

    out = tpl
    out = out.replace('<html lang="en">', f'<html lang="{ "zh-CN" if zh else "en" }">')
    out = out.replace("<!-- TITLE -->", title)
    out = out.replace("<!-- KICKER: e.g. stack-diagram / author / 2026-08 -->", kicker)
    out = out.replace("<!-- LEDE: 1-2 short sentences, or delete this <p> -->", lede)
    out = out.replace("width: 1000px; height: 540px;", f"width: {W}px; height: {H}px;")
    out = out.replace('<svg class="edges" viewBox="0 0 1000 540"',
                      f'<svg class="edges" viewBox="0 0 {W} {H}"')
    out = out.replace("svg.edges { position:absolute; inset:0; width:1000px; height:540px;",
                      f"svg.edges {{ position:absolute; inset:0; width:{W}px; height:{H}px;")
    # insert content before the structural anchors
    out = out.replace("    <!-- EDGES", "\n".join(groups_html) + "\n\n    <!-- EDGES", 1)
    out = out.replace("  </svg>", "\n".join(edges_html) + "\n  </svg>", 1)
    out = out.replace("\n  </div>\n  </div>", "\n" + "\n".join(nodes_html) + "\n  </div>\n  </div>", 1)
    out = out.replace("</style>", EXTRA_CSS + "</style>")
    out = out.replace("<span><!-- FOOT-LEFT: author / one-liner --></span>", f"<span>{foot_left}</span>")
    out = out.replace('<span><!-- FOOT-RIGHT: icon sources actually used, from manifest.json, '
                      'e.g. "icons: svgl / devicon / Lucide" -->',
                      f"<span>icons: {icons_credit}")
    # legend: replace the three sample spans with localized ones
    out = re.sub(r'<div class="legend">.*?</div>', f'<div class="legend">{legend_html}</div>', out, flags=re.S)
    return out
