# Website

Static marketing site for Valor.

```
website/
├── index.html              # landing page: hero → what it does → how → local-first → install
├── demo.html               # /demo — one full-screen app: session + review console
├── demo/
│   ├── transcripts.json    # generated — see below
│   └── pr-console.html     # generated — a real /valor-pr-console artifact
├── styles.css              # design system (dark, amber accent)
├── favicon.svg
├── og.svg                  # 1200×630 social card (SVG fallback; render to PNG for X/Twitter)
├── manifest.webmanifest
├── sitemap.xml
├── robots.txt
└── README.md
```

## The demo page

`demo.html` fills the viewport and never scrolls the document — only the thread
does. Two views switch in the header: the recorded **session** (type or take a
suggestion; replies stream in) and the **review console** (the real artifact,
iframed, loaded on first use). The long explanation lives in an About dialog
rather than on screen, so the page itself carries under 120 words. Typing
something unrecorded gets an honest answer, not an improvised one.

The content is real Valor output rather than mock-ups, from two sources:

- **`demo/transcripts.json`** — generated from the capture files in
  [`examples/demo/captures/`](../examples/demo/captures/), which are recordings of
  each workflow run against the seeded demo profile. Edit a capture, then:

  ```bash
  python3 examples/demo/build_transcripts.py
  ```

  A test asserts the committed JSON matches the captures, so the page can't drift
  from what was recorded. `--check` verifies without writing.

  The session flow — which inputs open the session, what each reply offers next,
  and the tool chips — is the `SESSION` table in that same script. The builder
  refuses to generate a graph with unknown ids, dead ends, or transcripts nothing
  can reach.

- **`demo/pr-console.html`** — an actual `/valor-pr-console` artifact built from
  the demo profile's fixture PR. Not a recording: it's the real page, embedded in
  an iframe and self-contained (no network calls), so visitors can drive the
  diagram and take the quiz.

The landing page's feature panels are trimmed excerpts of the same transcripts.
If you re-capture, re-check those excerpts too — nothing enforces the trim.

## Local preview

From the repo root:

```bash
python3 -m http.server 8000 --directory website
```

Then open `http://127.0.0.1:8000/`.
