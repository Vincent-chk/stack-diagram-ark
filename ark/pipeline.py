#!/usr/bin/env python3
"""End-to-end pipeline: sentence -> spec -> icons -> layout -> HTML -> PNG (+checks).

Everything runs in-process, reusing the skill's own code as modules:
fetch_icons / build / render_png live in ../skills/stack-diagram/scripts,
check.py sits next to this file. No subprocesses, no shell.
"""
import base64
import json
import pathlib
import re
import shutil
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
SKILL = REPO / "skills" / "stack-diagram"
SCRIPTS = SKILL / "scripts"
ASSETS = SKILL / "assets"
GENERIC = {"user", "browser", "internet", "device", "server"}
EXTS = {".svg", ".png", ".webp", ".jpg", ".jpeg"}
_SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,15}")          # never starts with '-'

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import fetch_icons                                       # noqa: E402  (skill's script, reused as module)
import build as build_mod                                # noqa: E402
import render_png as render_png_mod                      # noqa: E402
import check as check_mod                                # noqa: E402
import layout                                            # noqa: E402
import render_html                                       # noqa: E402
import spec as spec_mod                                  # noqa: E402

PRICING = {"lite": (0.8, 2.7), "pro": (6.0, 30.0)}       # ¥ per 1M tokens (in, out)
ICON_CACHE = HERE / ".icon-cache"                        # survives across requests (gitignored)


def _fetch_one(slug, icondir):
    """In-process version of fetch_icons.main() for one validated slug.
    Returns {source, dark} or None when every source missed."""
    for src, url, dark_url in fetch_icons.sources(slug):
        try:
            b = fetch_icons.read(url)
        except Exception:                                              # noqa: BLE001 - fall to next source
            continue
        ext = fetch_icons.ext_of(b, url)
        if not ext or len(b) < 50:
            continue
        if src == "lucide":
            b = b.replace(b'stroke="currentColor"', b'stroke="#3d4660"')
            b = b.replace(b'stroke-width="2"', b'stroke-width="1.7"')
        (icondir / f"{slug}.{ext}").write_bytes(b)
        dark = None
        if dark_url:
            try:
                db = fetch_icons.read(dark_url)
                dext = fetch_icons.ext_of(db, dark_url) if len(db) >= 50 else None
                if dext:
                    (icondir / f"{slug}_dark.{dext}").write_bytes(db)
                    dark = f"{slug}_dark"
            except Exception:                                          # noqa: BLE001 - dark variant is optional
                pass
        return {"source": src, "dark": dark}
    return None


def _cache_lookup(slug, icondir):
    """Copy cached icon (+dark variant) for slug; returns meta or None."""
    ICON_CACHE.mkdir(exist_ok=True)
    files = [f for f in ICON_CACHE.glob(f"{slug}.*")
             if f.suffix.lower() in EXTS and f.stem == slug]
    if not files:
        return None
    shutil.copy(files[0], icondir / files[0].name)
    dark = ICON_CACHE / f"{slug}_dark{files[0].suffix}"
    dark_name = None
    if dark.exists():
        shutil.copy(dark, icondir / dark.name)
        dark_name = f"{slug}_dark"
    src = "svgl"
    mpath = ICON_CACHE / "manifest.json"
    if mpath.exists():
        try:
            src = json.loads(mpath.read_text()).get(slug, {}).get("source", "svgl")
        except Exception:                                              # noqa: BLE001
            pass
    return {"plate": False, "dark": dark_name, "credit": src}


def _cache_store(slug, icondir, meta):
    """Persist a freshly fetched icon into the cache."""
    ICON_CACHE.mkdir(exist_ok=True)
    for f in icondir.glob(f"{slug}.*"):
        if f.suffix.lower() in EXTS and f.stem == slug:
            shutil.copy(f, ICON_CACHE / f.name)
    if meta.get("dark"):
        for f in icondir.glob(f"{slug}_dark.*"):
            shutil.copy(f, ICON_CACHE / f.name)
    mpath = ICON_CACHE / "manifest.json"
    m = {}
    try:
        m = json.loads(mpath.read_text())
    except Exception:                                                  # noqa: BLE001
        m = {}
    m[slug] = {"source": meta.get("credit", "svgl")}
    mpath.write_text(json.dumps(m, indent=1))


def _assemble_icons(slugs, icondir):
    """volc pack + generic glyphs locally, the rest through the svgl chain
    (with a persistent cache so repeated requests skip the network).
    Returns icon_meta {slug: {plate,dark,credit}} for slugs that resolved."""
    meta = {}
    for s in sorted(slugs):
        if not s or not _SLUG.fullmatch(s):
            continue
        if s in GENERIC:
            src = ASSETS / "generic" / f"{s}.svg"
            if src.exists():
                shutil.copy(src, icondir / f"{s}.svg")
                meta[s] = {"plate": False, "dark": None, "credit": "generic"}
            continue
        hits = fetch_icons.volc_sources(s)
        if hits:
            local = pathlib.Path(hits[0][1].replace("local://", ""))
            shutil.copy(local, icondir / f"{s}{local.suffix}")
            meta[s] = {"plate": True, "dark": None, "credit": "volc pack"}
            continue
        cached = _cache_lookup(s, icondir)
        if cached:
            meta[s] = cached
            continue
        got = _fetch_one(s, icondir)
        if got:
            entry = {"plate": False, "dark": got["dark"], "credit": got["source"]}
            meta[s] = entry
            _cache_store(s, icondir, entry)
    return meta


def generate(sentence, quality="lite", stub_spec=None):
    """Returns a result dict; raises RuntimeError with a plain-language message."""
    t0 = time.time()
    tmp = tempfile.TemporaryDirectory(prefix="ark-diagram-")
    work = pathlib.Path(tmp.name)
    icondir = work / "icons"
    icondir.mkdir()
    stages = {}
    try:
        # 1. spec (Ark call, unless a stub spec is supplied for offline runs)
        t = time.time()
        if stub_spec is not None:
            spec, notes, usage, latency = stub_spec, ["stub"], {}, 0.0
        else:
            spec, notes, usage, latency = spec_mod.ask(sentence, quality)
        stages["ark"] = round(time.time() - t, 1)

        # 2. icons
        t = time.time()
        slugs = {n["icon"] for n in spec["nodes"]} | {g.get("icon", "") for g in spec.get("groups", [])}
        meta = _assemble_icons(slugs, icondir)
        stages["icons"] = round(time.time() - t, 1)

        # 3. layout + render to draft HTML
        t = time.time()
        lay = layout.place(spec)
        draft = work / "draft.html"
        draft.write_text(render_html.render(spec, lay, meta), encoding="utf-8")
        stages["layout"] = round(time.time() - t, 1)

        # 4. inline fonts/icons into the HTML (skill's build.py)
        t = time.time()
        out_html = work / "out.html"
        build_mod.run(draft, icondir, out_html, ASSETS / "fonts")
        stages["inline"] = round(time.time() - t, 1)

        # 5. PNG, both themes (skill's render_png.py; PNG optional if chromium missing)
        t = time.time()
        png_b64 = png_dark_b64 = None
        try:
            render_png_mod.render(out_html, work / "out.png")
        except Exception as e:                                         # noqa: BLE001 - PNG is best-effort
            notes = list(notes) + [f"PNG 渲染跳过: {type(e).__name__}"]
        if (work / "out.png").exists():
            png_b64 = base64.b64encode((work / "out.png").read_bytes()).decode()
            dark_path = work / "out-dark.png"
            png_dark_b64 = (base64.b64encode(dark_path.read_bytes()).decode()
                            if dark_path.exists() else None)
        stages["png"] = round(time.time() - t, 1)

        # 6. deterministic visual check on the live DOM
        t = time.time()
        check = {"light": [], "dark": [], "passed": None}
        try:
            rep = check_mod.run_check(out_html)
            bad = sum(len(r.get("violations", [])) for r in rep.values())
            check = {"light": rep.get("light", {}).get("violations", []),
                     "dark": rep.get("dark", {}).get("violations", []),
                     "passed": bad == 0}
        except Exception as e:                                         # noqa: BLE001 - check is best-effort
            notes = list(notes) + [f"自查跳过: {type(e).__name__}"]
        stages["check"] = round(time.time() - t, 1)

        pin, pout = PRICING.get(quality, PRICING["lite"])
        cost = usage.get("prompt_tokens", 0) / 1e6 * pin + usage.get("completion_tokens", 0) / 1e6 * pout
        return {
            "spec": spec, "notes": notes, "warnings": lay.get("warnings", []),
            "png": png_b64, "png_dark": png_dark_b64,
            "html": out_html.read_text(encoding="utf-8"),
            "check": check,
            "meta": {"quality": quality, "latency_api": round(latency, 1),
                     "usage": usage, "est_cost_yuan": round(cost, 4),
                     "stages": stages, "total": round(time.time() - t0, 1),
                     "model": spec_mod.MODELS.get(quality, quality)},
        }
    finally:
        tmp.cleanup()
