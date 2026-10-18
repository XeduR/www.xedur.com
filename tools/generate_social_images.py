#!/usr/bin/env python3
"""
Social share card generator for www.xedur.com Tangents posts.

Renders a branded 1200x630 Open Graph / Twitter card per post (X mark, the
"Tangents" label, and the post title) plus one generic card for the index,
pagination, and tag pages. A card is regenerated only when the generator
script, the post title, or the logo/font assets change; the pair of SHA-256
hashes that gates this lives in the committed manifest
components/data/social_images.json.

Importable by update_website.py (same directory, like markdown_engine) and
runnable standalone. Pillow is imported lazily inside the render path only, so a
fully up-to-date build never imports it.

Vendored fonts (components/fonts/, part of the card-input hash):
    Roboto v3.016, hinted/static (full glyph coverage for arbitrary titles).
    Source: https://github.com/googlefonts/roboto-3-classic/releases/download/v3.016/Roboto_v3.016.zip
    License: SIL Open Font License 1.1 (components/fonts/Roboto-OFL.txt).
    Roboto-Regular.ttf sha256 9f300202f482ad59f8b13bc3131a295744d14fd530fa3765a0a11ec87264d203
    Roboto-Bold.ttf    sha256 44f13e570a8b3fc42240abfcb3d72fe298f3dd6a25db0c78d0c2495dbd0e9121

Usage:
    python generate_social_images.py              # every non-draft post + generic card
    python generate_social_images.py force        # regenerate everything
    python generate_social_images.py <slug> ...   # only the named posts (manifest kept)
"""

import io
import os
import sys
import json
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
COMPONENTS_DIR = os.path.join(SCRIPT_DIR, "components")
DATA_DIR = os.path.join(COMPONENTS_DIR, "data")
FONTS_DIR = os.path.join(COMPONENTS_DIR, "fonts")
TANGENTS_SRC_DIR = os.path.join(SCRIPT_DIR, "tangents")

MANIFEST_FILE = os.path.join(DATA_DIR, "social_images.json")

# Card assets.
LOGO_FILE = os.path.join(ROOT_DIR, "img", "xedur.png")
FONT_REGULAR = os.path.join(FONTS_DIR, "Roboto-Regular.ttf")
FONT_BOLD = os.path.join(FONTS_DIR, "Roboto-Bold.ttf")

# Absolute path to this script, hashed to invalidate every card on a script edit.
_SELF_PATH = os.path.abspath(__file__)

# Card contract (see task-4 spec). These are hashed into every card's inputs, so
# changing any of them regenerates all cards.
CARD_WIDTH = 1200
CARD_HEIGHT = 630
CARD_LABEL = "Tangents"
INDEX_CARD_REL = "tangents/tangents-social.png"

# Palette from the site stylesheet (tools/css/styles.css): background #0E0E0E,
# accent gold #FCBA04, white text; the URL line uses a muted gray.
BACKGROUND_COLOR = (14, 14, 14)
ACCENT_COLOR = (252, 186, 4)
TEXT_COLOR = (255, 255, 255)
MUTED_COLOR = (138, 138, 138)

# Layout, in pixels. Tuned so the title block never collides with the mark and
# every line stays inside the card bounds (verified against long/Nordic titles).
PADDING = 80
LOGO_SIZE = 360
LABEL_SIZE = 46
LABEL_Y = 92
TITLE_Y = 192
TITLE_GAP = 48
MAX_TITLE_LINES = 3
LINE_SPACING = 1.18
FOOTER_SIZE = 32
FOOTER_TEXT = "www.xedur.com"
GENERIC_LABEL_SIZE = 88
GENERIC_GAP = 44
ELLIPSIS = "..."


class SocialImageError(Exception):
    """Raised on a reserved-name value, a missing asset, or a render with Pillow absent."""


# ------------------------------------------------------------------------------------
# Paths and hashing (no Pillow needed here)

def _rel(abs_path):
    """Repo-relative POSIX path for messages and manifest keys."""
    return os.path.relpath(abs_path, ROOT_DIR).replace(os.sep, "/")


def generated_name(slug):
    """Reserved output filename for a post's auto-generated card."""
    return f"{slug}-social.png"


_BYTES_CACHE = {}


def _read_bytes(path, *, required=True):
    """Read a file's bytes, memoized. A missing required asset raises."""
    if path in _BYTES_CACHE:
        return _BYTES_CACHE[path]
    if not os.path.isfile(path):
        if required:
            raise SocialImageError(f"required card asset not found: {_rel(path)}")
        return b""
    with open(path, "rb") as f:
        data = f.read()
    _BYTES_CACHE[path] = data
    return data


def _generator_hash():
    """SHA-256 of this script's own bytes; any edit invalidates every card."""
    return hashlib.sha256(_read_bytes(_SELF_PATH)).hexdigest()


def _inputs_hash(title):
    """SHA-256 over a card's content inputs (dimensions, label, title, assets).

    The generic card hashes with an empty title. The byte sequence is fixed by
    the task-4 spec so the manifest stays comparable across runs.
    """
    h = hashlib.sha256()
    h.update(f"{CARD_WIDTH}x{CARD_HEIGHT}\x00{CARD_LABEL}\x00{title}\x00".encode("utf-8"))
    h.update(_read_bytes(LOGO_FILE))
    h.update(b"\x00")
    h.update(_read_bytes(FONT_BOLD))
    h.update(b"\x00")
    h.update(_read_bytes(FONT_REGULAR))
    return h.hexdigest()


# ------------------------------------------------------------------------------------
# Manifest

def _load_manifest():
    """Load the committed hash manifest; a corrupt or missing file reads as empty."""
    if not os.path.isfile(MANIFEST_FILE):
        return {}
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict) or data.get("version") != 1:
        return {}
    images = data.get("images")
    return images if isinstance(images, dict) else {}


def _save_manifest(images):
    """Persist the manifest (sorted keys, indent 2, trailing newline).

    Skips the write when the on-disk bytes already match, mirroring write_file's
    discipline so a warm run leaves the committed file untouched.
    """
    payload = json.dumps({"version": 1, "images": images}, indent=2, sort_keys=True) + "\n"
    if os.path.isfile(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            if f.read() == payload:
                return
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        f.write(payload)


# ------------------------------------------------------------------------------------
# Rendering (Pillow, imported lazily)

def _title_font_size(title):
    """Step the title size down as the title grows, per the spec's rough bands."""
    length = len(title)
    if length <= 40:
        return 72
    if length <= 70:
        return 60
    return 50


def _wrap_lines(draw, text, font, max_width, max_lines):
    """Greedily wrap text into at most max_lines lines within max_width pixels.

    Returns (lines, overflowed). A single word wider than max_width still takes
    its own line; it is ellipsized later if it is the overflowing last line.
    """
    words = text.split()
    lines = []
    i = 0
    n = len(words)
    while i < n and len(lines) < max_lines:
        line = words[i]
        i += 1
        while i < n and draw.textlength(f"{line} {words[i]}", font=font) <= max_width:
            line = f"{line} {words[i]}"
            i += 1
        lines.append(line)
    return lines, i < n


def _ellipsize(draw, text, font, max_width):
    """Trim text so text + '...' fits within max_width pixels."""
    if draw.textlength(text + ELLIPSIS, font=font) <= max_width:
        return text + ELLIPSIS
    trimmed = text
    while trimmed and draw.textlength(trimmed + ELLIPSIS, font=font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + ELLIPSIS) if trimmed.strip() else ELLIPSIS


def _render_card(title, generic):
    """Render a card to PNG bytes. Imports Pillow lazily and fails loudly if absent."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SocialImageError(
            "Pillow is required to render a social card but is not installed. "
            "Install it (the game-web-dev and ai-data-dev containers pin 12.2.0) "
            "or commit a custom image and name it via the post's socialImage key."
        ) from exc

    card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), BACKGROUND_COLOR + (255,))
    draw = ImageDraw.Draw(card)

    logo = Image.open(LOGO_FILE).convert("RGBA")
    logo = logo.resize((LOGO_SIZE, LOGO_SIZE), Image.Resampling.LANCZOS)

    if generic:
        _draw_generic(card, draw, logo, ImageFont)
    else:
        _draw_post(card, draw, logo, ImageFont, title)

    # Flatten onto the opaque background and encode. Pillow's default PNG encode
    # writes no timestamp chunk, so identical inputs produce identical bytes.
    buffer = io.BytesIO()
    card.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _draw_post(card, draw, logo, image_font, title):
    """Post card: mark on the right, label + wrapped title on the left, URL below."""
    logo_x = CARD_WIDTH - PADDING - LOGO_SIZE
    logo_y = (CARD_HEIGHT - LOGO_SIZE) // 2
    card.alpha_composite(logo, (logo_x, logo_y))

    label_font = image_font.truetype(FONT_REGULAR, LABEL_SIZE)
    draw.text((PADDING, LABEL_Y), CARD_LABEL, font=label_font, fill=ACCENT_COLOR, anchor="la")

    title_font = image_font.truetype(FONT_BOLD, _title_font_size(title))
    text_max_width = logo_x - TITLE_GAP - PADDING
    lines, overflowed = _wrap_lines(draw, title, title_font, text_max_width, MAX_TITLE_LINES)
    if lines and (overflowed or draw.textlength(lines[-1], font=title_font) > text_max_width):
        lines[-1] = _ellipsize(draw, lines[-1], title_font, text_max_width)

    line_height = round(_title_font_size(title) * LINE_SPACING)
    y = TITLE_Y
    for line in lines:
        draw.text((PADDING, y), line, font=title_font, fill=TEXT_COLOR, anchor="la")
        y += line_height

    footer_font = image_font.truetype(FONT_REGULAR, FOOTER_SIZE)
    draw.text((PADDING, CARD_HEIGHT - PADDING), FOOTER_TEXT, font=footer_font,
              fill=MUTED_COLOR, anchor="lb")


def _draw_generic(card, draw, logo, image_font):
    """Generic card: mark and "Tangents" label centered as one vertical composition.

    No URL line here (unlike the post cards): a centered footer would collide
    with the centered label, and the spec describes this card as just the
    centered mark plus label.
    """
    label_font = image_font.truetype(FONT_REGULAR, GENERIC_LABEL_SIZE)
    ascent, descent = label_font.getmetrics()
    label_h = ascent + descent

    composition_h = LOGO_SIZE + GENERIC_GAP + label_h
    top = (CARD_HEIGHT - composition_h) // 2

    logo_x = (CARD_WIDTH - LOGO_SIZE) // 2
    card.alpha_composite(logo, (logo_x, top))

    label_cy = top + LOGO_SIZE + GENERIC_GAP + label_h // 2
    draw.text((CARD_WIDTH // 2, label_cy), CARD_LABEL, font=label_font,
              fill=ACCENT_COLOR, anchor="mm")


# ------------------------------------------------------------------------------------
# Resolution and generation

def _process_auto_target(rel_path, title, gen_hash, prev_images, new_images, result,
                         force, generic):
    """Skip or render one auto-generated card, updating the manifest and result."""
    abs_path = os.path.join(ROOT_DIR, rel_path.replace("/", os.sep))
    inputs_hash = _inputs_hash(title)

    # Record the fresh hashes whether or not we render: the manifest reflects the
    # current inputs even when the bytes turn out identical.
    new_images[rel_path] = {"generator": gen_hash, "inputs": inputs_hash}

    entry = prev_images.get(rel_path)
    if (not force and os.path.isfile(abs_path) and entry is not None
            and entry.get("generator") == gen_hash and entry.get("inputs") == inputs_hash):
        result["skipped"].append(rel_path)
        print(f"  Skipped (up to date): {rel_path}")
        return

    # Render, then byte-compare before writing so a forced or cross-version rerun
    # that produces identical bytes causes no git churn.
    data = _render_card(title, generic=generic)
    existing = _read_bytes(abs_path, required=False) if os.path.isfile(abs_path) else None
    if existing != data:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)
        # Drop any stale cached bytes for this path so a later read sees the new file.
        _BYTES_CACHE.pop(abs_path, None)
    result["generated"].append(rel_path)
    print(f"  Generated: {rel_path}")


def resolve_and_generate(posts, force=False, prune=True):
    """Resolve every post's social image and generate what is missing or stale.

    posts: [{"slug": str, "title": str, "socialImage": str_or_None}, ...]
           (non-draft posts only; the caller filters).
    force: regenerate even when the manifest says up to date.
    prune: drop manifest entries not touched this run. True marks a full run
           (update_website.py, and the CLI with no slug filter): the generic card
           is processed and untouched entries are dropped. False marks a
           slug-filtered CLI run: only the named posts are touched and every
           other manifest entry survives.

    Returns a dict with og_image (slug -> repo-relative POSIX path), index_card,
    and the generated / skipped / custom / warnings lists.

    Raises SocialImageError on a reserved-name socialImage value, a missing
    logo/font asset, or a needed render with Pillow unavailable.
    """
    prev_images = _load_manifest()
    new_images = {}
    result = {
        "og_image": {},
        "index_card": INDEX_CARD_REL,
        "generated": [],
        "skipped": [],
        "custom": [],
        "warnings": [],
    }

    gen_hash = _generator_hash()

    for post in posts:
        slug = post["slug"]
        title = post["title"]
        social_image = post.get("socialImage")
        reserved = generated_name(slug)
        auto_rel = f"tangents/{slug}/{reserved}"

        if social_image and social_image != "auto":
            if "/" in social_image or "\\" in social_image or ".." in social_image:
                raise SocialImageError(
                    f"tangents/{slug}: socialImage {social_image!r} must be a bare "
                    f"filename inside tangents/{slug}/ (no '/', '\\', or '..')"
                )
            if social_image == reserved:
                raise SocialImageError(
                    f"tangents/{slug}: socialImage {social_image!r} uses the reserved "
                    f"generated-card name; rename the custom file or drop the key"
                )
            custom_rel = f"tangents/{slug}/{social_image}"
            custom_abs = os.path.join(ROOT_DIR, custom_rel.replace("/", os.sep))
            if os.path.isfile(custom_abs):
                result["og_image"][slug] = custom_rel
                result["custom"].append((slug, custom_rel))
                print(f"  Custom image: {custom_rel}")
                continue
            warning = (
                f"tangents/{slug}: socialImage {social_image!r} not found in "
                f"tangents/{slug}/; generating a card instead"
            )
            result["warnings"].append(warning)

        result["og_image"][slug] = auto_rel
        _process_auto_target(auto_rel, title, gen_hash, prev_images, new_images,
                             result, force, generic=False)

    # The generic card is a full-run concern only; a slug-filtered run leaves it
    # (and its surviving manifest entry) alone.
    if prune:
        _process_auto_target(INDEX_CARD_REL, "", gen_hash, prev_images, new_images,
                             result, force, generic=True)

    if prune:
        images = new_images
    else:
        images = dict(prev_images)
        images.update(new_images)
    _save_manifest(images)

    return result


# ------------------------------------------------------------------------------------
# Standalone CLI

def _load_posts_from_disk():
    """Gather non-draft post slug/title/socialImage from tools/tangents/*.md."""
    import markdown_engine

    posts = []
    if not os.path.isdir(TANGENTS_SRC_DIR):
        return posts
    for filename in sorted(os.listdir(TANGENTS_SRC_DIR)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(TANGENTS_SRC_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            front, _ = markdown_engine.parse_front_matter(f.read(), source=filename)
        if front.get("draft"):
            continue
        title = front.get("title")
        if not title:
            # The site build enforces a title; standalone we just skip it.
            continue
        posts.append({
            "slug": filename[:-3],
            "title": title,
            "socialImage": front.get("socialImage"),
        })
    return posts


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "force" in argv
    slugs = [arg for arg in argv if arg != "force"]

    posts = _load_posts_from_disk()
    if slugs:
        wanted = set(slugs)
        present = {p["slug"] for p in posts}
        for slug in sorted(wanted - present):
            print(f"  WARNING: no non-draft post named {slug!r}")
        posts = [p for p in posts if p["slug"] in wanted]

    result = resolve_and_generate(posts, force=force, prune=not slugs)

    for warning in result["warnings"]:
        print(f"  WARNING: {warning}")

    print(
        f"\n  {len(result['generated'])} generated, "
        f"{len(result['skipped'])} up to date, "
        f"{len(result['custom'])} custom."
    )


if __name__ == "__main__":
    main()
