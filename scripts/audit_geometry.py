#!/usr/bin/env python3
"""audit_geometry.py - Render-based geometry check for HTML decks (Playwright + Chrome).

validate_deck.py catches word counts and literal inline font-size strings by parsing
the HTML as text. It cannot see what actually renders: two elements overlapping, a
table or callout overflowing past the footer, or a computed font-size that ended up
tiny because of an inherited class rule the inline-style regex never saw. This script
renders every slide in a real browser and checks the computed layout instead.

Catches, concretely (each one bit an evaluator-calibration-talk deck in production):
  - overlap: two content elements' bounding boxes intersect (e.g. a callout drawn on
    top of a footnote after the callout's content grew).
  - overflow: content bottom sits past the footer's top (table/card got taller than
    the slide after a content edit, most content still "fits" visually until it
    doesn't).
  - small text: COMPUTED font-size below the floor, catching cases the static
    inline-style regex misses - a class rule sized for one context (e.g. a short
    1-line card body) reused for a dense multi-line block, or a `<code>` chip that
    inherited a shrunk parent size.

Usage:
  python3 scripts/audit_geometry.py deck.html [--min-font-px 15.5] [--slide-selector "section.slide"]
"""
import argparse
import json
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("needs playwright: pip install playwright  (uses your installed Chrome via channel=chrome, no browser download needed)")

JS = r"""
([selector, smallMin]) => {
  const sections = [...document.querySelectorAll(selector)];
  return sections.map((sec, idx) => {
    const small = [];
    const seen = new Set();
    sec.querySelectorAll('*').forEach(el => {
      if (el.closest('.slide-footer, aside.notes, footer, .page-number')) return;
      const st = getComputedStyle(el);
      const fs = parseFloat(st.fontSize);
      const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (!hasText || fs >= smallMin) return;
      const t = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60);
      const key = fs.toFixed(1) + '|' + t;
      if (seen.has(key) || !t) return;
      seen.add(key);
      small.push({fs: Math.round(fs * 10) / 10, tag: el.tagName.toLowerCase(), text: t});
    });
    const rects = [...sec.querySelectorAll('*')]
      .filter(el => !el.closest('.slide-footer, aside.notes, footer, .page-number'))
      .map(el => {
        const r = el.getBoundingClientRect();
        return {el, cls: el.className || el.tagName.toLowerCase(), r};
      }).filter(x => x.r.width > 0 && x.r.height > 0);
    const overlaps = [];
    for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
      if (rects[i].el.contains(rects[j].el) || rects[j].el.contains(rects[i].el)) continue;
      const a = rects[i].r, b = rects[j].r;
      const ox = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
      const oy = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
      if (ox * oy > 60) overlaps.push({a: rects[i].cls, b: rects[j].cls, px: Math.round(ox * oy)});
    }
    let overflow = null;
    const footer = sec.querySelector('.slide-footer, footer, .page-number');
    if (footer) {
      const bottoms = rects.map(x => x.r.bottom);
      const contentBottom = bottoms.length ? Math.max(...bottoms) : 0;
      const footerTop = footer.getBoundingClientRect().top;
      if (contentBottom > footerTop + 2) overflow = Math.round(contentBottom - footerTop);
    }
    return {index: idx, small, overlaps, overflow};
  });
}
"""


def audit(path, selector, min_font_px):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--force-device-scale-factor=1"])
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"file://{path}")
        page.wait_for_timeout(300)
        data = page.evaluate(JS, [selector, min_font_px])
        browser.close()
    return data


def main():
    ap = argparse.ArgumentParser(description="Render-based overlap/overflow/small-text audit.")
    ap.add_argument("deck")
    ap.add_argument("--min-font-px", type=float, default=15.5)
    ap.add_argument("--slide-selector", default="section.slide")
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything is flagged")
    args = ap.parse_args()

    import os
    data = audit(os.path.abspath(args.deck), args.slide_selector, args.min_font_px)
    flagged = [d for d in data if d["small"] or d["overlaps"] or d["overflow"]]
    if not flagged:
        print(f"clean: {len(data)} slides, 0 geometry issues")
        return
    for d in flagged:
        n = d["index"] + 1
        for s in d["small"]:
            print(f"WARN  [slide {n}] {s['fs']}px < {args.min_font_px}px floor: <{s['tag']}> \"{s['text']}\"")
        for o in d["overlaps"]:
            print(f"ERROR [slide {n}] overlap ({o['px']}px^2): .{o['a']} x .{o['b']}")
        if d["overflow"]:
            print(f"ERROR [slide {n}] content overflows footer by {d['overflow']}px")
    if args.strict and any(d["overlaps"] or d["overflow"] for d in flagged):
        sys.exit(1)


if __name__ == "__main__":
    main()
