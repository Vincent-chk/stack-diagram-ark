#!/usr/bin/env python3
"""FastAPI wrapper: one page, one endpoint. Run with `bash start.sh`."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import pipeline

app = FastAPI(title="一句话架构图 · Ark Seed 2.1", version="0.1.0")


class GenReq(BaseModel):
    sentence: str = Field(min_length=2, max_length=600)
    quality: str = "lite"


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "web", "index.html"))


@app.get("/api/health")
def health():
    return {"ok": True, "has_key": bool(os.environ.get("ARK_API_KEY")),
            "default_quality": "lite"}


@app.post("/api/generate")
def generate(req: GenReq):
    if req.quality not in ("lite", "pro"):
        raise HTTPException(400, "quality 只能是 lite 或 pro")
    if not os.environ.get("ARK_API_KEY"):
        raise HTTPException(400, "服务端未设置 ARK_API_KEY（把它写进 ark/.env 或环境变量后重启）")
    try:
        r = pipeline.generate(req.sentence.strip(), req.quality)
    except Exception as e:                                             # noqa: BLE001 - surface as plain text
        msg = str(e)
        if "Overdue" in msg or "403" in msg:
            msg = "方舟账户余额不足（AccountOverdue）：请到火山引擎控制台充值后重试。"
        elif "401" in msg or "Authentication" in msg:
            msg = "ARK_API_KEY 无效或已过期。"
        elif "timeout" in msg.lower() or "timed out" in msg.lower():
            msg = "调用方舟超时，请重试一次。"
        raise HTTPException(502, msg[:300])
    return r
