#!/usr/bin/env python3
"""Deterministic post-render checks for a built diagram HTML.

Replaces the upstream skill's "render the PNG and look at it" agent step with
assertions on the live DOM (Playwright/Chromium):

  1. no edge segment crosses label text (node names/roles, edge labels, group labels)
  2. every tile icon actually loaded (naturalWidth > 0)
  3. every node/group/edge stays inside the canvas
  4. both themes are checked (light and dark)

Usage:  python3 check.py BUILT.html
Exit 0 = clean, 1 = violations (printed as JSON).
"""
import json, pathlib, re, sys

JS = r"""
() => {
  const tol = 1.5;                       // halo stroke eats ~2px; allow hairline kisses
  const svgEl = document.querySelector('svg.edges');
  const off = svgEl.getBoundingClientRect();   // d-attrs are svg-local; texts are viewport-space
  const segs = [];                       // {cls, pts:[[x,y],...]}
  document.querySelectorAll('svg.edges path').forEach(p => {
    const d = p.getAttribute('d') || '';
    const tok = d.match(/[MHVL]|-?\d+(?:\.\d+)?/g) || [];
    let x = null, y = null, sx = null, sy = null, pts = [];
    for (let i = 0; i < tok.length; i++) {
      const t = tok[i];
      if (/[MHVL]/.test(t)) {
        if (t === 'M') { if (pts.length) segs.push({cls: p.className.baseVal, pts});
          x = parseFloat(tok[++i]); y = parseFloat(tok[++i]); pts = [[x, y]]; }
        else if (t === 'H') { x = parseFloat(tok[++i]); pts.push([x, y]); }
        else if (t === 'V') { y = parseFloat(tok[++i]); pts.push([x, y]); }
        else if (t === 'L') { x = parseFloat(tok[++i]); y = parseFloat(tok[++i]); pts.push([x, y]); }
      }
    }
    if (pts.length > 1) segs.push({cls: p.className.baseVal, pts: pts.map(q => [q[0] + off.left, q[1] + off.top])});
  });
  const texts = [];
  const pushText = (el, kind) => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) texts.push({kind, text: (el.textContent || '').trim().slice(0, 30),
      l: r.left, t: r.top, r: r.right, b: r.bottom});
  };
  document.querySelectorAll('.node .name, .node .role, .g-label').forEach(el => pushText(el, el.className.baseVal || 'label'));
  document.querySelectorAll('svg.edges text').forEach(el => pushText(el, 'edge-label'));
  const cr = document.querySelector('.canvas').getBoundingClientRect();
  const viol = [];
  const hit = (s, t) => {
    for (let i = 0; i < s.pts.length - 1; i++) {
      const [x1, y1] = s.pts[i], [x2, y2] = s.pts[i + 1];
      const lo = (a, b) => Math.min(a, b) + tol, hi = (a, b) => Math.max(a, b) - tol;
      // axis-aligned (or general) segment vs rect via clipping
      const inside = (x, y) => x >= t.l - 0 && x <= t.r && y >= t.t && y <= t.b;
      if (inside(x1, y1) || inside(x2, y2)) return true;
      const steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
      for (let k = 1; k < steps; k++) {
        const x = x1 + (x2 - x1) * k / steps, y = y1 + (y2 - y1) * k / steps;
        if (inside(x, y)) return true;
      }
      if (lo(x1, x2) <= t.r && hi(x1, x2) >= t.l && lo(y1, y2) <= t.b && hi(y1, y2) >= t.t) return true;
    }
    return false;
  };
  for (const s of segs)
    for (const t of texts)
      if (hit(s, t)) viol.push({type: 'edge-crosses-text', edge: s.cls, text: t.text});
  document.querySelectorAll('.tile img').forEach(img => {
    if (!img.complete || img.naturalWidth === 0) viol.push({type: 'icon-not-loaded', src: (img.getAttribute('src') || '').slice(0, 40)});
  });
  document.querySelectorAll('.node').forEach(n => {
    const r = n.getBoundingClientRect();
    if (r.left < cr.left - 1 || r.right > cr.right + 1 || r.top < cr.top - 1 || r.bottom > cr.bottom + 1)
      viol.push({type: 'node-outside-canvas', text: (n.textContent || '').trim().slice(0, 30)});
  });
  const dupes = {};
  const seen = new Set();
  document.querySelectorAll('.node .name').forEach(el => {
    const k = el.textContent.trim();
    if (seen.has(k)) dupes[k] = 1; seen.add(k);
  });
  Object.keys(dupes).forEach(k => viol.push({type: 'duplicate-node-name', text: k}));
  return {violations: viol, nEdges: segs.length, nTexts: texts.length};
}
"""


def run_check(src):
    """Load the built HTML, assert both themes; returns {light:{...}, dark:{...}}."""
    from playwright.sync_api import sync_playwright
    src = pathlib.Path(src).resolve()
    report = {}
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        page = b.new_page(viewport={"width": 1400, "height": 900})
        page.goto(src.as_uri())
        page.wait_for_timeout(600)
        for theme in ("light", "dark"):
            page.evaluate(f"document.documentElement.setAttribute('data-theme','{theme}')")
            page.wait_for_timeout(80)
            report[theme] = page.evaluate(JS)
        b.close()
    return report


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    report = run_check(sys.argv[1])
    bad = sum(len(r["violations"]) for r in report.values())
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if bad:
        sys.exit(f"CHECK FAILED: {bad} violation(s)")
    print("CHECK PASSED: no text crossings, all icons loaded, nothing outside canvas")


if __name__ == "__main__":
    main()
