"""
Standalone markdown engine for www.xedur.com.

Dependency-free (Python 3.9+ stdlib only) so update_website.py can `import
markdown_engine` without any path changes.  Kept decoupled from site specifics
(no site URLs, no template knowledge) so it can be reused elsewhere; the caller
passes in what it needs.

The block parser is a flat, line-oriented state machine.  Nested lists, lists
inside blockquotes, and multi-paragraph list items are intentionally out of
scope: post content is prose, images, videos, and simple lists.
"""

import re
from datetime import date


class MarkdownError(Exception):
    """Raised on an unknown directive or a malformed directive line."""


class FrontMatterError(MarkdownError):
    """Raised on malformed front matter."""


# ------------------------------------------------------------------------------------
# Escaping helpers

def _escape_html(text):
    """Escape the characters that matter in HTML text and double-quoted attributes.

    Done before any markup is generated so authored text can neither inject raw
    HTML nor break out of a generated attribute.
    """
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def _escape_code(text):
    """Escape a code span/block: quotes stay literal inside code."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _normalize_input(text):
    """Normalize CR/CRLF newlines to LF and strip NUL bytes.

    Newline normalization keeps raw-line handling (code fences) from carrying a
    stray CR into the output.  NUL is the module's internal placeholder
    sentinel, so a literal NUL in the input is removed to keep it from colliding
    with that scheme (which would otherwise raise on a bogus token index).
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\x00", "")


# ------------------------------------------------------------------------------------
# Front matter

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _coerce_front_matter_value(key, value, source):
    """Apply the built-in typed coercions; unknown keys stay trimmed strings."""
    if key == "tags":
        return [item.strip() for item in value.split(",") if item.strip()]

    if key == "draft":
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise FrontMatterError(f"{source}: 'draft' must be true or false, got {value!r}")

    if key == "published":
        if not _DATE_RE.match(value):
            raise FrontMatterError(
                f"{source}: 'published' must be YYYY-MM-DD, got {value!r}"
            )
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise FrontMatterError(
                f"{source}: 'published' is not a real date: {value!r}"
            )

    return value


def parse_front_matter(text: str, *, source: str = "<string>") -> tuple[dict, str]:
    """Return (front_matter_dict, body_text). Raises FrontMatterError on
    malformed input. `source` is used only in error messages."""
    text = _normalize_input(text)

    # Drop an optional leading UTF-8 BOM.
    if text.startswith("\ufeff"):
        text = text[1:]

    lines = text.split("\n")

    # Skip optional blank leading lines, then require an opening '---' fence.
    index = 0
    while index < len(lines) and lines[index].strip() == "":
        index += 1

    if index >= len(lines) or lines[index].strip() != "---":
        raise FrontMatterError(
            f"{source}: front matter must begin with a line containing only '---'"
        )
    index += 1

    front = {}
    closed = False
    while index < len(lines):
        line = lines[index]
        index += 1

        if line.strip() == "---":
            closed = True
            break
        if line.strip() == "":
            continue  # Blank lines inside front matter are ignored.
        if ":" not in line:
            raise FrontMatterError(
                f"{source}: front-matter line has no ':' -> {line!r}"
            )

        key, value = line.split(":", 1)
        front[key.strip()] = _coerce_front_matter_value(key.strip(), value.strip(), source)

    if not closed:
        raise FrontMatterError(f"{source}: front matter is missing its closing '---'")

    # The body is everything after the closing fence; the single newline that
    # follows the fence is consumed by the split.
    body = "\n".join(lines[index:])
    return front, body


# ------------------------------------------------------------------------------------
# Inline parser

_INLINE_CODE_RE = re.compile(r'`([^`]+)`')
_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_STAR_RE = re.compile(r'\*(.+?)\*')
_ITALIC_UNDERSCORE_RE = re.compile(r'_(.+?)_')
_LINK_TOKEN_RE = re.compile(r'\[([^\]]+)\]\(\x00URL(\d+)\x00\)')
_CODE_TOKEN_RE = re.compile(r'\x00CODE(\d+)\x00')


def inline(text):
    """Transform one logical line of markdown into inline HTML.

    Order is load-bearing: HTML-escape, protect inline code, tokenize link URLs,
    bold, italic, assemble links, restore code.  Escaping first blocks raw HTML;
    tokenizing only the URL part shields the '_'/'*' that URLs routinely contain
    while keeping link text visible to the emphasis rules.
    """
    text = _escape_html(text)

    code_tokens = []

    def _store_code(match):
        code_tokens.append(f'<code>{match.group(1)}</code>')
        return f'\x00CODE{len(code_tokens) - 1}\x00'

    text = _INLINE_CODE_RE.sub(_store_code, text)

    url_tokens = []

    def _store_url(match):
        url_tokens.append(match.group(2))
        return f'[{match.group(1)}](\x00URL{len(url_tokens) - 1}\x00)'

    text = _LINK_RE.sub(_store_url, text)

    # Bold before italic so **x** is not eaten by the single-* rule.
    text = _BOLD_RE.sub(r'<strong>\1</strong>', text)
    text = _ITALIC_STAR_RE.sub(r'<em>\1</em>', text)
    text = _ITALIC_UNDERSCORE_RE.sub(r'<em>\1</em>', text)

    def _assemble_link(match):
        url = url_tokens[int(match.group(2))]
        return f'<a href="{url}">{match.group(1)}</a>'

    text = _LINK_TOKEN_RE.sub(_assemble_link, text)

    def _restore_code(match):
        return code_tokens[int(match.group(1))]

    return _CODE_TOKEN_RE.sub(_restore_code, text)


# ------------------------------------------------------------------------------------
# Directives

def _directive_image(params, meta, base_path):
    src = params.get("src")
    if src is None:
        raise MarkdownError("directive 'image' requires a 'src' parameter")

    alt = params.get("alt")
    if alt is None:
        meta["warnings"].append(f"image directive missing 'alt' (src={src!r})")
        alt = ""

    # src is used verbatim: the author controls the path, so base_path is not
    # prefixed here.
    meta["images"].append(src)

    width = params.get("width")
    height = params.get("height")
    width_attr = f' width="{width}"' if width else ""
    height_attr = f' height="{height}"' if height else ""

    lines = ['<figure class="md-figure">']
    lines.append(
        f'    <img src="{src}" alt="{_escape_html(alt)}" loading="lazy"{width_attr}{height_attr}>'
    )
    caption = params.get("caption")
    if caption is not None:
        lines.append(f'    <figcaption>{_escape_html(caption)}</figcaption>')
    lines.append("</figure>")
    return "\n".join(lines)


def _directive_youtube(params, meta, base_path):
    video_id = params.get("id")
    if video_id is None:
        raise MarkdownError("directive 'youtube' requires an 'id' parameter")

    meta["needs_video_js"] = True
    title = _escape_html(params.get("title", ""))

    lines = [
        f'<div class="video-placeholder" data-video-id="{video_id}" data-video-title="{title}">',
        '    <div class="overlay">',
        "        <p>We don't use cookies, but YouTube does. To watch this video, you accept that YouTube may set cookies on your device.</p>",
        '        <button type="button" class="video-consent">I accept</button>',
        "    </div>",
        "</div>",
    ]
    return "\n".join(lines)


# Built-in directives stay site-agnostic.  Site-coupled ones (github, and later
# solar2d) are added by the caller via register_directive.
DIRECTIVES = {
    "image": _directive_image,
    "youtube": _directive_youtube,
}


def register_directive(name, handler):
    """Register a directive handler `handler(params, meta, base_path) -> str`.

    Lets the site wire in directives that need its templates (e.g. github)
    without coupling the engine to them.  A later registration overrides an
    earlier one.
    """
    DIRECTIVES[name] = handler


# ------------------------------------------------------------------------------------
# Directive dispatch

_DIRECTIVE_NAME_RE = re.compile(r'^\[\[([a-z][a-z0-9_-]*)\s*(.*)\]\]$')
_DIRECTIVE_PARAM_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _parse_directive_params(params_str, name):
    """Parse key="value" pairs into a dict; duplicate keys keep the last value."""
    if params_str == "":
        return {}

    pairs = _DIRECTIVE_PARAM_RE.findall(params_str)
    if not pairs:
        # Text present but no valid pairs: a typo worth surfacing loudly.
        raise MarkdownError(
            f"directive '{name}' has a malformed parameter section: {params_str!r}"
        )

    params = {}
    for key, value in pairs:
        params[key] = value
    return params


def _render_directive(line, meta, base_path):
    match = _DIRECTIVE_NAME_RE.match(line)
    if not match:
        # Starts with [[ and ends with ]] but fails the name pattern (e.g. a
        # capital letter): raise rather than silently render it as literal text.
        raise MarkdownError(f"malformed directive: {line!r}")

    name = match.group(1)
    handler = DIRECTIVES.get(name)
    if handler is None:
        raise MarkdownError(f"unknown directive: {name!r}")

    params = _parse_directive_params(match.group(2).strip(), name)
    return handler(params, meta, base_path)


# ------------------------------------------------------------------------------------
# Block parser

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_HR_RE = re.compile(r'^-{3,}$')
_BLOCKQUOTE_RE = re.compile(r'^>\s?(.*)$')
_UL_RE = re.compile(r'^[-*]\s+(.*)$')
_OL_RE = re.compile(r'^\d+\.\s+(.*)$')
_FENCE_LANG_RE = re.compile(r'[A-Za-z0-9+\-_]+')


def _fence_language(stripped):
    """Return the language token after the opening ``` fence, or '' if none."""
    match = _FENCE_LANG_RE.match(stripped[3:].strip())
    return match.group(0) if match else ""


def render_markdown(body: str, *, base_path: str = "") -> tuple[str, dict]:
    """Return (html, meta). meta collects flags like {'needs_video_js': bool,
    'needs_demo_js': bool, 'images': [src, ...]}. base_path is prefixed to
    directive-generated internal asset URLs when a directive opts in (see
    each directive). Raises MarkdownError on an unknown directive or malformed
    directive line."""
    body = _normalize_input(body)

    meta = {
        "needs_video_js": False,
        "needs_demo_js": False,
        "images": [],
        "warnings": [],
    }

    output = []
    block = None       # None | 'p' | 'ul' | 'ol' | 'blockquote'
    accum = []         # p/blockquote: raw text lines; ul/ol: item text
    in_code = False

    def flush():
        nonlocal block, accum
        if block == "p":
            output.append(f"<p>{inline(' '.join(accum))}</p>")
        elif block == "blockquote":
            output.append(f"<blockquote><p>{inline(' '.join(accum))}</p></blockquote>")
        elif block in ("ul", "ol"):
            items = "\n".join(f"<li>{inline(item)}</li>" for item in accum)
            output.append(f"<{block}>\n{items}\n</{block}>")
        block = None
        accum = []

    for raw_line in body.split("\n"):
        stripped = raw_line.strip()

        # 1. Code fence toggle (checked in both directions before the body rule).
        if stripped.startswith("```"):
            if not in_code:
                flush()
                in_code = True
                lang = _fence_language(stripped)
                if lang:
                    output.append(f'<pre><code class="language-{lang}">')
                else:
                    output.append("<pre><code>")
            else:
                output.append("</code></pre>")
                in_code = False
            continue

        # 2. Inside a code block: raw line escaped verbatim, no other processing.
        if in_code:
            output.append(_escape_code(raw_line))
            continue

        # 3. Directive on its own line.
        if stripped.startswith("[[") and stripped.endswith("]]"):
            flush()
            output.append(_render_directive(stripped, meta, base_path))
            continue

        # 4. Blank line closes the open block.
        if stripped == "":
            flush()
            continue

        # 5. Heading.
        heading = _HEADING_RE.match(stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            if level == 1:
                level = 2
                meta["warnings"].append(
                    "body '# ' heading demoted to h2; the page title is the sole h1"
                )
            output.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        # 6. Horizontal rule (safe: front matter, which also uses ---, is gone).
        if _HR_RE.match(stripped):
            flush()
            output.append("<hr>")
            continue

        # 7. Blockquote.
        blockquote = _BLOCKQUOTE_RE.match(stripped)
        if blockquote:
            if block != "blockquote":
                flush()
                block = "blockquote"
            accum.append(blockquote.group(1))
            continue

        # 8. Unordered list item.
        unordered = _UL_RE.match(stripped)
        if unordered:
            if block != "ul":
                flush()
                block = "ul"
            accum.append(unordered.group(1))
            continue

        # 9. Ordered list item.
        ordered = _OL_RE.match(stripped)
        if ordered:
            if block != "ol":
                flush()
                block = "ol"
            accum.append(ordered.group(1))
            continue

        # 10. Plain text joins into the current paragraph.
        if block != "p":
            flush()
            block = "p"
        accum.append(stripped)

    if in_code:
        output.append("</code></pre>")
        meta["warnings"].append("code fence left open at end of input; closed automatically")

    flush()
    return "\n".join(output), meta
