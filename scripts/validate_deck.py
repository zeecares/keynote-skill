#!/usr/bin/env python3
"""validate_deck.py - Lint an HTML deck against the Winston slide rules.

Checks distilled from Patrick Winston's "How to Speak" (MIT OCW); see
references/winston-rules.md for the rule-to-transcript mapping.

  - too many words on a slide (the "one language processor" rule)
  - missing empowerment promise early in the deck
  - weak final slides: "Questions?", "Thank you", bare "Conclusions"
    (Winston: the final slide is CONTRIBUTIONS, shown while people file out)
  - collaborator credits on the final slide (they belong on the first)
  - bullet clutter: deep nesting, long bullet lists
  - inline font sizes below the legibility floor
  - images without alt text

Exit code is 0 unless --strict is given and any ERROR fired.

Usage:
  python3 validate_deck.py deck.html [--strict] [--max-words 30]
"""
import argparse
import re
import sys
from html.parser import HTMLParser

PROMISE_HINTS = ("you will", "you'll", "promise", "by the end", "walk away")
BAD_FINAL = ("thank you", "thanks", "questions?", "any questions", "q&a", "q & a")
CONCLUSION_ONLY = ("conclusion", "conclusions", "summary")
COLLAB_HINTS = ("collaborator", "acknowledg", "with thanks to", "joint work")


class Slide:
    def __init__(self, classes):
        self.classes = classes
        self.text = []        # visible words
        self.headings = []
        self.styles = []      # inline style strings
        self.images = []      # (src, alt)
        self.li_depths = []
        self.has_notes = False


class DeckLint(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.slides = []
        self.cur = None
        self.skip = 0          # inside <aside class=notes> / <style> / <script>
        self.depth = 0         # ul/ol nesting
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "section" and "slide" in cls:
            self.cur = Slide(cls)
        if self.cur is None:
            return
        if tag in ("style", "script") or (tag == "aside" and "notes" in cls):
            self.skip += 1
            if tag == "aside":
                self.cur.has_notes = True
        if tag in ("ul", "ol"):
            self.depth += 1
        if tag == "li":
            self.cur.li_depths.append(self.depth)
        if tag in ("h1", "h2", "h3"):
            self.tag_stack.append(("h", []))
        elif self.tag_stack and self.tag_stack[-1][0] == "h":
            pass
        if a.get("style"):
            self.cur.styles.append(a["style"])
        if tag == "img":
            self.cur.images.append((a.get("src", ""), a.get("alt")))

    def handle_endtag(self, tag):
        if self.cur is None:
            return
        if tag in ("style", "script", "aside") and self.skip:
            self.skip -= 1
        if tag in ("ul", "ol") and self.depth:
            self.depth -= 1
        if tag in ("h1", "h2", "h3") and self.tag_stack and self.tag_stack[-1][0] == "h":
            _, buf = self.tag_stack.pop()
            self.cur.headings.append(" ".join(buf))
        if tag == "section":
            self.slides.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cur is None or self.skip:
            return
        words = data.split()
        self.cur.text.extend(words)
        if self.tag_stack and self.tag_stack[-1][0] == "h":
            self.tag_stack[-1][1].extend(words)


FONT_RE = re.compile(r"font-size\s*:\s*([0-9.]+)\s*(px|pt)", re.I)


def lint(path, max_words, min_font_pt):
    with open(path, encoding="utf-8") as fh:
        parser = DeckLint()
        parser.feed(fh.read())
    slides = parser.slides
    findings = []  # (level, slide_no, message)

    if not slides:
        return [("ERROR", 0, "no <section class=\"slide\"> elements found")]

    for i, s in enumerate(slides, 1):
        n = len(s.text)
        if n > max_words:
            findings.append(("ERROR", i,
                f"{n} words on the slide (max {max_words}) - people will read "
                f"the slide instead of listening to you"))
        if len(s.li_depths) > 6:
            findings.append(("WARN", i,
                f"{len(s.li_depths)} bullets on one slide - cut or split"))
        if max(s.li_depths, default=0) > 2:
            findings.append(("WARN", i,
                "bullets nested deeper than 2 levels - clutter"))
        for st in s.styles:
            for size, unit in FONT_RE.findall(st):
                pt = float(size) * (96 / 72 if unit == "px" else 1)
                if pt < min_font_pt:
                    findings.append(("WARN", i,
                        f"inline font-size {size}{unit} (~{pt:.0f}pt) below the "
                        f"{min_font_pt}pt floor - small fonts invite word cramming"))
        for src, alt in s.images:
            if alt is None:
                findings.append(("WARN", i, f"image {src or '?'} has no alt text"))

    # Deck-level structure checks.
    joined_early = " ".join(" ".join(s.text).lower() for s in slides[:2])
    if not any(h in joined_early for h in PROMISE_HINTS):
        findings.append(("WARN", 1,
            "no empowerment promise in the first two slides - open by telling "
            "the audience what they will know at the end that they don't know now"))

    last = slides[-1]
    last_text = " ".join(last.text).lower()
    last_head = " ".join(last.headings).lower()
    if any(b in last_text for b in BAD_FINAL):
        findings.append(("ERROR", len(slides),
            "weak final slide (thank-you / questions) - the final slide stays up "
            "during Q&A; make it CONTRIBUTIONS"))
    if last_head.strip() in CONCLUSION_ONLY:
        findings.append(("WARN", len(slides),
            "final slide labelled conclusions/summary - Winston: nobody cares "
            "about conclusions; they care what you DID. Label it Contributions"))
    if "contribution" not in last_head and not any(b in last_text for b in BAD_FINAL):
        findings.append(("WARN", len(slides),
            "final slide is not labelled Contributions"))
    if any(c in last_text for c in COLLAB_HINTS):
        findings.append(("WARN", len(slides),
            "credits/acknowledgements on the final slide - collaborators belong "
            "on the FIRST slide"))

    return findings


def main():
    ap = argparse.ArgumentParser(description="Lint an HTML deck against the Winston rules.")
    ap.add_argument("deck")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any ERROR")
    ap.add_argument("--max-words", type=int, default=30,
                    help="max readable words per slide (default 30)")
    ap.add_argument("--min-font-pt", type=float, default=18,
                    help="floor for inline font sizes (default 18pt)")
    args = ap.parse_args()
    findings = lint(args.deck, args.max_words, args.min_font_pt)
    if not findings:
        print("clean: no Winston-rule violations")
        return
    for level, slide, msg in findings:
        where = f"slide {slide}" if slide else "deck"
        print(f"{level:5} [{where}] {msg}")
    if args.strict and any(l == "ERROR" for l, _, _ in findings):
        sys.exit(1)


if __name__ == "__main__":
    main()
