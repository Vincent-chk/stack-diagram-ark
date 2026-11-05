#!/usr/bin/env python3
"""Build the three extra article figures: icon contact sheet, thinking-comparison
chart (matplotlib magazine style), bench collage. Run from anywhere; writes to
docs/figs/."""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent      # repo/ark
PROJECT = HERE.parent.parent                        # stack-diagram-ark/
FIGS = PROJECT / "docs" / "figs"
VOLC = HERE.parent / "skills" / "stack-diagram" / "assets" / "volc"
BENCH = PROJECT / "test-out" / "bench"

STYLE = """
body { margin:0; padding:28px; background:#fafbfc;
  font-family:"PingFang SC","Noto Sans SC",-apple-system,sans-serif; }
.grid { display:grid; grid-template-columns:repeat(3, 132px); gap:18px; }
.tile { background:#fff; border:1px solid #d8dee8; border-radius:12px;
  padding:16px 10px 12px; text-align:center;
  box-shadow:0 1px 2px rgba(36,42,64,.06); }
.tile img { width:48px; height:48px; object-fit:contain; }
.name { font-size:14px; font-weight:600; color:#2a3142; margin-top:8px; }
.src  { font-size:10.5px; color:#8a94a8; margin-top:2px; }
.kicker { font-size:11px; font-family:ui-monospace,Menlo,monospace; color:#3b6fd4;
  margin-bottom:14px; letter-spacing:.05em; }
"""


def sheet():
    tiles = [
        ("volcengine", "火山引擎", "官网 favicon"),
        ("doubao", "豆包", "官网 favicon"),
        ("coze", "扣子", "App Store"),
        ("trae", "TRAE", "官网 favicon"),
        ("feishu", "飞书", "官网 og:image"),
        ("wechat", "微信", "App Store"),
        ("douyin", "抖音", "App Store"),
        ("xiaohongshu", "小红书", "App Store"),
        ("cron", "定时任务", "Lucide 描线"),
    ]
    cells = "".join(
        f'<div class="tile"><img src="file://{VOLC}/{f}.{ext}"><div class="name">{n}</div>'
        f'<div class="src">{s}</div></div>'
        for f, n, s, ext in [(a, b, c, {"volcengine": "png", "doubao": "png", "coze": "jpg",
                                        "trae": "png", "feishu": "png", "wechat": "jpg",
                                        "douyin": "jpg", "xiaohongshu": "jpg", "cron": "svg"}[a])
                             for a, b, c in tiles])
    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{STYLE}</style></head>" \
           f"<body><div class='kicker'>volc icon pack / 9 marks / official sources</div>" \
           f"<div class='grid'>{cells}</div></body></html>"
    p = FIGS / "_icons.html"
    p.write_text(html, encoding="utf-8")
    return p


def collage():
    picks = ["01-公众号简报", "04-课程制作", "05-简历EN",
             "09-抖音内容流水线", "13-一稿多发", "20-三号运营"]
    cells = "".join(
        f'<div class="cell"><img src="file://{BENCH}/{n}.png"><div class="cap">{n.split("-", 1)[1]}</div></div>'
        for n in picks)
    css = STYLE + """
    .grid { grid-template-columns:repeat(3, 360px); gap:16px; }
    .cell { background:#fff; border:1px solid #e2e7ef; border-radius:10px; padding:10px; }
    .cell img { width:100%; border:1px solid #edf0f5; border-radius:6px; display:block; }
    .cap { font-size:12.5px; color:#5a6478; margin-top:8px; text-align:center; }
    """
    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head>" \
           f"<body><div class='kicker'>bench / 6 of 20 real runs / lite · no-thinking</div>" \
           f"<div class='grid'>{cells}</div></body></html>"
    p = FIGS / "_bench.html"
    p.write_text(html, encoding="utf-8")
    return p


def shoot(html_path, out_path, w, h):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"])
        page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        page.goto(html_path.resolve().as_uri())
        page.wait_for_timeout(400)
        page.screenshot(path=str(out_path), full_page=True)
        b.close()


def chart():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Arial Unicode MS", "STHeiti", "Heiti TC"]
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.9), dpi=150)
    data = [("单次延迟（秒）", [("开思考", 47, "38–56s"), ("关思考", 5.25, "4.1–6.4s")], 60),
            ("输出 tokens / 句", [("开思考", 3224, "2679–3768"), ("关思考", 418, "252–530")], 4200)]
    for ax, (title, bars, ymax) in zip(axes, data):
        xs = range(len(bars))
        vals = [b[1] for b in bars]
        colors = ["#c3cbd9", "#3b6fd4"]
        ax.bar(xs, vals, width=0.5, color=colors, zorder=3)
        for x, (label, v, rng) in zip(xs, bars):
            ax.text(x, v + ymax * 0.03, rng, ha="center", va="bottom",
                    fontsize=9.5, color="#2a3142")
        ax.set_xticks(list(xs))
        ax.set_xticklabels([b[0] for b in bars], fontsize=10.5)
        ax.set_title(title, fontsize=11, color="#2a3142", pad=8)
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", color="#e6eaf1", zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#c9d1de")
        ax.tick_params(colors="#5a6478", labelsize=9)
    fig.tight_layout(pad=1.2)
    fig.savefig(FIGS / "fig4-thinking.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    FIGS.mkdir(parents=True, exist_ok=True)
    shoot(sheet(), FIGS / "fig3-icons.png", 500, 620)
    shoot(collage(), FIGS / "fig8-bench-grid.png", 1180, 900)
    chart()
    print("figures done")
