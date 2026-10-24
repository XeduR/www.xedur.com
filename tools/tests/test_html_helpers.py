"""Unit tests for the HTML minifier and template indentation in update_website.py."""

import os
import sys
import unittest

# Make the tools importable regardless of the CWD the tests are run from.
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS_DIR)

from markdown_engine import render_markdown
from update_website import minify_html, replace_indented


CODE_BLOCK = '<pre><code class="language-lua">local x = 1\n\n\tif x then\n\t\tprint( x )\n\tend</code></pre>'


class TestMinifyHtml(unittest.TestCase):
    def test_pre_block_is_kept_verbatim(self):
        html = f"<div>\n    <p>text   here</p>\n    {CODE_BLOCK}\n</div>"
        result = minify_html(html)
        self.assertIn(CODE_BLOCK, result)
        self.assertIn("<p>text here</p>", result)

    def test_whitespace_around_pre_collapses_to_one_space(self):
        result = minify_html("<div>\n    <pre>a\n b</pre>\n    <p>x</p>\n</div>")
        self.assertEqual(result, "<div> <pre>a\n b</pre> <p>x</p></div>")

    def test_several_pre_blocks_each_survive(self):
        html = "<pre>one\n  1</pre>\n<p>mid</p>\n<PRE class=\"x\">two\n  2</PRE>"
        result = minify_html(html)
        self.assertIn("<pre>one\n  1</pre>", result)
        self.assertIn('<PRE class="x">two\n  2</PRE>', result)

    def test_tag_starting_with_pre_is_not_a_pre_block(self):
        result = minify_html("<preview>a\n   b</preview>")
        self.assertEqual(result, "<preview>a b</preview>")


class TestReplaceIndented(unittest.TestCase):
    TEMPLATE = "<article>\n        {{body}}\n</article>"

    def test_pre_lines_are_not_indented(self):
        content = f"<p>a</p>\n{CODE_BLOCK}\n<p>b</p>"
        result = replace_indented(self.TEMPLATE, "{{body}}", content)
        self.assertIn(CODE_BLOCK, result)
        self.assertIn("\n        <p>b</p>", result)

    def test_pre_on_first_line_is_not_indented(self):
        result = replace_indented(self.TEMPLATE, "{{body}}", "<pre>a\nb</pre>\n<p>c</p>")
        self.assertIn("<pre>a\nb</pre>", result)
        self.assertIn("\n        <p>c</p>", result)

    def test_lines_outside_pre_are_indented(self):
        result = replace_indented(self.TEMPLATE, "{{body}}", "<p>a</p>\n<p>b</p>")
        self.assertEqual(result, "<article>\n        <p>a</p>\n        <p>b</p>\n</article>")


class TestRenderedCodeBlockEndToEnd(unittest.TestCase):
    def test_fenced_code_survives_indent_and_minify(self):
        body = "Intro\n\n```lua\nlocal x = 1\n\nif x then\n\tprint( x )\nend\n```\n\nOutro"
        html, _ = render_markdown(body)
        page = minify_html(replace_indented(TestReplaceIndented.TEMPLATE, "{{body}}", html))
        self.assertIn(
            '<pre tabindex="0"><code class="language-lua">local x = 1\n\nif x then\n\tprint( x )\nend</code></pre>',
            page,
        )


if __name__ == "__main__":
    unittest.main()
