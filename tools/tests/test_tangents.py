"""Unit tests for Tangents post loading and page building in update_website.py.

Each test that loads posts runs against a throwaway root, so the repo's posts,
dates file, and pages are never read or written.
"""

import os
import shutil
import struct
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

# Make the tools importable regardless of the CWD the tests are run from.
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "tests"))

import markdown_engine
import update_website
from markdown_engine import FrontMatterError, parse_front_matter
from test_social_cards import case_folding_isfile, needs_pillow


def front_matter(**keys):
    lines = ["---"] + [f"{key}: {value}" for key, value in keys.items()] + ["---", "", "Body."]
    return "\n".join(lines)


def save_image(path, size, **options):
    from PIL import Image

    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", size, "red").save(path, **options)


def exif_jpeg(byte_order, orientation, size):
    """A JPEG header holding only an Exif Orientation tag and a frame header."""
    order = "<" if byte_order == b"II" else ">"
    tiff = (byte_order + struct.pack(order + "HIH", 42, 8, 1)
            + struct.pack(order + "HHIHHI", 0x0112, 3, 1, orientation, 0, 0))
    app1 = b"Exif\0\0" + tiff
    width, height = size
    sof = struct.pack(">BHHB", 8, height, width, 1) + b"\x01\x11\x00"
    return (b"\xff\xd8\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
            + b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof)


def folded_path(path):
    """The file a case-ignoring mount opens for path."""
    directory, name = os.path.split(path)
    return next((os.path.join(directory, entry) for entry in os.listdir(directory)
                 if entry.lower() == name.lower()), path)


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


@needs_pillow
class TestImageSize(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="image-size-test-")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_header_sizes_match_the_encoded_size(self):
        from PIL import Image

        cases = {
            "a.png": {},
            "a.gif": {},
            "baseline.jpg": {},
            "progressive.jpg": {"progressive": True},
            "lossy.webp": {},
            "lossless.webp": {"lossless": True},
            "extended.webp": {"exif": Image.Exif().tobytes()},
        }
        for name, options in cases.items():
            with self.subTest(name=name):
                path = os.path.join(self.dir, name)
                save_image(path, (1201, 631), **options)
                self.assertEqual(update_website.image_size(path), (1201, 631))

        with open(os.path.join(self.dir, "progressive.jpg"), "rb") as f:
            self.assertIn(b"\xff\xc2", f.read())
        chunks = set()
        for name in ("lossy.webp", "lossless.webp", "extended.webp"):
            with open(os.path.join(self.dir, name), "rb") as f:
                chunks.add(f.read(16)[12:])
        self.assertEqual(chunks, {b"VP8 ", b"VP8L", b"VP8X"})

    def test_exif_quarter_turn_swaps_jpeg_size(self):
        path = os.path.join(self.dir, "photo.jpg")
        for byte_order in (b"II", b"MM"):
            for orientation, expected in ((1, (400, 100)), (3, (400, 100)), (6, (100, 400)), (8, (100, 400))):
                with self.subTest(byte_order=byte_order, orientation=orientation):
                    with open(path, "wb") as f:
                        f.write(exif_jpeg(byte_order, orientation, (400, 100)))
                    self.assertEqual(update_website.image_size(path), expected)

    def test_other_files_have_no_size(self):
        path = os.path.join(self.dir, "logo.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>')
        self.assertIsNone(update_website.image_size(path))


class TestInlineImageSizes(TangentsRootMixin, unittest.TestCase):
    def image(self, name):
        return os.path.join(self.root, "tangents", "a-post", name)

    def load_body(self, body, **keys):
        self.write_post("a-post", **keys)
        with open(os.path.join(self.src, "a-post.md"), "a", encoding="utf-8") as f:
            f.write(f"\n{body}\n")
        return update_website.load_tangents_posts()[0]

    @needs_pillow
    def test_local_png_and_jpeg_get_their_size(self):
        save_image(self.image("shot.png"), (40, 20))
        save_image(self.image("photo.jpg"), (30, 10), progressive=True)
        post = self.load_body('[[image src="shot.png" alt="s"]]\n\n[[image src="photo.jpg" alt="p"]]')
        self.assertIn('alt="s" loading="lazy" width="40" height="20">', post["body_html"])
        self.assertIn('alt="p" loading="lazy" width="30" height="10">', post["body_html"])
        self.assertEqual([rel.rsplit("/", 1)[1] for rel in post["image_rels"]], ["shot.png", "photo.jpg"])

    @needs_pillow
    def test_author_sizes_are_kept(self):
        save_image(self.image("shot.png"), (40, 20))
        post = self.load_body('[[image src="shot.png" alt="s" width="4" height="2"]]')
        self.assertIn('alt="s" loading="lazy" width="4" height="2">', post["body_html"])
        self.assertEqual(post["image_rels"], [])

    def test_remote_and_missing_images_get_no_size(self):
        post = self.load_body(
            '[[image src="https://example.com/a.png" alt="r"]]\n\n[[image src="missing.png" alt="m"]]'
        )
        self.assertIn('alt="r" loading="lazy">', post["body_html"])
        self.assertIn('alt="m" loading="lazy">', post["body_html"])
        self.assertEqual(self.warnings(), ["tangents/a-post.md: image not found: 'missing.png'"])

    @needs_pillow
    def test_wrong_letter_case_counts_as_missing(self):
        save_image(self.image("cover.png"), (40, 20))
        save_image(self.image("shot.png"), (40, 20))
        real_isfile = os.path.isfile
        with mock.patch("os.path.isfile", lambda path: real_isfile(path) or case_folding_isfile(path)):
            post = self.load_body('[[image src="Shot.png" alt="s"]]', featureImage="Cover.png")
        self.assertIn('alt="s" loading="lazy">', post["body_html"])
        self.assertEqual(self.warnings(), [
            "tangents/a-post.md: image not found: 'Cover.png'",
            "tangents/a-post.md: image not found: 'Shot.png'",
        ])

    @needs_pillow
    def test_cut_short_image_warns_and_gets_no_size(self):
        from PIL import Image

        cases = {
            "a.png": ({}, lambda data: 20),
            "a.gif": ({}, lambda data: 8),
            "before-frame.jpg": ({}, lambda data: 10),
            "after-sof.jpg": ({}, lambda data: data.index(b"\xff\xc0") + 4),
            "lossy.webp": ({}, lambda data: 26),
            "lossless.webp": ({"lossless": True}, lambda data: 23),
            "extended.webp": ({"exif": Image.Exif().tobytes()}, lambda data: 27),
        }
        for name, (options, cut) in cases.items():
            with self.subTest(name=name):
                del update_website.BUILD_LOG_EVENTS[:]
                save_image(self.image(name), (40, 20), **options)
                with open(self.image(name), "rb") as f:
                    data = f.read()
                with open(self.image(name), "wb") as f:
                    f.write(data[:cut(data)])

                post = self.load_body(f'[[image src="{name}" alt="x"]]')
                self.assertIn('alt="x" loading="lazy">', post["body_html"])
                self.assertEqual(self.warnings(), [
                    f"tangents/a-post.md: image size unreadable (file cut short or damaged): '{name}'"
                ])

    @needs_pillow
    def test_replaced_image_does_not_date_the_post_as_updated(self):
        save_image(self.image("shot.png"), (40, 20))
        self.load_body('[[image src="shot.png" alt="s"]]', published="2026-10-01")
        save_image(self.image("shot.png"), (80, 40))
        post = update_website.load_tangents_posts()[0]
        self.assertIn('width="80" height="40"', post["body_html"])
        self.assertIsNone(post["updated"])

    @needs_pillow
    def test_sizes_are_read_without_pillow(self):
        save_image(self.image("shot.png"), (40, 20))
        with mock.patch.dict(sys.modules, {"PIL": None}):
            post = self.load_body('[[image src="shot.png" alt="s"]]')
        self.assertIn('width="40" height="20"', post["body_html"])


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

    def github_post(self, **overrides):
        return self.post(body_html='<p>Body.</p><div class="repo-panel">old panel</div>', **overrides)

    def build_against_matching_cache(self, stale_dep=None, **rebuild_overrides):
        self.build_posts([self.github_post()])
        deps = update_website._NEW_OUTPUTS[self.page_rel]
        update_website._PREV_OUTPUTS[self.page_rel] = list(deps)
        for dep in deps:
            update_website._PREV_SOURCES[dep] = update_website.source_hash(dep)
        if stale_dep:
            update_website._PREV_SOURCES[stale_dep] = "hash-before-the-edit"
        self.written.clear()
        with mock.patch.object(update_website, "FORCE", False):
            self.build_posts([self.github_post(**rebuild_overrides)])
        return self.page_rel in self.written

    def test_unchanged_sources_skip_the_post(self):
        self.assertFalse(self.build_against_matching_cache())

    def test_repo_panel_template_edit_rebuilds_a_post_using_the_github_directive(self):
        for template_rel in update_website.REPO_PANEL_TEMPLATE_RELS:
            with self.subTest(template=template_rel):
                self.assertTrue(self.build_against_matching_cache(stale_dep=template_rel))

    def test_resized_card_rebuilds_the_post_with_its_new_dimensions(self):
        rebuilt = self.build_against_matching_cache(
            stale_dep="tangents/a-post/a-post-social.png", og_image_size=(1000, 525)
        )
        self.assertTrue(rebuilt)
        html = self.written[self.page_rel]
        self.assertIn('<meta property="og:image:width" content="1000">', html)
        self.assertIn('<meta property="og:image:height" content="525">', html)


class TestInlineImageRebuild(TangentsRootMixin, unittest.TestCase):
    """Load and build a post twice over, keeping the incremental cache between builds."""

    def setUp(self):
        super().setUp()
        self.written = {}
        self.build_patches = [
            mock.patch.object(update_website, "ROOT_DIR", self.root),
            mock.patch.object(update_website, "write_file", self.capture),
            mock.patch.dict(update_website._PREV_OUTPUTS, clear=True),
            mock.patch.dict(update_website._PREV_SOURCES, clear=True),
            mock.patch.dict(update_website._NEW_OUTPUTS, clear=True),
            mock.patch.dict(update_website._HASH_CACHE, clear=True),
            mock.patch.object(update_website, "SKIPPED_PAGES", 0),
            mock.patch.object(update_website, "GLOBAL_DIRTY", False),
            mock.patch.object(update_website, "CACHE_MISSING", False),
            mock.patch.object(update_website, "FORCE", False),
        ]
        for patch in self.build_patches:
            patch.start()

    def tearDown(self):
        for patch in self.build_patches:
            patch.stop()
        super().tearDown()

    def capture(self, filepath, content):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self.written[os.path.relpath(filepath, self.root).replace(os.sep, "/")] = content

    def build(self):
        self.written.clear()
        posts = update_website.load_tangents_posts()
        for post in posts:
            post.update(og_image="https://www.xedur.com/tangents/a-post/a-post-social.png", og_image_size=(1200, 630))
        update_website.build_tangents_posts(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("tangents-post.html"), posts,
        )

        # Save the cache as the end of a build does.
        update_website._PREV_OUTPUTS.clear()
        update_website._PREV_OUTPUTS.update(update_website._NEW_OUTPUTS)
        for deps in update_website._NEW_OUTPUTS.values():
            for dep in deps:
                update_website._PREV_SOURCES[dep] = update_website.source_hash(dep)
        update_website._HASH_CACHE.clear()
        return self.written.get("tangents/a-post/index.html")

    @needs_pillow
    def test_replaced_image_rebuilds_the_post_with_its_new_size(self):
        image = os.path.join(self.root, "tangents", "a-post", "shot.png")
        save_image(image, (40, 20))
        self.write_post("a-post")
        with open(os.path.join(self.src, "a-post.md"), "a", encoding="utf-8") as f:
            f.write('\n[[image src="shot.png" alt="s"]]\n')

        self.assertIn('width="40" height="20"', self.build())
        self.assertIsNone(self.build())
        save_image(image, (80, 40))
        self.assertIn('width="80" height="40"', self.build())

    @needs_pillow
    def test_letter_case_rename_rebuilds_the_post(self):
        image = os.path.join(self.root, "tangents", "a-post", "shot.png")
        save_image(image, (40, 20))
        self.write_post("a-post")
        with open(os.path.join(self.src, "a-post.md"), "a", encoding="utf-8") as f:
            f.write('\n[[image src="shot.png" alt="s"]]\n')

        real_isfile = os.path.isfile
        real_sha256 = update_website._file_sha256
        with mock.patch("os.path.isfile", lambda path: real_isfile(path) or case_folding_isfile(path)), \
                mock.patch.object(update_website, "_file_sha256", lambda path: real_sha256(folded_path(path))):
            self.assertIn('width="40" height="20"', self.build())

            os.rename(image, os.path.join(self.root, "tangents", "a-post", "Shot.png"))
            page = self.build()
            self.assertIsNotNone(page)
            self.assertIn('alt="s" loading="lazy">', page)

            os.rename(os.path.join(self.root, "tangents", "a-post", "Shot.png"), image)
            self.assertIn('width="40" height="20"', self.build())


class TestListPage(BuildCaptureMixin, unittest.TestCase):
    def index(self, posts):
        self.build_lists(posts)
        return self.written["tangents/index.html"]

    def test_relative_feature_image_resolves_from_the_list_page(self):
        html = self.index([self.post(feature_image="cover.png")])
        self.assertIn('<li class="post-item has-image">', html)
        self.assertIn('<a class="post-item-image" href="../tangents/a-post/" tabindex="-1" aria-hidden="true">'
                      '<img src="../tangents/a-post/cover.png" alt="" fetchpriority="high"></a>', html)
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

    def test_logo_is_embedded_in_both_navs(self):
        html = self.page("<p>Body.</p>", "../../")
        self.assertEqual(html.count('src="data:image/png;base64,'), 2)
        self.assertNotIn("{{navLogo}}", html)


class TestSlugRules(TangentsRootMixin, unittest.TestCase):
    def test_all_digit_slug_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "not all digits"):
            self.load_one("2")

    def test_slugs_mixing_digits_with_letters_or_hyphens_are_accepted(self):
        for slug in ("v2", "2-fast", "2026-recap"):
            with self.subTest(slug=slug):
                self.assertTrue(update_website.TANGENT_SLUG_RE.match(slug))

    def test_shared_regex_rejects_all_digit_slugs(self):
        self.assertIsNone(update_website.TANGENT_SLUG_RE.match("12"))


class TestListThumbnailLoading(BuildCaptureMixin, unittest.TestCase):
    def build_eleven(self):
        posts = [
            self.post(f"post-{n}", feature_image="cover.png", tags=["Lua"], published=date(2026, 7, 20 - n))
            for n in range(11)
        ]
        self.build_lists(posts)

    def test_first_row_of_every_list_page_is_eager_and_high_priority(self):
        self.build_eleven()
        for page_rel, first_slug in (
            ("tangents/index.html", "post-0"),
            ("tangents/2/index.html", "post-10"),
            ("tangents/tag/lua/index.html", "post-0"),
            ("tangents/tag/lua/2/index.html", "post-10"),
        ):
            with self.subTest(page=page_rel):
                html = self.written[page_rel]
                self.assertEqual(html.count('fetchpriority="high"'), 1)
                self.assertRegex(html, r'tangents/' + first_slug + r'/cover\.png" alt="" fetchpriority="high">')

    def test_later_rows_stay_lazy(self):
        self.build_eleven()
        html = self.written["tangents/index.html"]
        self.assertEqual(html.count('loading="lazy"'), 9)
        self.assertRegex(html, r'tangents/post-1/cover\.png" alt="" loading="lazy">')


class TestFeedDiscovery(BuildCaptureMixin, unittest.TestCase):
    def feed_link(self, base_path):
        return ('<link rel="alternate" type="application/atom+xml" title="XeduR - Tangents" href="'
                + base_path + 'tangents/feed.xml">')

    def test_every_list_page_links_the_feed(self):
        posts = [self.post(f"post-{n}", tags=["Lua"], published=date(2026, 7, 20 - n)) for n in range(11)]
        self.build_lists(posts)
        for page_rel, base_path in (
            ("tangents/index.html", "../"),
            ("tangents/2/index.html", "../../"),
            ("tangents/tag/lua/index.html", "../../../"),
            ("tangents/tag/lua/2/index.html", "../../../../"),
        ):
            with self.subTest(page=page_rel):
                self.assertIn(self.feed_link(base_path), self.written[page_rel])

    def test_post_page_links_the_feed(self):
        self.build_posts([self.post()])
        self.assertIn(self.feed_link("../../"), self.written["tangents/a-post/index.html"])


QUOTE = "{{basePath}} {{contactSection}}"
SHOWN = "&#123;&#123;basePath}} &#123;&#123;contactSection}}"


class FilledPageMixin:
    def assert_filled(self, html):
        self.assertEqual(html.count('id="contact"'), 1)
        # main() fills inlineStyles into the base template before any builder runs.
        self.assertNotIn("{{", html.replace("{{inlineStyles}}", ""))


class TestPlaceholdersInPostText(FilledPageMixin, BuildCaptureMixin, unittest.TestCase):
    """Author text that quotes this site's templates shows literally, and every structural placeholder still fills."""

    def setUp(self):
        super().setUp()
        repo_panel = update_website.load_file("repo-panel.html")

        def github(params, meta, base_path):
            return repo_panel.replace("{{repository}}", update_website.escape_html(params["url"])).rstrip("\n")

        markdown_engine.register_directive("github", github, ("repo", "url"))
        self.addCleanup(markdown_engine.DIRECTIVES.pop, "github", None)

    def quoting_post(self):
        body = "\n\n".join([
            f"Text {QUOTE}.",
            f"Code `{QUOTE}`.",
            f"```\n{QUOTE}\n```",
            f'[[image src="a.png" alt="{QUOTE}" caption="{QUOTE}"]]',
            f'[[youtube id="dQw4w9WgXcQ" title="{QUOTE}"]]',
            f'[[callout title="{QUOTE}"]]\nx\n[[/callout]]',
            f'[[github url="https://github.com/x/{QUOTE}"]]',
        ])
        body_html, _ = markdown_engine.render_markdown(body)
        return self.post(title=f"Title {QUOTE}", summary=f"Summary {QUOTE}", tags=[f"Tag {QUOTE}"], body_html=body_html)

    def test_post_page(self):
        self.build_posts([self.quoting_post()])
        html = self.written["tangents/a-post/index.html"]
        self.assert_filled(html)
        for shown in (
            f"<title>XeduR - Title {SHOWN}</title>",
            f'<meta name="description" content="Summary {SHOWN}">',
            f'<meta property="og:title" content="Title {SHOWN}">',
            '"headline": "Title \\u007b\\u007bbasePath}} \\u007b\\u007bcontactSection}}"',
            f">Tag {SHOWN}</a>",
            f"<p>Text {SHOWN}.</p>",
            f"<code>{SHOWN}</code>.",
            f'<pre tabindex="0"><code>{SHOWN}</code></pre>',
            f'alt="{SHOWN}"',
            f"<figcaption>{SHOWN}</figcaption>",
            f'data-video-title="{SHOWN}"',
            f'<p class="md-callout-title">{SHOWN}</p>',
            f'href="https://github.com/x/{SHOWN}"',
            'src="../../img/github_lockup_white.svg"',
        ):
            with self.subTest(shown=shown):
                self.assertIn(shown, html)
        self.assertIn(f'<h1 class="title-tangent">Title {SHOWN}</h1>', html)

    def test_list_and_tag_pages(self):
        self.build_lists([self.quoting_post()])
        for page in ("tangents/index.html", "tangents/tag/tag-basepath-contactsection/index.html"):
            with self.subTest(page=page):
                html = self.written[page]
                self.assert_filled(html)
                self.assertIn(f"Title {SHOWN}", html)
                self.assertIn(f"Summary {SHOWN}", html)
                self.assertIn(f">Tag {SHOWN}</a>", html)
        self.assertIn(f'Tangents tagged "Tag {SHOWN}"', self.written["tangents/tag/tag-basepath-contactsection/index.html"])


class TestPlaceholdersInDemoText(FilledPageMixin, BuildCaptureMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="demo-placeholder-test-")
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "demo", "quoting", "app"))
        open(os.path.join(self.root, "demo", "quoting", "app", "quoting.bin"), "wb").close()
        for patch in (
            mock.patch.object(update_website, "OUTPUT_DIR", self.root),
            mock.patch.object(update_website, "_PREV_APP_LISTINGS", {}),
            mock.patch.object(update_website, "_NEW_APP_LISTINGS", {}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.demo = {
            "folder": "quoting",
            "title": f"Demo {QUOTE}",
            "descriptionShort": f"Short {QUOTE}",
            "tech": f"Lua {QUOTE}",
            "_body": f"Body {QUOTE}",
        }
        self.manifests = {"games": {
            "sectionIndex": f"01 {QUOTE}",
            "sectionTitle": f"Section {QUOTE}",
            "sectionDescription": f"About {QUOTE}",
            "demos": ["quoting"],
        }}

    def capture(self, filepath, content):
        self.written[os.path.relpath(filepath, update_website.OUTPUT_DIR).replace(os.sep, "/")] = content

    def test_demo_page_and_app_loader(self):
        update_website.build_demo_pages(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("demo.html"), update_website.load_file("iframe.html"),
            self.manifests, {"quoting": self.demo},
        )
        page = self.written["demo/quoting/index.html"]
        self.assert_filled(page)
        self.assertIn(f'<h1 class="title-demo">Demo {SHOWN}<a ', page)
        self.assertIn(f"<p>Body {SHOWN}</p>", page)

        loader = self.written["demo/quoting/app/index.html"]
        self.assertNotIn("{{", loader)
        self.assertIn(f"<title>Demo {SHOWN}</title>", loader)
        self.assertIn(f'content="Short {SHOWN}"', loader)
        self.assertIn('"quoting.bin"', loader)

    def test_demo_index(self):
        update_website.build_demo_index(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("demo-index.html"), self.manifests, {"quoting": self.demo},
        )
        html = self.written["demo/index.html"]
        self.assert_filled(html)
        self.assertIn(f'<a href="quoting/">Demo {SHOWN}</a>', html)

    def test_frontpage_sections_and_cards(self):
        load_json = update_website.load_json

        def quoting_load_json(name):
            data = load_json(name)
            return {**data, "contactSectionIndex": f"05 {QUOTE}"} if name == "frontpage.json" else data

        with mock.patch.object(update_website, "load_json", quoting_load_json):
            update_website.build_frontpage(
                update_website.load_file("base.html"), "", "", update_website.load_file("contact.html"),
                "{{games}}\n{{contact}}", self.manifests, {"quoting": self.demo},
            )
        html = self.written["index.html"]
        self.assert_filled(html)
        for value in ("01", "Section", "About", "Demo", "Screenshot of Demo", "Short", "Lua", "05"):
            with self.subTest(value=value):
                self.assertIn(f"{value} {SHOWN}", html)

    def test_external_card_href_and_image(self):
        card = update_website.generate_card(
            {"externalUrl": f"https://e/{QUOTE}", "image": f"img/{QUOTE}.png", "title": "T", "descriptionShort": "d"},
            update_website.load_file("card.html"),
        )
        self.assertIn(f'href="https://e/{SHOWN}"', card)
        self.assertIn(f'src="img/{SHOWN}.png"', card)

    def test_meta_keywords(self):
        html = update_website.wrap_in_base(
            update_website.load_file("base.html"), "", "", "<p>x</p>", "T",
            meta_keywords=f"Lua, {QUOTE}", base_path="../",
        )
        self.assertIn(f'<meta name="keywords" content="Lua, {SHOWN}">', html)
