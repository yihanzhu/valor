# Website

Static marketing site for Valor.

```
website/
├── index.html              # one-page landing
├── styles.css              # design system (dark, amber accent)
├── favicon.svg
├── og.svg                  # 1200×630 social card (SVG fallback; render to PNG for X/Twitter)
├── manifest.webmanifest
├── sitemap.xml
├── robots.txt
└── README.md
```

## Local preview

From the repo root:

```bash
python3 -m http.server 8000 --directory website
```

Then open `http://127.0.0.1:8000/`.
