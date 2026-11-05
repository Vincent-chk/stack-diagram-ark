#!/usr/bin/env python3
"""Offline end-to-end test: stub specs through the full pipeline (no Ark call).

Usage: python3 test_stub.py    — writes PNG/HTML into ../test-out/ and prints
the deterministic check result for both stubs.
"""
import base64
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline                                            # noqa: E402

OUT = HERE.parent.parent / "test-out"
OUT.mkdir(exist_ok=True)

STUBS = {
    "stub-gongzhonghao": {
        "title": "公众号行业简报流水线",
        "lede": "每天早上，Seed 2.1 读行业新闻生成简报，先发公众号再推飞书群",
        "nodes": [
            {"id": "user", "name": "读者", "role": "公众号关注者", "icon": "user"},
            {"id": "wechat", "name": "公众号", "role": "内容发布", "icon": "wechat"},
            {"id": "web", "name": "Next.js", "role": "官网与后台", "icon": "nextjs"},
            {"id": "cron", "name": "每日 8 点", "role": "定时任务", "icon": "cron"},
            {"id": "ark", "name": "火山方舟 Seed 2.1", "role": "生成简报", "icon": "ark"},
            {"id": "feishu", "name": "飞书群", "role": "推送", "icon": "feishu"},
        ],
        "groups": [],
        "edges": [
            {"from": "user", "to": "wechat", "label": "阅读", "kind": "primary"},
            {"from": "cron", "to": "ark", "label": "触发", "kind": "dev"},
            {"from": "ark", "to": "web", "label": "写草稿", "kind": "internal"},
            {"from": "web", "to": "wechat", "label": "发布", "kind": "primary"},
            {"from": "web", "to": "feishu", "label": "每日推送", "kind": "dev"},
        ],
    },
    "stub-hero": {
        "title": "Next.js + Hono on Vercel",
        "lede": "Next.js with a Hono API on Vercel; Neon Postgres, Clerk sessions, Stripe checkout",
        "nodes": [
            {"id": "user", "name": "User", "role": "browser", "icon": "user"},
            {"id": "web", "name": "Next.js", "role": "frontend", "icon": "nextjs"},
            {"id": "api", "name": "Hono", "role": "http api", "icon": "hono"},
            {"id": "ci", "name": "GitHub Actions", "role": "ci", "icon": "githubactions"},
            {"id": "db", "name": "Neon", "role": "postgres", "icon": "neon"},
            {"id": "auth", "name": "Clerk", "role": "sessions", "icon": "clerk"},
            {"id": "pay", "name": "Stripe", "role": "payments", "icon": "stripe"},
        ],
        "groups": [{"name": "Vercel", "icon": "vercel", "members": ["web", "api"]}],
        "edges": [
            {"from": "user", "to": "web", "label": "HTTPS", "kind": "primary"},
            {"from": "web", "to": "api", "label": "RPC", "kind": "primary"},
            {"from": "api", "to": "db", "label": "SQL", "kind": "primary"},
            {"from": "api", "to": "auth", "label": "sessions", "kind": "internal"},
            {"from": "api", "to": "pay", "label": "checkout", "kind": "internal"},
            {"from": "ci", "to": "web", "label": "deploy", "kind": "dev"},
        ],
    },
}


def main():
    failures = 0
    for name, spec in STUBS.items():
        try:
            r = pipeline.generate("(stub sentence)", stub_spec=spec)
        except Exception as e:                                        # noqa: BLE001
            print(f"[{name}] PIPELINE FAIL {type(e).__name__}: {e}")
            failures += 1
            continue
        if r["png"]:
            (OUT / f"{name}.png").write_bytes(base64.b64decode(r["png"]))
        if r["png_dark"]:
            (OUT / f"{name}-dark.png").write_bytes(base64.b64decode(r["png_dark"]))
        (OUT / f"{name}.html").write_text(r["html"], encoding="utf-8")
        ck = r["check"]
        print(f"[{name}] check_passed={ck['passed']} "
              f"violations={len(ck['light']) + len(ck['dark'])} "
              f"stages={r['meta']['stages']} warnings={r['warnings']} notes={r['notes']}")
        if not ck["passed"]:
            failures += 1
            print("   ", ck["light"][:4], ck["dark"][:4])
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
