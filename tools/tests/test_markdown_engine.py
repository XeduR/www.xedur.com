"""Adversarial unit tests for tools/markdown_engine.py.

Every expected value is derived from the engine spec (Part A of
.scratch/task-2-tangents-writing-system.md), not from observed output, and the
suite asserts exact substrings and exact exception types so a subtly broken
implementation fails.
"""

import os
import sys
import unittest
from datetime import date

# Make the engine importable regardless of the CWD the tests are run from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import markdown_engine
from markdown_engine import (
    parse_front_matter,
    render_markdown,
    inline,
    register_directive,
    MarkdownError,
    FrontMatterError,
)


class TestFrontMatter(unittest.TestCase):
    def test_valid_full(self):
        text = (
            "---\n"
            "title: Hello World\n"
            "summary: A short blurb\n"
            "tags: solar2d, lua, gamedev\n"
            "published: 2026-07-13\n"
            "draft: false\n"
            "---\n"
            "Body line one.\n"
            "Body line two."
        )
        front, body = parse_front_matter(text, source="post.md")
        self.assertEqual(front["title"], "Hello World")
        self.assertEqual(front["summary"], "A short blurb")
        self.assertEqual(front["tags"], ["solar2d", "lua", "gamedev"])
        self.assertEqual(front["published"], date(2026, 7, 13))
        self.assertIs(front["draft"], False)
        self.assertEqual(body, "Body line one.\nBody line two.")

    def test_body_verbatim_single_leading_newline_consumed(self):
        text = "---\ntitle: X\n---\nline1\nline2"
        _, body = parse_front_matter(text)
        self.assertEqual(body, "line1\nline2")

    def test_body_preserves_intentional_leading_blank_line(self):
        # Only the newline directly after the closing fence is consumed; a
        # deliberate blank first body line survives.
        text = "---\ntitle: X\n---\n\nreal body"
        _, body = parse_front_matter(text)
        self.assertEqual(body, "\nreal body")

    def test_bom_and_blank_leading_lines(self):
        text = "\ufeff\n\n---\ntitle: X\n---\nbody"
        front, body = parse_front_matter(text)
        self.assertEqual(front["title"], "X")
        self.assertEqual(body, "body")

    def test_missing_open_fence_raises_and_names_source(self):
        text = "title: Hello\n---\nbody"
        with self.assertRaises(FrontMatterError) as ctx:
            parse_front_matter(text, source="broken.md")
        self.assertIn("broken.md", str(ctx.exception))

    def test_missing_close_fence_raises(self):
        text = "---\ntitle: Hello\nno closing fence here"
        with self.assertRaises(FrontMatterError):
            parse_front_matter(text, source="post.md")

    def test_no_colon_line_raises_and_names_line(self):
        text = "---\nthislinehasnocolon\n---\n"
        with self.assertRaises(FrontMatterError) as ctx:
            parse_front_matter(text)
        self.assertIn("thislinehasnocolon", str(ctx.exception))

    def test_bad_published_format_raises(self):
        # Single-digit month fails the ^\d{4}-\d{2}-\d{2}$ shape.
        text = "---\npublished: 2026-7-13\n---\n"
        with self.assertRaises(FrontMatterError):
            parse_front_matter(text)

    def test_bad_published_impossible_date_raises(self):
        # Matches the shape but month 13 is not a real date.
        text = "---\npublished: 2026-13-01\n---\n"
        with self.assertRaises(FrontMatterError):
            parse_front_matter(text)

    def test_bad_draft_raises(self):
        text = "---\ndraft: maybe\n---\n"
        with self.assertRaises(FrontMatterError):
            parse_front_matter(text)

    def test_draft_true_case_insensitive(self):
        text = "---\ndraft: TRUE\n---\n"
        front, _ = parse_front_matter(text)
        self.assertIs(front["draft"], True)

    def test_tags_split_trim_and_drop_empties(self):
        text = "---\ntags: a, b ,  c ,,\n---\n"
        front, _ = parse_front_matter(text)
        self.assertEqual(front["tags"], ["a", "b", "c"])

    def test_unknown_key_passthrough_as_string(self):
        text = "---\nsocialImage: card.png\ncustomKey: some value\n---\n"
        front, _ = parse_front_matter(text)
        self.assertEqual(front["socialImage"], "card.png")
        self.assertEqual(front["customKey"], "some value")

    def test_value_split_on_first_colon_only(self):
        text = "---\ntitle: Ratio 16:9 explained\n---\n"
        front, _ = parse_front_matter(text)
        self.assertEqual(front["title"], "Ratio 16:9 explained")

    def test_quotes_are_not_stripped(self):
        text = '---\ntitle: "quoted"\n---\n'
        front, _ = parse_front_matter(text)
        self.assertEqual(front["title"], '"quoted"')

    def test_missing_optional_keys_absent(self):
        text = "---\ntitle: X\n---\n"
        front, _ = parse_front_matter(text)
        self.assertNotIn("tags", front)
        self.assertNotIn("draft", front)
        self.assertNotIn("published", front)


class TestBlockParser(unittest.TestCase):
    def test_heading_levels_h2_to_h6(self):
        html, _ = render_markdown("## Two")
        self.assertEqual(html, "<h2>Two</h2>")
        html, _ = render_markdown("###### Six")
        self.assertEqual(html, "<h6>Six</h6>")

    def test_h1_demoted_to_h2_with_warning(self):
        html, meta = render_markdown("# Title")
        self.assertEqual(html, "<h2>Title</h2>")
        self.assertTrue(any("demoted to h2" in w for w in meta["warnings"]))

    def test_seven_hashes_is_not_a_heading(self):
        # #{1,6} only; seven hashes falls through to a paragraph.
        html, _ = render_markdown("####### Nope")
        self.assertEqual(html, "<p>####### Nope</p>")

    def test_paragraph_joins_consecutive_lines_with_space(self):
        html, _ = render_markdown("Line one\nLine two")
        self.assertEqual(html, "<p>Line one Line two</p>")

    def test_blank_line_separates_paragraphs(self):
        html, _ = render_markdown("Para one\n\nPara two")
        self.assertEqual(html, "<p>Para one</p>\n<p>Para two</p>")

    def test_unordered_list(self):
        html, _ = render_markdown("- a\n- b")
        self.assertEqual(html, "<ul>\n<li>a</li>\n<li>b</li>\n</ul>")

    def test_unordered_list_star_marker(self):
        html, _ = render_markdown("* a\n* b")
        self.assertEqual(html, "<ul>\n<li>a</li>\n<li>b</li>\n</ul>")

    def test_ordered_list(self):
        html, _ = render_markdown("1. a\n2. b")
        self.assertEqual(html, "<ol>\n<li>a</li>\n<li>b</li>\n</ol>")

    def test_blockquote_joins_with_space(self):
        html, _ = render_markdown("> quoted\n> more")
        self.assertEqual(html, "<blockquote><p>quoted more</p></blockquote>")

    def test_horizontal_rule(self):
        self.assertEqual(render_markdown("---")[0], "<hr>")
        self.assertEqual(render_markdown("-----")[0], "<hr>")

    def test_dashes_with_trailing_text_is_not_hr(self):
        html, _ = render_markdown("--- text")
        self.assertEqual(html, "<p>--- text</p>")

    def test_code_fence_with_language(self):
        html, _ = render_markdown("```python\ncode line\n```")
        self.assertEqual(
            html, '<pre tabindex="0"><code class="language-python">code line</code></pre>'
        )

    def test_code_fence_without_language(self):
        html, _ = render_markdown("```\ncode line\n```")
        self.assertEqual(html, '<pre tabindex="0"><code>code line</code></pre>')

    def test_code_fence_isolates_inline_markup(self):
        html, _ = render_markdown("```\n*not bold* `x` [t](u) _no_\n```")
        self.assertIn("*not bold* `x` [t](u) _no_", html)
        self.assertNotIn("<strong>", html)
        self.assertNotIn("<em>", html)
        self.assertNotIn("<a ", html)

    def test_code_fence_escapes_html_chars(self):
        html, _ = render_markdown("```\na < b & c > d\n```")
        self.assertEqual(html, '<pre tabindex="0"><code>a &lt; b &amp; c &gt; d</code></pre>')

    def test_code_fence_preserves_indentation_and_blank_lines(self):
        html, _ = render_markdown("```\ndef f():\n\n    return 1\n```")
        self.assertEqual(
            html, '<pre tabindex="0"><code>def f():\n\n    return 1</code></pre>'
        )

    def test_unclosed_code_fence_auto_closes_with_warning(self):
        html, meta = render_markdown("```\nunterminated")
        self.assertEqual(html, '<pre tabindex="0"><code>unterminated</code></pre>')
        self.assertTrue(any("left open" in w for w in meta["warnings"]))

    def test_empty_body(self):
        html, meta = render_markdown("")
        self.assertEqual(html, "")
        self.assertEqual(meta["warnings"], [])

    def test_list_then_paragraph_are_separate_blocks(self):
        html, _ = render_markdown("- a\n\ntext")
        self.assertEqual(html, "<ul>\n<li>a</li>\n</ul>\n<p>text</p>")


class TestInlineParser(unittest.TestCase):
    def test_bold(self):
        self.assertEqual(inline("**bold**"), "<strong>bold</strong>")

    def test_italic_star(self):
        self.assertEqual(inline("*italic*"), "<em>italic</em>")

    def test_italic_underscore(self):
        self.assertEqual(inline("_italic_"), "<em>italic</em>")

    def test_bold_before_italic(self):
        # **x** must become <strong>x</strong>, never be eaten by the * rule.
        self.assertEqual(inline("**x**"), "<strong>x</strong>")
        self.assertNotIn("<em>", inline("**x**"))

    def test_triple_star_nests_strong_around_em(self):
        self.assertEqual(inline("***bi***"), "<strong><em>bi</em></strong>")

    def test_intra_word_underscores_stay_literal(self):
        self.assertEqual(inline("MAX_VALUE and MIN_VALUE"), "MAX_VALUE and MIN_VALUE")
        self.assertEqual(inline("call snake_case_name()"), "call snake_case_name()")

    def test_underscore_emphasis_may_contain_underscores(self):
        self.assertEqual(inline("_foo_bar_"), "<em>foo_bar</em>")

    def test_underscore_emphasis_next_to_punctuation(self):
        self.assertEqual(inline("(_soft_)."), "(<em>soft</em>).")

    def test_bold_and_italic_mixed(self):
        self.assertEqual(
            inline("**bold** and *soft*"),
            "<strong>bold</strong> and <em>soft</em>",
        )

    def test_link(self):
        self.assertEqual(
            inline("[text](http://example.com)"),
            '<a href="http://example.com">text</a>',
        )

    def test_inline_code(self):
        self.assertEqual(inline("`code`"), "<code>code</code>")

    def test_escapes_lt_and_amp(self):
        self.assertEqual(inline("a < b & c"), "a &lt; b &amp; c")

    def test_escapes_double_quote(self):
        self.assertEqual(inline('say "hi"'), "say &quot;hi&quot;")

    def test_escaping_happens_so_raw_html_is_inert(self):
        self.assertEqual(
            inline("<script>alert(1)</script>"),
            "&lt;script&gt;alert(1)&lt;/script&gt;",
        )

    def test_code_span_protects_asterisks_brackets_underscores(self):
        # None of the emphasis/link rules fire inside a code span.
        self.assertEqual(inline("`*x* [y](z) _w_`"), "<code>*x* [y](z) _w_</code>")

    def test_code_span_content_is_escaped(self):
        self.assertEqual(inline("`a < b`"), "<code>a &lt; b</code>")


class TestLinkProtection(unittest.TestCase):
    def test_url_with_underscore_survives_unmangled(self):
        html = inline("[link](http://example.com/a_b_c)")
        self.assertEqual(html, '<a href="http://example.com/a_b_c">link</a>')
        self.assertNotIn("<em>", html)

    def test_url_with_asterisks_survives_unmangled(self):
        html = inline("[link](http://example.com/a*b*c)")
        self.assertEqual(html, '<a href="http://example.com/a*b*c">link</a>')
        self.assertNotIn("<strong>", html)
        self.assertNotIn("<em>", html)

    def test_bold_inside_link_text_works(self):
        html = inline("[**bold link**](http://example.com)")
        self.assertEqual(
            html, '<a href="http://example.com"><strong>bold link</strong></a>'
        )

    def test_link_text_with_underscore_url_combined(self):
        # Emphasis inside the visible text, URL underscores untouched.
        html = inline("[**b**](http://x.com/a_b)")
        self.assertEqual(html, '<a href="http://x.com/a_b"><strong>b</strong></a>')

    def test_url_with_parentheses_stays_whole(self):
        html = inline("[Lua](https://en.wikipedia.org/wiki/Lua_(programming_language))")
        self.assertEqual(
            html, '<a href="https://en.wikipedia.org/wiki/Lua_(programming_language)">Lua</a>'
        )

    def test_url_ending_in_a_parenthesis_followed_by_text(self):
        html = inline("See [Lua](https://e.com/Lua_(language)) (a language) now.")
        self.assertEqual(
            html, 'See <a href="https://e.com/Lua_(language)">Lua</a> (a language) now.'
        )

    def test_link_inside_a_parenthetical_leaves_the_closing_parenthesis(self):
        html = inline("(see [docs](https://e.com/a_(b)))")
        self.assertEqual(html, '(see <a href="https://e.com/a_(b)">docs</a>)')

    def test_nesting_beyond_one_level_is_left_as_plain_text(self):
        text = "[x](https://e.com/a_(b_(c)))"
        html = inline(text)
        self.assertNotIn("<a", html)
        self.assertEqual(html, text)


    def test_url_special_chars_are_entity_escaped(self):
        # Escaping must run before URLs are captured, or a raw '"' reaches href.
        html = inline('[x](http://e.com?a="b&c=<d>)')
        self.assertEqual(
            html, '<a href="http://e.com?a=&quot;b&amp;c=&lt;d&gt;">x</a>'
        )


class TestUrlSchemes(unittest.TestCase):
    def test_allowed_links_render(self):
        for url in ("http://e.com", "https://e.com/a", "mailto:me@e.com",
                    "../page/", "page.html", "/abs/path", "#section", "?q=1"):
            with self.subTest(url=url):
                self.assertEqual(inline(f"[x]({url})"), f'<a href="{url}">x</a>')

    def test_scheme_check_is_case_insensitive(self):
        self.assertEqual(inline("[x](HTTPS://e.com)"), '<a href="HTTPS://e.com">x</a>')

    def test_disallowed_links_render_as_plain_text(self):
        for url in ("javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,hi",
                    "vbscript:x", " javascript:alert(1)", "java\tscript:alert(1)"):
            with self.subTest(url=url):
                html = inline(f"[x]({url})")
                self.assertNotIn("<a", html)
                self.assertTrue(html.startswith("[x]("), html)

    def test_disallowed_link_with_parentheses_renders_whole_as_plain_text(self):
        self.assertEqual(inline("[x](javascript:alert(1)) now"), "[x](javascript:alert(1)) now")

    def test_colon_after_path_is_relative(self):
        self.assertEqual(inline("[x](a/b:c)"), '<a href="a/b:c">x</a>')

    def test_disallowed_image_src_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown('[[image src="javascript:alert(1)" alt="a"]]')

    def test_https_image_src_allowed(self):
        html, _ = render_markdown('[[image src="https://e.com/a.png" alt="a"]]')
        self.assertIn('src="https://e.com/a.png"', html)


class TestImageDirective(unittest.TestCase):
    def test_full(self):
        html, meta = render_markdown(
            '[[image src="cat.jpg" alt="A cat" caption="My cat" '
            'width="640" height="480"]]'
        )
        expected = (
            '<figure class="md-figure">\n'
            '    <img src="cat.jpg" alt="A cat" loading="lazy" width="640" height="480">\n'
            '    <figcaption>My cat</figcaption>\n'
            "</figure>"
        )
        self.assertEqual(html, expected)
        self.assertEqual(meta["images"], ["cat.jpg"])

    def test_minimal_missing_alt_warns_and_omits_figcaption(self):
        html, meta = render_markdown('[[image src="cat.jpg"]]')
        expected = (
            '<figure class="md-figure">\n'
            '    <img src="cat.jpg" alt="" loading="lazy">\n'
            "</figure>"
        )
        self.assertEqual(html, expected)
        self.assertNotIn("<figcaption>", html)
        self.assertTrue(any("alt" in w for w in meta["warnings"]))
        self.assertEqual(meta["images"], ["cat.jpg"])

    def test_caption_is_escaped(self):
        html, _ = render_markdown('[[image src="x.jpg" alt="a" caption="a & <b>"]]')
        self.assertIn("<figcaption>a &amp; &lt;b&gt;</figcaption>", html)

    def test_src_width_height_are_escaped(self):
        html, meta = render_markdown(
            '[[image src="a.png?x=1&y=2" alt="a" width="1<2" height="3>4"]]'
        )
        self.assertIn('src="a.png?x=1&amp;y=2"', html)
        self.assertIn('width="1&lt;2"', html)
        self.assertIn('height="3&gt;4"', html)
        self.assertEqual(meta["images"], ["a.png?x=1&y=2"])

    def test_missing_src_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown('[[image alt="no source"]]')

    def test_src_not_prefixed_with_base_path(self):
        html, _ = render_markdown('[[image src="diagram.png" alt="d"]]', base_path="../../")
        self.assertIn('src="diagram.png"', html)
        self.assertNotIn("../../diagram.png", html)


class TestYoutubeDirective(unittest.TestCase):
    def test_output_and_flag(self):
        html, meta = render_markdown('[[youtube id="abcDEF12_-x" title="My Video"]]')
        expected = (
            '<div class="video-placeholder" data-video-id="abcDEF12_-x" '
            'data-video-title="My Video">\n'
            '    <div class="overlay">\n'
            "        <p>We don't use cookies, but YouTube does. To watch this "
            "video, you accept that YouTube may set cookies on your device.</p>\n"
            '        <button type="button" class="video-consent">I accept</button>\n'
            "    </div>\n"
            "</div>"
        )
        self.assertEqual(html, expected)
        self.assertIs(meta["needs_video_js"], True)

    def test_title_optional_defaults_empty(self):
        html, _ = render_markdown('[[youtube id="abcDEF12_-x"]]')
        self.assertIn('data-video-title=""', html)

    def test_title_is_escaped(self):
        html, _ = render_markdown('[[youtube id="abcDEF12_-x" title="a & <b>"]]')
        self.assertIn('data-video-title="a &amp; &lt;b&gt;"', html)

    def test_missing_id_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown('[[youtube title="no id"]]')

    def test_invalid_ids_raise(self):
        for video_id in ("abc", "abcDEF12_-xy", "abcDEF12'-x", "abcDEF12&-x", "abcDEF12 -x"):
            with self.subTest(video_id=video_id):
                with self.assertRaises(MarkdownError):
                    render_markdown(f'[[youtube id="{video_id}"]]')

    def test_flag_defaults_false_without_youtube(self):
        _, meta = render_markdown("just prose")
        self.assertIs(meta["needs_video_js"], False)


class TestGithubDirective(unittest.TestCase):
    """github is registered by the site, not the engine; test via register_directive."""

    def setUp(self):
        def handler(params, meta, base_path):
            repo = params.get("repo")
            url = params.get("url") or (
                f"https://github.com/{repo}" if repo else None
            )
            if not url:
                return "PRIVATE_PANEL"
            return f"PUBLIC:{url}"

        register_directive("github", handler)

    def tearDown(self):
        markdown_engine.DIRECTIVES.pop("github", None)

    def test_public_via_repo(self):
        html, _ = render_markdown('[[github repo="owner/name"]]')
        self.assertEqual(html, "PUBLIC:https://github.com/owner/name")

    def test_public_via_url(self):
        html, _ = render_markdown('[[github url="https://github.com/x/y/tree/main"]]')
        self.assertEqual(html, "PUBLIC:https://github.com/x/y/tree/main")

    def test_private_fallback_no_params(self):
        html, _ = render_markdown("[[github]]")
        self.assertEqual(html, "PRIVATE_PANEL")

    def test_unregistered_after_teardown(self):
        # Guards the tearDown so github does not leak into other test classes.
        markdown_engine.DIRECTIVES.pop("github", None)
        with self.assertRaises(MarkdownError):
            render_markdown("[[github]]")


class TestLineBreaks(unittest.TestCase):
    def test_trailing_backslash_breaks_the_line(self):
        html, _ = render_markdown("first\\\nsecond\nthird")
        self.assertEqual(html, "<p>first<br>\nsecond third</p>")

    def test_spaces_before_the_backslash_are_dropped(self):
        html, _ = render_markdown("first   \\\nsecond")
        self.assertEqual(html, "<p>first<br>\nsecond</p>")

    def test_backslash_on_the_last_line_stays_literal(self):
        html, _ = render_markdown("only line\\")
        self.assertEqual(html, "<p>only line\\</p>")

    def test_backslash_inside_a_line_stays_literal(self):
        html, _ = render_markdown("a \\ b\nc")
        self.assertEqual(html, "<p>a \\ b c</p>")

    def test_blockquote_hard_break(self):
        html, _ = render_markdown("> one\\\n> two")
        self.assertEqual(html, "<blockquote><p>one<br>\ntwo</p></blockquote>")

    def test_emphasis_spans_a_hard_break(self):
        html, _ = render_markdown("**bold\\\nstill bold**")
        self.assertEqual(html, "<p><strong>bold<br>\nstill bold</strong></p>")

    def test_break_inside_inline_code_still_breaks(self):
        html, _ = render_markdown("`a\\\nb`")
        self.assertEqual(html, "<p><code>a<br>\nb</code></p>")

    def test_list_item_backslash_stays_literal(self):
        html, _ = render_markdown("- item\\\n- next")
        self.assertIn("<li>item\\</li>", html)

    def test_break_directive_sits_between_paragraphs(self):
        html, _ = render_markdown("above\n\n[[break]]\n\nbelow")
        self.assertEqual(html, "<p>above</p>\n<br>\n<p>below</p>")

    def test_break_directive_closes_an_open_paragraph(self):
        html, _ = render_markdown("above\n[[break]]\nbelow")
        self.assertEqual(html, "<p>above</p>\n<br>\n<p>below</p>")

    def test_repeated_break_directives_stack(self):
        html, _ = render_markdown("a\n[[break]]\n[[break]]\nb")
        self.assertEqual(html.count("<br>"), 2)

    def test_extra_blank_lines_add_nothing(self):
        html, _ = render_markdown("a\n\n\n\nb")
        self.assertEqual(html, "<p>a</p>\n<p>b</p>")


class TestCallout(unittest.TestCase):
    def test_title_and_body(self):
        html, _ = render_markdown('[[callout title="Gotcha!"]]\nBody text.\n[[/callout]]')
        self.assertEqual(html, (
            '<div class="md-callout" role="note">\n'
            '<p class="md-callout-title">Gotcha!</p>\n'
            "<p>Body text.</p>\n"
            "</div>"
        ))

    def test_title_is_escaped_and_formatted(self):
        html, _ = render_markdown('[[callout title="<b> & `code`"]]\nx\n[[/callout]]')
        self.assertIn('<p class="md-callout-title">&lt;b&gt; &amp; <code>code</code></p>', html)

    def test_no_title(self):
        html, _ = render_markdown("[[callout]]\nBody.\n[[/callout]]")
        self.assertEqual(html, '<div class="md-callout" role="note">\n<p>Body.</p>\n</div>')

    def test_empty_callout(self):
        html, _ = render_markdown('[[callout title="T"]]\n[[/callout]]')
        self.assertEqual(html, '<div class="md-callout" role="note">\n<p class="md-callout-title">T</p>\n</div>')

    def test_body_holds_blocks(self):
        text = (
            '[[callout title="T"]]\n'
            "Para one.\n\n"
            "- item\n\n"
            "```lua\nlocal x = 1\n```\n"
            "[[/callout]]"
        )
        html, _ = render_markdown(text)
        self.assertIn("<p>Para one.</p>\n<ul>\n<li>item</li>\n</ul>\n<pre", html)
        self.assertIn('<code class="language-lua">local x = 1</code></pre>\n</div>', html)

    def test_closes_an_open_paragraph_and_text_follows(self):
        html, _ = render_markdown("before\n[[callout]]\nin\n[[/callout]]\nafter")
        self.assertEqual(html, (
            "<p>before</p>\n"
            '<div class="md-callout" role="note">\n<p>in</p>\n</div>\n'
            "<p>after</p>"
        ))

    def test_close_inside_a_code_fence_does_not_end_the_callout(self):
        text = "[[callout]]\n```\n[[/callout]]\n```\nstill inside\n[[/callout]]\nafter"
        html, _ = render_markdown(text)
        self.assertIn("<pre tabindex=\"0\"><code>[[/callout]]</code></pre>\n<p>still inside</p>\n</div>", html)
        self.assertTrue(html.endswith("</div>\n<p>after</p>"))

    def test_nested_callouts(self):
        text = '[[callout title="Outer"]]\n[[callout title="Inner"]]\nin\n[[/callout]]\nouter tail\n[[/callout]]\nafter'
        html, _ = render_markdown(text)
        self.assertEqual(html.count('<div class="md-callout"'), 2)
        self.assertIn("<p>in</p>\n</div>\n<p>outer tail</p>\n</div>\n<p>after</p>", html)

    def test_directives_inside_share_meta(self):
        text = '[[callout]]\n[[image src="a.png"]]\n[[youtube id="abcDEF12_-x"]]\n# Big\n[[/callout]]'
        _, meta = render_markdown(text)
        self.assertEqual(meta["images"], ["a.png"])
        self.assertIs(meta["needs_video_js"], True)
        self.assertEqual(len(meta["warnings"]), 2)

    def test_unknown_directive_inside_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown("[[callout]]\n[[nope]]\n[[/callout]]")

    def test_unclosed_callout_auto_closes_with_warning(self):
        html, meta = render_markdown("[[callout]]\nbody")
        self.assertEqual(html, '<div class="md-callout" role="note">\n<p>body</p>\n</div>')
        self.assertTrue(any("callout" in w for w in meta["warnings"]))

    def test_stray_close_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown("text\n[[/callout]]")

    def test_malformed_params_raise(self):
        with self.assertRaises(MarkdownError):
            render_markdown("[[callout title=Note]]\nx\n[[/callout]]")

    def test_close_inside_a_top_level_code_block_is_literal(self):
        html, _ = render_markdown("```\n[[/callout]]\n```")
        self.assertEqual(html, '<pre tabindex="0"><code>[[/callout]]</code></pre>')


class TestDirectiveErrors(unittest.TestCase):
    def test_unknown_directive_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown("[[bogus]]")

    def test_unknown_directive_with_valid_params_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown('[[bogus src="x"]]')

    def test_malformed_params_on_known_directive_raises(self):
        # image is known, but the param section has no key="value" pairs.
        with self.assertRaises(MarkdownError):
            render_markdown("[[image this is not valid]]")

    def test_capitalized_name_fails_pattern_and_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown('[[Image src="x"]]')

    def test_leading_digit_name_fails_pattern_and_raises(self):
        with self.assertRaises(MarkdownError):
            render_markdown('[[123bad src="x"]]')

    def test_empty_brackets_raise(self):
        with self.assertRaises(MarkdownError):
            render_markdown("[[]]")

    def test_duplicate_param_keys_last_wins(self):
        html, _ = render_markdown('[[image src="first.jpg" src="second.jpg" alt="a"]]')
        self.assertIn('src="second.jpg"', html)
        self.assertNotIn("first.jpg", html)

    def test_directive_not_on_own_line_is_literal_text(self):
        # A [[...]] not spanning the whole line is not a directive: no raise.
        html, _ = render_markdown("This is [[not a directive]] inline.")
        self.assertEqual(html, "<p>This is [[not a directive]] inline.</p>")


class TestInputNormalization(unittest.TestCase):
    def test_crlf_fenced_code_has_no_carriage_return(self):
        # Fence content uses raw lines, so a stray \r would leak without
        # newline normalization at the entry point.
        doc = "```\r\nline1\r\nline2\r\n```\r\n"
        html, _ = render_markdown(doc)
        self.assertNotIn("\r", html)
        self.assertEqual(html, '<pre tabindex="0"><code>line1\nline2</code></pre>')

    def test_lone_cr_is_normalized(self):
        doc = "para one\rpara two"
        html, _ = render_markdown(doc)
        self.assertNotIn("\r", html)
        self.assertEqual(html, "<p>para one para two</p>")

    def test_nul_bytes_stripped_and_render_without_error(self):
        # A literal NUL collides with the internal sentinel scheme; it must be
        # stripped rather than raise (only MarkdownError/FrontMatterError leak).
        doc = "\x00CODE9\x00 literal text\nmore"
        html, _ = render_markdown(doc)
        self.assertNotIn("\x00", html)
        self.assertIn("CODE9 literal text", html)

    def test_crlf_normalized_in_front_matter_body(self):
        text = "---\r\ntitle: X\r\ntags: a, b\r\n---\r\nline1\r\nline2"
        front, body = parse_front_matter(text)
        self.assertEqual(front["title"], "X")
        self.assertEqual(front["tags"], ["a", "b"])
        self.assertEqual(body, "line1\nline2")
        self.assertNotIn("\r", body)


class TestIntegration(unittest.TestCase):
    def test_multi_feature_document(self):
        doc = (
            "## Heading\n"
            "\n"
            "A paragraph with **bold**, *italic*, `code`, and a "
            "[link](http://example.com/a_b).\n"
            "\n"
            "- first\n"
            "- second\n"
            "\n"
            "> a quote\n"
            "\n"
            '[[image src="pic.png" alt="a picture"]]\n'
            "\n"
            '[[youtube id="abcDEF12_-x"]]\n'
            "\n"
            "```lua\n"
            "local x = 1 < 2\n"
            "```"
        )
        html, meta = render_markdown(doc, base_path="../../")

        self.assertIn("<h2>Heading</h2>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn('<a href="http://example.com/a_b">link</a>', html)
        self.assertIn("<ul>\n<li>first</li>\n<li>second</li>\n</ul>", html)
        self.assertIn("<blockquote><p>a quote</p></blockquote>", html)
        self.assertIn('<figure class="md-figure">', html)
        self.assertIn('data-video-id="abcDEF12_-x"', html)
        self.assertIn('<pre tabindex="0"><code class="language-lua">', html)
        self.assertIn("local x = 1 &lt; 2", html)

        self.assertIs(meta["needs_video_js"], True)
        self.assertIs(meta["needs_demo_js"], False)
        self.assertEqual(meta["images"], ["pic.png"])


if __name__ == "__main__":
    unittest.main()
