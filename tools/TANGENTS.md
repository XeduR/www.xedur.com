# Writing Tangents posts

How to write a post for Tangents (`/tangents/`): the post file, its front matter, and every markdown feature and directive the engine supports, with examples. Demo pages (`tools/demos/<stem>.md`) use the same markdown and directives. How the build turns posts into pages, dates, tag pages, the feed, and social cards is in the repo README's "Tangents (writing system)" section.

## Creating a post

1. Copy `tools/components/templates/new-tangent-post.md` to `tools/tangents/<slug>.md`.
2. Fill in the front matter and write the body below it.
3. Put the post's images in `tangents/<slug>/` (the folder beside the generated page, not in `tools/`).
4. Run `python update_website.py min` from `tools/`.

The file name is the slug and the URL: `tools/tangents/my-post.md` becomes `/tangents/my-post/`. Slugs are lowercase letters, digits, and hyphens only. Renaming the file changes the URL, so retitle a post by editing `title` instead.

## Front matter

Front matter is a block of `key: value` lines between two `---` lines at the top of the file. Values are taken literally: no quotes, and everything after the first colon is the value, so `title: Tangents: initial tests` works. A key left blank counts as unset.

```markdown
---
title: Tangents: initial tests
summary: A thorough test of the markdown features for Tangents.
tags: Test, Website
published:
updated:
featureImage: cover.png
featureImageAlt: Pixel art of a construction sign
socialImage:
draft:
---
```

| Key | Required | What it does |
|-----|----------|--------------|
| `title` | Yes | Post heading, browser title, list and feed title. |
| `summary` | Yes | Blurb on list pages (cut after 160 characters with `...`), search and share description (cut at a word within 160 characters), and the full feed summary. |
| `tags` | No | Comma-separated list. Each tag gets a chip and its own tag page. |
| `published` | No | `YYYY-MM-DD` to set or backdate the publish date. Left blank, the first build sets it to that day. |
| `updated` | No | `YYYY-MM-DD` shown as "Updated:" under "Published:". Left blank, the build uses the day the body last changed. |
| `featureImage` | No | Image above the post body and the thumbnail on list pages. |
| `featureImageAlt` | No | Alt text for the feature image. |
| `socialImage` | No | A custom share image file name in `tangents/<slug>/`. Left blank or `auto`, the build draws a card. |
| `draft` | No | `true` keeps the post out of the build. |

### Rules worth knowing

- "Updated:" shows only when its date is later than the publish date. An `updated` date earlier than `published` stops the build.
- Editing only `title`, `summary`, or `tags` does not count as an update; changing the body does.
- Tags that differ only by case or punctuation (`Solar2D` and `solar2d`) stop the build, because they would share one tag page.
- Tag page addresses keep only the letters a to z and digits, so a tag like `Ääkköset` gets a mangled address. Stick to ASCII tag names.
- `socialImage` takes a bare file name, never a path. 1200x630 is the recommended size.

## Feature image

`featureImage` takes a file name relative to the post (`cover.png` for `tangents/<slug>/cover.png`), a root-relative path (`/img/cover.png`), or a full `https://` URL.

The image is scaled to fit a 16:9 area without cropping or a visible frame, and a horizontal divider separates it from the body. On list pages it becomes a thumbnail that links to the post. If the image cannot load, an "Image unavailable" panel with the alt text takes its place; a missing local file also logs a build warning.

## Text

Paragraphs are separated by a blank line. Lines written next to each other join into one paragraph with a space between them.

```markdown
This is one paragraph,
written across two lines.

This is a second paragraph.
```

Inline formatting:

| Write | Result |
|-------|--------|
| `**bold**` | **bold** |
| `*italic*` or `_italic_` | *italic* |
| `***bold italic***` | ***bold italic*** |
| `` `code` `` | `code` |
| `[link text](https://example.com)` | a link |

- Formatting works inside a word (`un**believ**able`) and inside link text.
- Underscores inside a word stay as they are, so `snake_case_name` needs no escaping.
- Anything inside backticks stays literal: `` `**not bold**` ``.
- HTML tags and entities are shown as typed, never interpreted.

## Line breaks and extra space

End a line with a backslash to start a new line inside the same paragraph:

```markdown
First line,\
second line of the same paragraph.
```

To leave an empty line between two paragraphs, put `[[break]]` on its own line. Repeat it for a bigger gap. Extra blank lines in the source do nothing, so this is the only way to add space.

```markdown
A paragraph.

[[break]]

A paragraph that sits one empty line further down.
```

A backslash on the last line of a paragraph stays visible, because there is no next line to break to.

## Headings

```markdown
## Section
### Subsection
#### Smaller heading
```

Use `##` to `######`. The post title is the page's only top-level heading, so a `#` heading in the body is shown as `##` and logs a build warning.

## Lists

```markdown
- An item
- Another item

1. First step
2. Second step
```

- `*` works as well as `-` for unordered lists.
- Ordered lists always count from 1, whatever numbers you write.
- Nested lists and multi-paragraph items are not supported: indented items join the same flat list.

## Blockquotes

```markdown
> A quote can be written across
> several lines and joins into one paragraph.
```

A blockquote holds one paragraph. Two quotes need a blank line between them and render as two separate quotes.

## Horizontal dividers

A line of three or more hyphens and nothing else draws a divider:

```markdown
---
```

## Code blocks

Put three backticks on the lines before and after the code, with an optional language name after the opening ones:

````markdown
```lua
local function greet( name )
	print( "Hello, " .. name )
end
```
````

Everything inside is shown exactly as written, including indentation, HTML, and markdown. Long lines scroll sideways instead of wrapping.

## Links

Links accept `https://`, `http://`, `mailto:`, root-relative (`/demo/`), relative (`../`), and `#` addresses. Any other scheme, such as `javascript:`, shows the whole link as plain text so the mistake is visible. The same schemes apply to `[[image]]`, `[[github]]`, and `featureImage` addresses, where any other scheme stops the build. Full `http`/`https` addresses get an external-link icon and `mailto:` links an email icon automatically.

A bare address written as text is not turned into a link.

## Directives

Directives add things markdown has no syntax for. Each one sits alone on its own line, with values in double quotes:

```markdown
[[name key="value" other="value"]]
```

A directive name that does not exist, or a malformed value list, stops the build with an error.

### Images

```markdown
[[image src="screenshot.png" alt="What the image shows" caption="Optional caption" width="320" height="180"]]
```

- `src` is required: a file in `tangents/<slug>/`, a root-relative path, or a full URL.
- `alt` describes the image; leaving it out logs a build warning.
- `caption` is optional text under the image.
- `width` and `height` are optional and force the displayed size in pixels; without them the image shows at its own size, shrunk to fit narrow screens.
- A missing image shows the same "Image unavailable" panel as a feature image.

### YouTube videos

```markdown
[[youtube id="dQw4w9WgXcQ" title="Video title"]]
```

- `id` is the 11-character video id from the YouTube address; anything else stops the build.
- `title` is optional.
- The video shows as a thumbnail with a cookie consent button. Accepting loads every video on the page and is remembered on later visits.

### Repository panels

```markdown
[[github repo="XeduR/Solar2D-Projects"]]
[[github url="https://github.com/XeduR/Solar2D-Projects/tree/master/autotile"]]
[[github]]
```

The first two show a panel linking to the repository; the bare form shows a panel saying the source is not public yet, with a contact link.

### Empty line

```markdown
[[break]]
```

See "Line breaks and extra space" above.

### Callout boxes

A callout is a highlighted box for something the reader must not miss: a gotcha, a warning, a note. It opens with `[[callout]]` and ends with `[[/callout]]`, each on its own line, and everything between them is normal markdown.

````markdown
[[callout title="Gotcha!"]]
Display objects removed with `display.remove()` still hold their Lua table.

- Set the reference to `nil` as well.

```lua
display.remove( player )
player = nil
```
[[/callout]]
````

- `title` is any text you like ("Note", "IMPORTANT!", "Heads up"), and may contain inline formatting.
- Leave out `title` for a box with only a body.
- The body can hold paragraphs, lists, code blocks, images, videos, and even another callout.
- A `[[/callout]]` inside a code block is shown as code and does not close the box.
- A `[[/callout]]` with no open callout stops the build; a callout left open closes at the end of the post with a build warning.

## Not supported

These are shown as plain text or in a simplified form:

- Tables.
- Strikethrough (`~~text~~`).
- Standard markdown images (`![alt](file.png)`); use `[[image]]`.
- Task list checkboxes.
- Footnotes.
- Backslash escapes such as `\*`.
- Headings underlined with `===`.
- Heading anchors: headings get no ids, so `[text](#heading)` links go nowhere.
- Raw HTML.
