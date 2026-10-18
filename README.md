# www.xedur.com

Source code for [www.xedur.com](https://www.xedur.com/), a code portfolio site for Eetu Rantanen (XeduR). The site showcases interactive online demos for Solar2D plugins, games, and other projects. Most demos run directly in the browser via embedded iframes that load Solar2D HTML5 app binaries.

The site is hosted on GitHub Pages and built using a custom Python-based static page builder.

## Project structure

```
www.xedur.com/
├── js/                         # Copied from tools/js/ (unchanged files skipped)
│   ├── nav.js                  # Navbar scroll and mobile toggle
│   ├── loadDemo.js             # "Run the app" button handler
│   └── detectMobile.js         # Touch device detection
├── img/                        # Thumbnails and content images
├── favicon.* + site.webmanifest  # Favicon set in the repo root (ico/svg/png + manifest)
├── demo/                       # Generated demo pages + app binaries
│   └── <project>/
│       ├── index.html          # Demo page (generated)
│       └── app/
│           ├── index.html      # iframe loader (generated)
│           ├── <name>.bin      # Solar2D HTML5 binary (manual)
│           └── <name>.data     # Solar2D HTML5 data (manual)
├── tangents/                   # Generated Tangents posts, list/tag pages, feed
├── index.html                  # Generated homepage
├── 404.html                    # Generated 404 page
├── sitemap.xml                 # Generated sitemap
└── tools/                      # Build system
    ├── update_website.py       # Site build script
    ├── markdown_engine.py      # Markdown + front-matter renderer
    ├── html5_build_patcher.py  # Solar2D HTML5 post-build patcher
    ├── css/styles.css          # Stylesheet, inlined into every page
    ├── js/                     # JS source (copied to root js/)
    ├── demos/                  # Per-demo markdown + category manifests
    ├── tangents/               # Tangents post markdown sources
    ├── components/
    │   ├── templates/          # HTML templates
    │   ├── data/               # Site JSON (frontpage, llms, sitemap, Tangents + social-image state)
    │   └── fonts/              # Vendored Roboto (social-card rendering)
    └── standalone/             # Custom standalone projects
```

## Build instructions

Run the build script from the `tools/` directory:

```bash
python update_website.py            # incremental build
python update_website.py min        # incremental build, minified HTML
python update_website.py force      # full rebuild, ignoring the skip cache
python update_website.py min force  # full minified rebuild (either arg order)
```

The committed site is built with `min`; a plain run rewrites every page and `js/*.js` unminified.

### What it generates

| Output | Source |
|--------|--------|
| `index.html` | `frontpage.html` template + the category manifests and demo front matter |
| `404.html` | `404.html` template + collected valid paths for fuzzy matching |
| `sitemap.xml` | All valid page paths + today's date |
| `demo/<folder>/index.html` | `demo.html` template + the demo's `tools/demos/<folder>.md` |
| `demo/<folder>/app/index.html` | `iframe.html` template (Solar2D app loader) |
| `tangents/<slug>/index.html` | `tangents-post.html` template + `tools/tangents/<slug>.md` |
| `tangents/` and `tangents/<n>/` | `tangents-list.html` template (paginated index, 10/page) |
| `tangents/tag/<slug>/` | `tangents-list.html` template (per-tag, paginated) |
| `tangents/feed.xml` | Atom 1.0 feed of the newest posts |
| `tangents/<slug>/<slug>-social.png` | Auto-generated 1200x630 social card (unless `socialImage` names a custom file) |
| `tangents/tangents-social.png` | Generic social card for the index, pagination, and tag pages |
| `js/*.js` | Copied from `tools/js/` (minified with `min`) |

The build copies `tools/js/` into the root `js/` folder, skipping files that have not changed. It never touches `img/` or the app binary files inside `demo/` folders; those are managed manually. CSS lives in `tools/css/styles.css` and is inlined into every page, so there is no root `css/` folder.

### Incremental builds and caching

The builder is dependency-aware: it regenerates only what changed and prunes output that no longer has a source.

- Per-item pages (each `demo/<folder>/index.html`, its `app/index.html`, each `tangents/<slug>/index.html`, and each copied `js/*.js`) are skipped when none of their sources changed. Change detection is a SHA-256 hash of each source file's bytes, not its modification time, so a fresh `git clone` (which resets working-tree mtimes) does not force a rebuild.
- Aggregate pages (`index.html`, `demo/index.html`, the Tangents list and tag pages, `tangents/feed.xml`, `404.html`, `sitemap.xml`, `llms.txt`) are regenerated every run because they depend on many items. The content-level diff still skips the disk write when the output is byte-identical, so repeated runs stay cheap and produce no git churn.
- Global sources force a full rebuild of every per-item page when any of them changes: `base.html`, `navbar.html`, `footer.html`, `tools/css/styles.css`, `update_website.py`, and `markdown_engine.py` (the CSS is inlined into every page, and the templates and engine affect every page). Switching between normal and `min` output also triggers a full rebuild, since the two modes produce different bytes.
- Pruning: a generated page whose source was removed (a deleted demo `.md`, a dropped manifest entry, a deleted post, or a pagination page that no longer exists) is deleted automatically, and its now-empty generated directory is removed. Pruning is containment-guarded: only paths matching a recognized generated-output pattern (demo pages and app loaders, `tangents/` pages, feed and auto-generated social cards, the root generated files, and `js/*.js`) are ever deleted. Any other stale cache entry is logged as a warning and left in place, so a hand-edited or corrupted cache can never remove a manual asset (`img/`, demo thumbnails, `app/*.bin` and `*.data`, or a custom `socialImage` file).
- `force` rebuilds every page regardless of the cache (the cache still loads, so pruning and the app-loader listing check keep working). With no source changes the byte-compare still writes nothing.

The cache lives at `tools/.build_cache.json` (gitignored). It is a pure local build cache: deleting it just triggers one full rebuild whose output is byte-identical to what is already committed, so nothing is written. A corrupt cache is treated as absent.

### Build log

Every run writes a timestamped report to `tools/build_logs/build_log_<YYYY-MM-DD_HH-MM-SS>.txt` (the directory is gitignored). It records the mode, whether the run was forced, the counts of files written / pages skipped / files pruned, and the lists of errors, warnings, files written, and pruned paths. The directory self-rotates: only the newest 30 logs are kept, and each log notes how many older logs it deleted.

## Notes to self

Quick reference for future me. There are three types of projects on the site. Each one is a markdown file at `tools/demos/<stem>.md` whose stem is listed in one of the category manifests (`tools/demos/games.json`, `solar2d.json`, or `other.json`). The order of stems in a manifest's `demos` array is the display order on the site.

### The three project types

**Regular demo** — a Solar2D game/app that runs in the browser via an iframe. This is the most common type. The build script generates a demo page and an iframe app loader. The `.bin` filename is auto-detected from the `app/` folder, and the card thumbnail is auto-generated from the folder name.

**Standalone demo** — a custom HTML/JS project (not a Solar2D app). It uses the site's base template (navbar, footer) but has its own page content. Source files live in `tools/standalone/<folder>/`. Only one exists right now: the Pseudorandom Number Generator.

**External link** — just a card on the homepage that links somewhere else (new tab). No pages are generated. Used for things like Solar2D Playground, the Particle Editor, etc.

### How to tell them apart

The build script checks front-matter keys in this order:
1. Has `externalUrl`? &rarr; External link
2. Has `type: standalone`? &rarr; Standalone demo
3. Otherwise (just has `folder`) &rarr; Regular demo

### Quick checklist: adding a regular demo

1. Build the Solar2D project for HTML5
2. Run `html5_build_patcher.py` on the `.bin` file (removes blur freeze, alert popups, and unused HTML files)
3. Create `demo/<folder>/app/` and put the build files there (`.bin`, `.data`, etc.)
4. Add `<folder>-small.jpg` and `<folder>-large.jpg` to `demo/<folder>/`
5. Create `tools/demos/<folder>.md` with front matter (`title`, `folder`, `descriptionShort` at minimum) and a markdown body ending in a `[[github ...]]` directive
6. Add `<folder>` to the `demos` list in the right category manifest (`tools/demos/<category>.json`)
7. Run `python update_website.py` from `tools/`

### Quick checklist: adding a standalone demo

1. Create `tools/standalone/<folder>/` with:
   - `content.html` — the page body (gets wrapped in the site's base template)
   - `config.json` — page metadata (`title`, `metaDescription`, `metaKeywords`, optional `seo`)
   - `head.html` (optional) — extra `<head>` tags for CSS/JS includes
2. Create `demo/<folder>/` and add `<folder>-small.jpg` and `<folder>-large.jpg`
3. If the project has its own CSS/JS files, put them in `demo/<folder>/css/` or `demo/<folder>/js/` and reference them from `head.html` using `{{basePath}}` for the path prefix
4. Create `tools/demos/<folder>.md` with `type: standalone` front matter (no body) and add `<folder>` to the manifest
5. Run the build script

### Quick checklist: adding an external link

1. Create `tools/demos/<stem>.md` with `externalUrl` and `image` front matter (no body) and add `<stem>` to the right category manifest
2. Point `image` at `img/external/<name>.jpg` (or a custom image path)
3. Run the build script

That's it: no demo folders to create, no build files to place. The card just links out.

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

- The build script generates the HTML files and copies `tools/js/` into the root `js/` folder. It never touches `img/` or the binary files inside `demo/` folders, but it does prune generated pages whose source was removed (see "Incremental builds and caching").
- The build is incremental: unchanged per-item pages are skipped via a content-hash cache (`tools/.build_cache.json`), and the content-level diff still guards every disk write, so it's safe to run repeatedly. Each run writes a report to `tools/build_logs/`.
- The sitemap tracks lastmod dates in `tools/components/data/sitemap_dates.json`. Only pages with actual content or asset changes get today's date.
- For SEO overrides on a demo, add the flat `ogTitle`, `ogDescription`, `metaDescription`, or `ogImageAlt` keys to its front matter (see the detailed reference below).
- The 404 page has built-in fuzzy URL matching — it collects all valid paths during the build and suggests the closest match.

## How to add or update projects

Each project is a markdown file at `tools/demos/<stem>.md`, and its stem is listed in one of the category manifests: `tools/demos/games.json`, `solar2d.json`, or `other.json`. A manifest holds the section title, the section description, and an ordered `demos` list of stems; that order is the display order on the homepage.

The file stem is the demo identity. For regular and standalone demos it must equal the front-matter `folder` (and the `demo/<folder>/` output directory). For external links it is any unique kebab-case id.

Front matter is a flat `key: value` block between `---` fences (parsed by `markdown_engine.parse_front_matter`); it cannot nest, so there is no `seo` object, just individual `ogTitle`/`ogDescription`/`metaDescription`/`ogImageAlt` keys.

### Entry types

There are three types of entries, determined by which front-matter keys are present:

**1. Regular demo** (most common) — a hosted project with an iframe-embedded Solar2D app.

```
---
title: The Dark
folder: the-dark
descriptionShort: Card description shown on the homepage.
tech: Solar2D, Lua
ogTitle: XeduR - The Dark
ogDescription: Description for social media shares.
metaDescription: Custom meta description.
---
The long description in markdown: paragraphs, **bold**, *italic*, `- ` lists, `## ` subheadings, and `[text](url)` links.

[[github url="https://github.com/XeduR/..."]]
```

- `folder` must match the file stem and the actual folder name inside `demo/`.
- The card thumbnail is auto-generated as `demo/<folder>/<folder>-small.jpg` (no `image` key needed).
- The `.bin` filename is auto-detected from the `demo/<folder>/app/` directory (no `binName` key needed).
- `tech`, `ogTitle`, `ogDescription`, `metaDescription`, and `ogImageAlt` are optional.
- The body ends with a `[[github url="..."]]` directive for the public repo panel, or a bare `[[github]]` for the private-source panel when there is no repository.

Generates: `demo/<folder>/index.html` (demo page) and `demo/<folder>/app/index.html` (iframe loader).

**2. External link** — a card on the homepage that links to an external URL. No pages are generated.

```
---
title: Solar2D Playground
externalUrl: https://www.solar2dplayground.com/
image: img/external/solar2d-playground.jpg
descriptionShort: Card description.
tech: HTML5, CSS3, JavaScript
---
```

The presence of `externalUrl` makes it an external entry. `image` is required (there is no `folder` to derive a thumbnail from) and there is no body.

**3. Standalone** — a custom project with its own HTML content instead of an iframe-loaded app.

```
---
title: Pseudorandom Number Generator
folder: pseudorandom-number-generator
type: standalone
descriptionShort: Card description.
tech: HTML5, CSS3, JavaScript, Lua
---
```

No body: the page body, `<head>` extras, and SEO come from `tools/standalone/<folder>/`. That source folder must contain:

| File | Required | Purpose |
|------|----------|---------|
| `content.html` | Yes | The page body content (inserted into the base template) |
| `config.json` | Yes | Page metadata: `title`, `metaDescription`, `metaKeywords`, `seo` |
| `head.html` | No | Extra `<head>` tags (CSS, scripts, etc.) |

Generates: `demo/<folder>/index.html` only (no iframe loader).

### Adding a new regular demo

1. Create `demo/<folder>/app/` and place the Solar2D HTML5 build files there (the `.bin`, `.data`, and any other asset files).
2. Add the thumbnail images `<folder>-small.jpg` and `<folder>-large.jpg` to `demo/<folder>/`.
3. Create `tools/demos/<folder>.md` with front matter and a markdown body, then add `<folder>` to the `demos` list in the right category manifest.
4. Run `python update_website.py` from the `tools/` directory.

### Adding a new standalone project

1. Create `tools/standalone/<folder>/` with `content.html` and `config.json` (and optionally `head.html`).
2. Add the thumbnail images `<folder>-small.jpg` and `<folder>-large.jpg` to `demo/<folder>/`.
3. Create `tools/demos/<folder>.md` with `type: standalone` front matter (no body) and add `<folder>` to the manifest.
4. Run the build script.

### SEO overrides

A regular demo derives its `<meta description>` from `descriptionShort` and its social tags from defaults (`ogTitle` = `XeduR - <title>`, `ogDescription` = `descriptionShort`, `ogImageAlt` = `Screenshot of <title>`). Override any of them with flat front-matter keys:

```
metaDescription: Custom meta description.
ogTitle: Title for social media shares
ogDescription: Description for social media shares
ogImageAlt: Alt text for the preview image
```

`ogImage` is not set by hand: it is always `demo/<folder>/<folder>-large.jpg`. Keywords fall back to the site-wide defaults.

## Tangents (writing system)

Tangents is a markdown-authored writing section at `/tangents/`: paginated list pages, per-tag pages, per-post pages, and an Atom feed, all wrapped in the site chrome. Posts live in `tools/tangents/<slug>.md`; the file stem is the slug and the public URL is `/tangents/<slug>/`. Slugs must be lowercase kebab-case (`[a-z0-9-]`).

### Writing a post

1. Create `tools/tangents/<slug>.md` with front matter and a markdown body.
2. Commit any post images into `tangents/<slug>/` and reference them with `[[image src="foo.png" ...]]` (paths resolve relative to the post URL).
3. Run `python update_website.py` from `tools/`.

Front matter is a flat `key: value` block between `---` fences (no quoting; values are literal trimmed text):

| Key | Required | Purpose |
|-----|----------|---------|
| `title` | Yes | Page `<h1>`, `<title>`, list and feed title |
| `summary` | Yes | List blurb, meta description, OG and feed summary |
| `tags` | No | Comma list; drives the tag chips and tag pages |
| `published` | No | `YYYY-MM-DD` to backdate; otherwise assigned on the first build |
| `draft` | No | `true` excludes the post from the build entirely (not listed, tagged, fed, or in the sitemap) |
| `socialImage` | No | Custom social image filename in `tangents/<slug>/`; absent or `auto` auto-generates a card (see Social share images) |

### Markdown syntax

Headings (`##` through `######`; a body `#` is demoted to `##` because the title is the sole `<h1>`), paragraphs, `**bold**`, `*italic*` or `_italic_`, `[text](url)`, `` `inline code` ``, `-`/`*` and `1.` lists, `>` blockquotes, `---` horizontal rules, and ```` ``` ```` fenced code blocks. Raw HTML is escaped rather than passed through. The parser is flat: nested lists and multi-paragraph list items are out of scope.

Directives sit on their own line as `[[name key="value"]]`:

- `[[image src="foo.png" alt="..." caption="..." width="..." height="..."]]`: a `<figure>`; `src` is used verbatim and resolves relative to the post URL.
- `[[youtube id="VIDEO_ID" title="..."]]`: a GDPR-compliant click-to-load embed (see below).
- `[[github repo="owner/name"]]`, `[[github url="https://..."]]`, or a bare `[[github]]`: the repository link panel.

A mistyped or unknown directive is a build error, not silently rendered text.

### Dates

Publish dates and body-content hashes live in `tools/components/data/tangents_dates.json`, which is committed because publish dates cannot be re-derived after the fact. A post is published on its first build (or on its front-matter `published` date). "Last updated" is set only when the rendered body's hash changes, so editing `summary`, `tags`, or `title` alone does not bump it. Dates render as `13 July 2026`.

### Pagination, tags, feed

List pages hold 10 posts, newest first (`/tangents/`, then `/tangents/2/`, and so on). Each tag gets its own paginated set at `/tangents/tag/<slug>/`. Two tag spellings that slugify to the same value (for example `Solar2D` and `solar2d`) are a build error; unify them in the front matter. The Atom feed at `/tangents/feed.xml` carries the newest 20 posts and is linked from every post `<head>`.

### YouTube consent

`[[youtube]]` renders a thumbnail placeholder, not an iframe. `tools/js/video-consent.js` (loaded only on pages that need it) swaps in a `youtube-nocookie.com` iframe after the visitor clicks "I accept". Consent is stored in `localStorage` (`videosAccepted`), so the site sets no cookie of its own and nothing is requested from `youtube-nocookie.com` before consent. The thumbnail is a single cookieless image from `img.youtube.com`, loaded before consent as a deliberate trade-off.

### Social share images

Every post page ships an Open Graph / Twitter card. By default the build auto-generates a branded 1200x630 PNG (the X mark, a "Tangents" label, and the post title) at `tangents/<slug>/<slug>-social.png`. A single generic card at `tangents/tangents-social.png` serves the index, pagination, and tag pages.

The `socialImage` front-matter key overrides the default:

- Absent or `auto`: auto-generate the card.
- `<filename>`: use the committed file `tangents/<slug>/<filename>` verbatim (never resized or rewritten); 1200x630 is recommended. A missing file warns and falls back to auto-generation.
- `<slug>-social.png` (the reserved generated name) is a build error: rename the custom file or drop the key.

Auto-generated cards are committed like all generated output. A card regenerates only when the generator script, the post title, or the logo/font assets change; the two SHA-256 hashes that gate this live in the committed manifest `tools/components/data/social_images.json` (it ships empty and populates on the first build, like `tangents_dates.json`). An up-to-date card is never rewritten, so repeated builds cause no churn, and a generator design change rolls out to every card on the next build. Deleting a post prunes its generated card; a custom `socialImage` file is never pruned.

Rendering needs [Pillow](https://python-pillow.github.io/) (the `game-web-dev` and `ai-data-dev` containers pin 12.2.0). It is imported only when a card actually renders, so a fully up-to-date build never loads it. When a render is needed and Pillow is missing, the build fails with an actionable message rather than degrading the output.

The generator (`tools/generate_social_images.py`) also runs standalone for iterating on the card design:

```bash
python generate_social_images.py              # every non-draft post + the generic card
python generate_social_images.py force        # regenerate everything (writes only what changed)
python generate_social_images.py <slug> ...   # only the named posts (other manifest entries kept)
```

After adding posts, run `update_website.py` normally (it calls the generator); the CLI only refreshes images and the manifest, not the page HTML.

#### Vendored fonts

Card text uses Roboto, vendored into `tools/components/fonts/` because the deployed `fonts/*.woff2` are weight-limited latin subsets unsuitable for card rendering. The `hinted/static` builds are used (not the smaller `web/static` subset) for full glyph coverage of arbitrary post titles, including diacritics.

- Source: `Roboto_v3.016.zip` from <https://github.com/googlefonts/roboto-3-classic/releases/download/v3.016/Roboto_v3.016.zip> (release tag v3.016).
- License: SIL Open Font License 1.1 (`tools/components/fonts/Roboto-OFL.txt`).
- `Roboto-Regular.ttf` SHA-256 `9f300202f482ad59f8b13bc3131a295744d14fd530fa3765a0a11ec87264d203`
- `Roboto-Bold.ttf` SHA-256 `44f13e570a8b3fc42240abfcb3d72fe298f3dd6a25db0c78d0c2495dbd0e9121`

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
| `demo.html` | Demo page layout (rendered markdown body + iframe container) |
| `iframe.html` | Solar2D HTML5 app loader with Zlib decompression and progress bar |
| `contact.html` | Contact info snippet (reused at top and bottom of homepage) |
| `repo-panel.html` | GitHub repository link panel (emitted by the `[[github]]` directive) |
| `tangents-post.html` | Single Tangents post page |
| `tangents-list.html` | Tangents index and tag pages (paginated) |
| `tangents-item.html` | One row in a Tangents list |
| `404.html` | Error page with embedded valid paths for fuzzy URL matching |

The `{{basePath}}` token handles relative paths (empty for root pages, `../../` for demo pages).

## Author

Eetu Rantanen ([www.erantanen.com](https://www.erantanen.com/))

## License

MIT
