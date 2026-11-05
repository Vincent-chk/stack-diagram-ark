#!/usr/bin/env python3
"""Minimal OpenAI-compatible client for Volcengine Ark (stdlib only).

Used by probe_ark.py and server.py. Reads ARK_API_KEY / ARK_MODEL from the
environment. Talks only to Ark's official hosts (literal constants, selected
by ARK_REGION from a fixed table) over TLS via http.client — nothing
user-supplied ever reaches the connection target. Uses the subscription-plan
endpoint /api/plan/v3 (not pay-as-you-go /api/v3).
"""
import http.client
import ipaddress
import json
import os
import time


class ArkError(RuntimeError):
    pass


# Fixed official Ark hosts — safe by construction; no env/user input flows here.
_ARK_HOSTS = {"cn-beijing": "ark.cn-beijing.volces.com",
              "ap-southeast": "ark.ap-southeast.volces.com"}
# 订阅套餐端点（用户账号为 plan 套餐；按量 /api/v3 会报账户欠费）
_ARK_PATH = "/api/plan/v3/chat/completions"


def _assert_public_host(host):
    """Explicit guard: https-only transport elsewhere; reject loopback/private/
    reserved addresses before connecting (hosts here are constants, this makes
    the invariant enforced rather than implied)."""
    h = (host or "").strip().rstrip(".").lower()
    if not h or h == "localhost" or h.endswith((".local", ".internal", ".lan")):
        raise ArkError(f"blocked host: {host!r}")
    try:
        ip = ipaddress.ip_address(h)
        if not ip.is_global:
            raise ArkError(f"blocked non-global address: {h}")
    except ValueError:
        pass                                            # a domain name: fine
    return h


def chat(messages, model=None, temperature=0.2, max_tokens=2400, retries=1, timeout=90,
         thinking=False):
    """One chat completion. Returns (content_str, usage_dict, latency_s).
    thinking=False disables the Seed 2.1 reasoning pass — schema extraction
    does not need it, and it cut 40-55s latencies down to seconds."""
    key = os.environ.get("ARK_API_KEY", "")
    region = os.environ.get("ARK_REGION", "cn-beijing")
    model = model or os.environ.get("ARK_MODEL", "doubao-seed-2-1-lite-260915")
    if not key:
        raise ArkError("ARK_API_KEY not set")
    host = _assert_public_host(_ARK_HOSTS.get(region, _ARK_HOSTS["cn-beijing"]))
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {"type": "enabled" if thinking else "disabled"},
    }).encode("utf-8")
    last = None
    for attempt in range(retries + 1):
        conn = http.client.HTTPSConnection(host, timeout=timeout)
        t0 = time.time()
        try:
            conn.request("POST", _ARK_PATH, body=body, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            })
            r = conn.getresponse()
            raw = r.read().decode("utf-8")
            latency = time.time() - t0
            if r.status != 200:
                raise ArkError(f"HTTP {r.status}: {raw[:300]}")
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            return content, data.get("usage", {}), latency
        except Exception as e:              # noqa: BLE001 - HTTP/network errors: retry with backoff
            last = e if isinstance(e, ArkError) else ArkError(f"{type(e).__name__}: {e}")
            time.sleep(1.2 * (attempt + 1))
        finally:
            conn.close()
    raise last or ArkError("unknown failure")
