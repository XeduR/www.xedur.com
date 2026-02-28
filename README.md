# www.xedur.com

Source code for [www.xedur.com](https://www.xedur.com/), a code portfolio site for Eetu Rantanen (XeduR). The site showcases interactive online demos for Solar2D plugins, games, and other projects. Most demos run directly in the browser via embedded iframes that load Solar2D HTML5 app binaries.

The site is hosted on GitHub Pages and built using a custom Python-based static page builder.

## Project structure

```
www.xedur.com/
├── css/styles.css              # Main stylesheet
├── js/
│   ├── nav.js                  # Navbar scroll and mobile toggle
│   ├── loadDemo.js             # "Run the app" button handler
│   └── detectMobile.js         # Touch device detection
├── img/                        # Thumbnails, icons, favicons
├── demo/                       # Generated demo pages + app binaries
│   └── <project>/
│       ├── index.html          # Demo page (generated)
│       └── app/
│           ├── index.html      # iframe loader (generated)
│           ├── <name>.bin      # Solar2D HTML5 binary (manual)
│           └── <name>.data     # Solar2D HTML5 data (manual)
├── index.html                  # Generated homepage
├── 404.html                    # Generated 404 page
├── sitemap.xml                 # Generated sitemap
└── tools/                      # Build system
    ├── update_website.py       # Site build script
    ├── html5_build_patcher.py  # Solar2D HTML5 post-build patcher
    ├── components/
    │   ├── templates/          # HTML templates
    │   └── data/               # JSON section data
    └── standalone/             # Custom standalone projects
```

## Build instructions

Run the build script from the `tools/` directory:

```bash
python update_website.py          # normal build
python update_website.py min      # minified HTML (strips comments and whitespace)
```

### What it generates

| Output | Source |
|--------|--------|
| `index.html` | `frontpage.html` template + all section JSON files |
| `404.html` | `404.html` template + collected valid paths for fuzzy matching |
| `sitemap.xml` | All valid page paths + today's date |
| `demo/<folder>/index.html` | `demo.html` template + JSON entry data |
| `demo/<folder>/app/index.html` | `iframe.html` template (Solar2D app loader) |

The script never touches `css/`, `js/`, `img/`, or the app binary files inside `demo/` folders. Those are managed manually.

## Notes to self

Quick reference for future me. There are three types of projects on the site. Each one is just a JSON entry in one of the section files (`games.json`, `solar2d.json`, or `other.json`) under `tools/components/data/`. The order of entries in the `demos` array is the display order on the site.

### The three project types

**Regular demo** — a Solar2D game/app that runs in the browser via an iframe. This is the most common type. The build script generates a demo page and an iframe app loader. The `.bin` filename is auto-detected from the `app/` folder, and the card thumbnail is auto-generated from the folder name.

**Standalone demo** — a custom HTML/JS project (not a Solar2D app). It uses the site's base template (navbar, footer) but has its own page content. Source files live in `tools/standalone/<folder>/`. Only one exists right now: the Pseudorandom Number Generator.

**External link** — just a card on the homepage that links somewhere else (new tab). No pages are generated. Used for things like Solar2D Playground, the Particle Editor, etc.

### How to tell them apart in JSON

The build script checks fields in this order:
1. Has `externalUrl`? &rarr; External link
2. Has `"type": "standalone"`? &rarr; Standalone demo
3. Otherwise (just has `folder`) &rarr; Regular demo

### Quick checklist: adding a regular demo

1. Build the Solar2D project for HTML5
2. Run `html5_build_patcher.py` on the `.bin` file (removes blur freeze, alert popups, and unused HTML files)
3. Create `demo/<folder>/app/` and put the build files there (`.bin`, `.data`, etc.)
4. Add `<folder>-small.jpg` and `<folder>-large.jpg` to `demo/<folder>/`
5. Add a JSON entry to the right section file (needs `title`, `folder`, `descriptionShort` at minimum)
6. Run `python update_website.py` from `tools/`

### Quick checklist: adding a standalone demo

1. Create `tools/standalone/<folder>/` with:
   - `content.html` — the page body (gets wrapped in the site's base template)
   - `config.json` — page metadata (`title`, `metaDescription`, `metaKeywords`, optional `seo`)
   - `head.html` (optional) — extra `<head>` tags for CSS/JS includes
2. Create `demo/<folder>/` and add `<folder>-small.jpg` and `<folder>-large.jpg`
3. If the project has its own CSS/JS files, put them in `demo/<folder>/css/` or `demo/<folder>/js/` and reference them from `head.html` using `{{basePath}}` for the path prefix
4. Add a JSON entry with `"type": "standalone"` to the right section file
5. Run the build script

### Quick checklist: adding an external link

1. Add a JSON entry with `externalUrl` to the right section file
2. Set `"image": "img/external/placeholder.jpg"` (or a custom image path)
3. Run the build script

That's it — no folders to create, no files to place. The card just links out.

### The html5_build_patcher.py utility

Run this on every new Solar2D HTML5 build **before** placing files in `demo/<folder>/app/`. It patches the `.bin` file and the generated `index.html`:

```bash
python html5_build_patcher.py path/to/build/folder
```

What it does:
- Removes the blur callback that freezes the app when the user clicks outside of it
- Removes the `alert()` from `printErr` that causes blocking popups on non-fatal WASM errors
- Deletes `index-debug.html` and `index-nosplash.html` (unused in production)

### Other things to remember

- The build script only generates HTML files. It never touches `css/`, `js/`, `img/`, or the binary files inside `demo/` folders.
- The build script skips writing files that haven't changed (content-level diff check), so it's safe to run repeatedly.
- The sitemap tracks lastmod dates in `tools/components/data/sitemap_dates.json`. Only pages with actual content or asset changes get today's date.
- For SEO overrides on a demo, add an `seo` object to the JSON entry (see the detailed reference below).
- The 404 page has built-in fuzzy URL matching — it collects all valid paths during the build and suggests the closest match.

## How to add or update projects

All project entries are defined in JSON files under `tools/components/data/`. Each file represents one section on the homepage: `games.json`, `solar2d.json`, and `other.json`. The order of entries in the `demos` array determines the display order on the site.

See `template.json` in the same folder for a documented reference of all available fields.

### Entry types

There are three types of entries, determined by which fields are present:

**1. Regular demo** (most common) — a hosted project with an iframe-embedded Solar2D app.

```json
{
    "title": "The Dark",
    "folder": "the-dark",
    "descriptionShort": "Card description shown on the homepage.",
    "descriptionLong": "Longer description shown on the demo page. HTML allowed.",
    "tech": "Solar2D, Lua",
    "repository": "https://github.com/XeduR/..."
}
```

- `folder` must match the actual folder name inside `demo/`.
- The card thumbnail is auto-generated as `demo/<folder>/<folder>-small.jpg` (no `image` field needed).
- The `.bin` filename is auto-detected from the `demo/<folder>/app/` directory (no `binName` field needed).
- `descriptionLong`, `tech`, `repository`, and `seo` are all optional.

Generates: `demo/<folder>/index.html` (demo page) and `demo/<folder>/app/index.html` (iframe loader).

**2. External link** — a card on the homepage that links to an external URL. No pages are generated.

```json
{
    "title": "Solar2D Playground",
    "externalUrl": "https://www.solar2dplayground.com/",
    "image": "img/external/solar2d-playground.jpg",
    "descriptionShort": "Card description.",
    "tech": "HTML5, CSS3, JavaScript"
}
```

The presence of `externalUrl` makes it an external entry. The card opens in a new tab.

**3. Standalone** — a custom project with its own HTML content instead of an iframe-loaded app.

```json
{
    "title": "Pseudorandom Number Generator",
    "type": "standalone",
    "folder": "pseudorandom-number-generator",
    "descriptionShort": "Card description.",
    "tech": "HTML5, CSS3, JavaScript, Lua"
}
```

Standalone projects require a source folder at `tools/standalone/<folder>/` containing:

| File | Required | Purpose |
|------|----------|---------|
| `content.html` | Yes | The page body content (inserted into the base template) |
| `config.json` | Yes | Page metadata: `title`, `metaDescription`, `metaKeywords`, `seo` |
| `head.html` | No | Extra `<head>` tags (CSS, scripts, etc.) |

Generates: `demo/<folder>/index.html` only (no iframe loader).

### Adding a new regular demo

1. Create `demo/<folder>/app/` and place the Solar2D HTML5 build files there (the `.bin`, `.data`, and any other asset files).
2. Add the thumbnail images `<folder>-small.jpg` and `<folder>-large.jpg` to `demo/<folder>/`.
3. Add an entry to the appropriate section JSON file in `tools/components/data/`.
4. Run `python update_website.py` from the `tools/` directory.

### Adding a new standalone project

1. Create `tools/standalone/<folder>/` with `content.html` and `config.json` (and optionally `head.html`).
2. Add the thumbnail images `<folder>-small.jpg` and `<folder>-large.jpg` to `demo/<folder>/`.
3. Add an entry with `"type": "standalone"` to the appropriate section JSON file.
4. Run the build script.

### SEO overrides

Any demo entry can include an optional `seo` object to override meta tags and social media previews:

```json
"seo": {
    "metaDescription": "Custom meta description.",
    "metaKeywords": "custom, keywords",
    "ogTitle": "Title for social media shares",
    "ogDescription": "Description for social media shares",
    "ogImage": "https://www.xedur.com/img/preview.jpg",
    "ogImageAlt": "Alt text for the preview image"
}
```

If omitted, `metaDescription` falls back to `descriptionShort` and keywords fall back to the site-wide defaults.

## Templates

HTML templates live in `tools/components/templates/`. They use `{{placeholder}}` tokens that the build script replaces with generated content.

| Template | Purpose |
|----------|---------|
| `base.html` | Root HTML document (head, meta tags, favicon links, navbar, footer) |
| `navbar.html` | Navigation bar (desktop + mobile responsive) |
| `footer.html` | Page footer |
| `frontpage.html` | Homepage layout (intro, sections, Learn Solar2D, contact) |
| `section.html` | Section container with heading, description, and card grid |
| `card.html` | Individual project card |
| `demo.html` | Demo page layout (description, repo link, iframe container) |
| `iframe.html` | Solar2D HTML5 app loader with Zlib decompression and progress bar |
| `contact.html` | Contact info snippet (reused at top and bottom of homepage) |
| `repo-panel.html` | GitHub repository link panel |
| `404.html` | Error page with embedded valid paths for fuzzy URL matching |

The `{{basePath}}` token handles relative paths (empty for root pages, `../../` for demo pages).

## Author

Eetu Rantanen ([www.erantanen.com](https://www.erantanen.com/))

## License

MIT
