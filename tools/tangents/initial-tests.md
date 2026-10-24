---
title: Tangents: initial tests
summary: A thorough test of the markdown features, behaviour and layout cases for Tangents, and some other unsupported cases.
tags: Test, Website
published:
updated:
featureImage: pixel-art.png
featureImageAlt: Pixel art of a construction sign
---

[[callout title="Note"]]
This is a test page for Tangents, my site's new writing section.

This is the first set of tests. This page is used to try out the features, see what works, check how everything looks, and decide what's missing, etc.

Nothing on this page is meant to be read as real content. These are just tests.
[[/callout]]

This post is a thorough set of tests for the Tangents markdown engine: the features it supports, how it behaves, and how the layout holds up, along with some cases it does not support. Each section says what it tests and what should happen, so a broken result is easy to spot.

This second paragraph is written across
several source lines
to check that they join into one paragraph with single spaces between them.

# A level-one heading in the body

The heading above was written with a single `#`. It should render as an `h2`, because the post title is the only `h1`, and the build should log a warning about it.

## Headings

### Level three heading

#### Level four heading

##### Level five heading

###### Level six heading

####### Seven hashes is not a heading and should stay a plain paragraph.

## Inline formatting

Plain text, **bold text**, *italic with stars*, _italic with underscores_, ***bold and italic***, and `inline code`.

Formatting inside a word: un**believ**able and in*cred*ible.

Underscores inside words stay literal: `snake_case` in code, and snake_case_name, __init__ and file_name_here as plain text.

Asterisks inside code stay literal: `a * b * c` and `**not bold**`.

Unbalanced markers should survive as text: a lone * star, a lone ** pair, and a lone _ underscore.

Characters that must be escaped: 5 < 6 > 4, Tom & Jerry, "double quotes", 'single quotes', and a raw tag <b>this should not be bold</b> that should show as literal text.

HTML entities written by hand: &copy; and &amp; should show as typed, not as symbols.

Unicode: ääkköset ÄÄKKÖSET, Hämäläinen, Räikkönen, Müller, Ørsted, Þór, naïve café, 日本語, Ελληνικά, and the arrows ← → ↑ ↓.

A very long word to test wrapping on narrow screens: Pneumonoultramicroscopicsilicovolcanoconiosis-plus-some-extra-characters-for-good-measure.

A very long URL as plain text: https://www.example.com/a/very/long/path/that/keeps/going/and/going/without/any/spaces/to/break/on/index.html

## Line breaks

A line ending in a backslash breaks the line here,\
so this sentence starts on a new line inside the same paragraph,\
and so does this one.

A backslash at the very end of a paragraph has no line to break to and stays visible as text.\

A `[[break]]` directive on its own line adds an empty line between two paragraphs. One follows this paragraph.

[[break]]

This paragraph sits one empty line further down than usual. Two directives in a row follow it, for a larger gap.

[[break]]
[[break]]

This paragraph sits two empty lines further down. Extra blank lines in the source, like the three below, collapse and add no space.



This paragraph sits at the normal distance.

## Links

- External: [Solar2D](https://solar2d.com)
- Plain http: [Example over http](http://example.com)
- Underscores and asterisks in the URL: [Lua manual](https://www.lua.org/manual/5.1/manual.html#pdf-string_format_test*star)
- Email: [Send an email](mailto:example@example.com)
- Root-relative: [The demos page](/demo/)
- Relative: [Back to the Tangents index](../)
- Formatted link text: [**bold link** with *italic* and `code`](https://www.xedur.com)
- Disallowed scheme, should show as plain text: [click me](javascript:alert(1))
- Bare URL, which the engine does not autolink: https://www.xedur.com

## Unordered lists

- First item written with a hyphen
- Second item with **bold**, *italic*, and `code`
- Third item that is long enough to wrap onto a second line on most screens, so the hanging indent and the line height of wrapped list items can be checked properly.

* First item written with an asterisk
* Second item written with an asterisk

## Ordered lists

1. First step
2. Second step with a [link](https://www.xedur.com)
3. Third step

Numbers are ignored and the list always counts from one:

5. Written as five
9. Written as nine
1. Written as one

A list with ten or more items, to check how two-digit markers align:

1. One
2. Two
3. Three
4. Four
5. Five
6. Six
7. Seven
8. Eight
9. Nine
10. Ten
11. Eleven

## Blockquotes

> A single-line blockquote.

> A blockquote written across
> several source lines, with **bold**, *italic*, `code`, and a [link](https://www.xedur.com),
> which should all join into one paragraph.

> Two blockquotes in a row separated by a blank line.

> This is the second one.

## Callouts

A callout with a custom title and a single paragraph:

[[callout title="Gotcha!"]]
Display objects removed with `display.remove()` still hold their Lua table, so set the reference to `nil` as well.
[[/callout]]

A callout whose title carries inline formatting, with several paragraphs, a list, and a code block inside:

[[callout title="Heads up: `require` caching"]]
A module is loaded **once** and cached, so a second `require` returns the same table.

Two consequences:

- Edits to the file need a restart to show up.
- State stored in the module is shared by every caller.

```lua
local a = require( "settings" )
local b = require( "settings" )
print( a == b ) -- true
```
[[/callout]]

A callout with no title:

[[callout]]
A callout without a title is just the box and its body.
[[/callout]]

A callout nested inside another, plus a closing line inside a code block that must not end the callout early:

[[callout title="IMPORTANT!"]]
The outer callout starts here.

[[callout title="Nested"]]
The inner callout sits inside the outer one.
[[/callout]]

```
[[/callout]]
```

The outer callout ends after this paragraph.
[[/callout]]

## Horizontal rule

Text above the rule.

---

Text below the rule. A longer rule written with more dashes follows.

----------

## Code blocks

A Lua block:

```lua
local function greet( name )
	print( "Hello, " .. name .. "!" )
end

local enemies = { "slime", "bat", "ghost" }
for _, enemy in ipairs( enemies ) do
	greet( enemy )
end
```

A Python block:

```python
def fizzbuzz(limit: int) -> list[str]:
    return ["FizzBuzz" if n % 15 == 0 else "Fizz" if n % 3 == 0 else "Buzz" if n % 5 == 0 else str(n) for n in range(1, limit + 1)]
```

A block with no language, holding HTML and markdown that must stay literal:

```
<script>alert("this must not run")</script>
<b>not bold</b> &amp; not an entity
**not bold** *not italic* [not a link](https://www.xedur.com)
[[youtube id="dQw4w9WgXcQ"]]
# not a heading
- not a list
```

A block with a very long line, to test horizontal scrolling:

```lua
local thisIsAVeryLongVariableNameThatKeepsGoing = someFunctionWithAVeryLongName( firstArgument, secondArgument, thirdArgument, fourthArgument, fifthArgument )
```

## Images

A wide 1200x630 screenshot with alt text and a caption:

[[image src="wide-screenshot.jpg" alt="Screenshot of The Dark" caption="A wide screenshot with a caption."]]

A square transparent PNG forced to 128x128 with width and height:

[[image src="square-logo.png" alt="The XeduR logo" width="128" height="128" caption="Forced to 128 by 128."]]

A pixel-art image at its natural 512x512 size with no caption:

[[image src="pixel-art.png" alt="Pixel art of a construction sign"]]

An image with no alt text, which should log a build warning:

[[image src="square-logo.png" width="64" height="64"]]

A local image that does not exist, which should log a build warning and show an "image unavailable" panel with its alt text:

[[image src="does-not-exist.png" alt="A local file that is not there" caption="A missing local image."]]

A remote image that returns 404, which should show the same panel:

[[image src="https://www.xedur.com/img/does-not-exist.png" alt="A remote file that is not there" caption="A missing remote image."]]

An image loaded by absolute URL from the live site:

[[image src="https://www.xedur.com/img/xedur.png" alt="The XeduR logo from the live site" width="96" height="96" caption="Loaded by absolute URL."]]

## Videos

A 16:9 video:

[[youtube id="dQw4w9WgXcQ" title="Rick Astley - Never Gonna Give You Up"]]

A 4:3 video, to see how a different aspect ratio fits the 16:9 frame. Accepting either video should load both, and the choice should be remembered on reload:

[[youtube id="jNQXAC9IVRw" title="Me at the zoo"]]

## Repository panels

A repository by owner and name:

[[github repo="XeduR/Solar2D-Projects"]]

A repository by full URL:

[[github url="https://github.com/XeduR/Solar2D-Projects/tree/master/autotile"]]

A private repository, with no URL:

[[github]]

## Unsupported syntax

Everything below is outside what the engine supports and should render as plain text or in some degraded but readable form.

Nested lists, where the indented items should flatten into the same list:

- Parent item
  - Child item
  - Another child item
- Second parent item

A table:

| Column A | Column B |
|----------|----------|
| One | Two |

Strikethrough: ~~this is not struck through~~.

Standard markdown image syntax: ![alt text](square-logo.png)

Task list items:

- [ ] Not a checkbox
- [x] Not a checked checkbox

A footnote reference[^1] and its definition:

[^1]: This is not a footnote.

Backslash escapes: \*not italic\* and \_not italic\_.

A setext heading, whose `=` underline stays plain text:

Not a heading
=============

Heading anchors: [jump to the code blocks](#code-blocks) renders as a link, but headings get no ids, so it goes nowhere.

That is the end of the tests.
