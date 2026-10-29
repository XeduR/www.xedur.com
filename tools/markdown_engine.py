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
    return _escape_code(text).replace('"', "&quot;")


def _escape_code(text):
    """Escape a code span/block: quotes stay literal inside code."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # The caller fills {{placeholders}} after splicing in this output, so authored text must never match one.
    return text.replace("{{", "&#123;&#123;")


_SAFE_URL_SCHEMES = ("http", "https", "mailto")
_URL_STRIP_CHARS = "".join(chr(code) for code in range(0x21))


def is_safe_url(url):
    """True for http, https, mailto, relative, and '#' anchor URLs.

    Browsers ignore ASCII whitespace and control characters inside a scheme, so
    the check drops them too before reading it.
    """
    cleaned = "".join(ch for ch in url if ch not in _URL_STRIP_CHARS)
    for ch in cleaned:
        if ch in "/?#":
            return True
        if ch == ":":
            scheme = cleaned.split(":", 1)[0].lower()
            return scheme in _SAFE_URL_SCHEMES
    return True


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

    if key in ("published", "updated"):
        if not _DATE_RE.match(value):
            raise FrontMatterError(
                f"{source}: '{key}' must be YYYY-MM-DD, got {value!r}"
            )
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise FrontMatterError(
                f"{source}: '{key}' is not a real date: {value!r}"
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
        if value.strip() == "":
            continue  # A blank value leaves the key unset, so templates can list every key.
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
# The URL may hold one level of balanced parentheses, as Wikipedia and MDN URLs do.
# It runs on escaped text, so a double-quoted title is delimited by &quot;.
# The URL holds no whitespace, so only the title alternatives can follow it and matching stays linear.
_LINK_RE = re.compile(
    r'\[([^\]]+)\]\('
    r'(((?:[^()\s]|\([^()]*\))+)'
    r'(?:\s+(?:&quot;(.*?)&quot;|\'([^\']*)\'))?)'
    r'\s*\)'
)
_BOLD_ITALIC_RE = re.compile(r'\*\*\*(.+?)\*\*\*')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_STAR_RE = re.compile(r'\*(.+?)\*')
# Word boundaries keep the underscores in snake_case names literal.
_ITALIC_UNDERSCORE_RE = re.compile(r'(?<!\w)_(.+?)_(?!\w)')
_YOUTUBE_ID_RE = re.compile(r'[A-Za-z0-9_-]{11}')
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
    code_literals = []

    def _store_code(match):
        code_tokens.append(f'<code>{match.group(1)}</code>')
        code_literals.append(match.group(0))
        return f'\x00CODE{len(code_tokens) - 1}\x00'

    text = _INLINE_CODE_RE.sub(_store_code, text)

    url_tokens = []

    def _store_url(match):
        title = match.group(4) if match.group(4) is not None else match.group(5)
        url_tokens.append((match.group(3), title, match.group(2)))
        return f'[{match.group(1)}](\x00URL{len(url_tokens) - 1}\x00)'

    text = _LINK_RE.sub(_store_url, text)

    # Bold before italic so **x** is not eaten by the single-* rule, and the
    # triple form before both so ***x*** nests correctly.
    text = _BOLD_ITALIC_RE.sub(r'<strong><em>\1</em></strong>', text)
    text = _BOLD_RE.sub(r'<strong>\1</strong>', text)
    text = _ITALIC_STAR_RE.sub(r'<em>\1</em>', text)
    text = _ITALIC_UNDERSCORE_RE.sub(r'<em>\1</em>', text)

    def _assemble_link(match):
        url, title, inner = url_tokens[int(match.group(2))]
        if not is_safe_url(url):
            # A disallowed scheme stays visible as plain text so the author spots it.
            return f'[{match.group(1)}]({inner})'
        # An attribute cannot hold markup, so code spans in a title stay as written.
        title = _CODE_TOKEN_RE.sub(lambda code: code_literals[int(code.group(1))], title or "")
        title_attr = f' title="{title}"' if title else ""
        return f'<a href="{url}"{title_attr}>{match.group(1)}</a>'

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
    if not is_safe_url(src):
        raise MarkdownError(f"directive 'image' has a disallowed URL scheme: src={src!r}")

    alt = params.get("alt")
    if alt is None:
        meta["warnings"].append(f"image directive missing 'alt' (src={src!r})")
        alt = ""

    # src is used verbatim: the author controls the path, so base_path is not
    # prefixed here.
    meta["images"].append(src)

    width = params.get("width")
    height = params.get("height")
    if not width and not height and meta["image_size"]:
        size = meta["image_size"](src)
        if size:
            width, height = (str(length) for length in size)
    width_attr = f' width="{_escape_html(width)}"' if width else ""
    height_attr = f' height="{_escape_html(height)}"' if height else ""

    lines = ['<figure class="md-figure">']
    lines.append(
        f'    <img src="{_escape_html(src)}" alt="{_escape_html(alt)}" loading="lazy"{width_attr}{height_attr}>'
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
    if not _YOUTUBE_ID_RE.fullmatch(video_id):
        raise MarkdownError(f"directive 'youtube' id must be an 11-character YouTube id, got {video_id!r}")

    meta["needs_video_js"] = True
    title = _escape_html(params.get("title", ""))

    lines = [
        f'<div class="video-placeholder" data-video-id="{_escape_html(video_id)}" data-video-title="{title}">',
        '    <div class="overlay">',
        "        <p>We don't use cookies, but YouTube does. To watch this video, you accept that YouTube may set cookies on your device.</p>",
        '        <button type="button" class="video-consent">I accept</button>',
        "    </div>",
        "</div>",
    ]
    return "\n".join(lines)


def _directive_break(params, meta, base_path):
    return "<br>"


# Built-in directives stay site-agnostic.  Site-coupled ones (github, and later
# solar2d) are added by the caller via register_directive.  Each entry is
# (handler, accepted parameter keys).
DIRECTIVES = {
    "break": (_directive_break, ()),
    "image": (_directive_image, ("src", "alt", "caption", "width", "height")),
    "youtube": (_directive_youtube, ("id", "title")),
}

_CALLOUT_KEYS = ("title",)


def register_directive(name, handler, keys):
    """Register a directive handler `handler(params, meta, base_path) -> str`
    that accepts the parameter names in `keys`.

    Lets the site wire in directives that need its templates (e.g. github)
    without coupling the engine to them.  A later registration overrides an
    earlier one.
    """
    DIRECTIVES[name] = (handler, tuple(keys))


# ------------------------------------------------------------------------------------
# Directive dispatch

_DIRECTIVE_NAME_RE = re.compile(r'^\[\[([a-z][a-z0-9_-]*)\s*(.*)\]\]$')
_DIRECTIVE_PARAM_RE = re.compile(r'\s*(\w+)\s*=\s*"([^"]*)"')


def _parse_directive_params(params_str, name, keys):
    """Parse key="value" pairs into a dict; duplicate keys keep the last value.

    Every character must belong to a pair and every key must be one of `keys`,
    so a typo stops the build instead of silently dropping a value.
    """
    params = {}
    position = 0
    while position < len(params_str):
        match = _DIRECTIVE_PARAM_RE.match(params_str, position)
        if not match:
            raise MarkdownError(
                f"directive '{name}' has a malformed parameter: {params_str[position:].strip()!r}"
            )

        key = match.group(1)
        if key not in keys:
            accepted = ", ".join(keys) or "none"
            raise MarkdownError(
                f"directive '{name}' has an unknown parameter {key!r} (accepted: {accepted})"
            )

        params[key] = match.group(2)
        position = match.end()
    return params


def _render_directive(line, meta, base_path):
    match = _DIRECTIVE_NAME_RE.match(line)
    if not match:
        # Starts with [[ and ends with ]] but fails the name pattern (e.g. a
        # capital letter): raise rather than silently render it as literal text.
        raise MarkdownError(f"malformed directive: {line!r}")

    name = match.group(1)
    if name not in DIRECTIVES:
        raise MarkdownError(f"unknown directive: {name!r}")

    handler, keys = DIRECTIVES[name]
    params = _parse_directive_params(match.group(2).strip(), name, keys)
    return handler(params, meta, base_path)


# ------------------------------------------------------------------------------------
# Block parser

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
_HR_RE = re.compile(r'^-{3,}$')
_BLOCKQUOTE_RE = re.compile(r'^>\s?(.*)$')
_UL_RE = re.compile(r'^[-*]\s+(.*)$')
_OL_RE = re.compile(r'^(\d+)\.\s+(.*)$')
_FENCE_LANG_RE = re.compile(r'[A-Za-z0-9+\-_]+')


def _fence_language(stripped):
    """Return the language token after the opening backtick fence, or '' if none."""
    match = _FENCE_LANG_RE.match(stripped.lstrip("`").strip())
    return match.group(0) if match else ""


def _fence_length(stripped):
    """Return the backtick count of a line that opens a code fence, or 0."""
    length = len(stripped) - len(stripped.lstrip("`"))
    return length if length >= 3 else 0


def _closes_fence(stripped, open_length):
    """True for a line of only backticks, at least as many as the opening fence."""
    return len(stripped) >= open_length and stripped == "`" * len(stripped)


_HARD_BREAK = "\x00BR\x00"
_CALLOUT_CLOSE = "[[/callout]]"


def _inline_lines(lines):
    """Join paragraph lines with spaces, turning a trailing backslash into a hard line break.

    A backslash on the last line stays literal, as in CommonMark, because there
    is no following line to break to.
    """
    joined = ""
    for line in lines[:-1]:
        if line.endswith("\\"):
            joined += line[:-1].rstrip() + _HARD_BREAK
        else:
            joined += line + " "
    joined += lines[-1]
    return inline(joined).replace(_HARD_BREAK, "<br>\n")


def _callout_name(stripped):
    """Return the directive params string if the line opens a callout, else None."""
    match = _DIRECTIVE_NAME_RE.match(stripped)
    if match and match.group(1) == "callout":
        return match.group(2).strip()
    return None


def _render_callout(params_str, lines, meta, base_path):
    params = _parse_directive_params(params_str, "callout", _CALLOUT_KEYS)
    parts = ['<div class="md-callout" role="note">']
    title = params.get("title")
    if title:
        parts.append(f'<p class="md-callout-title">{inline(title)}</p>')
    body_html = _render_blocks(lines, meta, base_path)
    if body_html:
        parts.append(body_html)
    parts.append("</div>")
    return "\n".join(parts)


def render_markdown(body: str, *, base_path: str = "", image_size=None) -> tuple[str, dict]:
    """Return (html, meta). meta collects flags like {'needs_video_js': bool,
    'needs_demo_js': bool, 'images': [src, ...]}. base_path is prefixed to
    directive-generated internal asset URLs when a directive opts in (see
    each directive). image_size(src) -> (width, height) or None supplies the
    size of an image whose author gave neither width nor height. Raises
    MarkdownError on an unknown directive or malformed directive line."""
    body = _normalize_input(body)

    meta = {
        "needs_video_js": False,
        "needs_demo_js": False,
        "images": [],
        "warnings": [],
        "image_size": image_size,
    }

    html = _render_blocks(body.split("\n"), meta, base_path)
    del meta["image_size"]
    return html, meta


def _render_blocks(lines, meta, base_path):
    output = []
    block = None       # None | 'p' | 'ul' | 'ol' | 'blockquote'
    accum = []         # p/blockquote: raw text lines; ul/ol: one list of lines per item
    ol_start = 1
    ol_gap = False     # a blank line sits after the open ordered list's last item
    code_fence = 0     # backtick count of the open code fence, 0 outside code
    code_open = ""
    code_lines = []

    # A callout's body is captured raw and rendered recursively once it closes.
    callout_params = None
    callout_lines = []
    callout_depth = 0
    callout_fence = 0

    def close_code():
        # One output item, so no newline sits between <code> and the first line
        # (only a newline right after <pre> is ignored by browsers).
        output.append(code_open + "\n".join(code_lines) + "</code></pre>")

    def flush():
        nonlocal block, accum, ol_gap
        if block == "p":
            output.append(f"<p>{_inline_lines(accum)}</p>")
        elif block == "blockquote":
            output.append(f"<blockquote><p>{_inline_lines(accum)}</p></blockquote>")
        elif block in ("ul", "ol"):
            items = "\n".join(f"<li>{_inline_lines(item)}</li>" for item in accum)
            start = f' start="{ol_start}"' if block == "ol" and ol_start != 1 else ""
            output.append(f"<{block}{start}>\n{items}\n</{block}>")
        block = None
        accum = []
        ol_gap = False

    for raw_line in lines:
        stripped = raw_line.strip()

        # 0. Inside a callout: collect lines until its own closing line. Fences
        # and nested callouts are tracked so their lines cannot close it early.
        if callout_params is not None:
            if callout_fence:
                if _closes_fence(stripped, callout_fence):
                    callout_fence = 0
            elif _fence_length(stripped):
                callout_fence = _fence_length(stripped)
            elif stripped == _CALLOUT_CLOSE:
                if callout_depth == 0:
                    output.append(_render_callout(callout_params, callout_lines, meta, base_path))
                    callout_params = None
                    continue
                callout_depth -= 1
            elif _callout_name(stripped) is not None:
                callout_depth += 1
            callout_lines.append(raw_line)
            continue

        # 1. Inside a code block: raw line escaped verbatim until a closing fence.
        if code_fence:
            if _closes_fence(stripped, code_fence):
                close_code()
                code_fence = 0
            else:
                code_lines.append(_escape_code(raw_line))
            continue

        # 2. Opening code fence.
        if _fence_length(stripped):
            flush()
            code_fence = _fence_length(stripped)
            lang = _fence_language(stripped)
            # tabindex lets keyboard users scroll a block wider than the page.
            code_open = f'<pre tabindex="0"><code class="language-{lang}">' if lang else '<pre tabindex="0"><code>'
            code_lines = []
            continue

        # 3. Directive on its own line; a callout opens a captured block instead.
        if stripped.startswith("[[") and stripped.endswith("]]"):
            flush()
            if stripped == _CALLOUT_CLOSE:
                raise MarkdownError("'[[/callout]]' has no opening '[[callout]]'")
            params_str = _callout_name(stripped)
            if params_str is not None:
                callout_params = params_str
                callout_lines = []
                callout_depth = 0
                callout_fence = 0
                continue
            output.append(_render_directive(stripped, meta, base_path))
            continue

        # 4. Blank line closes the open block; an ordered list stays open for a following item.
        if stripped == "":
            if block == "ol":
                ol_gap = True
            else:
                flush()
            continue

        if ol_gap and not _OL_RE.match(stripped):
            flush()

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
            accum.append([unordered.group(1)])
            continue

        # 9. Ordered list item; later item numbers are ignored.
        ordered = _OL_RE.match(stripped)
        if ordered:
            if block != "ol":
                flush()
                block = "ol"
                ol_start = int(ordered.group(1))
            ol_gap = False
            accum.append([ordered.group(2)])
            continue

        # 10. An indented line continues a list item and any plain line continues a quote.
        if block in ("ul", "ol") and raw_line[:1] in (" ", "\t"):
            accum[-1].append(stripped)
            continue
        if block == "blockquote":
            accum.append(stripped)
            continue

        # 11. Plain text joins into the current paragraph.
        if block != "p":
            flush()
            block = "p"
        accum.append(stripped)

    if code_fence:
        close_code()
        meta["warnings"].append("code fence left open at end of input; closed automatically")

    flush()

    if callout_params is not None:
        output.append(_render_callout(callout_params, callout_lines, meta, base_path))
        meta["warnings"].append("callout left open at end of input; closed automatically")

    return "\n".join(output)
