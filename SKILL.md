---
name: keynote
description: Generate presentation decks as HTML first, then export to Keynote and PPTX. Use when the user asks for a deck, slides, keynote, talk, or presentation. Applies Patrick Winston's "How to Speak" rules (MIT OCW) - empowerment-promise openings, few words per slide, contributions endings - and lints the deck against them before export.
---

# Keynote generation (Winston method)

Generate decks HTML-first, then export to Keynote or PPTX. Every design rule
comes from Patrick Winston's MIT lecture "How to Speak"; the full
rule-by-rule distillation with transcript citations is in
`references/winston-rules.md`. Read it before designing a deck.

## When to use

- The user asks for a deck, slides, a keynote, a talk, or a presentation.
- The user asks to turn notes, an essay, a brief, or a report into slides.
- The user asks to review or improve an existing deck's design.

## The rules that drive every decision

Slides **expose** ideas; they do not teach them. They are condiments, not the
main event. Concretely:

1. **Open with an empowerment promise, never a joke** - what the audience
   will know at the end that they don't know now.
2. **One language processor** - the audience can read the slide OR listen to
   the speaker, never both. So: few words per slide (target under 30), big
   type, air. If a sentence matters, the speaker says it; it does not go on
   the slide.
3. **Strip the crimes**: background junk, logos, redundant titles, clutter,
   gratuitous bullets, tiny fonts (35pt is already too small), reading the
   slide, laser pointers (put an arrow in the image instead).
4. **One idea per slide.** Cycle big ideas three times across the deck.
   Divider slides are verbal punctuation so the fogged-out 20% can reboard.
5. **Make it memorable - Winston's star**: Symbol, Slogan, Surprise, Salient
   idea (one that sticks out), Story.
6. **End with Contributions.** The final slide stays up during Q&A; never
   "Thank you", never "Questions?", never bare "Conclusions". Collaborators
   and acknowledgements go on the FIRST slide.

## Deck format: HTML first

Author the deck as ONE self-contained HTML file (`templates/deck.html` is
the starting point):

- One `<section class="slide">` per slide; first slide uses
  `class="slide slide-title"` with `<h1>`, `.subtitle`, `.speaker`.
- Content slides: exactly one `<h2>` headline, then `<p>`, `<ul>/<li>`,
  `<blockquote>`, `<img>`/`<figure>`.
- Speaker notes: `<aside class="notes">` - never rendered on the slide,
  exported into PPTX/Keynote speaker notes.
- Inline `<strong>`/`<em>` carry through to the export.
- Images: relative paths resolve against the deck file's directory.

The embedded CSS renders each slide 1280x720 in any browser and prints one
slide per page, so the HTML alone is already presentable.

## Workflow

1. Extract the speaker's actual facts, numbers, and claims into working
   notes. **Never invent content** - no made-up metrics, dates, quotes,
   logos, or attributions. Gaps go in speaker notes as "[fill: ...]".
2. Plan the slide list against the rules: promise early, one idea per slide,
   contributions last. Draft headlines that carry each slide alone.
3. Write the deck HTML from `templates/deck.html`.
4. Lint it:

   ```bash
   python3 scripts/validate_deck.py deck.html --strict
   ```

   Fix every ERROR; justify every WARN you keep.
5. Preview the HTML in a browser and LOOK at every slide. Fix overflow,
   orphaned words, crowded slides. Re-lint.
6. Export (below), then open the exported file and inspect it too - the
   deliverable is the export, not the HTML.

## Export to PPTX (and Keynote)

```bash
pip install python-pptx        # the only dependency
python3 scripts/html_to_pptx.py deck.html -o deck.pptx
```

The exporter builds a 16:9 PPTX from native text boxes and pictures - every
headline, bullet, and note stays editable. Speaker notes land in the PPTX
notes pane.

**Keynote**: Keynote opens PPTX natively. Open `deck.pptx` in Keynote,
then File > Save As to get a `.key`. Fonts, text, shapes, images, and
speaker notes carry over and remain editable. This is the supported
HTML-to-Keynote path; there is no direct .key writer, and PDF/image routes
produce non-editable slides - do not use them unless the user explicitly
wants an image-only artifact.

## Reviewing an existing deck

Convert to the HTML format (or lint the structure directly) and report
against the rule list: word counts, final-slide form, collaborator
placement, clutter, font floor. Propose the rewrite as HTML, then export.

## Files

- `references/winston-rules.md` - every rule with its transcript citation
- `templates/deck.html` - annotated starting template
- `scripts/validate_deck.py` - the Winston linter (stdlib only)
- `scripts/html_to_pptx.py` - HTML -> PPTX exporter (needs python-pptx)
- `examples/winston-rules-deck.html` - the method presented in its own format
