#!/usr/bin/env python3
"""M0 probe: can Seed 2.1 lite turn one sentence into a valid diagram spec?

Runs 5 sentences (3 EN-ecosystem, 2 Chinese volcano-stack) through the Ark
chat API and reports parse/validate results, latency and token usage.

Usage: ARK_API_KEY=... python3 probe_ark.py [model]
"""
import json, re, sys, time

import ark_client

SYSTEM_PROMPT = """You convert a one-sentence description of someone's tech stack into a JSON diagram spec. Output ONLY valid JSON — no markdown fence, no commentary — matching exactly:
{
 "title": string,
 "lede": string,
 "nodes": [{"id": string, "name": string, "role": string, "icon": string}],
 "groups": [{"name": string, "icon": string, "members": [string]}],
 "edges": [{"from": string, "to": string, "label": string, "kind": "primary"|"internal"|"dev"}]
}
Rules:
- ids: short lowercase ascii slugs (web, api, db, bot); unique; used by edges/groups.
- name: the official product name as the user wrote it (Next.js, 火山方舟, 飞书); keep it short.
- role: 1-3 lowercase words for the part it plays (http api, postgres, 客服机器人).
- icon: MUST be one of the slugs in KNOWN ICONS below, or "" when unsure. Never invent a slug.
- The human participant is a node with id "user", icon "user" (读者/店主/客户 as its name).
- groups only when nodes share a runtime/vendor/platform (a deployment, a monorepo, a cloud). Every node in at most one group. group icon: a KNOWN ICONS slug or "".
- edges carry the real request/data flow. kind "primary" = the one main user-visible chain; "internal" = secondary calls; "dev" = CI / deploy / scheduled jobs. label: 1-2 short words (HTTPS, 每日推送, deploys).
- Scheduled jobs (e.g. "every morning at 8") are a node with icon "cron" and an edge to what they drive, kind "dev".
- At most 14 nodes; fewer is better. Include what the user said — do not pad with invented services.
KNOWN ICONS: user cron volcengine ark doubao coze trae feishu wechat douyin xiaohongshu hiagent agentkit nextjs vercel netlify cloudflare aws gcp azure githubactions github gitlab docker kubernetes postgresql mysql redis mongodb sqlite neon supabase hono fastapi django flask spring nodejs python go rust react vue svelte tailwindcss nginx openai anthropic gemma"""

SENTENCES = [
    "EN-hero",
    "Diagram our stack: Next.js and a Hono API on Vercel. Postgres on Neon, auth with Clerk, payments with Stripe. GitHub Actions deploys.",
    "ZH-公众号",
    "我做了个公众号：Next.js 部署在 Vercel，AI 用火山方舟的 Seed 2.1 每天早上生成行业简报，自动推送到飞书群。",
    "ZH-小店客服",
    "我开了个网店，用扣子搭了个客服机器人回答售后问题，机器人调用豆包大模型，聊天记录同步到飞书多维表格。",
    "EN-docs-bot",
    "Docs chatbot: Next.js on Vercel searches Supabase pgvector and answers with Ark Seed 2.1. Feishu docs synced nightly.",
]

KNOWN = set(re.search(r"KNOWN ICONS: (.*)", SYSTEM_PROMPT, re.S).group(1).split())


def extract_json(text):
    """Best-effort: strip fences/prefix, find the outermost {...}."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError(f"no JSON object found in: {t[:120]!r}")
    return json.loads(t[a:b + 1])


def validate(spec):
    errs = []
    for k in ("title", "nodes", "edges"):
        if k not in spec:
            errs.append(f"missing key {k}")
    if errs:
        return errs
    ids = []
    for n in spec["nodes"]:
        for k in ("id", "name", "role", "icon"):
            if k not in n:
                errs.append(f"node missing {k}: {n}")
        if n.get("id") and not re.fullmatch(r"[a-z0-9_-]{1,16}", str(n["id"])):
            errs.append(f"bad id {n.get('id')!r}")
        if n.get("icon") and n["icon"] not in KNOWN:
            errs.append(f"unknown icon {n['icon']!r} (node {n.get('id')})")
        ids.append(n.get("id"))
    if len(ids) != len(set(ids)):
        errs.append("duplicate node ids")
    if not (1 <= len(ids) <= 14):
        errs.append(f"node count {len(ids)} out of range")
    idset = set(ids)
    for e in spec["edges"]:
        if e.get("from") not in idset or e.get("to") not in idset:
            errs.append(f"edge refs unknown node: {e}")
        if e.get("kind") not in ("primary", "internal", "dev"):
            errs.append(f"bad edge kind: {e.get('kind')!r}")
    seen = []
    for g in spec.get("groups", []):
        for m in g.get("members", []):
            if m not in idset:
                errs.append(f"group {g.get('name')!r} refs unknown member {m!r}")
            if m in seen:
                errs.append(f"node {m!r} in two groups")
            seen.append(m)
    return errs


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else None
    tot_in = tot_out = 0
    ok = 0
    for label, sent in zip(SENTENCES[0::2], SENTENCES[1::2]):
        t0 = time.time()
        try:
            content, usage, latency = ark_client.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": sent}],
                model=model, temperature=0.2, max_tokens=2000)
        except Exception as e:                                    # noqa: BLE001
            print(f"[{label}] CALL FAIL {e}")
            continue
        wall = time.time() - t0
        tot_in += usage.get("prompt_tokens", 0)
        tot_out += usage.get("completion_tokens", 0)
        try:
            spec = extract_json(content)
            errs = validate(spec)
        except Exception as e:                                    # noqa: BLE001
            print(f"[{label}] PARSE FAIL {e} | raw[:150]={content[:150]!r}")
            continue
        status = "VALID" if not errs else f"INVALID ({'; '.join(errs[:4])})"
        if not errs:
            ok += 1
        g = spec.get("groups", [])
        print(f"[{label}] {status} | nodes={len(spec['nodes'])} edges={len(spec['edges'])} "
              f"groups={len(g)} | {latency:.1f}s api / {wall:.1f}s wall | "
              f"tokens in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')}")
    print(f"\nsummary: {ok}/5 valid | tokens: in={tot_in} out={tot_out} | "
          f"est cost lite ¥{tot_in / 1e6 * 0.8 + tot_out / 1e6 * 2.7:.4f} "
          f"pro ¥{tot_in / 1e6 * 6 + tot_out / 1e6 * 30:.4f}")


if __name__ == "__main__":
    main()
