"""Unit tests for Tangents post loading and page building in update_website.py.

Each test that loads posts runs against a throwaway root, so the repo's posts,
dates file, and pages are never read or written.
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

# Make the tools importable regardless of the CWD the tests are run from.
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS_DIR)

import markdown_engine
import update_website
from markdown_engine import FrontMatterError, parse_front_matter


def front_matter(**keys):
    lines = ["---"] + [f"{key}: {value}" for key, value in keys.items()] + ["---", "", "Body."]
    return "\n".join(lines)


class TestFrontMatterKeys(unittest.TestCase):
    def test_blank_values_leave_keys_unset(self):
        front, _ = parse_front_matter("---\ntitle: T\npublished:\nupdated:\ndraft:\ntags:\nfeatureImage:\n---\n")
        self.assertEqual(front, {"title": "T"})

    def test_template_parses_to_no_keys(self):
        with open(os.path.join(update_website.TEMPLATES_DIR, "new-tangent-post.md"), encoding="utf-8") as f:
            front, body = parse_front_matter(f.read())
        self.assertEqual(front, {})
        self.assertEqual(body.strip(), "")

    def test_updated_parses_as_date(self):
        front, _ = parse_front_matter("---\nupdated: 2026-11-02\n---\n")
        self.assertEqual(front["updated"], date(2026, 11, 2))

    def test_malformed_updated_raises(self):
        for value in ("2026-1-2", "yesterday", "2026-02-30"):
            with self.assertRaises(FrontMatterError, msg=value):
                parse_front_matter(f"---\nupdated: {value}\n---\n")


class TestTruncateDescription(unittest.TestCase):
    def test_short_text_is_unchanged(self):
        self.assertEqual(update_website.truncate_description("A short summary."), "A short summary.")

    def test_whitespace_collapses(self):
        self.assertEqual(update_website.truncate_description("a\n  b\tc"), "a b c")

    def test_long_text_cuts_at_a_word_within_the_limit(self):
        text = " ".join(["wordy"] * 200)
        result = update_website.truncate_description(text)
        self.assertLessEqual(len(result), update_website.SUMMARY_MAX)
        self.assertTrue(result.endswith("wordy…"))

    def test_exact_limit_is_not_cut(self):
        text = "x" * update_website.SUMMARY_MAX
        self.assertEqual(update_website.truncate_description(text), text)

    def test_one_huge_word_is_cut_hard(self):
        result = update_website.truncate_description("y" * 500)
        self.assertEqual(len(result), update_website.SUMMARY_MAX)
        self.assertTrue(result.endswith("…"))

    def test_trailing_punctuation_is_dropped_before_the_ellipsis(self):
        text = ("word, " * 60).strip()
        self.assertTrue(update_website.truncate_description(text).endswith("word…"))


class TestTruncateListSummary(unittest.TestCase):
    def test_up_to_160_characters_is_unchanged(self):
        text = "z" * 160
        self.assertEqual(update_website.truncate_list_summary(text), text)

    def test_161_characters_cuts_at_160_and_adds_dots(self):
        result = update_website.truncate_list_summary("z" * 161)
        self.assertEqual(result, "z" * 160 + "...")
        self.assertEqual(len(result), 163)

    def test_cut_never_exceeds_163_characters(self):
        for length in (161, 250, 1000):
            text = ("word " * 400)[:length]
            self.assertLessEqual(len(update_website.truncate_list_summary(text)), 163)

    def test_space_at_the_cut_is_dropped_before_the_dots(self):
        text = "a" * 159 + " " + "b" * 50
        self.assertEqual(update_website.truncate_list_summary(text), "a" * 159 + "...")

    def test_whitespace_collapses_before_counting(self):
        self.assertEqual(update_website.truncate_list_summary("a   b"), "a b")


class TestImageUrls(unittest.TestCase):
    def test_page_relative(self):
        for url in ("cover.png", "img/cover.png", "../shared/cover.png"):
            self.assertTrue(update_website.is_page_relative_url(url), url)
        for url in ("/img/cover.png", "https://example.com/a.png", "//cdn.example.com/a.png"):
            self.assertFalse(update_website.is_page_relative_url(url), url)

    def test_local_path_resolution(self):
        root = update_website.OUTPUT_DIR
        self.assertEqual(update_website.local_image_path("a b.png?v=2", "tangents/x"),
                         os.path.join(root, "tangents", "x", "a b.png"))
        self.assertEqual(update_website.local_image_path("a%20b.png", "tangents/x"),
                         os.path.join(root, "tangents", "x", "a b.png"))
        self.assertEqual(update_website.local_image_path("/img/xedur.png", "tangents/x"),
                         os.path.join(root, "img", "xedur.png"))
        self.assertIsNone(update_website.local_image_path("https://example.com/a.png", "tangents/x"))
        self.assertIsNone(update_website.local_image_path("//cdn.example.com/a.png", "tangents/x"))


class TangentsRootMixin:
    """Point the post loader at a throwaway source dir, dates file, and output root."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="tangents-test-")
        self.src = os.path.join(self.root, "tools", "tangents")
        os.makedirs(self.src)
        self.dates_file = os.path.join(self.root, "tangents_dates.json")
        with open(self.dates_file, "w", encoding="utf-8") as f:
            f.write("{}")
        self.patches = [
            mock.patch.object(update_website, "TANGENTS_SRC_DIR", self.src),
            mock.patch.object(update_website, "TANGENTS_DATES_FILE", self.dates_file),
            mock.patch.object(update_website, "OUTPUT_DIR", self.root),
        ]
        for patch in self.patches:
            patch.start()
        del update_website.BUILD_LOG_EVENTS[:]

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        del update_website.BUILD_LOG_EVENTS[:]
        shutil.rmtree(self.root)

    def write_post(self, slug, **keys):
        keys.setdefault("title", "A post")
        keys.setdefault("summary", "A summary.")
        with open(os.path.join(self.src, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write(front_matter(**keys))

    def load_one(self, slug="a-post", **keys):
        self.write_post(slug, **keys)
        return update_website.load_tangents_posts()[0]

    def warnings(self):
        return [message for level, message in update_website.BUILD_LOG_EVENTS if level == "warning"]


class TestUpdatedDate(TangentsRootMixin, unittest.TestCase):
    def test_no_updated_date_shows_none(self):
        self.assertIsNone(self.load_one(published="2026-10-01")["updated"])

    def test_same_day_as_published_is_hidden(self):
        post = self.load_one(published="2026-10-01", updated="2026-10-01")
        self.assertIsNone(post["updated"])

    def test_later_date_is_kept(self):
        post = self.load_one(published="2026-10-01", updated="2026-10-20")
        self.assertEqual(post["updated"], date(2026, 10, 20))

    def test_earlier_than_published_stops_the_build(self):
        with self.assertRaises(ValueError):
            self.load_one(published="2026-10-20", updated="2026-10-01")

    def test_front_matter_date_overrides_the_tracked_body_change(self):
        self.write_post("a-post", published="2026-10-01", updated="2026-10-05")
        update_website.load_tangents_posts()
        with open(os.path.join(self.src, "a-post.md"), "a", encoding="utf-8") as f:
            f.write("\nMore body.\n")
        post = update_website.load_tangents_posts()[0]
        self.assertEqual(post["updated"], date(2026, 10, 5))


class TestFeatureImageLoading(TangentsRootMixin, unittest.TestCase):
    def test_absent_feature_image(self):
        post = self.load_one()
        self.assertIsNone(post["feature_image"])
        self.assertEqual(post["feature_image_alt"], "")

    def test_missing_local_feature_image_only_warns(self):
        post = self.load_one(featureImage="cover.png")
        self.assertEqual(post["feature_image"], "cover.png")
        self.assertTrue(any("cover.png" in message for message in self.warnings()))

    def test_present_local_feature_image_does_not_warn(self):
        os.makedirs(os.path.join(self.root, "tangents", "a-post"))
        open(os.path.join(self.root, "tangents", "a-post", "cover.png"), "wb").close()
        self.load_one(featureImage="cover.png")
        self.assertEqual(self.warnings(), [])

    def test_remote_feature_image_is_not_checked(self):
        self.load_one(featureImage="https://example.com/gone.png")
        self.assertEqual(self.warnings(), [])

    def test_missing_inline_image_only_warns(self):
        self.write_post("a-post")
        with open(os.path.join(self.src, "a-post.md"), "a", encoding="utf-8") as f:
            f.write('\n[[image src="nope.png" alt="x"]]\n')
        post = update_website.load_tangents_posts()[0]
        self.assertTrue(post["has_images"])
        self.assertTrue(any("nope.png" in message for message in self.warnings()))

    def test_disallowed_scheme_stops_the_build(self):
        with self.assertRaises(ValueError):
            self.load_one(featureImage="javascript:alert(1)")


class BuildCaptureMixin:
    """Run the Tangents builders with their writes captured, never made."""

    def setUp(self):
        self.written = {}
        self.patches = [
            mock.patch.object(update_website, "write_file", self.capture),
            mock.patch.object(update_website, "FORCE", True),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def capture(self, filepath, content):
        self.written[os.path.relpath(filepath, update_website.ROOT_DIR).replace(os.sep, "/")] = content

    def post(self, slug="a-post", **overrides):
        post = {
            "slug": slug,
            "title": "A Post",
            "summary": "Summary.",
            "tags": [],
            "published": date(2026, 7, 1),
            "updated": None,
            "body_html": "<p>Body.</p>",
            "needs_video_js": False,
            "has_images": False,
            "social_image": None,
            "feature_image": None,
            "feature_image_alt": "",
            "og_image": "https://www.xedur.com/tangents/a-post/a-post-social.png",
            "og_image_size": (1200, 630),
        }
        post.update(overrides)
        return post

    def build_posts(self, posts):
        update_website.build_tangents_posts(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("tangents-post.html"), posts,
        )

    def build_lists(self, posts):
        update_website.build_tangents_list_pages(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("tangents-list.html"),
            update_website.load_file("tangents-item.html"),
            posts, "https://www.xedur.com/tangents/tangents-social.png",
        )


class TestPostPage(BuildCaptureMixin, unittest.TestCase):
    def page(self, **overrides):
        self.build_posts([self.post(**overrides)])
        return self.written["tangents/a-post/index.html"]

    def test_updated_line_follows_published(self):
        html = self.page(updated=date(2026, 7, 9))
        self.assertIn("Published: 1 July 2026<br>Updated: 9 July 2026", html)

    def test_no_updated_line_without_a_date(self):
        self.assertNotIn("Updated:", self.page())

    def test_feature_image_and_fallback_script(self):
        html = self.page(feature_image="cover.png", feature_image_alt='A "cover"')
        self.assertIn('<figure class="feature-image">', html)
        self.assertIn('<img src="cover.png" alt="A &quot;cover&quot;" fetchpriority="high">', html)
        self.assertIn("js/image-fallback.js", html)

    def test_feature_image_is_followed_by_a_divider_before_the_body(self):
        html = self.page(feature_image="cover.png")
        figure_end = html.index("</figure>", html.index('<figure class="feature-image">'))
        self.assertRegex(html[figure_end:], r"^</figure>\s*<hr>\s*<p>Body.</p>")

    def test_no_divider_without_a_feature_image(self):
        self.assertNotIn("<hr>", self.page())

    def test_no_feature_image_and_no_images_loads_no_fallback_script(self):
        html = self.page()
        self.assertNotIn("feature-image", html)
        self.assertNotIn("image-fallback.js", html)

    def test_inline_images_alone_load_the_fallback_script(self):
        self.assertIn("image-fallback.js", self.page(has_images=True))

    def test_long_summary_is_truncated_in_meta_tags_only_there(self):
        summary = " ".join(["lengthy"] * 200)
        html = self.page(summary=summary)
        description = update_website.truncate_description(summary)
        self.assertIn(f'<meta name="description" content="{description}">', html)
        self.assertIn(f'<meta property="og:description" content="{description}">', html)
        self.assertNotIn(summary, html)

    def test_post_nav_labels_and_titles(self):
        self.build_posts([
            self.post("newest", title="Newest"),
            self.post("middle", title="Middle & more"),
            self.post("oldest", title="Oldest"),
        ])
        html = self.written["tangents/middle/index.html"]
        self.assertIn('<a class="nav-prev" href="../../tangents/oldest/"><span class="nav-label">Previous: </span>'
                      '<span class="nav-title">Oldest</span></a>', html)
        self.assertIn('<a class="nav-next" href="../../tangents/newest/"><span class="nav-label">Next: </span>'
                      '<span class="nav-title">Newest</span></a>', html)
        self.assertNotIn("Previous post", html)

    def test_back_button_links_to_the_index(self):
        self.assertIn('<a class="back-button" href="../../tangents/">', self.page())


class TestPostRebuild(BuildCaptureMixin, unittest.TestCase):
    """Drive should_build's incremental path with a cache that matches every dep."""

    def setUp(self):
        super().setUp()
        self.page_rel = "tangents/a-post/index.html"
        self.page_abs = os.path.join(update_website.ROOT_DIR, "tangents", "a-post", "index.html")
        real_exists = os.path.exists
        self.cache_patches = [
            mock.patch.dict(update_website._PREV_OUTPUTS, clear=True),
            mock.patch.dict(update_website._PREV_SOURCES, clear=True),
            mock.patch.dict(update_website._NEW_OUTPUTS, clear=True),
            mock.patch.dict(update_website._HASH_CACHE, clear=True),
            mock.patch.object(update_website, "SKIPPED_PAGES", 0),
            mock.patch.object(update_website, "GLOBAL_DIRTY", False),
            mock.patch.object(update_website, "CACHE_MISSING", False),
            mock.patch("os.path.exists", lambda path: path == self.page_abs or real_exists(path)),
        ]
        for patch in self.cache_patches:
            patch.start()

    def tearDown(self):
        for patch in self.cache_patches:
            patch.stop()
        super().tearDown()

    def github_post(self):
        return self.post(body_html='<p>Body.</p><div class="repo-panel">old panel</div>')

    def build_against_matching_cache(self, stale_dep=None):
        self.build_posts([self.github_post()])
        deps = update_website._NEW_OUTPUTS[self.page_rel]
        update_website._PREV_OUTPUTS[self.page_rel] = list(deps)
        for dep in deps:
            update_website._PREV_SOURCES[dep] = update_website.source_hash(dep)
        if stale_dep:
            update_website._PREV_SOURCES[stale_dep] = "hash-before-the-edit"
        self.written.clear()
        with mock.patch.object(update_website, "FORCE", False):
            self.build_posts([self.github_post()])
        return self.page_rel in self.written

    def test_unchanged_sources_skip_the_post(self):
        self.assertFalse(self.build_against_matching_cache())

    def test_repo_panel_template_edit_rebuilds_a_post_using_the_github_directive(self):
        for template_rel in update_website.REPO_PANEL_TEMPLATE_RELS:
            with self.subTest(template=template_rel):
                self.assertTrue(self.build_against_matching_cache(stale_dep=template_rel))


class TestListPage(BuildCaptureMixin, unittest.TestCase):
    def index(self, posts):
        self.build_lists(posts)
        return self.written["tangents/index.html"]

    def test_relative_feature_image_resolves_from_the_list_page(self):
        html = self.index([self.post(feature_image="cover.png")])
        self.assertIn('<li class="post-item has-image">', html)
        self.assertIn('<a class="post-item-image" href="../tangents/a-post/" tabindex="-1" aria-hidden="true">'
                      '<img src="../tangents/a-post/cover.png" alt="" loading="lazy"></a>', html)
        self.assertIn("js/image-fallback.js", html)

    def test_relative_feature_image_resolves_from_a_tag_page(self):
        self.build_lists([self.post(feature_image="cover.png", tags=["Lua"])])
        html = self.written["tangents/tag/lua/index.html"]
        self.assertIn('<img src="../../../tangents/a-post/cover.png"', html)

    def test_absolute_and_root_relative_images_stay_as_written(self):
        html = self.index([
            self.post("one", feature_image="https://example.com/a.png", published=date(2026, 7, 2)),
            self.post("two", feature_image="/img/xedur.png"),
        ])
        self.assertIn('<img src="https://example.com/a.png"', html)
        self.assertIn('<img src="/img/xedur.png"', html)

    def test_row_without_image_has_no_thumbnail(self):
        html = self.index([self.post()])
        self.assertIn('<li class="post-item">', html)
        self.assertNotIn("post-item-image", html)
        self.assertNotIn("image-fallback.js", html)

    def test_long_summary_is_cut_after_160_characters(self):
        summary = "x" * 150 + " " + "y" * 150
        html = self.index([self.post(summary=summary)])
        self.assertIn('<p class="post-item-summary">' + summary[:160] + '...</p>', html)

    def test_short_summary_stays_whole(self):
        html = self.index([self.post(summary="Short & sweet.")])
        self.assertIn('<p class="post-item-summary">Short &amp; sweet.</p>', html)

    def test_tag_chips_sort_by_count_then_name_with_data(self):
        html = self.index([
            self.post("one", tags=["beta", "Alpha"], published=date(2026, 7, 3)),
            self.post("two", tags=["beta", "gamma"], published=date(2026, 7, 2)),
        ])
        order = [html.index(f'data-tag="{name}"') for name in ("beta", "Alpha", "gamma")]
        self.assertEqual(order, sorted(order))
        self.assertIn('data-tag="beta" data-count="2"', html)
        self.assertIn('<div class="tag-tools" hidden>', html)
        self.assertIn('<option value="count-desc">Most tangents</option>', html)
        self.assertIn('<input id="tag-search" type="search"', html)
        self.assertIn('<button type="button" class="tag-reset">Clear all</button>', html)
        self.assertIn("js/tag-filter.js", html)

    def test_no_tags_means_no_tag_tools(self):
        html = self.index([self.post()])
        self.assertNotIn("tag-tools", html)
        self.assertNotIn("tag-filter.js", html)


if __name__ == "__main__":
    unittest.main()


class TestContactPanel(BuildCaptureMixin, unittest.TestCase):
    def test_post_page_ends_with_the_contact_panel_without_a_section_number(self):
        self.build_posts([self.post()])
        html = self.written["tangents/a-post/index.html"]
        self.assertIn('<span class="anchor" id="contact"></span>', html)
        self.assertLess(html.index('class="post-nav"'), html.index('id="contact"'))
        self.assertNotIn("section-index", html)
        self.assertNotIn("{{contactIndex}}", html)

    def test_every_list_page_carries_the_contact_panel(self):
        posts = [self.post(f"post-{i:02d}", tags=["Lua"]) for i in range(11)]
        self.build_lists(posts)
        for page in ("tangents/index.html", "tangents/2/index.html", "tangents/tag/lua/index.html"):
            with self.subTest(page=page):
                self.assertEqual(self.written[page].count('id="contact"'), 1)


    def test_demo_index_carries_the_contact_panel(self):
        update_website.build_demo_index(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("demo-index.html"), {}, {},
        )
        html = self.written["demo/index.html"]
        self.assertEqual(html.count('id="contact"'), 1)
        self.assertNotIn("{{contactSection}}", html)


class TestNavbarContactLink(unittest.TestCase):
    def page(self, body, base_path):
        return update_website.wrap_in_base(
            "{{navbar}}\n{{bodyContent}}", update_website.load_file("navbar.html"), "",
            body, "Title", base_path=base_path,
        )

    def test_page_with_a_contact_panel_links_to_its_own(self):
        html = self.page('<span class="anchor" id="contact"></span>', "../../")
        self.assertEqual(html.count('href="#contact"'), 2)
        self.assertNotIn('href="../../#contact"', html)

    def test_page_without_a_panel_links_to_the_frontpage(self):
        html = self.page("<p>Body.</p>", "../../")
        self.assertEqual(html.count('href="../../#contact"'), 2)
        self.assertNotIn("{{contactHref}}", html)
