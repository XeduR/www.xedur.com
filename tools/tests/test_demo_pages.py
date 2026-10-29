"""Tests for the demo page hero preload and demo sitemap lastmod dates."""

import json
import os
import re
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

import update_website
from test_social_cards import case_folding_isfile

OLD_DATE = "2020-01-01"
# Asset mtime earlier than OLD_DATE, so an mtime check alone never sees a change.
OLD_MTIME = 1500000000


class TestDemoHeroPreload(unittest.TestCase):
    def setUp(self):
        self.written = {}
        self.patches = [
            mock.patch.object(update_website, "write_file", self.capture),
            mock.patch.object(update_website, "FORCE", True),
            mock.patch.object(update_website, "log_error"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def capture(self, filepath, content):
        self.written[os.path.relpath(filepath, update_website.ROOT_DIR).replace(os.sep, "/")] = content

    def test_preload_href_is_the_css_hero_url(self):
        demo = {"folder": "fake-demo", "title": "Fake Demo", "descriptionShort": "Short.", "_body": "Body."}
        update_website.build_demo_pages(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("demo.html"), update_website.load_file("iframe.html"),
            {"games": {"demos": ["fake-demo"]}}, {"fake-demo": demo},
        )
        page = self.written["demo/fake-demo/index.html"]

        css_url = re.search(r"background: black url\('([^']+)'\)", page).group(1)
        self.assertEqual(css_url, "fake-demo-large.jpg")
        self.assertIn(f'<link rel="preload" as="image" href="{css_url}" fetchpriority="high">', page)


class TestDemoInlineImages(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="demo-image-test-")
        self.written = {}
        self.patches = [
            mock.patch.object(update_website, "ROOT_DIR", self.root),
            mock.patch.object(update_website, "OUTPUT_DIR", self.root),
            mock.patch.object(update_website, "write_file", self.capture),
            mock.patch.object(update_website, "FORCE", True),
            mock.patch.object(update_website, "log_error"),
            mock.patch.dict(update_website._NEW_OUTPUTS, clear=True),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        shutil.rmtree(self.root)

    def capture(self, filepath, content):
        self.written[os.path.relpath(filepath, self.root).replace(os.sep, "/")] = content

    def test_local_image_gets_its_size_and_is_a_page_dep(self):
        os.makedirs(os.path.join(self.root, "demo", "fake-demo"))
        # A PNG signature and IHDR header are all the size reader looks at.
        with open(os.path.join(self.root, "demo", "fake-demo", "shot.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + struct.pack(">II", 40, 20))
        demo = {"folder": "fake-demo", "title": "Fake Demo", "_body": '[[image src="shot.png" alt="s"]]'}
        update_website.build_demo_pages(
            update_website.load_file("base.html"), "", "",
            update_website.load_file("demo.html"), update_website.load_file("iframe.html"),
            {"games": {"demos": ["fake-demo"]}}, {"fake-demo": demo},
        )
        self.assertIn('alt="s" loading="lazy" width="40" height="20">', self.written["demo/fake-demo/index.html"])
        self.assertIn("demo/fake-demo/shot.png", update_website._NEW_OUTPUTS["demo/fake-demo/index.html"])


class TestDemoImageCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="demo-image-case-test-")
        self.patches = [
            mock.patch.object(update_website, "ROOT_DIR", self.root),
            mock.patch.object(update_website, "log_warning"),
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
        open(path, "wb").close()

    def check(self):
        update_website.log_warning.reset_mock()
        demos = {
            "fake": {"folder": "fake"},
            "ext": {"externalUrl": "https://example.com/", "image": "img/ext.jpg", "title": "Ext"},
        }
        real_isfile = os.path.isfile
        with mock.patch("os.path.isfile", lambda path: real_isfile(path) or case_folding_isfile(path)):
            update_website.check_images({"games": {"demos": ["fake", "ext"]}}, demos)
        return [call.args[0] for call in update_website.log_warning.call_args_list]

    def test_exact_names_pass(self):
        for rel in ("demo/fake/fake-small.jpg", "demo/fake/fake-large.jpg", "img/ext.jpg"):
            self.touch(rel)
        self.assertEqual(self.check(), [])

    def test_wrong_letter_case_counts_as_missing(self):
        for rel in ("demo/fake/fake-Small.jpg", "demo/fake/fake-large.jpg", "img/Ext.jpg"):
            self.touch(rel)
        self.assertEqual(self.check(), [
            "image not found: demo/fake/fake-small.jpg",
            "image not found: img/ext.jpg (external: Ext)",
        ])


class TestDemoSitemapDates(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="demo-sitemap-test-")
        self.dates_file = os.path.join(self.root, "sitemap_dates.json")
        self.asset = os.path.join(self.root, "demo", "fake", "app", "fake.bin")
        os.makedirs(os.path.dirname(self.asset))
        self.write_asset(b"original")
        self.write_dates({"/demo/fake/": OLD_DATE})
        self.prev_stats = {}
        self.patches = [
            mock.patch.object(update_website, "ROOT_DIR", self.root),
            mock.patch.object(update_website, "OUTPUT_DIR", self.root),
            mock.patch.object(update_website, "STANDALONE_DIR", os.path.join(self.root, "standalone")),
            mock.patch.object(update_website, "SITEMAP_DATES_FILE", self.dates_file),
            mock.patch.object(update_website, "write_file", lambda filepath, content: None),
            mock.patch.object(update_website, "CHANGED_FILES", set()),
            mock.patch.object(update_website, "_PREV_ASSET_STATS", {}),
            mock.patch.object(update_website, "_NEW_ASSET_STATS", {}),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        shutil.rmtree(self.root)

    def write_asset(self, content, mtime=OLD_MTIME):
        with open(self.asset, "wb") as f:
            f.write(content)
        os.utime(self.asset, (mtime, mtime))

    def write_dates(self, data):
        with open(self.dates_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def read_dates(self):
        with open(self.dates_file, encoding="utf-8") as f:
            return json.load(f)

    def build(self, keep_stat_cache=True):
        """One build's asset check and sitemap write; without the stat cache it is a fresh clone."""
        update_website.CHANGED_FILES = set()
        update_website._PREV_ASSET_STATS = self.prev_stats if keep_stat_cache else {}
        update_website._NEW_ASSET_STATS = {}
        hashes = update_website.check_demo_assets({"games": {"demos": ["fake"]}}, {"fake": {"folder": "fake"}})
        update_website.build_sitemap(["/demo/fake/"], None, hashes)
        self.prev_stats = update_website._NEW_ASSET_STATS
        return self.read_dates()

    def test_first_build_records_hashes_and_keeps_dates(self):
        self.write_asset(b"original", mtime=OLD_MTIME + 10 ** 9)
        dates = self.build()
        self.assertEqual(dates["/demo/fake/"], OLD_DATE)
        self.assertEqual(set(dates[update_website.SITEMAP_ASSET_HASHES_KEY]), {"/demo/fake/"})

    def test_fresh_mtimes_with_identical_bytes_do_not_bump(self):
        self.build()
        self.write_asset(b"original", mtime=OLD_MTIME + 10 ** 9)
        self.assertEqual(self.build(keep_stat_cache=False)["/demo/fake/"], OLD_DATE)
        self.assertEqual(self.build()["/demo/fake/"], OLD_DATE)

    def test_changed_bytes_bump(self):
        self.build()
        self.write_asset(b"changed!", mtime=OLD_MTIME - 10)
        self.assertEqual(self.build()["/demo/fake/"], date.today().isoformat())

    def test_unchanged_stat_reuses_the_stored_hash(self):
        first = self.build()
        with mock.patch.object(update_website, "_file_sha256", side_effect=AssertionError("re-hashed")):
            self.assertEqual(self.build(), first)

    def test_corrupt_dates_file_only_warns(self):
        with open(self.dates_file, "w", encoding="utf-8") as f:
            f.write("{")
        with mock.patch.object(update_website, "log_warning") as warn:
            dates = self.build()
        warn.assert_called()
        self.assertEqual(dates["/demo/fake/"], date.today().isoformat())
        self.assertIn("/demo/fake/", dates[update_website.SITEMAP_ASSET_HASHES_KEY])


if __name__ == "__main__":
    unittest.main()
