#!/usr/bin/env python3
"""
Static site builder for www.xedur.com.
Reads templates and JSON data from components/,
then generates HTML pages in the site root directory.

Usage:
    python update_website.py            # incremental build
    python update_website.py min        # incremental build, minified HTML
    python update_website.py force      # full rebuild (ignore the skip cache)
    python update_website.py min force  # full minified rebuild
"""

import os
import re
import sys
import json
import hashlib
import urllib.parse
from datetime import date, datetime

import markdown_engine
import generate_social_images

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
COMPONENTS_DIR = os.path.join(SCRIPT_DIR, "components")
TEMPLATES_DIR = os.path.join(COMPONENTS_DIR, "templates")
DATA_DIR = os.path.join(COMPONENTS_DIR, "data")
DEMOS_DIR = os.path.join(SCRIPT_DIR, "demos")
STANDALONE_DIR = os.path.join(SCRIPT_DIR, "standalone")
CSS_SRC_DIR = os.path.join(SCRIPT_DIR, "css")
JS_SRC_DIR = os.path.join(SCRIPT_DIR, "js")
OUTPUT_DIR = ROOT_DIR

# Module-level flag set by main() based on the "min" argument.
MINIFY = False

# Tracks output files that were actually modified during this build (forward-slash paths
# relative to ROOT_DIR).  Used by build_sitemap to decide which lastmod dates to bump.
CHANGED_FILES = set()

# Persistent record of per-page lastmod dates so unchanged pages keep their old date.
SITEMAP_DATES_FILE = os.path.join(SCRIPT_DIR, "components", "data", "sitemap_dates.json")

# Categories in display order (matches frontpage.html tag order)
CATEGORIES = ["games", "solar2d", "other"]

DEFAULT_KEYWORDS = (
    "Eetu Rantanen, XeduR, Solar2D, Lua, "
    "gamedev, game development, open source, code portfolio"
)

SITE_BASE_URL = "https://www.xedur.com"

# Tangents writing system.
TANGENTS_SRC_DIR = os.path.join(SCRIPT_DIR, "tangents")
TANGENTS_DATES_FILE = os.path.join(DATA_DIR, "tangents_dates.json")
TANGENTS_PAGE_SIZE = 10
# Longest summary shown anywhere: list rows cut there and add "...", and
# meta/OG descriptions end at a word with an ellipsis within it.
SUMMARY_MAX = 160
# Sort menu, search field, and reset over the tag chips; hidden until js/tag-filter.js runs.
TAG_TOOLS_HTML = (
    '<div class="tag-tools" hidden>\n'
    '<div class="tag-tool">\n'
    '<label for="tag-sort">Sort by:</label>\n'
    '<span class="select-wrap">\n'
    '<select id="tag-sort">\n'
    '<option value="count-desc">Most tangents</option>\n'
    '<option value="count-asc">Fewest tangents</option>\n'
    '<option value="name-asc">A to Z</option>\n'
    '<option value="name-desc">Z to A</option>\n'
    "</select>\n"
    "</span>\n"
    "</div>\n"
    '<div class="tag-tool">\n'
    '<label for="tag-search">Search:</label>\n'
    '<input id="tag-search" type="search" autocomplete="off" spellcheck="false">\n'
    "</div>\n"
    '<button type="button" class="tag-reset">Clear all</button>\n'
    "</div>"
)
IMAGE_FALLBACK_SCRIPT = '<script defer src="{{basePath}}js/image-fallback.js"></script>'
FEED_MAX_ENTRIES = 20

# Intro blurb on the Tangents index, also its meta description.
TANGENTS_INTRO = "Occasional musings, tutorials, half-formed ideas, and other pointless thoughts."

# Locale-independent English month names for the "13 July 2026" date format.
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# Post slugs (file stems) must be lowercase kebab-case.
TANGENT_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# Inline SVG icons injected next to external and mailto links.
LINK_ICON_SVG = (
    '<svg class="link-icon" viewBox="0 0 24 24">'
    '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    '<polyline points="15 3 21 3 21 9"/>'
    '<line x1="10" y1="14" x2="21" y2="3"/>'
    '</svg>'
)

EMAIL_ICON_SVG = (
    '<svg class="email-icon" viewBox="0 0 24 24">'
    '<rect width="20" height="16" x="2" y="4" rx="2"/>'
    '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'
    '</svg>'
)

# ------------------------------------------------------------------------------------
# Incremental build cache and build log

# Gitignored local build cache (content-hash manifest of sources and outputs).
BUILD_CACHE_FILE = os.path.join(SCRIPT_DIR, ".build_cache.json")

# Sources whose change forces a full rebuild of every per-item page. Paths are
# relative to SCRIPT_DIR (the tools/ directory). CSS is inlined into every page,
# and the base/navbar/footer templates plus the markdown engine affect them all.
GLOBAL_SOURCES = [
    "components/templates/base.html",
    "components/templates/navbar.html",
    "components/templates/footer.html",
    "css/styles.css",
    "update_website.py",
    "markdown_engine.py",
]

# Repo-relative POSIX patterns for paths prune_orphans is allowed to delete. A
# stale cache entry matching none of these is warned and left in place, so a
# poisoned or hand-edited cache can never delete a manual asset.
GENERATED_OUTPUT_PATTERNS = [
    re.compile(r"^index\.html$"),
    re.compile(r"^404\.html$"),
    re.compile(r"^sitemap\.xml$"),
    re.compile(r"^llms\.txt$"),
    re.compile(r"^js/[^/]+\.js$"),
    re.compile(r"^demo/index\.html$"),
    re.compile(r"^demo/[^/]+/index\.html$"),
    re.compile(r"^demo/[^/]+/app/index\.html$"),
    re.compile(r"^tangents/feed\.xml$"),
    re.compile(r"^tangents/(?:[^/]+/)*index\.html$"),
    # Auto-generated social cards (per-post, the generic index card, the frontpage
    # card, and per-demo cards). Custom socialImage files never match these and
    # are never recorded, so pruning cannot touch them.
    re.compile(r"^tangents/[^/]+/[^/]+-social\.png$"),
    re.compile(r"^tangents/tangents-social\.png$"),
    re.compile(r"^img/xedur-social\.png$"),
    re.compile(r"^demo/([^/]+)/\1-social\.png$"),
]

# Loaded from the previous manifest by load_build_cache(); read by should_build().
_PREV_SOURCES = {} # {rel_path: sha256}
_PREV_OUTPUTS = {} # {rel_path: [dep, ...]}
_PREV_APP_LISTINGS = {} # {app_dir_rel: "a.bin,b.data,..."}
_PREV_MINIFY = False # MINIFY mode of the run that wrote the manifest

# Accumulated during this run.
_HASH_CACHE = {} # {abs_path: sha256} memoized for this run
_NEW_OUTPUTS = {} # {rel_path: [dep, ...]}
_NEW_APP_LISTINGS = {} # {app_dir_rel: listing}

SKIPPED_PAGES = 0 # per-item pages skipped as up to date
CACHE_MISSING = True # no prior cache existed (forces a full build)
FORCE = False # set from the "force" CLI arg
GLOBAL_DIRTY = True # recomputed in main() after the cache loads

# Per-run build log (gitignored directory, newest BUILD_LOG_KEEP kept).
BUILD_LOG_DIR = os.path.join(SCRIPT_DIR, "build_logs")
BUILD_LOG_KEEP = 30
BUILD_LOG_EVENTS = [] # [(level, message)], level in {"info", "warning", "error"}


def read_json_file(path, *, required):
    """Load a committed JSON data file; a missing file is an empty dict.

    A corrupt file raises when required (its contents cannot be re-derived, so
    the build must not overwrite it), and otherwise warns and reads as empty.
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as error:
        rel = os.path.relpath(path, ROOT_DIR)
        if required:
            raise ValueError(f"{rel} is unreadable ({error}); restore it from git before building") from error
        log_warning(f"{rel} is unreadable ({error}); starting from an empty record")
        return {}


def write_json_file(path, data, **dump_options):
    """Write JSON through a temporary file so an interrupted build never truncates it.

    An unchanged file is left untouched.
    """
    text = json.dumps(data, **dump_options) + "\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == text:
                return
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(temp_path, path)


def log_info(message):
    print(f"  {message}")
    BUILD_LOG_EVENTS.append(("info", message))


def log_warning(message):
    print(f"  WARNING: {message}")
    BUILD_LOG_EVENTS.append(("warning", message))


def log_error(message):
    print(f"  ERROR: {message}")
    BUILD_LOG_EVENTS.append(("error", message))


# ------------------------------------------------------------------------------------
# Minification and formatting helpers

def minify_html(text):
    """Remove HTML comments and collapse whitespace, preserving script, style, and pre blocks."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Extract <script> and <style> blocks so HTML whitespace collapsing
    # doesn't destroy JavaScript // comments or CSS syntax.
    blocks = []

    def _extract(match):
        blocks.append(match.group(0))
        return f'\x00BLOCK{len(blocks) - 1}\x00'

    text = re.sub(r'<script[^>]*>.*?</script>', _extract, text,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', _extract, text,
                  flags=re.DOTALL | re.IGNORECASE)
    # <pre> whitespace is rendered, so its blocks are restored verbatim.
    text = re.sub(r'<pre\b[^>]*>.*?</pre>', _extract, text,
                  flags=re.DOTALL | re.IGNORECASE)

    # Minify HTML (outside the extracted blocks).
    text = re.sub(r'>\s+<', '><', text)
    text = re.sub(r'\s+', ' ', text)

    # Minify and restore each extracted block.
    for i, block in enumerate(blocks):
        m = re.match(r'(<script[^>]*>)(.*?)(</script>)',
                     block, flags=re.DOTALL | re.IGNORECASE)
        if m:
            block = m.group(1) + minify_js(m.group(2)) + m.group(3)
        else:
            m = re.match(r'(<style[^>]*>)(.*?)(</style>)',
                         block, flags=re.DOTALL | re.IGNORECASE)
            if m:
                block = m.group(1) + minify_css(m.group(2)) + m.group(3)
        text = text.replace(f'\x00BLOCK{i}\x00', block, 1)

    return text.strip()


def minify_css(text):
    """Remove CSS comments and collapse whitespace for a smaller file."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'\s+', ' ', text)
    # '+' keeps its spaces: calc() requires whitespace around + and -.
    text = re.sub(r'\s*([{}:;,>~])\s*', r'\1', text)
    text = re.sub(r';\s*}', '}', text)
    return text.strip()


def _strip_inline_comment(line):
    """Remove a trailing // comment from a JS line, preserving // inside strings."""
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '\\' and (in_single or in_double):
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == '/' and not in_single and not in_double:
            if i + 1 < len(line) and line[i + 1] == '/':
                return line[:i].rstrip()
        i += 1
    return line


def minify_js(text):
    """Remove JS comments and collapse whitespace for a smaller file.

    Uses a conservative approach suitable for the simple scripts on this site.
    """
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        if stripped:
            stripped = _strip_inline_comment(stripped)
            if stripped:
                lines.append(stripped)
    text = '\n'.join(lines)
    # Collapse horizontal whitespace only. Newlines must be preserved
    # because JavaScript relies on them for automatic semicolon insertion
    # and this "homebaked no dependency minifier" isn't a proper minifier.
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text.strip()


def indent_block(text, spaces):
    """Indent all non-empty lines of text by the given number of spaces."""
    prefix = " " * spaces
    lines = text.split('\n')
    return '\n'.join(prefix + line if line.strip() else line for line in lines)


_PRE_TAG_RE = re.compile(r'<(/?)pre\b', re.IGNORECASE)


def _ends_inside_pre(line, in_pre):
    """Return whether a <pre> is still open after this line."""
    for match in _PRE_TAG_RE.finditer(line):
        in_pre = match.group(1) == ""
    return in_pre


def replace_indented(template, tag, content):
    """Replace a template tag, indenting all content lines to match the tag's position.

    When a tag like ``{{body}}`` sits on its own line with leading whitespace,
    subsequent lines of the replacement content are indented to the same level
    so that the generated HTML nesting stays correct.
    """
    if not content:
        return template.replace(tag, "")

    # Detect how many leading spaces the tag's line has.
    indent_str = ""
    for line in template.split('\n'):
        stripped = line.lstrip()
        if stripped.startswith(tag):
            indent_str = " " * (len(line) - len(stripped))
            break

    if not indent_str:
        return template.replace(tag, content)

    # Apply that indentation to every content line after the first, except
    # lines inside a <pre>, whose whitespace is rendered.
    content_lines = content.split('\n')
    indented_lines = [content_lines[0]]
    in_pre = _ends_inside_pre(content_lines[0], False)
    for cline in content_lines[1:]:
        if in_pre:
            indented_lines.append(cline)
        elif cline.strip():
            indented_lines.append(indent_str + cline)
        else:
            indented_lines.append("")
        in_pre = _ends_inside_pre(cline, in_pre)

    return template.replace(tag, '\n'.join(indented_lines))


# ------------------------------------------------------------------------------------
# File loading

def load_file(filename):
    """Read a file from components/templates/ and return its contents as a string."""
    filepath = os.path.join(TEMPLATES_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def load_json(filename):
    """Read a JSON file from components/data/ and return the parsed object."""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_demo_data():
    """Return (manifests, demos_by_stem).

    manifests[cat] = {sectionIndex, band, sectionTitle, sectionDescription, demos: [stem, ...]}
    demos_by_stem[stem] = parsed front-matter dict for tools/demos/<stem>.md
    """
    manifests, demos_by_stem = {}, {}
    for cat in CATEGORIES:
        path = os.path.join(DEMOS_DIR, f"{cat}.json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            manifests[cat] = json.load(f)
        for stem in manifests[cat].get("demos", []):
            if stem in demos_by_stem:
                continue
            md_path = os.path.join(DEMOS_DIR, f"{stem}.md")
            with open(md_path, "r", encoding="utf-8") as f:
                front, body = markdown_engine.parse_front_matter(f.read(), source=f"{stem}.md")
            # The stem is the demo identity; for non-external demos it must equal
            # the front-matter folder (the demo/<folder>/ output dir).
            if not front.get("externalUrl") and front.get("folder") != stem:
                raise ValueError(f"{stem}.md: front-matter folder {front.get('folder')!r} must equal the file stem")
            front["_body"] = body            # stash raw body for lazy render
            demos_by_stem[stem] = front
    return manifests, demos_by_stem


# ------------------------------------------------------------------------------------
# Incremental build helpers

def _rel(abs_path):
    """Repo-relative POSIX path for a manifest key."""
    return os.path.relpath(abs_path, ROOT_DIR).replace(os.sep, "/")


def source_hash(rel_path):
    """SHA-256 of a source file, memoized. rel_path is repo-relative POSIX.

    Missing files hash to the empty-string sentinel "" so that adding or
    removing a dependency is itself detected as a change.
    """
    abs_path = os.path.join(ROOT_DIR, rel_path.replace("/", os.sep))
    if abs_path in _HASH_CACHE:
        return _HASH_CACHE[abs_path]
    if not os.path.isfile(abs_path):
        _HASH_CACHE[abs_path] = ""
        return ""
    h = hashlib.sha256()
    with open(abs_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()
    _HASH_CACHE[abs_path] = digest
    return digest


def load_build_cache():
    """Load the previous build manifest into module state.

    Runs even under FORCE: pruning and the app-listing comparison need the
    previous manifest either way. FORCE only bypasses the skip decisions, which
    check it directly. A corrupt, unreadable, or structurally invalid cache is
    treated as missing so a bad file never breaks the build.
    """
    global _PREV_SOURCES, _PREV_OUTPUTS, _PREV_APP_LISTINGS, _PREV_MINIFY, CACHE_MISSING
    if not os.path.exists(BUILD_CACHE_FILE):
        CACHE_MISSING = True
        return
    try:
        with open(BUILD_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        CACHE_MISSING = True
        return

    # An unrecognized schema version must not be misread as v1.
    if not isinstance(data, dict) or data.get("version") != 1:
        CACHE_MISSING = True
        return

    sources = data.get("sources")
    outputs = data.get("outputs")
    listings = data.get("app_listings")
    if not (isinstance(sources, dict) and isinstance(outputs, dict)
            and isinstance(listings, dict)):
        CACHE_MISSING = True
        return

    _PREV_SOURCES = sources
    _PREV_OUTPUTS = outputs
    _PREV_APP_LISTINGS = listings
    _PREV_MINIFY = bool(data.get("minify", False))
    CACHE_MISSING = False


def compute_global_dirty():
    """True if any global source changed (cache missing, force, or mode flip)."""
    if CACHE_MISSING or FORCE:
        return True
    if _PREV_MINIFY != MINIFY:
        # A min build and a normal build produce different bytes from the same
        # sources, so switching modes must rebuild everything.
        return True
    for rel in (_rel(os.path.join(SCRIPT_DIR, p)) for p in GLOBAL_SOURCES):
        if source_hash(rel) != _PREV_SOURCES.get(rel):
            return True
    return False


def should_build(output_rel, dep_rels, extra_dirty=False):
    """Decide whether a per-item page must be regenerated.

    dep_rels: repo-relative POSIX source paths this output depends on. Do NOT
        include the global sources; GLOBAL_DIRTY covers those.
    extra_dirty: caller-supplied dirtiness for inputs that are not hashable
        source files (the app-listing comparison uses this).
    Always records the output and its deps in _NEW_OUTPUTS so pruning keeps the
    page alive even when the build is skipped. A change to the dependency SET
    itself (a dep added or removed since last run) also forces a rebuild; the
    per-dep hash loop below cannot see a dropped dep because it is no longer in
    dep_rels. Tangents post pages rely on this when a neighbour post appears or
    disappears, and Task 4's custom-image dep will rely on it too.
    """
    global SKIPPED_PAGES
    _NEW_OUTPUTS[output_rel] = list(dep_rels)
    if GLOBAL_DIRTY or CACHE_MISSING or FORCE or extra_dirty:
        return True
    abs_out = os.path.join(ROOT_DIR, output_rel.replace("/", os.sep))
    if not os.path.exists(abs_out):
        return True
    if output_rel not in _PREV_OUTPUTS:
        return True
    if set(dep_rels) != set(_PREV_OUTPUTS[output_rel]):
        return True
    for dep in dep_rels:
        if source_hash(dep) != _PREV_SOURCES.get(dep):
            return True
    SKIPPED_PAGES += 1
    return False


def record_output(output_rel, dep_rels=()):
    """Record an output produced outside should_build so pruning keeps it.

    Used by write_file for the always-built aggregate pages, and available to
    future builders that emit outputs (for example generated images) without a
    per-item skip decision.
    """
    _NEW_OUTPUTS[output_rel] = list(dep_rels)


def save_build_cache():
    """Persist the manifest: hash every source referenced this run.

    Hashes are gathered here (memoized via source_hash) rather than relying on
    what the skip checks hashed: on cold and forced builds should_build and
    compute_global_dirty short-circuit before hashing, and a manifest saved from
    those partial hashes would leave the next run unable to skip anything.
    """
    referenced = set()
    for deps in _NEW_OUTPUTS.values():
        referenced.update(deps)
    referenced.update(_rel(os.path.join(SCRIPT_DIR, p)) for p in GLOBAL_SOURCES)
    sources = {rel: source_hash(rel) for rel in sorted(referenced)}
    data = {
        "version": 1,
        "sources": sources,
        "outputs": _NEW_OUTPUTS,
        "app_listings": _NEW_APP_LISTINGS,
        "minify": MINIFY,
    }
    write_json_file(BUILD_CACHE_FILE, data, indent=2, sort_keys=True)


def _is_generated_output(rel):
    """True if rel matches a recognized generated-output pattern (prune-eligible)."""
    return any(p.match(rel) for p in GENERATED_OUTPUT_PATTERNS)


def prune_orphans():
    """Delete generated files present last run but not produced this run.

    A stale path is deleted only when it matches a recognized generated-output
    pattern (GENERATED_OUTPUT_PATTERNS); any other stale cache entry is warned
    and left in place, so a hand-edited or corrupted cache can never delete a
    manual asset. Returns the sorted list of pruned repo-relative paths.
    """
    stale = set(_PREV_OUTPUTS) - set(_NEW_OUTPUTS)
    removed = []
    removed_dirs = set()
    for rel in sorted(stale):
        if not _is_generated_output(rel):
            log_warning(f"stale cache entry is not a recognized generated path, leaving in place: {rel}")
            continue
        abs_path = os.path.join(ROOT_DIR, rel.replace("/", os.sep))
        if os.path.isfile(abs_path):
            os.remove(abs_path)
            log_info(f"Pruned: {rel}")
            removed.append(rel)
            removed_dirs.add(os.path.dirname(abs_path))
    # Remove now-empty generated directories (deepest first), but never ROOT.
    for d in sorted(removed_dirs, key=len, reverse=True):
        try:
            while d and os.path.abspath(d) != os.path.abspath(ROOT_DIR) and not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
        except OSError:
            pass
    return removed


def write_build_log(mode, force, pruned, social=None):
    """Write a timestamped build report to tools/build_logs/ and rotate old logs.

    Keeps the newest BUILD_LOG_KEEP logs (counting the one written now) and
    reports how many older logs were deleted. social, when given, is the
    generate_social_images.resolve_and_generate result; its per-card lists feed
    the "Social images" section.
    """
    os.makedirs(BUILD_LOG_DIR, exist_ok=True)

    # Rotate before writing so the deletion count lands in this run's log.
    existing = sorted(
        name for name in os.listdir(BUILD_LOG_DIR)
        if name.startswith("build_log_") and name.endswith(".txt")
    )
    surplus = max(0, len(existing) - (BUILD_LOG_KEEP - 1))
    deleted = 0
    for name in existing[:surplus]:
        try:
            os.remove(os.path.join(BUILD_LOG_DIR, name))
            deleted += 1
        except OSError:
            pass

    now = datetime.now()
    errors = [m for level, m in BUILD_LOG_EVENTS if level == "error"]
    warnings = [m for level, m in BUILD_LOG_EVENTS if level == "warning"]
    written = sorted(CHANGED_FILES)

    lines = [f"Build log: {now.strftime('%Y-%m-%d %H:%M:%S')}"]
    lines.append(f"Mode: {mode}; force: {'yes' if force else 'no'}")
    lines.append(
        f"Result: {len(written)} file(s) written, "
        f"{SKIPPED_PAGES} per-item page(s) skipped as up to date, "
        f"{len(pruned)} file(s) pruned"
    )

    for title, items in (
        ("Errors", errors),
        ("Warnings", warnings),
        ("Files written", written),
        ("Pruned", pruned),
    ):
        lines.append("")
        lines.append(f"{title} ({len(items)}):")
        lines.extend(f"- {item}" for item in items)

    if social is not None:
        generated = sorted(social["generated"])
        skipped = sorted(social["skipped"])
        custom = sorted(rel for _, rel in social["custom"])
        lines.append("")
        lines.append("Social images:")
        for label, items in (
            ("Generated", generated),
            ("Skipped, up to date", skipped),
            ("Custom", custom),
        ):
            suffix = (": " + ", ".join(items)) if items else ":"
            lines.append(f"- {label} ({len(items)}){suffix}")

    lines.append("")
    lines.append(f"Old build logs deleted: {deleted}")

    stamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(BUILD_LOG_DIR, f"build_log_{stamp}.txt")
    if os.path.exists(log_path):
        # Two builds in the same second would clobber; disambiguate by microsecond.
        log_path = os.path.join(BUILD_LOG_DIR, f"build_log_{stamp}_{now.microsecond:06d}.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ------------------------------------------------------------------------------------
# HTML generation helpers

def strip_html(text):
    """Strip HTML tags and collapse whitespace for plain-text output."""
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def decorate_links(html: str) -> str:
    """Add external-link or email icons to qualifying anchor tags."""
    def _add_icon(match):
        attrs = match.group(1)
        content = match.group(2)

        # Skip links containing media or structural child elements.
        if re.search(r'<(img|svg|div|button)\b', content, re.IGNORECASE):
            return match.group(0)

        href_match = re.search(r'href\s*=\s*["\']([^"\']*)["\']', attrs)
        if not href_match:
            return match.group(0)

        href = href_match.group(1)

        if href.startswith('mailto:'):
            icon = EMAIL_ICON_SVG
        elif href.startswith('http'):
            icon = LINK_ICON_SVG
        else:
            return match.group(0)

        return f'<a{attrs}>{content}{icon}</a>'

    return re.sub(r'<a(\s[^>]*)>(.*?)</a>', _add_icon, html, flags=re.DOTALL)


def is_external(demo):
    """Check if a demo entry is an external link (has a non-empty externalUrl)."""
    return bool(demo.get("externalUrl"))


def is_standalone(demo):
    """Check if a demo entry is a standalone project (has type 'standalone')."""
    return demo.get("type") == "standalone"


def load_standalone_config(folder):
    """Parsed tools/standalone/<folder>/config.json, or {} when it is absent."""
    config_path = os.path.join(STANDALONE_DIR, folder, "config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def demo_page_title(demo):
    """The title a demo page shows; a standalone config.json title wins over front matter."""
    if is_standalone(demo):
        return load_standalone_config(demo["folder"]).get("title", demo.get("title", ""))
    return demo.get("title", "")


def social_card_demos(demos_by_stem):
    """Card inputs for every demo with a page on the site; external demos have none."""
    return [
        {"folder": demo["folder"], "title": demo_page_title(demo)}
        for _, demo in sorted(demos_by_stem.items())
        if not is_external(demo)
    ]


def generate_card(demo, card_template):
    """Generate a single project card from the card template."""
    if is_external(demo):
        href = demo["externalUrl"]
        target = ' target="_blank"'
        image = demo.get("image", "")
        external_html = f'<p class="external-notice">External: This link opens in a new tab.{LINK_ICON_SVG}</p>'
        img_width = "1200"
        img_height = "630"
    else:
        folder = demo.get("folder", "")
        href = f"demo/{folder}/"
        target = ""
        image = f"demo/{folder}/{folder}-small.jpg"
        external_html = ""
        img_width = "600"
        img_height = "315"

    title = demo.get("title", "")
    alt_text = f"Screenshot of {title}" if title else ""
    tech = demo.get("tech", "")
    tech_html = f'<p class="tech"><b>Tech:</b> {tech}</p>' if tech else ""

    card = card_template
    card = card.replace("{{cardHref}}", href)
    card = card.replace("{{cardTarget}}", target)
    card = card.replace("{{cardTitle}}", title)
    card = card.replace("{{cardImage}}", image)
    card = card.replace("{{cardAlt}}", alt_text)
    card = card.replace("{{cardWidth}}", img_width)
    card = card.replace("{{cardHeight}}", img_height)
    card = card.replace("{{cardDescription}}", demo.get("descriptionShort", ""))
    card = card.replace("{{cardTech}}", tech_html)
    card = card.replace("{{cardExternal}}", external_html)
    return card.rstrip('\n')


def generate_section(category_name, manifest, demos_by_stem, card_template, section_template):
    """Generate a full frontpage section from the section and card templates."""
    cards_html = ""
    for stem in manifest.get("demos", []):
        cards_html += generate_card(demos_by_stem[stem], card_template) + '\n'

    html = section_template
    html = html.replace("{{sectionId}}", category_name)
    html = html.replace("{{sectionIndex}}", manifest.get("sectionIndex", ""))
    html = html.replace("{{sectionBand}}", " band" if manifest.get("band") else "")
    html = html.replace("{{sectionTitle}}", manifest.get("sectionTitle", ""))
    html = html.replace("{{sectionDescription}}", manifest.get("sectionDescription", ""))
    html = replace_indented(html, "{{sectionCards}}", cards_html.rstrip('\n'))
    return html.rstrip('\n')


# A paragraph holding only bold text that ends in a colon ("**How to play:**")
# is a label for the content below it, not emphasis.
MICRO_LABEL_RE = re.compile(r"<p><strong>([^<]*:)</strong></p>")


def mark_micro_labels(body_html):
    """Turn label-only bold paragraphs in a rendered markdown body into micro-labels."""
    return MICRO_LABEL_RE.sub(r'<p class="micro-label">\1</p>', body_html)


def generate_social_tags(seo, url="", og_type="website", published=None, modified=None,
                         image_width=0, image_height=0):
    """Generate Open Graph and Twitter/X Card meta tags from SEO data.

    og_type defaults to "website" so existing callers are unchanged; posts pass
    "article" with published/modified dates to emit the article:* time tags.
    image_width/image_height, when both set, add og:image:width/height (pages
    whose image is a generated card); the Twitter mirror has no dimension tags.
    """
    if not seo:
        return ""

    # Escape author text once here so callers pass raw values (og:image is a
    # site-generated URL and stays verbatim).
    og_title = escape_html(seo.get("ogTitle", ""))
    og_description = escape_html(seo.get("ogDescription", ""))
    og_image = seo.get("ogImage", "")
    og_image_alt = escape_html(seo.get("ogImageAlt", ""))

    # Open Graph tags
    og_lines = ['<!-- Open Graph meta tags -->']
    og_lines.append('<meta property="og:site_name" content="XeduR">')
    og_lines.append(f'<meta property="og:type" content="{og_type}">')
    if url:
        og_lines.append(f'<meta property="og:url" content="{url}">')
    if og_title:
        og_lines.append(f'<meta property="og:title" content="{og_title}">')
    if og_description:
        og_lines.append(f'<meta property="og:description" content="{og_description}">')
    if og_image:
        og_lines.append(f'<meta property="og:image" content="{og_image}">')
        if image_width and image_height:
            og_lines.append(f'<meta property="og:image:width" content="{image_width}">')
            og_lines.append(f'<meta property="og:image:height" content="{image_height}">')
    if og_image_alt:
        og_lines.append(f'<meta property="og:image:alt" content="{og_image_alt}">')
    if og_type == "article":
        if published:
            og_lines.append(f'<meta property="article:published_time" content="{published.isoformat()}">')
        if modified:
            og_lines.append(f'<meta property="article:modified_time" content="{modified.isoformat()}">')

    # Twitter/X Card tags (mirrors OG values)
    twitter_lines = ['<!-- Twitter/X Card meta tags -->']
    twitter_lines.append('<meta name="twitter:card" content="summary_large_image">')
    if og_title:
        twitter_lines.append(f'<meta name="twitter:title" content="{og_title}">')
    if og_description:
        twitter_lines.append(f'<meta name="twitter:description" content="{og_description}">')
    if og_image:
        twitter_lines.append(f'<meta name="twitter:image" content="{og_image}">')
    if og_image_alt:
        twitter_lines.append(f'<meta name="twitter:image:alt" content="{og_image_alt}">')

    return "\n".join(og_lines) + "\n\n" + "\n".join(twitter_lines)


def ld_json_script_tag(data):
    """Wrap JSON-LD in its script element.

    The \\u escapes keep author text such as "</script>" from closing the element
    early, and parse back to the same JSON values.
    """
    text = json.dumps(data, indent=4, ensure_ascii=False)
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<script type="application/ld+json">\n' + text + "\n</script>"


def generated_card_size():
    """(width, height) of every generated social card."""
    canvas = generate_social_images.load_card_config()["canvas"]
    return canvas["width"], canvas["height"]


def social_card_image(card_rel=None):
    """Return (url, width, height) for a page's og:image.

    Falls back from the page's own card to the frontpage card, then to the static
    frontpage.json image, whose size is unknown and so is declared as 0x0.
    """
    rel = generate_social_images.existing_card(card_rel)
    if rel:
        return (f"{SITE_BASE_URL}/{rel}", *generated_card_size())
    default = (load_json("frontpage.json").get("seo") or {}).get("ogImage", "")
    return default, 0, 0


def wrap_in_base(base_template, navbar_html, footer_html, body_content,
                 page_title, meta_description="", meta_keywords=DEFAULT_KEYWORDS,
                 og_tags="", base_path="", extra_head="", canonical_url=""):
    """Wrap body content in the base HTML template."""
    html = base_template
    # Inline tags (single-line values). meta_description and page_title carry
    # author text into a content="..." attribute and <title>, so escape here
    # (callers pass raw values; single escaping is guaranteed).
    html = html.replace("{{metaKeywords}}", meta_keywords)
    html = html.replace("{{metaDescription}}", escape_html(meta_description))
    html = html.replace("{{pageTitle}}", escape_html(page_title))
    # Block tags (multi-line content that needs indentation)
    html = replace_indented(html, "{{ogTags}}", og_tags)
    canonical_tag = f'<link rel="canonical" href="{canonical_url}">' if canonical_url else ""
    html = replace_indented(html, "{{canonicalURL}}", canonical_tag)
    html = replace_indented(html, "{{extraHead}}", extra_head)
    # The Contact link stays on pages that carry their own contact panel.
    contact_href = "#contact" if 'id="contact"' in body_content else "{{basePath}}#contact"
    html = replace_indented(html, "{{navbar}}", navbar_html.replace("{{contactHref}}", contact_href))
    html = replace_indented(html, "{{bodyContent}}", decorate_links(body_content))
    html = replace_indented(html, "{{footer}}", footer_html)
    # Path prefix (inline, applied last, must be after all other replacements
    # since injected content like extra_head may contain {{basePath}} references)
    html = html.replace("{{basePath}}", base_path)
    return html


def write_file(filepath, content):
    """Write content to a file only when it differs from the existing version.

    If MINIFY is enabled and the file is HTML, minify before comparing.
    Files that are actually written are recorded in CHANGED_FILES so that
    build_sitemap can update only the dates that need changing. Every target
    path is also recorded in the build manifest so orphan pruning keeps it.
    """
    if MINIFY and filepath.endswith(".html"):
        content = minify_html(content)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    rel_path = os.path.relpath(filepath, ROOT_DIR)
    rel_key = rel_path.replace(os.sep, "/")

    # should_build already recorded per-item pages with their deps; aggregates
    # (always rebuilt) are recorded here so they are never pruned.
    if rel_key not in _NEW_OUTPUTS:
        record_output(rel_key)

    # Skip writing if the file already exists with identical content.
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            if f.read() == content:
                print(f"  Unchanged: {rel_path}")
                return

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    CHANGED_FILES.add(rel_key)
    print(f"  Built: {rel_path}")


# ------------------------------------------------------------------------------------
# Build steps

def collect_site_paths(manifests, demos_by_stem, include_hashes=False, tangents_posts=None):
    """Collect all valid page paths on the site.

    Args:
        manifests: Per-category manifest dicts (section metadata + stem lists).
        demos_by_stem: Parsed front-matter dicts keyed by demo stem.
        include_hashes: If True, include hash-based anchor sections
                        (e.g. /#plugins) for fuzzy matching on the 404 page.
        tangents_posts: The sorted Tangents post list; its pages (index,
                        pagination, posts, tag pages) are appended when given.
    Returns:
        A list of root-relative path strings.
    """
    paths = ["/"]

    if include_hashes:
        for section in ["me", "learn"] + CATEGORIES:
            paths.append(f"/#{section}")
        paths.append("/demo/")

    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue
        for stem in manifests[cat_name]["demos"]:
            demo = demos_by_stem[stem]
            if is_external(demo):
                continue
            folder = demo.get("folder")
            if folder:
                paths.append(f"/demo/{folder}/")

    if tangents_posts is not None:
        paths.extend(enumerate_tangents_paths(tangents_posts))

    return paths


CONTACT_TEMPLATE_REL = _rel(os.path.join(TEMPLATES_DIR, "contact.html"))

# The [[github]] directive inlines these, so any page that may use it depends on both.
REPO_PANEL_TEMPLATE_RELS = [
    _rel(os.path.join(TEMPLATES_DIR, "repo-panel.html")),
    _rel(os.path.join(TEMPLATES_DIR, "repo-panel-private.html")),
]


def contact_section(center_class):
    """The frontpage contact panel, without its section number, as a closing page section."""
    panel = load_file("contact.html").replace("{{contactIndex}}", "")
    section = (
        '<section class="section contact-section">\n'
        '    <div class="center ' + center_class + '">\n'
        "        {{contact}}\n"
        "    </div>\n"
        "</section>"
    )
    return replace_indented(section, "{{contact}}", panel)


def build_frontpage(base_template, navbar_html, footer_html,
                    contact_html, frontpage_content, manifests, demos_by_stem):
    """Build index.html from frontpage.html and the demo manifests."""
    card_template = load_file("card.html")
    section_template = load_file("section.html")

    content = frontpage_content

    # Replace snippet tags (indented to match their position in the template)
    frontpage_data = load_json("frontpage.json")
    section_index = '<span class="section-index" aria-hidden="true">' + frontpage_data["contactSectionIndex"] + "</span>"
    content = replace_indented(content, "{{contact}}", contact_html.replace("{{contactIndex}}", section_index))

    # Replace category tags with generated section HTML
    for cat_name in CATEGORIES:
        tag = "{{" + cat_name + "}}"
        if cat_name in manifests:
            section = generate_section(
                cat_name, manifests[cat_name], demos_by_stem,
                card_template, section_template,
            )
            content = replace_indented(content, tag, section)
        else:
            content = content.replace(tag, "")

    # Wrap in base template
    page_title = frontpage_data.get("pageTitle", "")
    meta_desc = frontpage_data.get("metaDescription", "")
    meta_kw = frontpage_data.get("metaKeywords", DEFAULT_KEYWORDS)
    frontpage_seo = dict(frontpage_data.get("seo") or {})
    og_image, image_width, image_height = social_card_image()
    frontpage_seo["ogImage"] = og_image
    og_tags = generate_social_tags(
        frontpage_seo, url=f"{SITE_BASE_URL}/",
        image_width=image_width, image_height=image_height,
    )

    # JSON-LD: WebSite for xedur.com referencing the canonical Person on erantanen.com.
    person_id = "https://www.erantanen.com/#eetu-rantanen"
    ld_json = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Person",
                "@id": person_id,
                "name": "Eetu Rantanen",
                "alternateName": "XeduR",
                "givenName": "Eetu",
                "familyName": "Rantanen",
                "url": "https://www.erantanen.com/",
                "sameAs": [
                    "https://github.com/XeduR/",
                    "https://www.erantanen.com/",
                ],
            },
            {
                "@type": "WebSite",
                "@id": f"{SITE_BASE_URL}/#website",
                "url": f"{SITE_BASE_URL}/",
                "name": "XeduR",
                "description": meta_desc,
                "inLanguage": "en",
                "author": {"@id": person_id},
                "publisher": {"@id": person_id},
            },
        ],
    }
    ld_json_script = ld_json_script_tag(ld_json)

    page = wrap_in_base(
        base_template, navbar_html, footer_html,
        body_content=content,
        page_title=page_title,
        meta_description=meta_desc,
        meta_keywords=meta_kw,
        og_tags=og_tags,
        base_path="./",
        extra_head=ld_json_script,
        canonical_url=f"{SITE_BASE_URL}/",
    )

    write_file(os.path.join(OUTPUT_DIR, "index.html"), page)


def build_404(base_template, navbar_html, footer_html, four04_template,
              valid_paths=None):
    """Build 404.html, injecting the valid paths list for fuzzy redirect."""
    body = four04_template
    paths_json = json.dumps(valid_paths) if valid_paths else "[]"
    body = body.replace("{{validPaths}}", paths_json)

    # The 404 shares the frontpage card and its alt text.
    meta_desc = (
        "This is the 404 page for XeduR.com. "
        "If you are seeing this, then you are lost."
    )
    og_image, image_width, image_height = social_card_image()
    seo = {
        "ogTitle": "XeduR - 404",
        "ogDescription": meta_desc,
        "ogImage": og_image,
        "ogImageAlt": (load_json("frontpage.json").get("seo") or {}).get("ogImageAlt", "XeduR"),
    }
    og_tags = generate_social_tags(seo, image_width=image_width, image_height=image_height)

    page = wrap_in_base(
        base_template, navbar_html, footer_html,
        body_content=body,
        page_title="XeduR - 404",
        meta_description=meta_desc,
        og_tags=og_tags,
        base_path="/",
        extra_head='<meta name="robots" content="noindex">',
    )

    write_file(os.path.join(OUTPUT_DIR, "404.html"), page)


def build_demo_pages(base_template, navbar_html, footer_html,
                     demo_template, iframe_template, manifests, demos_by_stem):
    """Build individual demo pages for all non-external demos."""
    demo_tpl_rel = _rel(os.path.join(TEMPLATES_DIR, "demo.html"))
    iframe_tpl_rel = _rel(os.path.join(TEMPLATES_DIR, "iframe.html"))
    contact_html = contact_section("demo-page")

    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue

        for stem in manifests[cat_name]["demos"]:
            demo = demos_by_stem[stem]
            # Skip external and standalone entries (handled separately)
            if is_external(demo) or is_standalone(demo):
                continue

            folder = demo["folder"]
            title = demo.get("title", "")
            desc_short = demo.get("descriptionShort", "")

            demo_dir = os.path.join(OUTPUT_DIR, "demo", folder)
            md_rel = _rel(os.path.join(DEMOS_DIR, f"{stem}.md"))

            # Record and decide both pages before the .bin scan below: a
            # transiently missing binary must not leave a live page unrecorded,
            # or prune_orphans would delete it over a build hiccup.
            page_rel = f"demo/{folder}/index.html"
            card_rel = generate_social_images.demo_card_rel(folder)
            page_deps = [md_rel, demo_tpl_rel, *REPO_PANEL_TEMPLATE_RELS, card_rel, CONTACT_TEMPLATE_REL]
            build_page = should_build(page_rel, page_deps)

            app_dir = os.path.join(demo_dir, "app")
            app_files = sorted(os.listdir(app_dir)) if os.path.isdir(app_dir) else []
            # The loader is this build's own output, not an app file.
            app_files = [name for name in app_files if name != "index.html"]
            listing = ",".join(app_files)
            app_key = f"demo/{folder}/app/"
            listing_changed = listing != _PREV_APP_LISTINGS.get(app_key)
            _NEW_APP_LISTINGS[app_key] = listing
            app_page_rel = f"demo/{folder}/app/index.html"
            app_deps = [md_rel, iframe_tpl_rel]
            build_app = should_build(app_page_rel, app_deps, extra_dirty=listing_changed)

            if build_page:
                body_html, meta = markdown_engine.render_markdown(demo["_body"], base_path="../../")
                body_html = mark_micro_labels(body_html)
                for w in meta["warnings"]:
                    log_warning(f"{stem}.md: {w}")

                # Build demo page body from template
                body = demo_template
                body = body.replace("{{demoTitle}}", title)
                body = body.replace("{{demoImage}}", f"{folder}-large.jpg")
                body = replace_indented(body, "{{demoBody}}", body_html)
                body = replace_indented(body, "{{contactSection}}", contact_html)

                # SEO from flat front-matter keys (nested seo object retired).
                og_image, image_width, image_height = social_card_image(card_rel)
                demo_seo = {
                    "ogTitle": demo.get("ogTitle", f"XeduR - {title}"),
                    "ogDescription": demo.get("ogDescription", desc_short),
                    "ogImage": og_image,
                    "ogImageAlt": demo.get("ogImageAlt", f"XeduR - {title}"),
                }
                meta_desc = demo.get("metaDescription") or desc_short
                demo_url = f"{SITE_BASE_URL}/demo/{folder}/"
                og_tags = generate_social_tags(
                    demo_seo, url=demo_url,
                    image_width=image_width, image_height=image_height,
                )

                # Wrap in base template
                page = wrap_in_base(
                    base_template, navbar_html, footer_html,
                    body_content=body,
                    page_title=f"XeduR - {title}",
                    meta_description=meta_desc,
                    og_tags=og_tags,
                    base_path="../../",
                    extra_head=IMAGE_FALLBACK_SCRIPT if meta["images"] else "",
                    canonical_url=demo_url,
                )

                # Write demo page under demo/ subfolder
                write_file(os.path.join(demo_dir, "index.html"), page)

            # The app loader needs the .bin name, so scan even when the page is
            # up to date; a missing binary is an error worth reporting each run.
            bin_files = [f for f in app_files if f.endswith(".bin")]
            if not bin_files:
                log_error(f"No .bin file found in demo/{folder}/app/")
                continue
            if len(bin_files) > 1:
                log_warning(f"Multiple .bin files in demo/{folder}/app/: {bin_files}")

            bin_name = bin_files[0].removesuffix(".bin")

            if build_app:
                # Create app/ subfolder with iframe loader
                iframe_html = iframe_template.replace("{{demoTitle}}", title)
                iframe_html = iframe_html.replace("{{demoBinName}}", bin_name)
                iframe_html = iframe_html.replace("{{demoDescription}}", desc_short)
                write_file(os.path.join(demo_dir, "app", "index.html"), iframe_html)


def build_demo_index(base_template, navbar_html, footer_html,
                     demo_index_template, manifests, demos_by_stem):
    """Build demo/index.html with a simple list of all available demos."""
    items = []
    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue
        for stem in manifests[cat_name]["demos"]:
            demo = demos_by_stem[stem]
            if is_external(demo):
                continue
            folder = demo.get("folder")
            title = demo.get("title", folder)
            if folder:
                items.append(f'<li><a href="{folder}/">{title}</a></li>')

    body = replace_indented(demo_index_template, "{{demoList}}", "\n".join(items))
    body = replace_indented(body, "{{contactSection}}", contact_section("demo-index"))

    page = wrap_in_base(
        base_template, navbar_html, footer_html,
        body_content=body,
        page_title="XeduR - Demos",
        meta_description="List of all demos on XeduR.com.",
        base_path="../",
        extra_head='<meta name="robots" content="noindex">',
    )

    write_file(os.path.join(OUTPUT_DIR, "demo", "index.html"), page)


def build_standalone_pages(base_template, navbar_html, footer_html, manifests, demos_by_stem):
    """Build pages for standalone projects that use their own content templates.

    Standalone projects are identified by ``type: standalone`` in their front
    matter.  Source files (content.html, head.html, config.json) are read from
    tools/standalone/<folder>/.
    """
    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue

        for stem in manifests[cat_name]["demos"]:
            demo = demos_by_stem[stem]
            if not is_standalone(demo):
                continue

            folder = demo.get("folder")
            if not folder:
                continue

            standalone_dir = os.path.join(STANDALONE_DIR, folder)

            # Record and decide before the source-folder check so a temporarily
            # missing tools/standalone/<folder>/ never gets the live page pruned.
            page_rel = f"demo/{folder}/index.html"
            card_rel = generate_social_images.demo_card_rel(folder)
            deps = [
                _rel(os.path.join(DEMOS_DIR, f"{stem}.md")),
                _rel(os.path.join(standalone_dir, "content.html")),
                _rel(os.path.join(standalone_dir, "head.html")),
                _rel(os.path.join(standalone_dir, "config.json")),
                card_rel,
                CONTACT_TEMPLATE_REL,
            ]
            build = should_build(page_rel, deps)

            if not os.path.isdir(standalone_dir):
                log_warning(f"standalone folder not found: {folder}")
                continue
            if not build:
                continue

            # Load standalone project files
            content_path = os.path.join(standalone_dir, "content.html")
            head_path = os.path.join(standalone_dir, "head.html")

            with open(content_path, "r", encoding="utf-8") as f:
                body_content = f.read()
            body_content = replace_indented(body_content, "{{contactSection}}", contact_section("demo-page"))

            extra_head = ""
            if os.path.exists(head_path):
                with open(head_path, "r", encoding="utf-8") as f:
                    extra_head = f.read()

            config = load_standalone_config(folder)
            title = demo_page_title(demo)
            meta_desc = config.get("metaDescription", demo.get("descriptionShort", ""))
            meta_keywords = config.get("metaKeywords", DEFAULT_KEYWORDS)

            demo_url = f"{SITE_BASE_URL}/demo/{folder}/"
            standalone_seo = dict(config.get("seo", {}))
            og_image, image_width, image_height = social_card_image(card_rel)
            standalone_seo["ogImage"] = og_image
            standalone_seo["ogImageAlt"] = (
                demo.get("ogImageAlt") or standalone_seo.get("ogImageAlt") or f"XeduR - {title}"
            )
            og_tags = generate_social_tags(
                standalone_seo, url=demo_url,
                image_width=image_width, image_height=image_height,
            )

            # The output lives at demo/<folder>/index.html, which is 2 levels
            # below site root, same as regular demo pages.
            page = wrap_in_base(
                base_template, navbar_html, footer_html,
                body_content=body_content,
                page_title=f"XeduR - {title}",
                meta_description=meta_desc,
                meta_keywords=meta_keywords,
                og_tags=og_tags,
                base_path="../../",
                extra_head=extra_head,
                canonical_url=demo_url,
            )

            demo_dir = os.path.join(OUTPUT_DIR, "demo", folder)
            write_file(os.path.join(demo_dir, "index.html"), page)


# ------------------------------------------------------------------------------------
# Tangents (markdown-authored posts, paginated list/tag pages, Atom feed)

def escape_html(text):
    """Escape author text for safe use in HTML element and attribute contexts."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def escape_xml(text):
    """Escape text for an Atom/XML text node."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def format_date(d):
    """Render a date as '13 July 2026' (locale-independent English month)."""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def truncate_description(text, limit=SUMMARY_MAX):
    """Collapse whitespace and cut text to at most `limit` characters at a word break."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-") + "\u2026"


def truncate_list_summary(text, limit=SUMMARY_MAX):
    """Collapse whitespace and cut text after `limit` characters, adding '...'."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def local_image_path(url, page_dir):
    """Repo path a same-site image URL points at, or None for an external URL."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    path = urllib.parse.unquote(parts.path)
    if path.startswith("/"):
        return os.path.normpath(os.path.join(OUTPUT_DIR, path.lstrip("/")))
    return os.path.normpath(os.path.join(OUTPUT_DIR, page_dir, path))


def is_page_relative_url(url):
    """True for a URL resolved against the page it sits on (no scheme, host, or leading '/')."""
    parts = urllib.parse.urlsplit(url)
    return not parts.scheme and not parts.netloc and not url.startswith("/")


def base_path_for(url_dir):
    """Return the '../'-chain from a page's URL dir back to the site root.

    'tangents/tag/solar2d/2/' -> '../../../../'; 'tangents/' -> '../'; '' -> ''.
    """
    trimmed = url_dir.strip("/")
    depth = trimmed.count("/") + 1 if trimmed else 0
    return "../" * depth


def tag_slug(label):
    """Slugify a tag label: 'Solar2D' -> 'solar2d', 'Game Dev' -> 'game-dev'."""
    return re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")


def collect_tangents_tags(posts):
    """Return {label: count} across posts, erroring on a slug collision.

    Two spellings that slugify to the same value (e.g. 'Solar2D' and 'solar2d')
    would silently share one tag page, so this raises instead of picking a winner.
    """
    counts = {}
    slug_owner = {}
    for post in posts:
        for label in post["tags"]:
            slug = tag_slug(label)
            if slug in slug_owner and slug_owner[slug] != label:
                raise ValueError(
                    f"tangents: tag spellings {slug_owner[slug]!r} and {label!r} both "
                    f"map to slug {slug!r}; unify them in the post front matter"
                )
            slug_owner[slug] = label
            counts[label] = counts.get(label, 0) + 1
    return counts


def _paginate(subset):
    """Split posts into page-sized slices; always at least one (possibly empty) page."""
    return [subset[i:i + TANGENTS_PAGE_SIZE]
            for i in range(0, len(subset), TANGENTS_PAGE_SIZE)] or [[]]


def enumerate_tangents_paths(posts):
    """All root-relative Tangents page paths (index, pagination, posts, tag pages).

    Shared with collect_site_paths so the sitemap and the 404 fuzzy matcher list
    exactly the pages the builders emit.
    """
    paths = ["/tangents/"]
    for page_no in range(2, len(_paginate(posts)) + 1):
        paths.append(f"/tangents/{page_no}/")

    for post in posts:
        paths.append(f"/tangents/{post['slug']}/")

    tag_counts = collect_tangents_tags(posts)
    for label in sorted(tag_counts):
        slug = tag_slug(label)
        subset = [p for p in posts if label in p["tags"]]
        prefix = f"/tangents/tag/{slug}/"
        paths.append(prefix)
        for page_no in range(2, len(_paginate(subset)) + 1):
            paths.append(f"{prefix}{page_no}/")

    return paths


def render_post_tags(tags):
    """Return the post page's tag chip list, or '' when there are no tags."""
    if not tags:
        return ""
    items = []
    for label in tags:
        items.append(
            '<li><a class="tag-chip" href="{{basePath}}tangents/tag/' + tag_slug(label)
            + '/">' + escape_html(label) + "</a></li>"
        )
    return (
        '<div class="tag-group">\n<span class="tags-label">Tags:</span>\n'
        '<ul class="tag-list">\n' + "\n".join(items) + "\n</ul>\n</div>"
    )


def render_inline_tags(tags):
    """Return inline tag chips for a list row's meta line, or '' when there are none."""
    if not tags:
        return ""
    chips = []
    for label in tags:
        chips.append(
            '<a class="tag-chip" href="{{basePath}}tangents/tag/' + tag_slug(label)
            + '/">' + escape_html(label) + "</a>"
        )
    return ' <span class="post-item-tags">' + "".join(chips) + "</span>"


def load_tangents_posts():
    """Parse tools/tangents/*.md into sorted post dicts and update the dates map.

    Publish dates are assigned on first sight and stored in tangents_dates.json
    (committed, since they cannot be re-derived).  The tracked updated date bumps
    only when the rendered body's hash changes, so editing summary/tags/title alone
    does not; a front-matter 'updated' date overrides it.
    """
    dates_map = read_json_file(TANGENTS_DATES_FILE, required=True)

    if os.path.isdir(TANGENTS_SRC_DIR):
        md_files = sorted(f for f in os.listdir(TANGENTS_SRC_DIR) if f.endswith(".md"))
    else:
        md_files = []

    today = date.today()
    posts = []

    for filename in md_files:
        slug = filename[:-3]
        if not TANGENT_SLUG_RE.match(slug):
            raise ValueError(
                f"tangents: invalid slug {slug!r} (must be lowercase kebab-case [a-z0-9-]+)"
            )

        path = os.path.join(TANGENTS_SRC_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            front, body = markdown_engine.parse_front_matter(f.read(), source=filename)

        if front.get("draft"):
            continue

        title = front.get("title")
        summary = front.get("summary")
        if not title:
            raise ValueError(f"tangents/{filename}: missing required 'title'")
        if not summary:
            raise ValueError(f"tangents/{filename}: missing required 'summary'")

        body_html, meta = markdown_engine.render_markdown(
            body, base_path=base_path_for(f"tangents/{slug}/")
        )
        for warning in meta["warnings"]:
            log_warning(f"tangents/{filename}: {warning}")

        feature_image = front.get("featureImage")
        if feature_image and not markdown_engine.is_safe_url(feature_image):
            raise ValueError(
                f"tangents/{filename}: 'featureImage' has a disallowed URL scheme: {feature_image!r}"
            )

        # A missing image only warns: the page shows a placeholder in its place.
        for src in ([feature_image] if feature_image else []) + meta["images"]:
            local_path = local_image_path(src, f"tangents/{slug}")
            if local_path and not os.path.isfile(local_path):
                log_warning(f"tangents/{filename}: image not found: {src!r}")

        content_hash = hashlib.sha256(body_html.encode("utf-8")).hexdigest()
        fm_published = front.get("published")  # date or None (front-matter override)
        fm_updated = front.get("updated")

        entry = dates_map.get(slug)
        if entry is None:
            published = fm_published or today
            updated = None
        else:
            published = fm_published or date.fromisoformat(entry["published"])
            if content_hash != entry.get("contentHash"):
                updated = today
            elif entry.get("updated"):
                updated = date.fromisoformat(entry["updated"])
            else:
                updated = None

        dates_map[slug] = {
            "published": published.isoformat(),
            "updated": updated.isoformat() if updated else None,
            "contentHash": content_hash,
        }

        # A front-matter 'updated' overrides the tracked body-change date. Either
        # is shown only when it is later than the publish date.
        if fm_updated and fm_updated < published:
            raise ValueError(
                f"tangents/{filename}: 'updated' {fm_updated.isoformat()} is earlier "
                f"than 'published' {published.isoformat()}"
            )
        updated = fm_updated or updated
        if updated and updated <= published:
            updated = None

        posts.append({
            "slug": slug,
            "title": title,
            "summary": summary,
            "tags": front.get("tags", []),
            "published": published,
            "updated": updated,
            "body_html": body_html,
            "needs_video_js": meta["needs_video_js"],
            "has_images": bool(meta["images"]),
            "social_image": front.get("socialImage"),
            "feature_image": feature_image,
            "feature_image_alt": front.get("featureImageAlt", ""),
        })

    # Newest first; same-day ties break by slug descending (deterministic).
    posts.sort(key=lambda p: (p["published"], p["slug"]), reverse=True)

    write_json_file(TANGENTS_DATES_FILE, dates_map, indent=4, sort_keys=True)

    return posts


def build_tangents_posts(base_template, navbar_html, footer_html, post_template, posts):
    """Write tangents/<slug>/index.html for every post, with Prev/Next nav and SEO."""
    total = len(posts)
    post_tpl_rel = _rel(os.path.join(TEMPLATES_DIR, "tangents-post.html"))
    contact_html = contact_section("tangents-post")
    for i, post in enumerate(posts):
        slug = post["slug"]
        page_rel = f"tangents/{slug}/index.html"
        md_rel = _rel(os.path.join(TANGENTS_SRC_DIR, f"{slug}.md"))

        # The Prev/Next nav embeds the immediate neighbours' titles, so the page
        # depends on their sources too. A neighbour retitle changes that dep's
        # hash; a neighbour added or removed changes the dependency set, which
        # should_build detects even though the dropped path leaves dep_rels.
        deps = [md_rel, post_tpl_rel, *REPO_PANEL_TEMPLATE_RELS, CONTACT_TEMPLATE_REL]
        if i > 0:
            deps.append(_rel(os.path.join(TANGENTS_SRC_DIR, f"{posts[i - 1]['slug']}.md")))
        if i < total - 1:
            deps.append(_rel(os.path.join(TANGENTS_SRC_DIR, f"{posts[i + 1]['slug']}.md")))
        # A custom socialImage names a file whose presence flips the page's
        # og:image between the custom name and the generated card. Depending on
        # it (even while absent, via source_hash's "" sentinel) rebuilds the page
        # exactly when that file appears or disappears.
        social_image = post.get("social_image")
        if social_image and social_image != "auto":
            deps.append(f"tangents/{slug}/{social_image}")
        if not should_build(page_rel, deps):
            continue

        title = post["title"]
        published = post["published"]
        updated = post["updated"]
        canonical = f"{SITE_BASE_URL}/tangents/{slug}/"

        dates_str = f"Published: {format_date(published)}"
        if updated:
            dates_str += f"<br>Updated: {format_date(updated)}"

        feature_html = ""
        if post["feature_image"]:
            feature_html = (
                '<figure class="feature-image">\n'
                '    <img src="' + escape_html(post["feature_image"]) + '" alt="'
                + escape_html(post["feature_image_alt"]) + '" fetchpriority="high">\n'
                "</figure>\n"
                "<hr>"
            )

        # Previous = older (higher index), Next = newer (lower index); hide at ends.
        nav_links = []
        if i < total - 1:
            older = posts[i + 1]
            nav_links.append(
                '<a class="nav-prev" href="{{basePath}}tangents/' + older["slug"]
                + '/"><span class="nav-label">Previous: </span><span class="nav-title">'
                + escape_html(older["title"]) + "</span></a>"
            )
        if i > 0:
            newer = posts[i - 1]
            nav_links.append(
                '<a class="nav-next" href="{{basePath}}tangents/' + newer["slug"]
                + '/"><span class="nav-label">Next: </span><span class="nav-title">'
                + escape_html(newer["title"]) + "</span></a>"
            )

        body = post_template
        body = body.replace("{{postTitle}}", escape_html(title))
        body = body.replace("{{postDates}}", dates_str)
        body = replace_indented(body, "{{postTags}}", render_post_tags(post["tags"]))
        body = replace_indented(body, "{{postFeature}}", feature_html)
        body = replace_indented(body, "{{postBody}}", post["body_html"])
        body = replace_indented(body, "{{postNav}}", "\n".join(nav_links))
        body = replace_indented(body, "{{contactSection}}", contact_html)

        og_image = post["og_image"]
        image_width, image_height = post["og_image_size"]
        description = truncate_description(post["summary"])
        seo = {
            "ogTitle": title,
            "ogDescription": description,
            "ogImage": og_image,
            "ogImageAlt": title,
        }
        og_tags = generate_social_tags(
            seo, url=canonical, og_type="article",
            published=published, modified=(updated or published),
            image_width=image_width, image_height=image_height,
        )

        # BlogPosting reuses the canonical Person entity on erantanen.com.
        person = {
            "@type": "Person",
            "@id": "https://www.erantanen.com/#eetu-rantanen",
            "name": "Eetu Rantanen",
        }
        ld = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "description": description,
            "datePublished": published.isoformat(),
            "dateModified": (updated or published).isoformat(),
            "url": canonical,
            "mainEntityOfPage": canonical,
            "author": person,
            "publisher": person,
        }
        if og_image:
            ld["image"] = og_image
        ld_script = ld_json_script_tag(ld)

        extra_head_parts = [
            ld_script,
            '<link rel="alternate" type="application/atom+xml" '
            'title="XeduR - Tangents" href="{{basePath}}tangents/feed.xml">',
        ]
        if post["needs_video_js"]:
            extra_head_parts.append('<script defer src="{{basePath}}js/video-consent.js"></script>')
        if post["feature_image"] or post["has_images"]:
            extra_head_parts.append(IMAGE_FALLBACK_SCRIPT)

        page = wrap_in_base(
            base_template, navbar_html, footer_html,
            body_content=body,
            page_title=f"XeduR - {title}",
            meta_description=description,
            og_tags=og_tags,
            base_path="../../",
            extra_head="\n".join(extra_head_parts),
            canonical_url=canonical,
        )
        write_file(os.path.join(OUTPUT_DIR, "tangents", slug, "index.html"), page)


def build_tangents_list_pages(base_template, navbar_html, footer_html,
                              list_template, item_template, posts, tangents_card_url):
    """Build the paginated index and one paginated page set per tag."""
    tag_counts = collect_tangents_tags(posts)
    card_width, card_height = generated_card_size()
    contact_html = contact_section("tangents-list")

    def render_item(post):
        image_html = ""
        if post["feature_image"]:
            src = post["feature_image"]
            if is_page_relative_url(src):
                src = "{{basePath}}tangents/" + post["slug"] + "/" + src
            # The title link already names the post, so the image link is a
            # mouse/touch shortcut kept out of the tab order and accessibility tree.
            image_html = (
                '<a class="post-item-image" href="{{basePath}}tangents/' + post["slug"]
                + '/" tabindex="-1" aria-hidden="true"><img src="' + escape_html(src)
                + '" alt="" loading="lazy"></a>'
            )
        row = item_template
        row = row.replace("{{itemClass}}", " has-image" if image_html else "")
        row = replace_indented(row, "{{itemImage}}", image_html)
        row = row.replace("{{itemSlug}}", post["slug"])
        row = row.replace("{{itemTitle}}", escape_html(post["title"]))
        row = row.replace("{{itemDate}}", format_date(post["published"]))
        row = row.replace("{{itemTags}}", render_inline_tags(post["tags"]))
        row = row.replace("{{itemSummary}}", escape_html(truncate_list_summary(post["summary"])))
        return row.rstrip("\n")

    def build_tag_filter(active_label):
        if not tag_counts:
            return ""
        items = []
        all_active = ' class="active"' if active_label is None else ""
        items.append('<li><a' + all_active + ' href="{{basePath}}tangents/">All</a></li>')
        # Most-used first matches the sort menu's default, so the order holds when the script runs.
        for label in sorted(tag_counts, key=lambda name: (-tag_counts[name], name.casefold())):
            active = ' class="active"' if label == active_label else ""
            items.append(
                '<li data-tag="' + escape_html(label) + '" data-count="' + str(tag_counts[label])
                + '"><a' + active + ' href="{{basePath}}tangents/tag/' + tag_slug(label)
                + '/">' + escape_html(label) + " (" + str(tag_counts[label]) + ")</a></li>"
            )
        return (
            TAG_TOOLS_HTML + "\n"
            '<span class="tags-label">Tags:</span>\n'
            '<ul class="tag-filter-list">\n' + "\n".join(items) + "\n</ul>\n"
            '<p class="tag-empty" hidden>No tags match the search.</p>'
        )

    def page_dir(url_prefix, page_no):
        return url_prefix if page_no == 1 else f"{url_prefix}{page_no}/"

    def nav_link(css_class, label, url_prefix, target_page, enabled):
        # An end of the range keeps its link in place, faded, so the bar never shifts.
        if not enabled:
            return '<span class="' + css_class + ' nav-disabled" aria-disabled="true">' + label + "</span>"
        return ('<a class="' + css_class + '" href="{{basePath}}' + page_dir(url_prefix, target_page)
                + '">' + label + "</a>")

    def build_page_nav(url_prefix, page_no, n):
        page_jump = (
            '<div class="page-jump">\n'
            '<label for="page-jump-input">Page</label>\n'
            '<input id="page-jump-input" class="page-jump-input" type="text" inputmode="numeric"'
            ' autocomplete="off" size="3" value="' + str(page_no) + '"'
            ' aria-describedby="page-jump-total"'
            ' data-current="' + str(page_no) + '" data-total="' + str(n) + '"'
            ' data-first="{{basePath}}' + url_prefix + '">\n'
            '<span id="page-jump-total">out of ' + str(n) + "</span>\n"
            "</div>"
        )
        return "\n".join([
            nav_link("nav-newer", "Newer posts", url_prefix, page_no - 1, page_no > 1),
            page_jump,
            nav_link("nav-older", "Older posts", url_prefix, page_no + 1, page_no < n),
        ])

    def build_paginated(subset, url_prefix, heading_html, intro, page_title_base,
                        meta_desc, active_label):
        pages = _paginate(subset)
        n = len(pages)
        for idx, page_posts in enumerate(pages):
            page_no = idx + 1
            url_dir = page_dir(url_prefix, page_no)
            base_path = base_path_for(url_dir)
            canonical = f"{SITE_BASE_URL}/{url_dir}"
            page_title = page_title_base if page_no == 1 else f"{page_title_base} (page {page_no})"
            list_scripts = ['<script defer src="{{basePath}}js/page-jump.js"></script>']
            if tag_counts:
                list_scripts.append('<script defer src="{{basePath}}js/tag-filter.js"></script>')
            if any(p["feature_image"] for p in page_posts):
                list_scripts.append(IMAGE_FALLBACK_SCRIPT)

            body = list_template
            body = body.replace("{{listHeading}}", heading_html)
            body = body.replace("{{listIntro}}", intro)
            body = replace_indented(body, "{{tagFilter}}", build_tag_filter(active_label))
            body = replace_indented(body, "{{postItems}}", "\n".join(render_item(p) for p in page_posts))
            body = replace_indented(body, "{{pageNav}}", build_page_nav(url_prefix, page_no, n))
            body = replace_indented(body, "{{contactSection}}", contact_html)

            seo = {
                "ogTitle": page_title,
                "ogDescription": meta_desc,
                "ogImage": tangents_card_url,
                "ogImageAlt": "XeduR - Tangents",
            }
            og_tags = generate_social_tags(
                seo, url=canonical, image_width=card_width, image_height=card_height
            )

            page = wrap_in_base(
                base_template, navbar_html, footer_html,
                body_content=body,
                page_title=page_title,
                meta_description=meta_desc,
                og_tags=og_tags,
                base_path=base_path,
                extra_head="\n".join(list_scripts),
                canonical_url=canonical,
            )
            write_file(os.path.join(OUTPUT_DIR, url_dir, "index.html"), page)

    build_paginated(
        posts, "tangents/", "Tangents", TANGENTS_INTRO,
        "XeduR - Tangents", TANGENTS_INTRO, None,
    )

    for label in sorted(tag_counts):
        subset = [p for p in posts if label in p["tags"]]
        heading_html = 'Tangents tagged "' + escape_html(label) + '"'
        build_paginated(
            subset, f"tangents/tag/{tag_slug(label)}/", heading_html, "",
            f"XeduR - Tangents tagged {label}",
            f"Tangents posts tagged {label}.", label,
        )


def build_tangents_feed(posts):
    """Write the Atom 1.0 feed to tangents/feed.xml (newest FEED_MAX_ENTRIES posts)."""
    included = posts[:FEED_MAX_ENTRIES]
    if included:
        feed_updated = max((p["updated"] or p["published"]) for p in included)
    else:
        feed_updated = date.today()

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<feed xmlns="http://www.w3.org/2005/Atom">')
    lines.append("    <title>XeduR - Tangents</title>")
    lines.append(f"    <id>{SITE_BASE_URL}/tangents/</id>")
    lines.append(f'    <link rel="alternate" href="{SITE_BASE_URL}/tangents/"/>')
    lines.append(f'    <link rel="self" href="{SITE_BASE_URL}/tangents/feed.xml"/>')
    lines.append(f"    <icon>{SITE_BASE_URL}/favicon-96x96.png</icon>")
    lines.append(f"    <logo>{SITE_BASE_URL}/img/xedur-code-portfolio.png</logo>")
    lines.append(f"    <updated>{feed_updated.isoformat()}T00:00:00Z</updated>")
    lines.append("    <author><name>Eetu Rantanen</name></author>")
    for post in included:
        published = post["published"].isoformat()
        modified = (post["updated"] or post["published"]).isoformat()
        lines.append("    <entry>")
        lines.append(f'        <title>{escape_xml(post["title"])}</title>')
        lines.append(f'        <id>{SITE_BASE_URL}/tangents/{post["slug"]}/</id>')
        lines.append(f'        <link rel="alternate" href="{SITE_BASE_URL}/tangents/{post["slug"]}/"/>')
        lines.append(f"        <published>{published}T00:00:00Z</published>")
        lines.append(f"        <updated>{modified}T00:00:00Z</updated>")
        lines.append(f'        <summary>{escape_xml(post["summary"])}</summary>')
        lines.append("    </entry>")
    lines.append("</feed>")

    write_file(os.path.join(OUTPUT_DIR, "tangents", "feed.xml"), "\n".join(lines) + "\n")


def check_images(manifests, demos_by_stem):
    """Verify that all expected images exist on disk.

    For non-external demos (regular and standalone), checks for
    ``demo/<folder>/<folder>-small.jpg`` and ``demo/<folder>/<folder>-large.jpg``.
    For external links, checks the image path defined in front matter.
    """
    missing = []
    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue
        for stem in manifests[cat_name]["demos"]:
            demo = demos_by_stem[stem]
            if is_external(demo):
                image = demo.get("image", "")
                if image:
                    img_path = os.path.join(ROOT_DIR, image.replace("/", os.sep))
                    if not os.path.isfile(img_path):
                        missing.append(f"{image} (external: {demo.get('title', '')})")
            else:
                folder = demo.get("folder")
                if not folder:
                    continue
                for suffix in ("small", "large"):
                    img_name = f"{folder}-{suffix}.jpg"
                    img_path = os.path.join(ROOT_DIR, "demo", folder, img_name)
                    if not os.path.isfile(img_path):
                        missing.append(f"demo/{folder}/{img_name}")

    for m in missing:
        log_warning(f"image not found: {m}")


def check_demo_assets(manifests, demos_by_stem):
    """Detect non-generated asset changes in demo and standalone directories.

    For regular demos, scans ``demo/<folder>/app/`` (excluding the generated
    ``index.html``).  For standalone pages, scans both the output directory
    ``demo/<folder>/`` and the source directory ``tools/standalone/<folder>/``.

    Any demo whose assets were modified after its stored sitemap date is
    added to CHANGED_FILES so that build_sitemap bumps the lastmod.
    """
    existing_dates = read_json_file(SITEMAP_DATES_FILE, required=False)

    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue

        for stem in manifests[cat_name]["demos"]:
            demo = demos_by_stem[stem]
            if is_external(demo):
                continue

            folder = demo.get("folder")
            if not folder:
                continue

            sitemap_path = f"/demo/{folder}/"
            stored_date = existing_dates.get(sitemap_path)
            if not stored_date:
                continue  # New page — build_sitemap assigns today's date.

            output_file = f"demo/{folder}/index.html"
            if output_file in CHANGED_FILES:
                continue  # Already marked changed by the build step.

            stored_date_obj = date.fromisoformat(stored_date)

            # Collect directories to scan and generated files to skip.
            dirs_to_scan = []
            generated = {output_file}

            if is_standalone(demo):
                dirs_to_scan.append(os.path.join(OUTPUT_DIR, "demo", folder))
                standalone_src = os.path.join(STANDALONE_DIR, folder)
                if os.path.isdir(standalone_src):
                    dirs_to_scan.append(standalone_src)
            else:
                app_dir = os.path.join(OUTPUT_DIR, "demo", folder, "app")
                if os.path.isdir(app_dir):
                    dirs_to_scan.append(app_dir)
                generated.add(f"demo/{folder}/app/index.html")

            # Walk directories looking for any file newer than the stored date.
            asset_changed = False
            for scan_dir in dirs_to_scan:
                if not os.path.isdir(scan_dir):
                    continue
                for dirpath, _, filenames in os.walk(scan_dir):
                    for fname in filenames:
                        fpath = os.path.join(dirpath, fname)
                        rel = os.path.relpath(fpath, ROOT_DIR).replace("\\", "/")
                        if rel in generated:
                            continue
                        mtime = date.fromtimestamp(os.path.getmtime(fpath))
                        if mtime > stored_date_obj:
                            asset_changed = True
                            break
                    if asset_changed:
                        break
                if asset_changed:
                    break

            if asset_changed:
                CHANGED_FILES.add(output_file)
                print(f"  Asset changed: demo/{folder}/")


def build_llms_txt(manifests, demos_by_stem):
    """Generate llms.txt, a plain-text site summary for LLM crawlers."""
    llms_data = load_json("llms.json")

    lines = [f"# {llms_data['title']}", ""]

    # Wrap description as a blockquote.
    desc_words = llms_data["description"].split()
    bq_lines = []
    current = ">"
    for word in desc_words:
        if len(current) + 1 + len(word) > 80:
            bq_lines.append(current)
            current = ">" + " " + word
        else:
            current += " " + word
    bq_lines.append(current)
    lines.extend(bq_lines)
    lines.append("")

    links_heading = llms_data.get("linksHeading", "")
    if links_heading:
        lines.append(f"## {links_heading}")
        lines.append("")

    for link in llms_data.get("links", []):
        lines.append(f"- {link}")
    lines.append("")

    projects_heading = llms_data.get("projectsHeading", "")
    if projects_heading:
        lines.append(f"## {projects_heading}")
        lines.append("")
        projects_desc = llms_data.get("projectsDescription", "")
        if projects_desc:
            lines.append(projects_desc)
            lines.append("")

    for cat_name in CATEGORIES:
        if cat_name not in manifests:
            continue

        manifest = manifests[cat_name]
        heading_level = "###" if projects_heading else "##"
        lines.append(f"{heading_level} {manifest.get('sectionTitle', '')}")
        lines.append("")

        section_desc = manifest.get("sectionDescription", "")
        if section_desc:
            lines.append(strip_html(section_desc))
            lines.append("")

        for stem in manifest["demos"]:
            demo = demos_by_stem[stem]
            title = demo.get("title", "")
            desc = demo.get("descriptionShort", "")

            if is_external(demo):
                url = demo["externalUrl"]
            else:
                folder = demo.get("folder", "")
                url = f"{SITE_BASE_URL}/demo/{folder}/"

            lines.append(f"- [{title}]({url}): {desc}")

        lines.append("")

    write_file(os.path.join(OUTPUT_DIR, "llms.txt"), "\n".join(lines))


def build_sitemap(site_paths, tangents_lastmod=None):
    """Generate sitemap.xml, updating lastmod only for pages whose content changed.

    A persistent JSON file (sitemap_dates.json) stores the last-modified date
    for each page.  Only pages recorded in CHANGED_FILES get today's date;
    all others keep their previously stored date.  Pages appearing for the
    first time also receive today's date.  tangents_lastmod overrides the
    heuristic for post pages with the post's own updated/published date.
    """
    tangents_lastmod = tangents_lastmod or {}
    today = date.today().isoformat()

    existing_dates = read_json_file(SITEMAP_DATES_FILE, required=False)

    # Determine the lastmod date for every sitemap path.
    updated_dates = {}
    for path in site_paths:
        # Map the sitemap URL path to the corresponding output file.
        if path == "/":
            output_file = "index.html"
        else:
            output_file = path.strip("/") + "/index.html"

        if path in tangents_lastmod:
            updated_dates[path] = tangents_lastmod[path]
        elif output_file in CHANGED_FILES:
            updated_dates[path] = today
        elif path in existing_dates:
            updated_dates[path] = existing_dates[path]
        else:
            # Brand-new page with no prior record.
            updated_dates[path] = today

    # Persist the updated dates for the next build.
    write_json_file(SITEMAP_DATES_FILE, updated_dates, indent=4)

    # Generate sitemap.xml.
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for path in site_paths:
        url = SITE_BASE_URL + path
        lastmod = updated_dates[path]
        lines.append('    <url>')
        lines.append(f'        <loc>{url}</loc>')
        lines.append(f'        <lastmod>{lastmod}</lastmod>')
        lines.append('    </url>')
    lines.append('</urlset>')

    write_file(os.path.join(OUTPUT_DIR, "sitemap.xml"), '\n'.join(lines) + '\n')


# ------------------------------------------------------------------------------------
# Static assets (CSS / JS)

def build_static_assets():
    """Copy JS source files from tools/ into the site root.

    CSS is inlined into the HTML templates, so only JS files are copied.
    When MINIFY is enabled the files are minified before writing. Each copy is
    cache-gated: unchanged sources are skipped, and the copy is recorded in the
    manifest so a JS file deleted from tools/js/ has its stale copy pruned.
    """
    if not os.path.isdir(JS_SRC_DIR):
        return
    out_dir = os.path.join(OUTPUT_DIR, "js")
    for filename in sorted(os.listdir(JS_SRC_DIR)):
        src_path = os.path.join(JS_SRC_DIR, filename)
        if not os.path.isfile(src_path):
            continue
        if not should_build(f"js/{filename}", [_rel(src_path)]):
            continue
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
        if MINIFY:
            content = minify_js(content)
        write_file(os.path.join(out_dir, filename), content)


# ------------------------------------------------------------------------------------
# Main

def main():
    global MINIFY, FORCE, GLOBAL_DIRTY
    args = set(sys.argv[1:])
    MINIFY = "min" in args
    FORCE = "force" in args

    mode = "minified" if MINIFY else "standard"
    print(f"Building site ({mode})...")
    if FORCE:
        print("  Force: full rebuild requested.")

    # Load all source files and inline CSS into the base template so pages
    # don't need an external stylesheet (eliminates a render-blocking request).
    base_template = load_file("base.html")

    css_path = os.path.join(CSS_SRC_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css_content = f.read()
    if MINIFY:
        css_content = minify_css(css_content)
    # Font URLs in the CSS are relative to css/styles.css (../fonts/).
    # When inlined into HTML, they must be relative to the page itself.
    css_content = css_content.replace("../fonts/", "{{basePath}}fonts/")
    base_template = replace_indented(
        base_template, "{{inlineStyles}}", f"<style>{css_content}</style>"
    )
    navbar_html = load_file("navbar.html")
    footer_html = load_file("footer.html")
    contact_html = load_file("contact.html")
    demo_template = load_file("demo.html")
    iframe_template = load_file("iframe.html")
    frontpage_content = load_file("frontpage.html")
    four04_template = load_file("404.html")
    demo_index_template = load_file("demo-index.html")
    tangents_post_template = load_file("tangents-post.html")
    tangents_list_template = load_file("tangents-list.html")
    tangents_item_template = load_file("tangents-item.html")

    # Register the site-specific github directive so markdown demo bodies can
    # emit the repo panel (mirrors the retired generate_repo_panel behaviour).
    repo_public = load_file("repo-panel.html")
    repo_private = load_file("repo-panel-private.html")

    def _github_directive(params, meta, base_path):
        repo = params.get("repo")
        url = params.get("url") or (f"https://github.com/{repo}" if repo else None)
        if not url:
            return repo_private.rstrip("\n")
        if not markdown_engine.is_safe_url(url):
            raise markdown_engine.MarkdownError(f"directive 'github' has a disallowed URL scheme: url={url!r}")
        return repo_public.replace("{{repository}}", escape_html(url)).rstrip("\n")

    markdown_engine.register_directive("github", _github_directive)

    # Load demo manifests and per-demo markdown front matter
    manifests, demos_by_stem = load_demo_data()

    # Load Tangents posts (updates tangents_dates.json) before path collection so
    # the sitemap and 404 fuzzy matcher can enumerate the post/tag/pagination pages.
    tangents_posts = load_tangents_posts()

    # Resolve each post's social card (custom-or-generated), the generic card, the
    # frontpage card, and one card per demo page.
    # The generator manages its own regeneration through a committed hash manifest,
    # so it is not a GLOBAL_SOURCES entry; force flows through so a forced build
    # also refreshes every card (its byte-compare keeps identical output write-free).
    social = generate_social_images.resolve_and_generate(
        [{"slug": p["slug"], "title": p["title"], "socialImage": p["social_image"]}
         for p in tangents_posts],
        force=FORCE,
        demos=social_card_demos(demos_by_stem),
    )
    # A custom image's size is unknown, so only generated cards declare one.
    custom_slugs = {slug for slug, _ in social["custom"]}
    card_size = generated_card_size()
    for p in tangents_posts:
        p["og_image"] = f"{SITE_BASE_URL}/{social['og_image'][p['slug']]}"
        p["og_image_size"] = (0, 0) if p["slug"] in custom_slugs else card_size
    tangents_card_url = f"{SITE_BASE_URL}/{social['index_card']}"
    for warning in social["warnings"]:
        log_warning(warning)
    # Record auto-generated cards (generated or skipped) so a deleted post's or
    # demo's card is pruned like its page. Custom images are never recorded, so the prune
    # guard leaves them untouched.
    for rel in social["generated"]:
        record_output(rel)
    for rel in social["skipped"]:
        record_output(rel)

    # Collect site paths for sitemap and 404 fuzzy matching
    site_paths = collect_site_paths(manifests, demos_by_stem, tangents_posts=tangents_posts)
    fuzzy_paths = collect_site_paths(
        manifests, demos_by_stem, include_hashes=True, tangents_posts=tangents_posts
    )

    # Load the previous manifest and decide global dirtiness before any builder
    # runs (the JS copies are cache-gated too).
    load_build_cache()
    GLOBAL_DIRTY = compute_global_dirty()
    if GLOBAL_DIRTY and not CACHE_MISSING and not FORCE:
        if _PREV_MINIFY != MINIFY:
            log_info(f"Minify mode changed (now {mode}): rebuilding all pages.")
        else:
            log_info("Global component changed: rebuilding all pages.")

    # Copy (and optionally minify) CSS and JS assets
    build_static_assets()

    # Build all pages
    build_frontpage(
        base_template, navbar_html, footer_html,
        contact_html, frontpage_content, manifests, demos_by_stem,
    )
    build_404(base_template, navbar_html, footer_html, four04_template, fuzzy_paths)
    build_demo_pages(
        base_template, navbar_html, footer_html,
        demo_template, iframe_template, manifests, demos_by_stem,
    )
    build_standalone_pages(
        base_template, navbar_html, footer_html, manifests, demos_by_stem,
    )
    build_demo_index(
        base_template, navbar_html, footer_html,
        demo_index_template, manifests, demos_by_stem,
    )
    build_tangents_posts(
        base_template, navbar_html, footer_html,
        tangents_post_template, tangents_posts,
    )
    build_tangents_list_pages(
        base_template, navbar_html, footer_html,
        tangents_list_template, tangents_item_template, tangents_posts,
        tangents_card_url,
    )
    build_tangents_feed(tangents_posts)
    check_images(manifests, demos_by_stem)
    check_demo_assets(manifests, demos_by_stem)
    build_llms_txt(manifests, demos_by_stem)

    # Post pages carry their own updated/published lastmod (more meaningful than
    # the build-day heuristic used for aggregate pages).
    tangents_lastmod = {
        f"/tangents/{p['slug']}/": (p["updated"] or p["published"]).isoformat()
        for p in tangents_posts
    }
    build_sitemap(site_paths, tangents_lastmod)

    # Prune orphaned outputs, persist the manifest, and write the build log.
    pruned = prune_orphans()
    save_build_cache()
    write_build_log(mode, FORCE, pruned, social)

    if CHANGED_FILES:
        print(f"\n  {len(CHANGED_FILES)} file(s) updated.")
    else:
        print("\n  All files up to date: nothing written.")
    if SKIPPED_PAGES:
        print(f"  {SKIPPED_PAGES} page(s) skipped as up to date.")
    print("Build complete.")


if __name__ == "__main__":
    main()
