"""Unit tests for the social card generator and its wiring in update_website.py.

Expected values come from the card contract (1200x630, the card paths, the
fallback chain, and the CSS text metrics in tools/css/styles.css), not from
observed output. Every test that writes runs inside a temporary root, so the
repo's committed cards and manifest are never touched.
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

# Make the tools importable regardless of the CWD the tests are run from.
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS_DIR)

import generate_social_images as gen
import update_website

try:
    from PIL import Image, ImageChops, ImageDraw
    HAVE_PILLOW = True
except ImportError:
    HAVE_PILLOW = False

needs_pillow = unittest.skipUnless(HAVE_PILLOW, "Pillow is not installed")

SITE = update_website.SITE_BASE_URL
STYLES_CSS = os.path.join(TOOLS_DIR, "css", "styles.css")


class TempRootMixin:
    """Point the generator at a throwaway root holding only the logo."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="social-cards-test-")
        os.makedirs(os.path.join(self.root, "img"))
        shutil.copy(os.path.join(gen.ROOT_DIR, "img", "xedur.png"), os.path.join(self.root, "img"))
        self.patches = [
            mock.patch.object(gen, "ROOT_DIR", self.root),
            mock.patch.object(gen, "MANIFEST_FILE", os.path.join(self.root, "social_images.json")),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        shutil.rmtree(self.root)

    def touch(self, rel):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"card")


class TestNaming(unittest.TestCase):
    def test_demo_card_path(self):
        self.assertEqual(gen.demo_card_rel("autotile"), "demo/autotile/autotile-social.png")

    def test_frontpage_card_path(self):
        self.assertEqual(gen.FRONTPAGE_CARD_REL, "img/xedur-social.png")

    def test_card_demos_use_page_title_and_skip_external(self):
        demos_by_stem = {
            "b-demo": {"folder": "b-demo", "title": "Front Matter Title", "type": "standalone"},
            "a-demo": {"folder": "a-demo", "title": "Autotile"},
            "ext": {"title": "Elsewhere", "externalUrl": "https://example.com/"},
        }
        with mock.patch.object(update_website, "load_standalone_config",
                               return_value={"title": "Config Title"}):
            self.assertEqual(update_website.social_card_demos(demos_by_stem), [
                {"folder": "a-demo", "title": "Autotile"},
                {"folder": "b-demo", "title": "Config Title"},
            ])

    def test_standalone_without_config_title_uses_front_matter(self):
        demo = {"folder": "b-demo", "title": "Front Matter Title", "type": "standalone"}
        with mock.patch.object(update_website, "load_standalone_config", return_value={}):
            self.assertEqual(update_website.demo_page_title(demo), "Front Matter Title")

    def test_prune_patterns_cover_new_cards_only(self):
        def generated(rel):
            return update_website._is_generated_output(rel)

        self.assertTrue(generated("img/xedur-social.png"))
        self.assertTrue(generated("demo/autotile/autotile-social.png"))
        self.assertFalse(generated("demo/autotile/other-social.png"))
        self.assertFalse(generated("demo/autotile/autotile-large.jpg"))
        self.assertFalse(generated("img/xedur.png"))

    def test_inputs_hash_separates_kinds(self):
        self.assertNotEqual(gen._inputs_hash("post", "Same"), gen._inputs_hash("demo", "Same"))
        self.assertNotEqual(gen._inputs_hash("demo", "A"), gen._inputs_hash("demo", "B"))


class TestFallback(TempRootMixin, unittest.TestCase):
    def test_own_card_wins(self):
        self.touch("img/xedur-social.png")
        self.touch("demo/autotile/autotile-social.png")
        self.assertEqual(gen.existing_card("demo/autotile/autotile-social.png"),
                         "demo/autotile/autotile-social.png")

    def test_missing_card_falls_back_to_frontpage_card(self):
        self.touch("img/xedur-social.png")
        self.assertEqual(gen.existing_card("demo/autotile/autotile-social.png"), "img/xedur-social.png")

    def test_no_cards_falls_back_to_static_default(self):
        self.assertIsNone(gen.existing_card("demo/autotile/autotile-social.png"))
        default = update_website.load_json("frontpage.json")["seo"]["ogImage"]
        self.assertEqual(update_website.social_card_image("demo/autotile/autotile-social.png"),
                         (default, 0, 0))

    def test_card_url_declares_card_size(self):
        self.touch("img/xedur-social.png")
        self.assertEqual(update_website.social_card_image(),
                         (f"{SITE}/img/xedur-social.png", 1200, 630))


class TestCssMetrics(unittest.TestCase):
    """The card config must echo the stylesheet's text metrics."""

    @classmethod
    def setUpClass(cls):
        with open(STYLES_CSS, "r", encoding="utf-8") as f:
            cls.css = f.read()
        cls.config = gen.load_card_config()

    def rule(self, selector):
        match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(match, selector)
        return match.group(1)

    def value(self, block, prop):
        match = re.search(r"(?m)^\s*" + re.escape(prop) + r"\s*:\s*([^;]+);", block)
        self.assertIsNotNone(match, prop)
        return match.group(1).strip()

    def test_tracking_matches_tokens(self):
        root = self.rule(":root")
        display = float(self.value(root, "--display-tracking").removesuffix("em"))
        label = float(self.value(root, "--label-tracking").removesuffix("em"))
        styles = self.config["styles"]
        self.assertEqual(styles["heading"]["tracking"], display)
        self.assertEqual(styles["section"]["tracking"], display)
        self.assertEqual(styles["label"]["tracking"], label)

    def test_line_heights_match_elements(self):
        styles = self.config["styles"]
        self.assertEqual(styles["heading"]["lineHeight"], float(self.value(self.rule(".hero h1"), "line-height")))
        self.assertEqual(styles["section"]["lineHeight"], float(self.value(self.rule("h1"), "line-height")))
        self.assertEqual(styles["name"]["lineHeight"], float(self.value(self.rule("p"), "line-height")))
        self.assertEqual(styles["lead"]["lineHeight"], float(self.value(self.rule("p"), "line-height")))

    def test_palette_matches_tokens(self):
        root = self.rule(":root")
        colors = self.config["colors"]
        for key, token in (("background", "--bg"), ("line", "--line"), ("text", "--text"),
                           ("muted", "--muted"), ("accent", "--accent")):
            self.assertEqual(colors[key].upper(), self.value(root, token).upper(), key)


@needs_pillow
class TestTextMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = gen.load_card_config()

    def test_line_advance_is_size_times_line_height(self):
        for name, spec in self.config["styles"].items():
            for size in (24, 50, 88):
                style = gen.make_style(self.config, name, size)
                self.assertEqual(style.advance, round(size * spec["lineHeight"]), (name, size))

    def test_block_advances_by_line_height(self):
        style = gen.make_style(self.config, "name", 50)
        image = Image.new("RGB", (1200, 400))
        last = gen.draw_block(ImageDraw.Draw(image), 0, 20, ["One", "Two", "Three"], style)
        self.assertEqual(last, 20 + gen.cap_height(style) + 2 * round(50 * 1.6))
        self.assertEqual(gen.block_height(["One", "Two", "Three"], style), last - 20)

    def test_measured_width_equals_drawn_width(self):
        for name in ("heading", "label", "name"):
            style = gen.make_style(self.config, name, 64)
            text = style.prepare("Hämeenlinna Äyriäisiä")
            image = Image.new("RGB", (2000, 200))
            end = gen.draw_tracked(ImageDraw.Draw(image), 10, 120, text, style)
            self.assertAlmostEqual(end - 10, gen.tracked_width(text, style), places=6)
            ink_right = image.getbbox()[2]
            self.assertLessEqual(ink_right, end + 2, name)
            self.assertGreater(ink_right, end - 0.2 * style.size, name)

    def test_untracked_run_matches_whole_string_draw(self):
        style = gen.make_style(self.config, "name", 60)
        text = "AVATAR Typewriter Yo"
        tracked = Image.new("RGB", (1200, 200))
        whole = Image.new("RGB", (1200, 200))
        gen.draw_tracked(ImageDraw.Draw(tracked), 10, 120, text, style)
        ImageDraw.Draw(whole).text((10, 120), text, font=style.font, fill=style.color, anchor="ls")
        self.assertIsNone(ImageChops.difference(tracked, whole).getbbox())

    def test_ink_stays_inside_run_ending_in_kerned_pair(self):
        for name in ("name", "heading"):
            style = gen.make_style(self.config, name, 60)
            text = style.prepare("AVATAR Typewriter Yo")
            image = Image.new("RGB", (1600, 200))
            end = gen.draw_tracked(ImageDraw.Draw(image), 10, 120, text, style)
            self.assertLessEqual(image.getbbox()[2], end, name)

    def test_tracking_changes_width_by_gaps(self):
        style = gen.make_style(self.config, "heading", 100)
        plain = style.font.getlength("XEDUR")
        self.assertAlmostEqual(gen.tracked_width("XEDUR", style), plain + 4 * -2.0, places=6)

    def test_wrapped_lines_fit(self):
        style, lines = gen.fit_text(self.config, "name", "word " * 200, [44, 36], 1056, 2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith("..."))
        for line in lines:
            self.assertLessEqual(gen.tracked_width(line, style), 1056)


@needs_pillow
class TestRender(TempRootMixin, unittest.TestCase):
    def test_every_kind_is_1200x630_and_deterministic(self):
        for kind, text in (("frontpage", ""), ("tangents", ""), ("demo", "Pseudorandom Number Generator"),
                           ("post", "Kävin tänään Hämeenlinnassa ja söin äyriäisiä")):
            data = gen.render_card(kind, text)
            image = Image.open(io.BytesIO(data))
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(data, gen.render_card(kind, text), kind)

    def test_unknown_kind_raises(self):
        with self.assertRaises(gen.SocialImageError):
            gen.render_card("nope")

    def test_full_run_then_warm_run_writes_nothing(self):
        demos = [{"folder": "autotile", "title": "Autotile"}]
        first = gen.resolve_and_generate([], demos=demos)
        expected = {"tangents/tangents-social.png", "img/xedur-social.png",
                    "demo/autotile/autotile-social.png"}
        self.assertEqual(set(first["generated"]), expected)

        card = os.path.join(self.root, "demo", "autotile", "autotile-social.png")
        with open(card, "rb") as f:
            card_bytes = f.read()
        stamps = {rel: os.stat(os.path.join(self.root, rel)).st_mtime_ns for rel in expected}
        manifest_stamp = os.stat(gen.MANIFEST_FILE).st_mtime_ns

        second = gen.resolve_and_generate([], demos=demos)
        self.assertEqual(second["generated"], [])
        self.assertEqual(set(second["skipped"]), expected)
        for rel, stamp in stamps.items():
            self.assertEqual(os.stat(os.path.join(self.root, rel)).st_mtime_ns, stamp, rel)
        self.assertEqual(os.stat(gen.MANIFEST_FILE).st_mtime_ns, manifest_stamp)

        forced = gen.resolve_and_generate([], demos=demos, force=True)
        self.assertEqual(set(forced["generated"]), expected)
        with open(card, "rb") as f:
            self.assertEqual(f.read(), card_bytes)

    def test_removed_demo_leaves_manifest(self):
        gen.resolve_and_generate([], demos=[{"folder": "autotile", "title": "Autotile"}])
        result = gen.resolve_and_generate([], demos=[])
        self.assertNotIn("demo/autotile/autotile-social.png", result["generated"] + result["skipped"])
        self.assertNotIn("demo/autotile/autotile-social.png", gen._load_manifest())

    def test_untitled_demo_is_an_error(self):
        for title in ("", "   "):
            with self.assertRaises(gen.SocialImageError):
                gen.resolve_and_generate([], demos=[{"folder": "autotile", "title": title}])
        self.assertFalse(os.path.exists(os.path.join(self.root, "demo", "autotile", "autotile-social.png")))

    def test_warm_run_never_imports_pillow(self):
        demos = [{"folder": "autotile", "title": "Autotile"}]
        gen.resolve_and_generate([], demos=demos)
        with mock.patch.dict(sys.modules, {"PIL": None}), \
                mock.patch.object(gen, "render_card", wraps=gen.render_card) as render:
            result = gen.resolve_and_generate([], demos=demos)
        render.assert_not_called()
        self.assertEqual(result["generated"], [])

    def test_needed_render_without_pillow_fails_loudly(self):
        with mock.patch.dict(sys.modules, {"PIL": None}):
            with self.assertRaises(gen.SocialImageError):
                gen.resolve_and_generate([], demos=[])


class CaptureBuildsMixin(TempRootMixin):
    """Run page builders with their writes captured, never made."""

    def setUp(self):
        super().setUp()
        self.written = {}
        self.base = update_website.load_file("base.html")
        self.builder_patches = [
            mock.patch.object(update_website, "write_file", self.capture),
            mock.patch.object(update_website, "FORCE", True),
        ]
        for patch in self.builder_patches:
            patch.start()

    def tearDown(self):
        for patch in self.builder_patches:
            patch.stop()
        super().tearDown()

    def capture(self, filepath, content):
        self.written[os.path.relpath(filepath, update_website.ROOT_DIR).replace(os.sep, "/")] = content

    def meta(self, rel, prop):
        match = re.search(r'<meta (?:property|name)="' + re.escape(prop) + r'" content="([^"]*)">',
                          self.written[rel])
        return match.group(1) if match else None


class TestBuilderWiring(CaptureBuildsMixin, unittest.TestCase):
    """Builders point each page at its card."""

    def build_frontpage(self):
        update_website.build_frontpage(self.base, "", "", "", "<p>Hi</p>", {}, {})

    def build_404(self):
        update_website.build_404(self.base, "", "", "{{validPaths}}", [])

    def build_demo(self, folder="fake-demo", title="Fake Demo", alt=None):
        demo = {"folder": folder, "title": title, "descriptionShort": "Short.", "_body": "Body."}
        if alt:
            demo["ogImageAlt"] = alt
        with mock.patch.object(update_website, "log_error"):
            update_website.build_demo_pages(self.base, "", "", update_website.load_file("demo.html"),
                                            update_website.load_file("iframe.html"),
                                            {"games": {"demos": [folder]}}, {folder: demo})

    def build_standalone(self):
        manifests, demos_by_stem = update_website.load_demo_data()
        self.assertTrue(update_website.is_standalone(demos_by_stem["pseudorandom-number-generator"]))
        update_website.build_standalone_pages(self.base, "", "", manifests, demos_by_stem)

    def test_frontpage_and_404_share_the_frontpage_card(self):
        self.touch("img/xedur-social.png")
        self.build_frontpage()
        self.build_404()
        for rel in ("index.html", "404.html"):
            self.assertEqual(self.meta(rel, "og:image"), f"{SITE}/img/xedur-social.png", rel)
            self.assertEqual(self.meta(rel, "twitter:image"), f"{SITE}/img/xedur-social.png", rel)
            self.assertEqual(self.meta(rel, "og:image:width"), "1200", rel)
            self.assertEqual(self.meta(rel, "og:image:height"), "630", rel)

    def test_demo_uses_its_card_and_default_alt(self):
        self.touch("img/xedur-social.png")
        self.touch("demo/fake-demo/fake-demo-social.png")
        self.build_demo()
        rel = "demo/fake-demo/index.html"
        self.assertEqual(self.meta(rel, "og:image"), f"{SITE}/demo/fake-demo/fake-demo-social.png")
        self.assertEqual(self.meta(rel, "og:image:alt"), "XeduR - Fake Demo")
        self.assertEqual(self.meta(rel, "og:image:width"), "1200")

    def test_demo_alt_override_wins(self):
        self.touch("demo/fake-demo/fake-demo-social.png")
        self.build_demo(alt="Custom alt")
        self.assertEqual(self.meta("demo/fake-demo/index.html", "og:image:alt"), "Custom alt")

    def test_demo_without_card_falls_back_to_frontpage_card(self):
        self.touch("img/xedur-social.png")
        self.build_demo()
        self.assertEqual(self.meta("demo/fake-demo/index.html", "og:image"), f"{SITE}/img/xedur-social.png")

    def test_demo_without_any_card_uses_static_default_without_size(self):
        self.build_demo()
        rel = "demo/fake-demo/index.html"
        default = update_website.load_json("frontpage.json")["seo"]["ogImage"]
        self.assertEqual(self.meta(rel, "og:image"), default)
        self.assertIsNone(self.meta(rel, "og:image:width"))

    def test_demo_page_depends_on_its_card(self):
        self.build_demo()
        self.assertIn("demo/fake-demo/fake-demo-social.png",
                      update_website._NEW_OUTPUTS["demo/fake-demo/index.html"])

    def test_standalone_page_uses_its_card(self):
        card = "demo/pseudorandom-number-generator/pseudorandom-number-generator-social.png"
        self.touch(card)
        self.build_standalone()
        rel = "demo/pseudorandom-number-generator/index.html"
        self.assertEqual(self.meta(rel, "og:image"), f"{SITE}/{card}")
        self.assertEqual(self.meta(rel, "twitter:image"), f"{SITE}/{card}")
        self.assertEqual(self.meta(rel, "og:image:alt"), "XeduR - Pseudorandom Number Generator")
        self.assertEqual(self.meta(rel, "og:image:height"), "630")
        self.assertIn(card, update_website._NEW_OUTPUTS[rel])


class TestPostPages(CaptureBuildsMixin, unittest.TestCase):
    """Tangents post pages: card size, JSON-LD escaping, and dependencies."""

    def build_post(self, title="A Post", og_image_size=(1200, 630), social_image=None):
        post = {
            "slug": "a-post",
            "title": title,
            "summary": "Summary.",
            "tags": [],
            "published": date(2026, 7, 1),
            "updated": None,
            "body_html": "<p>Body.</p>",
            "needs_video_js": False,
            "social_image": social_image,
            "og_image": f"{SITE}/tangents/a-post/a-post-social.png",
            "og_image_size": og_image_size,
        }
        update_website.build_tangents_posts(self.base, "", "",
                                            update_website.load_file("tangents-post.html"), [post])
        return self.written["tangents/a-post/index.html"]

    def test_generated_card_declares_its_size(self):
        self.build_post()
        self.assertEqual(self.meta("tangents/a-post/index.html", "og:image:width"), "1200")
        self.assertEqual(self.meta("tangents/a-post/index.html", "og:image:height"), "630")

    def test_custom_image_declares_no_size(self):
        self.build_post(og_image_size=(0, 0), social_image="custom.png")
        self.assertIsNone(self.meta("tangents/a-post/index.html", "og:image:width"))
        self.assertIsNone(self.meta("tangents/a-post/index.html", "og:image:height"))

    def test_json_ld_survives_script_close_in_title(self):
        title = "Escaping </script> & <b> in HTML"
        page = self.build_post(title=title)
        start = page.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        end = page.index("</script>", start)
        data = json.loads(page[start:end])
        self.assertEqual(data["headline"], title)
        self.assertNotIn("<", page[start:end])

    def test_post_does_not_depend_on_the_shared_dates_file(self):
        self.build_post()
        deps = update_website._NEW_OUTPUTS["tangents/a-post/index.html"]
        self.assertNotIn(update_website._rel(update_website.TANGENTS_DATES_FILE), deps)


class TestPostCardNames(TempRootMixin, unittest.TestCase):
    def test_reserved_name_is_case_insensitive(self):
        for name in ("my-post-Social.png", "MY-POST-SOCIAL.PNG"):
            with self.subTest(name=name):
                with self.assertRaises(gen.SocialImageError):
                    gen.resolve_and_generate(
                        [{"slug": "my-post", "title": "T", "socialImage": name}], prune=False)

    def test_cli_rejects_malformed_slug(self):
        source_dir = os.path.join(self.root, "posts")
        os.makedirs(source_dir)
        with open(os.path.join(source_dir, "Bad_Name.md"), "w", encoding="utf-8") as f:
            f.write("---\ntitle: T\nsummary: S\n---\nBody.\n")
        with mock.patch.object(gen, "TANGENTS_SRC_DIR", source_dir):
            with self.assertRaises(ValueError):
                gen._load_posts_from_disk()


class TestJsonDataFiles(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="json-data-test-")
        self.path = os.path.join(self.root, "dates.json")

    def tearDown(self):
        shutil.rmtree(self.root)

    def write_raw(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_missing_file_reads_empty(self):
        self.assertEqual(update_website.read_json_file(self.path, required=True), {})

    def test_corrupt_required_file_raises_and_stays_intact(self):
        self.write_raw('{"a-post": {"published": "2026-')
        with self.assertRaises(ValueError):
            update_website.read_json_file(self.path, required=True)
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"a-post": {"published": "2026-')

    def test_corrupt_optional_file_warns_and_reads_empty(self):
        self.write_raw("{")
        with mock.patch.object(update_website, "log_warning") as warn:
            self.assertEqual(update_website.read_json_file(self.path, required=False), {})
        warn.assert_called_once()

    def test_write_round_trips_and_leaves_no_temp_file(self):
        update_website.write_json_file(self.path, {"b": 1, "a": 2}, indent=4, sort_keys=True)
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{\n    "a": 2,\n    "b": 1\n}\n')
        self.assertEqual(os.listdir(self.root), ["dates.json"])

    def test_unchanged_write_leaves_the_file_alone(self):
        update_website.write_json_file(self.path, {"a": 1}, indent=4)
        os.utime(self.path, (1, 1))
        update_website.write_json_file(self.path, {"a": 1}, indent=4)
        self.assertEqual(os.stat(self.path).st_mtime, 1)


if __name__ == "__main__":
    unittest.main()
