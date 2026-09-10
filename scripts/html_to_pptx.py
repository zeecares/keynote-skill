#!/usr/bin/env python3
"""html_to_pptx.py - Export a Winston-style HTML deck to an editable PPTX.

Input contract (see templates/deck.html):
  - One <section class="slide"> per slide.
  - First slide may carry class "slide-title" (h1 + .subtitle + .speaker).
  - Content slides: one <h2> headline, then <p>, <ul>/<li>, <blockquote>,
    <img>/<figure> elements.
  - <aside class="notes"> becomes speaker notes (never rendered on the slide).
  - <strong>/<em> map to bold/italic runs.

Output: a 16:9 .pptx built from native text boxes and pictures - every
element stays editable in PowerPoint, Keynote, and Google Slides.

Dependencies: python-pptx (pip install python-pptx). Stdlib otherwise.

Usage:
  python3 html_to_pptx.py deck.html [-o deck.pptx]
"""
import argparse
import os
import sys
from html.parser import HTMLParser

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.6)

INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x55, 0x55, 0x55)

# Winston floor: he puts the minimum legible slide font at ~35-40 pt for a
# projected room (see references/winston-rules.md). Export defaults keep body
# text at or above BODY_PT; validate_deck.py warns when authors go smaller
# via inline styles.
TITLE_PT = 44
HEAD_PT = 32
BODY_PT = 22
SMALL_PT = 18


class Slide:
    def __init__(self):
        self.kind = "content"      # 'title' | 'content'
        self.title = None          # h1 or h2 runs
        self.blocks = []           # ordered content blocks
        self.notes = []            # speaker-notes text


def _runs(text, bold=False, italic=False):
    return [{"text": text, "bold": bold, "italic": italic}] if text else []


class DeckParser(HTMLParser):
    def __init__(self, base_dir):
        super().__init__(convert_charrefs=True)
        self.base_dir = base_dir
        self.slides = []
        self.slide = None
        self.stack = []            # open tags
        self.buf = []              # (text, bold, italic) under collection
        self.collect = None        # 'title' | 'block' | 'notes' | None
        self.block = None          # current block dict
        self.li_level = 0
        self.in_notes = False

    # -- helpers ----------------------------------------------------------
    def _cls(self, attrs):
        return dict(attrs).get("class", "") or ""

    def _flush_buf_to(self, target):
        if self.buf:
            target.extend(self.buf)
            self.buf = []

    # -- tag handling -----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = self._cls(attrs)
        self.stack.append(tag)

        if tag == "section" and "slide" in cls.split():
            self.slide = Slide()
            if "slide-title" in cls.split():
                self.slide.kind = "title"
            return
        if self.slide is None:
            return

        if tag == "aside" and "notes" in cls.split():
            self.in_notes = True
            self.collect = "notes"
            return
        if self.in_notes:
            return

        if tag in ("h1", "h2"):
            self.collect = "title"
            self.buf = []
            return
        if tag == "ul" or tag == "ol":
            if self.block is None:
                self.block = {"type": "bullets", "items": []}
            else:
                self.li_level += 1
            return
        if tag == "li":
            self.buf = []
            self.collect = "block"
            return
        if tag == "p":
            kind = "p"
            if "subtitle" in cls.split():
                kind = "subtitle"
            elif "speaker" in cls.split():
                kind = "speaker"
            self.block = {"type": kind, "runs": []}
            self.buf = []
            self.collect = "block"
            return
        if tag == "blockquote":
            self.block = {"type": "quote", "runs": []}
            self.buf = []
            self.collect = "block"
            return
        if tag == "figcaption":
            self.block = {"type": "caption", "runs": []}
            self.buf = []
            self.collect = "block"
            return
        if tag == "img":
            src = a.get("src", "")
            if src and not src.startswith(("http://", "https://", "data:")):
                src = os.path.normpath(os.path.join(self.base_dir, src))
            self.slide.blocks.append(
                {"type": "image", "src": src, "alt": a.get("alt", "")})
            return

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        if self.slide is None:
            return

        if tag == "section":
            if self.block is not None:
                self._close_block()
            self.slides.append(self.slide)
            self.slide = None
            self.in_notes = False
            self.collect = None
            return
        if self.in_notes:
            if tag == "aside":
                self._flush_buf_to(self.slide.notes)
                self.in_notes = False
                self.collect = None
            return

        if tag in ("h1", "h2") and self.collect == "title":
            self.slide.title = self.buf
            self.buf = []
            self.collect = None
            return
        if tag == "li":
            if self.block is not None and self.block["type"] == "bullets":
                self.block["items"].append({"level": self.li_level, "runs": self.buf})
            self.buf = []
            self.collect = None
            return
        if tag in ("ul", "ol"):
            if self.li_level > 0:
                self.li_level -= 1
            else:
                self._close_block()
            return
        if tag in ("p", "blockquote", "figcaption"):
            self._close_block()
            return

    def _close_block(self):
        if self.block is None:
            return
        if "runs" in self.block:
            self.block["runs"] = self.buf if self.buf else self.block["runs"]
            self.buf = []
        if self.block.get("type") == "bullets" and not self.block["items"]:
            self.block = None
            self.collect = None
            return
        self.slide.blocks.append(self.block)
        self.block = None
        self.collect = None

    def handle_data(self, data):
        if self.collect is None or self.slide is None:
            return
        text = " ".join(data.split())
        if not text:
            return
        bold = "strong" in self.stack or "b" in self.stack
        italic = "em" in self.stack or "i" in self.stack
        self.buf.append({"text": text, "bold": bold, "italic": italic})


# -- PPTX rendering --------------------------------------------------------

def _text_box(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    return tf


def _fill_runs(paragraph, runs, size, color=INK, force_italic=False):
    for r in runs:
        run = paragraph.add_run()
        run.text = r["text"] + " "
        run.font.size = Pt(size)
        run.font.bold = bool(r["bold"])
        run.font.italic = bool(r["italic"]) or force_italic
        run.font.color.rgb = color


def _title_slide(slide, model):
    tf = _text_box(slide, MARGIN, Inches(2.2), SLIDE_W - 2 * MARGIN, Inches(1.6))
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _fill_runs(p, model.title or [{"text": "Untitled", "bold": True, "italic": False}],
               TITLE_PT)
    subs = [b for b in model.blocks if b["type"] == "subtitle"]
    spk = [b for b in model.blocks if b["type"] == "speaker"]
    if subs:
        tf2 = _text_box(slide, MARGIN, Inches(3.9), SLIDE_W - 2 * MARGIN, Inches(0.9))
        p2 = tf2.paragraphs[0]
        p2.alignment = PP_ALIGN.CENTER
        _fill_runs(p2, subs[0]["runs"], BODY_PT, color=MUTED)
    if spk:
        tf3 = _text_box(slide, MARGIN, Inches(4.8), SLIDE_W - 2 * MARGIN, Inches(0.7))
        p3 = tf3.paragraphs[0]
        p3.alignment = PP_ALIGN.CENTER
        _fill_runs(p3, spk[0]["runs"], SMALL_PT, color=MUTED)


def _content_slide(slide, model):
    if model.title:
        tf = _text_box(slide, MARGIN, Inches(0.35), SLIDE_W - 2 * MARGIN, Inches(0.9))
        _fill_runs(tf.paragraphs[0], model.title, HEAD_PT)

    images = [b for b in model.blocks if b["type"] == "image"]
    texts = [b for b in model.blocks if b["type"] != "image"]

    body_top = Inches(1.35)
    body_h = SLIDE_H - body_top - Inches(0.4)
    if images:
        # Text gets the left 55%, first image the right 40%.
        text_w = Emu(int((SLIDE_W - 2 * MARGIN) * 0.55))
        img_w = Emu(int((SLIDE_W - 2 * MARGIN) * 0.40))
    else:
        text_w = SLIDE_W - 2 * MARGIN
        img_w = None

    if texts:
        tf = _text_box(slide, MARGIN, body_top, text_w, body_h)
        first = True
        for block in texts:
            if block["type"] == "bullets":
                for item in block["items"]:
                    p = tf.paragraphs[0] if first else tf.add_paragraph()
                    first = False
                    p.level = min(item["level"], 4)
                    p.space_after = Pt(10)
                    _fill_runs(p, item["runs"], BODY_PT)
                    p.runs[0].text = ("• " if item["level"] == 0 else "– ") + p.runs[0].text
            elif block["type"] == "quote":
                p = tf.paragraphs[0] if first else tf.add_paragraph()
                first = False
                p.space_before = Pt(14)
                _fill_runs(p, block["runs"], BODY_PT, color=MUTED, force_italic=True)
            elif block["type"] == "caption":
                p = tf.add_paragraph()
                _fill_runs(p, block["runs"], SMALL_PT, color=MUTED)
            else:
                size = BODY_PT
                color = INK
                if block["type"] == "subtitle":
                    size, color = BODY_PT, MUTED
                elif block["type"] == "speaker":
                    size, color = SMALL_PT, MUTED
                p = tf.paragraphs[0] if first else tf.add_paragraph()
                first = False
                p.space_after = Pt(10)
                _fill_runs(p, block["runs"], size, color=color)

    if images and img_w is not None:
        img = images[0]
        if img["src"] and os.path.exists(img["src"]):
            left = SLIDE_W - MARGIN - img_w
            try:
                slide.shapes.add_picture(img["src"], left, body_top, width=img_w)
            except Exception as exc:  # unreadable image - keep going
                print(f"warning: could not embed {img['src']}: {exc}", file=sys.stderr)
        else:
            print(f"warning: image not found: {img['src']}", file=sys.stderr)


def convert(html_path, out_path):
    base_dir = os.path.dirname(os.path.abspath(html_path))
    with open(html_path, "r", encoding="utf-8") as fh:
        parser = DeckParser(base_dir)
        parser.feed(fh.read())
    if not parser.slides:
        sys.exit("error: no <section class=\"slide\"> elements found")

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]
    for model in parser.slides:
        slide = prs.slides.add_slide(blank)
        if model.kind == "title":
            _title_slide(slide, model)
        else:
            _content_slide(slide, model)
        if model.notes:
            notes = " ".join(r["text"] for r in model.notes)
            slide.notes_slide.notes_text_frame.text = notes
    prs.save(out_path)
    print(f"wrote {out_path} ({len(parser.slides)} slides)")


def main():
    ap = argparse.ArgumentParser(description="Export a Winston-style HTML deck to PPTX.")
    ap.add_argument("deck", help="path to the deck HTML file")
    ap.add_argument("-o", "--out", help="output .pptx path (default: deck name + .pptx)")
    args = ap.parse_args()
    out = args.out or os.path.splitext(args.deck)[0] + ".pptx"
    convert(args.deck, out)


if __name__ == "__main__":
    main()
