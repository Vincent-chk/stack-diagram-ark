#!/usr/bin/env python3
"""Minimal OpenAI-compatible client for Volcengine Ark (stdlib only).

Used by probe_ark.py and server.py. Reads ARK_API_KEY / ARK_MODEL from the
environment. Talks only to Ark's official hosts (literal constants, selected
by ARK_REGION from a fixed table) over TLS via http.client — nothing
user-supplied ever reaches the connection target.
"""
import http.client, json, os, time


class ArkError(RuntimeError):
    pass


# Fixed official Ark hosts — safe by construction; no env/user input flows here.
_ARK_HOSTS = {"cn-beijing": "ark.cn-beijing.volces.com",
              "ap-southeast": "ark.ap-southeast.volces.com"}
_ARK_PATH = "/api/v3/chat/completions"


def chat(messages, model=None, temperature=0.2, max_tokens=2400, retries=1, timeout=90):
    """One chat completion. Returns (content_str, usage_dict, latency_s)."""
    key = os.environ.get("ARK_API_KEY", "")
    region = os.environ.get("ARK_REGION", "cn-beijing")
    model = model or os.environ.get("ARK_MODEL", "doubao-seed-2-1-lite-260915")
    if not key:
        raise ArkError("ARK_API_KEY not set")
    host = _ARK_HOSTS.get(region, _ARK_HOSTS["cn-beijing"])
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
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
