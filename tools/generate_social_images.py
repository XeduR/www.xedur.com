#!/usr/bin/env python3
"""
Social share cards (posts, Tangents, frontpage, demos) for www.xedur.com.

Usage:
    python generate_social_images.py              # every card: posts, generic, frontpage, demos
    python generate_social_images.py force        # regenerate everything
    python generate_social_images.py <slug> ...   # only the named posts (manifest kept)
"""

import io
import os
import re
import sys
import json
import struct
import hashlib
import functools
from dataclasses import dataclass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
COMPONENTS_DIR = os.path.join(SCRIPT_DIR, "components")
DATA_DIR = os.path.join(COMPONENTS_DIR, "data")
FONTS_DIR = os.path.join(COMPONENTS_DIR, "fonts")
TANGENTS_SRC_DIR = os.path.join(SCRIPT_DIR, "tangents")

MANIFEST_FILE = os.path.join(DATA_DIR, "social_images.json")
CONFIG_FILE = os.path.join(DATA_DIR, "social_cards.json")

# Absolute path to this script, hashed to invalidate every card on a script edit.
_SELF_PATH = os.path.abspath(__file__)

INDEX_CARD_REL = "tangents/tangents-social.png"
FRONTPAGE_CARD_REL = "img/xedur-social.png"

CARD_KINDS = ("post", "tangents", "frontpage", "demo")

# A custom socialImage reaches og:image verbatim, so it is limited to characters
# that need no URL encoding, and a leading dot is barred.
SOCIAL_IMAGE_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")


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


# ------------------------------------------------------------------------------------
# Glyph coverage (no Pillow needed here)

@functools.cache
def _font_codepoints(path: str) -> frozenset[int]:
    """Codepoints the font maps to a real glyph in its format 4 and 12 cmap subtables.
    A codepoint mapped to glyph 0 is the missing-glyph box, so it does not count."""
    data = _read_bytes(path)
    for i in range(struct.unpack_from(">H", data, 4)[0]):
        tag, _, cmap, _ = struct.unpack_from(">4sIII", data, 12 + 16 * i)
        if tag == b"cmap":
            break

    covered = set()
    for i in range(struct.unpack_from(">H", data, cmap + 2)[0]):
        sub = cmap + struct.unpack_from(">I", data, cmap + 8 + 8 * i)[0]
        subtable_format = struct.unpack_from(">H", data, sub)[0]

        if subtable_format == 4:
            seg_count = struct.unpack_from(">H", data, sub + 6)[0] // 2
            ends = struct.unpack_from(f">{seg_count}H", data, sub + 14)
            starts = struct.unpack_from(f">{seg_count}H", data, sub + 16 + 2 * seg_count)
            deltas = struct.unpack_from(f">{seg_count}H", data, sub + 16 + 4 * seg_count)
            range_base = sub + 16 + 6 * seg_count
            range_offsets = struct.unpack_from(f">{seg_count}H", data, range_base)
            for seg, (start, end, delta, range_offset) in enumerate(zip(starts, ends, deltas, range_offsets)):
                for code in range(start, end + 1):
                    if range_offset:
                        glyph_pos = range_base + 2 * seg + range_offset + 2 * (code - start)
                        glyph = struct.unpack_from(">H", data, glyph_pos)[0]
                        glyph = (glyph + delta) & 0xFFFF if glyph else 0
                    else:
                        glyph = (code + delta) & 0xFFFF
                    if glyph:
                        covered.add(code)

        elif subtable_format == 12:
            for group in range(struct.unpack_from(">I", data, sub + 12)[0]):
                start, end, start_glyph = struct.unpack_from(">III", data, sub + 16 + 12 * group)
                covered.update(range(start + (start_glyph == 0), end + 1))

    return frozenset(covered)


def card_title(config: dict, text: str) -> tuple[str, str]:
    """The title as the card font can draw it, and the characters it dropped."""
    covered = _font_codepoints(_font_path(config, config["styles"]["name"]["font"]))
    missing = "".join(dict.fromkeys(ch for ch in text if ord(ch) not in covered and not ch.isspace()))
    if not missing:
        return text, ""
    return " ".join("".join(ch for ch in text if ch not in missing).split()), missing


def _drawable_title(config: dict, label: str, text: str, warnings: list) -> str:
    title, missing = card_title(config, text)
    if missing:
        warnings.append(f"{label}: the social card font has no glyph for {missing!r}; "
                        f"the card title leaves them out")
    return title


def load_card_config() -> dict:
    """Parse the card config: colours, fonts, text, and layout numbers."""
    return json.loads(_read_bytes(CONFIG_FILE).decode("utf-8"))


def _font_path(config: dict, role: str) -> str:
    return os.path.join(FONTS_DIR, config["fonts"][role])


def _logo_path(config: dict) -> str:
    return os.path.join(ROOT_DIR, config["logo"].replace("/", os.sep))


def _inputs_hash(kind: str, text: str) -> str:
    """SHA-256 over a card's content inputs (dimensions, kind, text, config, assets).

    The site-wide cards hash with empty text.
    """
    config = load_card_config()
    canvas = config["canvas"]
    h = hashlib.sha256()
    h.update(f"{canvas['width']}x{canvas['height']}\x00{kind}\x00{text}\x00".encode("utf-8"))
    h.update(_read_bytes(CONFIG_FILE))
    h.update(b"\x00")
    h.update(_read_bytes(_logo_path(config)))
    for role in sorted(config["fonts"]):
        h.update(b"\x00")
        h.update(_read_bytes(_font_path(config, role)))
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

@dataclass(frozen=True)
class TextStyle:
    """One text role at one size, with the CSS metrics the site applies to it."""

    font: object
    size: int
    tracking: float
    advance: int
    color: tuple[int, int, int]
    uppercase: bool

    def prepare(self, text: str) -> str:
        return text.upper() if self.uppercase else text


_FONT_CACHE = {}


def _hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _load_font(path: str, size: int):
    key = (path, size)
    if key not in _FONT_CACHE:
        from PIL import ImageFont

        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def make_style(config: dict, name: str, size: int) -> TextStyle:
    """Build a text role from the config; tracking is em-relative and the line
    advance is round(size * line-height), as the browser lays it out."""
    spec = config["styles"][name]
    return TextStyle(
        font=_load_font(_font_path(config, spec["font"]), size),
        size=size,
        tracking=spec["tracking"] * size,
        advance=round(size * spec["lineHeight"]),
        color=_hex_color(config["colors"][spec["color"]]),
        uppercase=spec["uppercase"],
    )


def tracked_width(text: str, style: TextStyle) -> float:
    """Width of a run as draw_tracked lays it out, so measure and draw always agree."""
    if not text:
        return 0.0
    return style.font.getlength(text) + style.tracking * (len(text) - 1)


def draw_tracked(draw, x: float, baseline: float, text: str, style: TextStyle) -> float:
    """Draw a run glyph by glyph, as a whole-string draw cannot space interior
    glyphs the way CSS letter-spacing does. Each glyph sits at its pen position
    in the kerned whole run (the run through it, minus its own advance), plus the
    tracking, because the browser keeps kerning under letter-spacing. Returns the
    x where the run ends."""
    for i, ch in enumerate(text):
        offset = style.font.getlength(text[:i + 1]) - style.font.getlength(ch) + style.tracking * i
        draw.text((x + offset, baseline), ch, font=style.font, fill=style.color, anchor="ls")
    return x + tracked_width(text, style)


def cap_height(style: TextStyle) -> int:
    return -style.font.getbbox("H", anchor="ls")[1]


def wrap_lines(text: str, style: TextStyle, max_width: float,
               max_lines: int) -> tuple[list[str], bool]:
    """Greedily wrap text into at most max_lines lines within max_width pixels.

    Returns (lines, overflowed). A single word wider than max_width still takes
    its own line; fit_text ellipsizes it.
    """
    words = text.split()
    lines = []
    i = 0
    n = len(words)
    while i < n and len(lines) < max_lines:
        line = words[i]
        i += 1
        while i < n and tracked_width(f"{line} {words[i]}", style) <= max_width:
            line = f"{line} {words[i]}"
            i += 1
        lines.append(line)
    return lines, i < n


def ellipsize(text: str, style: TextStyle, max_width: float, ellipsis: str) -> str:
    """Trim text so text + ellipsis fits within max_width pixels."""
    if tracked_width(text + ellipsis, style) <= max_width:
        return text + ellipsis
    trimmed = text
    while trimmed and tracked_width(trimmed + ellipsis, style) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + ellipsis) if trimmed.strip() else ellipsis


def fit_text(config: dict, style_name: str, text: str, sizes: list[int], max_width: float,
             max_lines: int) -> tuple[TextStyle, list[str]]:
    """Pick the largest size whose wrap fits; the smallest size ellipsizes what still overflows."""
    for size in sizes:
        style = make_style(config, style_name, size)
        lines, overflowed = wrap_lines(style.prepare(text), style, max_width, max_lines)
        if not overflowed and all(tracked_width(line, style) <= max_width for line in lines):
            return style, lines

    ellipsis = style.prepare(config["text"]["ellipsis"])
    for i, line in enumerate(lines):
        last = i == len(lines) - 1
        if tracked_width(line, style) > max_width or (last and overflowed):
            lines[i] = ellipsize(line, style, max_width, ellipsis)
    return style, lines


def block_height(lines: list[str], style: TextStyle) -> int:
    """Distance from the first line's cap top to the last line's baseline."""
    return cap_height(style) + style.advance * (len(lines) - 1)


def draw_block(draw, x: float, cap_top: float, lines: list[str], style: TextStyle) -> float:
    """Draw lines with the first cap top at cap_top; returns the last baseline."""
    baseline = cap_top + cap_height(style)
    for i, line in enumerate(lines):
        if i:
            baseline += style.advance
        draw_tracked(draw, x, baseline, line, style)
    return baseline


def _draw_rule(draw, config: dict, x: int, y: int, width: int, thickness: int) -> None:
    color = _hex_color(config["colors"]["line"])
    draw.rectangle([x, y, x + width - 1, y + thickness - 1], fill=color)


def _load_logo(config: dict, size: int):
    """The mark cropped to its visible pixels and scaled to fit a size x size box,
    so it aligns to the padding by ink rather than by the PNG's transparent margin."""
    from PIL import Image

    logo = Image.open(_logo_path(config)).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    scale = size / max(logo.width, logo.height)
    target = (round(logo.width * scale), round(logo.height * scale))
    return logo.resize(target, Image.Resampling.LANCZOS)


def _single_line(text: str, style: TextStyle, max_width: float, ellipsis: str) -> str:
    if tracked_width(text, style) <= max_width:
        return text
    return ellipsize(text, style, max_width, ellipsis)


def render_card(kind: str, text: str = "", config: dict | None = None) -> bytes:
    """Render one card to PNG bytes.

    kind is one of CARD_KINDS; text is the post title or demo name and is unused
    by the frontpage and generic Tangents cards. Imports Pillow lazily and fails
    loudly if it is absent.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SocialImageError(
            "Pillow is required to render a social card but is not installed. "
            "Install it (the game-web-dev and ai-data-dev containers pin 12.2.0) "
            "or commit a custom image and name it via the post's socialImage key."
        ) from exc

    if kind not in CARD_KINDS:
        raise SocialImageError(f"unknown card kind {kind!r}")

    config = config if config is not None else load_card_config()
    size = (config["canvas"]["width"], config["canvas"]["height"])
    card = Image.new("RGB", size, _hex_color(config["colors"]["background"]))
    draw = ImageDraw.Draw(card)
    _draw_card(card, draw, config, kind, text)

    # Pillow's default PNG encode writes no timestamp chunk, so identical inputs
    # produce identical bytes.
    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    return buffer.getvalue()


def _draw_card(card, draw, config: dict, kind: str, text: str) -> None:
    """Site heading top-left, mark top-right, then a hairline over the page's
    band across the full width at the bottom."""
    spec = config["layout"]
    labels = config["text"]
    ellipsis = labels["ellipsis"]
    width, height = card.size
    padding = spec["padding"]
    content_width = width - 2 * padding

    logo = _load_logo(config, spec["logoSize"])
    card.paste(logo, (width - padding - logo.width, padding), logo)

    heading = make_style(config, "heading", spec["headingSize"])
    heading_baseline = draw_block(draw, padding, padding, [heading.prepare(labels["siteName"])], heading)

    if kind == "frontpage" and labels["tagline"]:
        lead = make_style(config, "lead", spec["taglineSize"])
        column_width = content_width - logo.width - spec["columnGap"]
        tagline = _single_line(labels["tagline"], lead, column_width, ellipsis)
        draw_block(draw, padding, heading_baseline + spec["taglineGap"], [tagline], lead)

    if kind == "frontpage":
        style = make_style(config, "footer", spec["footerSize"])
        lines = [_single_line(labels["footer"], style, content_width, ellipsis)]
    elif kind == "tangents":
        style, lines = fit_text(config, "section", labels["tangentsLabel"], spec["sectionSizes"],
                                content_width, 1)
    elif kind == "post":
        style, lines = fit_text(config, "name", text, spec["postTitleSizes"], content_width,
                                spec["postTitleMaxLines"])
    else:
        style, lines = fit_text(config, "name", text, spec["nameSizes"], content_width,
                                spec["nameMaxLines"])

    band_top = height - padding - block_height(lines, style)
    draw_block(draw, padding, band_top, lines, style)

    if kind == "post":
        label = make_style(config, "label", spec["labelSize"])
        band_top -= spec["labelGap"] + cap_height(label)
        draw_block(draw, padding, band_top, [label.prepare(labels["tangentsLabel"])], label)

    _draw_rule(draw, config, padding, band_top - spec["ruleGap"] - spec["ruleWidth"],
               content_width, spec["ruleWidth"])


# ------------------------------------------------------------------------------------
# Resolution and generation

def demo_card_rel(folder: str) -> str:
    """Repo-relative path of a demo page's generated card."""
    return f"demo/{folder}/{generated_name(folder)}"


def existing_card(card_rel: str | None) -> str | None:
    """The page's own card if it is on disk, else the frontpage card, else None."""
    for rel in (card_rel, FRONTPAGE_CARD_REL):
        if rel and os.path.isfile(os.path.join(ROOT_DIR, rel.replace("/", os.sep))):
            return rel
    return None


def _process_auto_target(rel_path: str, kind: str, text: str, gen_hash: str, prev_images: dict,
                         new_images: dict, result: dict, force: bool) -> None:
    """Skip or render one auto-generated card, updating the manifest and result."""
    abs_path = os.path.join(ROOT_DIR, rel_path.replace("/", os.sep))
    inputs_hash = _inputs_hash(kind, text)

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
    data = render_card(kind, text)
    existing = _read_bytes(abs_path, required=False) if os.path.isfile(abs_path) else None
    if existing != data:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)
        # Drop any stale cached bytes for this path so a later read sees the new file.
        _BYTES_CACHE.pop(abs_path, None)
    result["generated"].append(rel_path)
    print(f"  Generated: {rel_path}")


def resolve_and_generate(posts, force=False, prune=True, demos=()):
    """Resolve every post's social image and generate what is missing or stale.

    posts: [{"slug": str, "title": str, "socialImage": str_or_None}, ...]
           (non-draft posts only; the caller filters).
    demos: [{"folder": str, "title": str}, ...], the title as the demo page shows
           it (update_website.social_card_demos); rendered on full runs only.
    force: regenerate even when the manifest says up to date.
    prune: drop manifest entries not touched this run. True marks a full run
           (update_website.py, and the CLI with no slug filter): the generic,
           frontpage, and demo cards are processed and untouched entries are
           dropped. False marks a
           slug-filtered CLI run: only the named posts are touched and every
           other manifest entry survives.

    Returns a dict with og_image (slug -> repo-relative POSIX path), index_card,
    and the generated / skipped / custom / warnings lists.

    Raises SocialImageError on a malformed or reserved-name socialImage value, a
    demo without a title, a missing logo/font asset, or a needed render with
    Pillow unavailable.
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
    config = load_card_config()

    for post in posts:
        slug = post["slug"]
        title = post["title"]
        social_image = post.get("socialImage")
        reserved = generated_name(slug)
        auto_rel = f"tangents/{slug}/{reserved}"

        if social_image and social_image != "auto":
            if not SOCIAL_IMAGE_RE.fullmatch(social_image):
                raise SocialImageError(
                    f"tangents/{slug}: socialImage {social_image!r} must be a bare "
                    f"filename inside tangents/{slug}/ using only letters, digits, "
                    f"'-', '_', and '.', not starting with '.'"
                )
            # Case-insensitive filesystems treat mypost-Social.png as the card itself.
            if social_image.lower() == reserved.lower():
                raise SocialImageError(
                    f"tangents/{slug}: socialImage {social_image!r} uses the reserved "
                    f"generated-card name; rename the custom file or drop the key"
                )
            custom_rel = f"tangents/{slug}/{social_image}"
            post_dir = os.path.join(ROOT_DIR, "tangents", slug)
            # An exact listing match, as isfile ignores case on the Windows-backed mount and Pages does not.
            if os.path.isdir(post_dir) and social_image in os.listdir(post_dir):
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
        title = _drawable_title(config, f"tangents/{slug}", title, result["warnings"])
        _process_auto_target(auto_rel, "post", title, gen_hash, prev_images, new_images,
                             result, force)

    # The site-wide cards are a full-run concern only; a slug-filtered run leaves
    # them (and their surviving manifest entries) alone.
    if prune:
        _process_auto_target(INDEX_CARD_REL, "tangents", "", gen_hash, prev_images, new_images,
                             result, force)
        _process_auto_target(FRONTPAGE_CARD_REL, "frontpage", "", gen_hash, prev_images,
                             new_images, result, force)
        for demo in demos:
            if not demo["title"].strip():
                raise SocialImageError(f"demo/{demo['folder']}: a demo page needs a title for its social card")
            title = _drawable_title(config, f"demo/{demo['folder']}", demo["title"], result["warnings"])
            _process_auto_target(demo_card_rel(demo["folder"]), "demo", title, gen_hash,
                                 prev_images, new_images, result, force)

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
    import update_website

    posts = []
    if not os.path.isdir(TANGENTS_SRC_DIR):
        return posts
    for filename in sorted(os.listdir(TANGENTS_SRC_DIR)):
        if not filename.endswith(".md"):
            continue
        slug = filename[:-3]
        # The slug becomes the card's output directory, so it gets the site build's check.
        if not update_website.TANGENT_SLUG_RE.match(slug):
            raise ValueError(
                f"tangents: invalid slug {slug!r} (must be lowercase kebab-case [a-z0-9-]+, not all digits)"
            )
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
            "slug": slug,
            "title": title,
            "socialImage": front.get("socialImage"),
        })
    return posts


def _load_demos_from_disk() -> list[dict]:
    """Card inputs for every hosted demo, read the way the site build reads them."""
    import update_website

    _, demos_by_stem = update_website.load_demo_data()
    return update_website.social_card_demos(demos_by_stem)


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

    demos = [] if slugs else _load_demos_from_disk()
    result = resolve_and_generate(posts, force=force, prune=not slugs, demos=demos)

    for warning in result["warnings"]:
        print(f"  WARNING: {warning}")

    print(
        f"\n  {len(result['generated'])} generated, "
        f"{len(result['skipped'])} up to date, "
        f"{len(result['custom'])} custom."
    )


if __name__ == "__main__":
    main()
