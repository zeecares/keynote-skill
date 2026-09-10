# keynote-skill

An agent skill for generating presentation decks the way Patrick Winston
taught: slides that expose ideas instead of burying them, opened with an
empowerment promise and closed with contributions.

Distilled from Winston's MIT lecture **"How to Speak"** (MIT OpenCourseWare,
RES.TLL-005, IAP 2018 - given annually for ~40 years). Every rule in the
skill is grounded in the official transcript; see
`references/winston-rules.md` for the rule-by-rule citations.

## Architecture: HTML first

```
                templates/deck.html
                       |
                 deck.html  (one self-contained file: slides + notes)
                  /      \
   scripts/validate_deck.py   browser preview / print-to-PDF
                  |
       scripts/html_to_pptx.py
                  |
              deck.pptx  --(Keynote opens PPTX natively)-->  deck.key
```

- **One source of truth**: the deck is a single HTML file. Slides are
  semantic (`section.slide`, one `h2` headline each), speaker notes are
  `aside.notes`, and the embedded CSS makes the HTML itself presentable in
  any browser.
- **Export, don't redraw**: `html_to_pptx.py` builds the PPTX from native
  text boxes and pictures, so the output stays fully editable - no bitmap
  slides.
- **Keynote**: open the PPTX in Keynote and Save As `.key`. Text, shapes,
  images, and speaker notes carry over. (There is no direct `.key` writer;
  PDF/image routes lose editability.)
- **The rules are executable**: `validate_deck.py` lints the deck against
  the Winston rules - word count per slide, promise up front, contributions
  at the end, no thank-you/questions final slide, no collaborator credits at
  the end, clutter and font floors.

## Use it

```bash
pip install python-pptx                     # only dependency, export only

cp templates/deck.html my-talk.html         # author slides + speaker notes
python3 scripts/validate_deck.py my-talk.html --strict
python3 scripts/html_to_pptx.py my-talk.html -o my-talk.pptx
# Keynote: open my-talk.pptx, then File > Save As -> my-talk.key
```

As an agent skill, drop the repo (or just `SKILL.md` + `references/` +
`templates/` + `scripts/`) into your agent's skills directory; `SKILL.md`
follows the standard name/description frontmatter format.

## What's inside

| Path | What |
| --- | --- |
| `SKILL.md` | Agent skill: when to use, the rules, the workflow |
| `references/winston-rules.md` | Full Winston distillation with transcript citations |
| `templates/deck.html` | Annotated deck template (the authoring contract) |
| `scripts/validate_deck.py` | Winston-rule linter (Python stdlib only) |
| `scripts/html_to_pptx.py` | HTML -> editable PPTX exporter |
| `examples/winston-rules-deck.html` | Example: the method, presented in its own format |

## Provenance

Rules and quotes come from the official MIT OCW transcript of "How to Speak"
by Patrick Winston:

- Lecture page: https://ocw.mit.edu/courses/res-tll-005-how-to-speak-january-iap-2018/pages/how-to-speak/
- Transcript: https://ocw.mit.edu/courses/15-371-innovation-teams-fall-2024/resources/unzc731icuy_transcript/
- Video: https://www.youtube.com/watch?v=Unzc731iCUY

MIT OpenCourseWare material is CC BY-NC-SA 4.0.
