#!/usr/bin/env python3
"""M3c bench: 20 sentences through the real pipeline, artifacts to test-out/bench/.

Usage: ARK_API_KEY=... python3 bench.py
Writes a markdown results table to ../docs/M3c-实测20句.md
"""
import base64
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline                                            # noqa: E402

OUT = HERE.parent.parent / "test-out" / "bench"
OUT.mkdir(parents=True, exist_ok=True)
DOCS = HERE.parent.parent.parent / "docs"
DOCS.mkdir(exist_ok=True)

SENTENCES = [
    ("公众号简报", "我做了个公众号：Next.js 部署在 Vercel，AI 用火山方舟的 Seed 2.1 每天早上生成行业简报，自动推送到飞书群。"),
    ("小店客服", "我开了个网店，用扣子搭了个客服机器人回答售后问题，机器人调用豆包大模型，聊天记录同步到飞书多维表格。"),
    ("私活官网", "给客户做了个官网：前端 Next.js 放在火山引擎，后端 FastAPI，数据库用 PostgreSQL，图片存对象存储 TOS。"),
    ("课程制作", "我做付费课程：文案用豆包生成，配音用火山引擎语音合成，视频剪好后发到抖音和小红书，学员群在飞书。"),
    ("简历EN", "My side project: Next.js on Vercel, API in Hono, Postgres on Neon, auth with Clerk, payments with Stripe."),
    ("文档机器人EN", "Docs chatbot: Next.js on Vercel searches Supabase pgvector and answers with Ark Seed 2.1. Feishu docs synced nightly."),
    ("仓库工具链EN", "Draw our monorepo tooling: a pnpm workspace with Turborepo, Biome, Vitest and Lefthook. GitHub Actions runs CI and publishes to npm."),
    ("飞书审批机器人", "我们团队在飞书上做了个审批机器人，逻辑跑在火山方舟上，审批数据存 PostgreSQL，超时未处理会推送给主管。"),
    ("抖音内容流水线", "我做抖音号：脚本用豆包写，配音用火山引擎语音，剪好的视频定时发抖音，评论区关键词由扣子机器人自动回复。"),
    ("电商小程序", "小店的微信小程序：前端用微信小程序，后端 Node.js 放火山引擎，商品数据在 MySQL，订单通知推到企业微信群。"),
    ("运营看板", "运营每天要看数据：飞书多维表格记录订单，Python 脚本每小时拉一次汇总成图表，异常时用飞书机器人提醒。"),
    ("播客制作", "我录播客：录音用手机，转写用火山引擎语音识别，豆包整理成文字稿，成片发到抖音。"),
    ("一稿多发", "写完一篇文章，想让它在公众号、知乎、小红书各发一版：豆包负责改写文风，改好的稿子存飞书文档，我手动发布。"),
    ("民宿管家", "我家民宿的智能管家：客人通过微信小程序下单，扣子机器人回答入住问题，开锁密码通过飞书发给保洁阿姨。"),
    ("内部知识库", "公司内部知识库：文档都在飞书，扣子搭了个问答机器人，回答不上来的问题转给人工，人工答案再喂回豆包总结。"),
    ("客服质检", "电商客服团队的管理看板：聊天记录从飞书导出，豆包每天晚上抽查服务质量，打分结果存 PostgreSQL 供主管查看。"),
    ("留学助手", "留学申请小工具：学生把简历传到网页上，火山方舟抽取经历亮点，生成文书初稿，老师在飞书里批注。"),
    ("健身餐订阅", "健身餐订阅：用户在微信小程序下单，菜单每周由豆包按营养目标生成，采购单自动发到飞书群。"),
    ("AWS英文", "Our stack on AWS: CloudFront in front of S3, an ALB in a public subnet, Fargate and RDS in a private subnet. GitHub Actions deploys."),
    ("三号运营", "我同时运营三个号：公众号文章用豆包润色，抖音视频用火山引擎语音配音，小红书笔记配图用 Seedream 生成，所有排期在飞书日历上。"),
]


def main():
    rows, ok_count, check_ok = [], 0, 0
    tot_in = tot_out = 0
    t_all = time.time()
    for i, (name, sent) in enumerate(SENTENCES, 1):
        t0 = time.time()
        try:
            r = pipeline.generate(sent, quality="lite")
        except Exception as e:                                        # noqa: BLE001
            rows.append((i, name, 0, 0, 0, "FAIL", 0, 0, 0, str(e)[:60]))
            print(f"[{i:02d} {name}] FAIL {str(e)[:90]}", flush=True)
            continue
        m = r["meta"]
        ok_count += 1
        ck = "✓" if r["check"]["passed"] else "△"
        if r["check"]["passed"]:
            check_ok += 1
        u = m.get("usage", {})
        tot_in += u.get("prompt_tokens", 0)
        tot_out += u.get("completion_tokens", 0)
        if r["png"]:
            (OUT / f"{i:02d}-{name}.png").write_bytes(base64.b64decode(r["png"]))
        if r["png_dark"]:
            (OUT / f"{i:02d}-{name}-dark.png").write_bytes(base64.b64decode(r["png_dark"]))
        (OUT / f"{i:02d}-{name}.html").write_text(r["html"], encoding="utf-8")
        n_viol = len(r["check"]["light"]) + len(r["check"]["dark"])
        rows.append((i, name, len(r["spec"]["nodes"]), len(r["spec"]["edges"]),
                     len(r["spec"].get("groups", [])), ck, m["total"],
                     u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                     f"{n_viol}viol;" + ";".join((r["warnings"] + r["notes"])[:2])[:70]))
        print(f"[{i:02d} {name}] {ck} {m['total']}s nodes={len(r['spec']['nodes'])} "
              f"viol={n_viol} stages={m['stages']}", flush=True)
    wall = time.time() - t_all

    lines = ["# M3c 实测：20 句真实生成（lite / 关思考 / 订阅套餐端点）", "",
             f"- 生成成功 {ok_count}/20，确定性自查通过 {check_ok}/{ok_count}",
             f"- 总耗时 {wall:.0f}s，平均 {wall / 20:.1f}s/句（含图标缓存冷启动）",
             f"- tokens 合计 in={tot_in} out={tot_out}，按量等价成本 ¥{tot_in / 1e6 * 0.8 + tot_out / 1e6 * 2.7:.4f}（订阅套餐内边际成本为 0）", "",
             "| # | 场景 | 节点/边/组 | 自查 | 总耗时s | tok in/out | 备注 |",
             "|---|---|---|---|---|---|---|"]
    for (i, name, n, e, g, ck, tot, ti, to, note) in rows:
        lines.append(f"| {i:02d} | {name} | {n}/{e}/{g} | {ck} | {tot} | {ti}/{to} | {note} |")
    (DOCS / "M3c-实测20句.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport -> {DOCS / 'M3c-实测20句.md'}")


if __name__ == "__main__":
    main()
