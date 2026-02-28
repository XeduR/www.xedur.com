#!/usr/bin/env python3
"""
Static site builder for www.xedur.com.
Reads templates and JSON data from components/,
then generates HTML pages in the site root directory.

Usage:
    python update_website.py          # normal build
    python update_website.py min      # build with minified HTML
"""

import os
import re
import sys
import json
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
COMPONENTS_DIR = os.path.join(SCRIPT_DIR, "components")
TEMPLATES_DIR = os.path.join(COMPONENTS_DIR, "templates")
DATA_DIR = os.path.join(COMPONENTS_DIR, "data")
STANDALONE_DIR = os.path.join(SCRIPT_DIR, "standalone")
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

# ------------------------------------------------------------------------------------
# Minification and formatting helpers

def minify_html(text):
    """Remove HTML comments and collapse all whitespace into a single line."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'>\s+<', '><', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def indent_block(text, spaces):
    """Indent all non-empty lines of text by the given number of spaces."""
    prefix = " " * spaces
    lines = text.split('\n')
    return '\n'.join(prefix + line if line.strip() else line for line in lines)


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

    # Apply that indentation to every content line after the first.
    content_lines = content.split('\n')
    indented_lines = [content_lines[0]]
    for cline in content_lines[1:]:
        if cline.strip():
            indented_lines.append(indent_str + cline)
        else:
            indented_lines.append("")

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


# ------------------------------------------------------------------------------------
# HTML generation helpers

def is_external(demo):
    """Check if a demo entry is an external link (has a non-empty externalUrl)."""
    return bool(demo.get("externalUrl"))


def is_standalone(demo):
    """Check if a demo entry is a standalone project (has type 'standalone')."""
    return demo.get("type") == "standalone"


def generate_card(demo, card_template):
    """Generate a single project card from the card template."""
    if is_external(demo):
        href = demo["externalUrl"]
        target = ' target="_blank"'
        image = demo.get("image", "")
        external_html = '<p class="external-notice">External: This link opens in a new tab.</p>'
    else:
        folder = demo.get("folder", "")
        href = f"demo/{folder}/"
        target = ""
        image = f"demo/{folder}/{folder}-small.jpg"
        external_html = ""

    tech = demo.get("tech", "")
    tech_html = f'<p class="tech"><b>Tech:</b> {tech}</p>' if tech else ""

    card = card_template
    card = card.replace("{{cardHref}}", href)
    card = card.replace("{{cardTarget}}", target)
    card = card.replace("{{cardTitle}}", demo.get("title", ""))
    card = card.replace("{{cardImage}}", image)
    card = card.replace("{{cardDescription}}", demo.get("descriptionShort", ""))
    card = card.replace("{{cardTech}}", tech_html)
    card = card.replace("{{cardExternal}}", external_html)
    return card.rstrip('\n')


def generate_section(category_name, data, card_template, section_template):
    """Generate a full frontpage section from the section and card templates."""
    demos = data.get("demos", [])

    cards_html = ""
    for demo in demos:
        cards_html += generate_card(demo, card_template) + '\n'

    html = section_template
    html = html.replace("{{sectionId}}", category_name)
    html = html.replace("{{sectionTitle}}", data.get("sectionTitle", ""))
    html = html.replace("{{sectionDescription}}", data.get("sectionDescription", ""))
    html = replace_indented(html, "{{sectionCards}}", cards_html.rstrip('\n'))
    return html.rstrip('\n')


def generate_repo_panel(repository, repo_panel_template, private_template=""):
    """Generate the repository link panel from the template."""
    if not repository:
        return private_template.rstrip('\n')

    html = repo_panel_template
    html = html.replace("{{repository}}", repository)
    return html.rstrip('\n')


def generate_social_tags(seo, url=""):
    """Generate Open Graph and Twitter/X Card meta tags from SEO data."""
    if not seo:
        return ""

    og_title = seo.get("ogTitle", "")
    og_description = seo.get("ogDescription", "")
    og_image = seo.get("ogImage", "")
    og_image_alt = seo.get("ogImageAlt", "")

    # Open Graph tags
    og_lines = ['<!-- Open Graph meta tags -->']
    og_lines.append('<meta property="og:site_name" content="XeduR">')
    og_lines.append('<meta property="og:type" content="website">')
    if url:
        og_lines.append(f'<meta property="og:url" content="{url}">')
    if og_title:
        og_lines.append(f'<meta property="og:title" content="{og_title}">')
    if og_description:
        og_lines.append(f'<meta property="og:description" content="{og_description}">')
    if og_image:
        og_lines.append(f'<meta property="og:image" content="{og_image}">')
    if og_image_alt:
        og_lines.append(f'<meta property="og:image:alt" content="{og_image_alt}">')

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


def wrap_in_base(base_template, navbar_html, footer_html, body_content,
                 page_title, meta_description="", meta_keywords=DEFAULT_KEYWORDS,
                 og_tags="", base_path="", extra_head=""):
    """Wrap body content in the base HTML template."""
    html = base_template
    # Inline tags (single-line values)
    html = html.replace("{{metaKeywords}}", meta_keywords)
    html = html.replace("{{metaDescription}}", meta_description)
    html = html.replace("{{pageTitle}}", page_title)
    # Block tags (multi-line content that needs indentation)
    html = replace_indented(html, "{{ogTags}}", og_tags)
    html = replace_indented(html, "{{extraHead}}", extra_head)
    html = replace_indented(html, "{{navbar}}", navbar_html)
    html = replace_indented(html, "{{bodyContent}}", body_content)
    html = replace_indented(html, "{{footer}}", footer_html)
    # Path prefix (inline, applied last — must be after all other replacements
    # since injected content like extra_head may contain {{basePath}} references)
    html = html.replace("{{basePath}}", base_path)
    return html


def write_file(filepath, content):
    """Write content to a file only when it differs from the existing version.

    If MINIFY is enabled and the file is HTML, minify before comparing.
    Files that are actually written are recorded in CHANGED_FILES so that
    build_sitemap can update only the dates that need changing.
    """
    if MINIFY and filepath.endswith(".html"):
        content = minify_html(content)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    rel_path = os.path.relpath(filepath, ROOT_DIR)

    # Skip writing if the file already exists with identical content.
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            if f.read() == content:
                print(f"  Unchanged: {rel_path}")
                return

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    CHANGED_FILES.add(rel_path.replace("\\", "/"))
    print(f"  Built: {rel_path}")


# ------------------------------------------------------------------------------------
# Build steps

def collect_site_paths(category_data, include_hashes=False):
    """Collect all valid page paths on the site.

    Args:
        category_data: The loaded category JSON data.
        include_hashes: If True, include hash-based anchor sections
                        (e.g. /#plugins) for fuzzy matching on the 404 page.
    Returns:
        A list of root-relative path strings.
    """
    paths = ["/"]

    if include_hashes:
        for section in ["me", "learn"] + CATEGORIES:
            paths.append(f"/#{section}")

    for cat_name in CATEGORIES:
        if cat_name not in category_data:
            continue
        for demo in category_data[cat_name].get("demos", []):
            if is_external(demo):
                continue
            folder = demo.get("folder")
            if folder:
                paths.append(f"/demo/{folder}/")

    return paths


def build_frontpage(base_template, navbar_html, footer_html,
                    contact_html, frontpage_content, category_data):
    """Build index.html from frontpage.html and category JSON data."""
    card_template = load_file("card.html")
    section_template = load_file("section.html")

    content = frontpage_content

    # Replace snippet tags (indented to match their position in the template)
    content = replace_indented(content, "{{contact}}", contact_html)

    # Replace category tags with generated section HTML
    for cat_name in CATEGORIES:
        tag = "{{" + cat_name + "}}"
        if cat_name in category_data:
            section = generate_section(
                cat_name, category_data[cat_name],
                card_template, section_template,
            )
            content = replace_indented(content, tag, section)
        else:
            content = content.replace(tag, "")

    # Wrap in base template
    frontpage_data = load_json("frontpage.json")
    page_title = frontpage_data.get("pageTitle", "")
    meta_desc = frontpage_data.get("metaDescription", "")
    meta_kw = frontpage_data.get("metaKeywords", DEFAULT_KEYWORDS)
    og_tags = generate_social_tags(
        frontpage_data.get("seo"), url=f"{SITE_BASE_URL}/"
    )
    page = wrap_in_base(
        base_template, navbar_html, footer_html,
        body_content=content,
        page_title=page_title,
        meta_description=meta_desc,
        meta_keywords=meta_kw,
        og_tags=og_tags,
    )

    write_file(os.path.join(OUTPUT_DIR, "index.html"), page)


def build_404(base_template, navbar_html, footer_html, four04_template,
              valid_paths=None):
    """Build 404.html, injecting the valid paths list for fuzzy redirect."""
    body = four04_template
    paths_json = json.dumps(valid_paths) if valid_paths else "[]"
    body = body.replace("{{validPaths}}", paths_json)

    page = wrap_in_base(
        base_template, navbar_html, footer_html,
        body_content=body,
        page_title="XeduR - 404",
        meta_description=(
            "This is the 404 page for XeduR.com. "
            "If you are seeing this, then you are lost."
        ),
    )

    write_file(os.path.join(OUTPUT_DIR, "404.html"), page)


def build_demo_pages(base_template, navbar_html, footer_html,
                     demo_template, iframe_template, category_data):
    """Build individual demo pages for all non-external demos."""
    repo_panel_template = load_file("repo-panel.html")
    repo_private_template = load_file("repo-panel-private.html")

    for cat_name in CATEGORIES:
        if cat_name not in category_data:
            continue

        for demo in category_data[cat_name].get("demos", []):
            # Skip external and standalone entries (handled separately)
            if is_external(demo) or is_standalone(demo):
                continue

            folder = demo.get("folder")
            if not folder:
                continue

            title = demo.get("title", "")
            desc_short = demo.get("descriptionShort", "")
            desc_long = demo.get("descriptionLong") or desc_short
            repository = demo.get("repository")
            seo = demo.get("seo")

            # Build demo page body from template
            body = demo_template
            body = body.replace("{{demoTitle}}", title)
            body = body.replace("{{demoImage}}", f"{folder}-large.jpg")
            body = body.replace("{{demoDescriptionLong}}", desc_long)
            body = replace_indented(
                body, "{{demoRepository}}",
                generate_repo_panel(repository, repo_panel_template, repo_private_template),
            )
            # Determine meta description and OG tags.
            meta_desc = desc_short
            demo_url = f"{SITE_BASE_URL}/demo/{folder}/"
            demo_seo = dict(seo) if seo else {}
            if seo:
                meta_desc = seo.get("metaDescription") or desc_short
            demo_seo["ogImage"] = f"{SITE_BASE_URL}/demo/{folder}/{folder}-large.jpg"
            og_tags = generate_social_tags(demo_seo, url=demo_url)

            # Wrap in base template
            page = wrap_in_base(
                base_template, navbar_html, footer_html,
                body_content=body,
                page_title=f"XeduR - {title}",
                meta_description=meta_desc,
                og_tags=og_tags,
                base_path="../../",
            )

            # Write demo page under demo/ subfolder
            demo_dir = os.path.join(OUTPUT_DIR, "demo", folder)
            write_file(os.path.join(demo_dir, "index.html"), page)

            # Scan app/ folder for the .bin file
            app_dir = os.path.join(demo_dir, "app")
            bin_files = [f for f in os.listdir(app_dir) if f.endswith(".bin")] if os.path.isdir(app_dir) else []

            if not bin_files:
                print(f"  ERROR: No .bin file found in demo/{folder}/app/")
                continue
            if len(bin_files) > 1:
                print(f"  WARNING: Multiple .bin files in demo/{folder}/app/: {bin_files}")

            bin_name = bin_files[0].removesuffix(".bin")

            # Create app/ subfolder with iframe loader
            iframe_html = iframe_template.replace("{{demoTitle}}", title)
            iframe_html = iframe_html.replace("{{demoBinName}}", bin_name)
            iframe_html = iframe_html.replace("{{demoDescription}}", desc_short)
            write_file(os.path.join(demo_dir, "app", "index.html"), iframe_html)


def build_standalone_pages(base_template, navbar_html, footer_html, category_data):
    """Build pages for standalone projects that use their own content templates.

    Standalone projects are identified by ``"type": "standalone"`` in their
    JSON data entry.  Source files (content.html, head.html, config.json) are
    read from tools/standalone/<folder>/.
    """
    for cat_name in CATEGORIES:
        if cat_name not in category_data:
            continue

        for demo in category_data[cat_name].get("demos", []):
            if not is_standalone(demo):
                continue

            folder = demo.get("folder")
            if not folder:
                continue

            standalone_dir = os.path.join(STANDALONE_DIR, folder)
            if not os.path.isdir(standalone_dir):
                print(f"  Warning: standalone folder not found: {folder}")
                continue

            # Load standalone project files
            content_path = os.path.join(standalone_dir, "content.html")
            head_path = os.path.join(standalone_dir, "head.html")
            config_path = os.path.join(standalone_dir, "config.json")

            with open(content_path, "r", encoding="utf-8") as f:
                body_content = f.read()

            extra_head = ""
            if os.path.exists(head_path):
                with open(head_path, "r", encoding="utf-8") as f:
                    extra_head = f.read()

            config = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

            title = config.get("title", demo.get("title", ""))
            meta_desc = config.get("metaDescription", demo.get("descriptionShort", ""))
            meta_keywords = config.get("metaKeywords", DEFAULT_KEYWORDS)

            demo_url = f"{SITE_BASE_URL}/demo/{folder}/"
            standalone_seo = dict(config.get("seo", {}))
            standalone_seo["ogImage"] = f"{SITE_BASE_URL}/demo/{folder}/{folder}-large.jpg"
            og_tags = generate_social_tags(standalone_seo, url=demo_url)

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
            )

            demo_dir = os.path.join(OUTPUT_DIR, "demo", folder)
            write_file(os.path.join(demo_dir, "index.html"), page)


def check_images(category_data):
    """Verify that all expected images exist on disk.

    For non-external demos (regular and standalone), checks for
    ``demo/<folder>/<folder>-small.jpg`` and ``demo/<folder>/<folder>-large.jpg``.
    For external links, checks the image path defined in JSON.
    """
    missing = []
    for cat_name in CATEGORIES:
        if cat_name not in category_data:
            continue
        for demo in category_data[cat_name].get("demos", []):
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

    if missing:
        print(f"\n  WARNING: {len(missing)} image(s) not found:")
        for m in missing:
            print(f"    - {m}")


def check_demo_assets(category_data):
    """Detect non-generated asset changes in demo and standalone directories.

    For regular demos, scans ``demo/<folder>/app/`` (excluding the generated
    ``index.html``).  For standalone pages, scans both the output directory
    ``demo/<folder>/`` and the source directory ``tools/standalone/<folder>/``.

    Any demo whose assets were modified after its stored sitemap date is
    added to CHANGED_FILES so that build_sitemap bumps the lastmod.
    """
    existing_dates = {}
    if os.path.exists(SITEMAP_DATES_FILE):
        with open(SITEMAP_DATES_FILE, "r", encoding="utf-8") as f:
            existing_dates = json.load(f)

    for cat_name in CATEGORIES:
        if cat_name not in category_data:
            continue

        for demo in category_data[cat_name].get("demos", []):
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


def build_sitemap(site_paths):
    """Generate sitemap.xml, updating lastmod only for pages whose content changed.

    A persistent JSON file (sitemap_dates.json) stores the last-modified date
    for each page.  Only pages recorded in CHANGED_FILES get today's date;
    all others keep their previously stored date.  Pages appearing for the
    first time also receive today's date.
    """
    today = date.today().isoformat()

    # Load previously stored dates (if any).
    existing_dates = {}
    if os.path.exists(SITEMAP_DATES_FILE):
        with open(SITEMAP_DATES_FILE, "r", encoding="utf-8") as f:
            existing_dates = json.load(f)

    # Determine the lastmod date for every sitemap path.
    updated_dates = {}
    for path in site_paths:
        # Map the sitemap URL path to the corresponding output file.
        if path == "/":
            output_file = "index.html"
        else:
            output_file = path.strip("/") + "/index.html"

        if output_file in CHANGED_FILES:
            updated_dates[path] = today
        elif path in existing_dates:
            updated_dates[path] = existing_dates[path]
        else:
            # Brand-new page with no prior record.
            updated_dates[path] = today

    # Persist the updated dates for the next build.
    with open(SITEMAP_DATES_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_dates, f, indent=4)
        f.write("\n")

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
# Main

def main():
    global MINIFY
    MINIFY = len(sys.argv) > 1 and sys.argv[1] == "min"

    mode = "minified" if MINIFY else "standard"
    print(f"Building site ({mode})...")

    # Load all source files
    base_template = load_file("base.html")
    navbar_html = load_file("navbar.html")
    footer_html = load_file("footer.html")
    contact_html = load_file("contact.html")
    demo_template = load_file("demo.html")
    iframe_template = load_file("iframe.html")
    frontpage_content = load_file("frontpage.html")
    four04_template = load_file("404.html")

    # Load category JSON data
    category_data = {}
    for cat in CATEGORIES:
        json_path = os.path.join(DATA_DIR, f"{cat}.json")
        if os.path.exists(json_path):
            category_data[cat] = load_json(f"{cat}.json")

    # Collect site paths for sitemap and 404 fuzzy matching
    site_paths = collect_site_paths(category_data)
    fuzzy_paths = collect_site_paths(category_data, include_hashes=True)

    # Build all pages
    build_frontpage(
        base_template, navbar_html, footer_html,
        contact_html, frontpage_content, category_data,
    )
    build_404(base_template, navbar_html, footer_html, four04_template, fuzzy_paths)
    build_demo_pages(
        base_template, navbar_html, footer_html,
        demo_template, iframe_template, category_data,
    )
    build_standalone_pages(
        base_template, navbar_html, footer_html, category_data,
    )
    check_images(category_data)
    check_demo_assets(category_data)
    build_sitemap(site_paths)

    if CHANGED_FILES:
        print(f"\n  {len(CHANGED_FILES)} file(s) updated.")
    else:
        print("\n  All files up to date — nothing written.")
    print("Build complete.")


if __name__ == "__main__":
    main()
