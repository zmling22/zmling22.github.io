import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publication_images as images
import merge_publications as merge
import sync_publications as sync

AUTHOR = "25-QBtwAAAAJ"
AUTO = AUTHOR + ":auto"
MANUAL = AUTHOR + ":manual"
TITLE = "A vector-only research diagram"
URL = "https://arxiv.org/pdf/2501.12345v2"


def vector_pdf(page_number=1, caption="Figure 1. A complete vector figure.", two_columns=False):
    with fitz.open() as document:
        document.set_metadata({"title": TITLE})
        for index in range(page_number):
            page = document.new_page(width=600, height=800)
            page.insert_text((50, 40), TITLE)
            if index != page_number - 1:
                page.draw_rect(fitz.Rect(40, 100, 550, 500), fill=(.9, .9, .9))
                page.insert_text((50, 550), "The method is illustrated in Figure 1 on a later page.")
        right = 270 if two_columns else 550
        page.draw_rect(fitz.Rect(50, 120, right, 260), color=(0, 0, 1), fill=(.9, .9, 1))
        page.insert_text((65, 150), "Vector labels and arrows")
        page.draw_line((70, 180), (220, 230), color=(1, 0, 0))
        # Nearby author text must not get incorporated into the illustration.
        page.insert_text((80, 111), "author@example.org", fontsize=9)
        page.insert_text((50, 285), caption, fontsize=9)
        page.insert_text((50, 315), "This body paragraph must stay outside the image.")
        if two_columns:
            page.draw_rect(fitz.Rect(330, 120, 550, 260), fill=(1, 0, 0))
            page.insert_text((330, 285), "Figure 2. Unrelated figure.", fontsize=9)
        return document.tobytes()


def prepare(root):
    raw = {"scholar_id": AUTHOR, "updated": "2026-10-23T07:00:00+00:00", "citedby": 3, "publications": {}}
    for key in (AUTO, MANUAL):
        raw["publications"][key] = {"author_pub_id": key, "bib": {"title": TITLE, "pub_year": "2026"},
                                     "pub_url": URL, "num_citations": 3}
    overrides = {MANUAL: {"image": "images/curated.png"}}
    merge.atomic_json(root / "_data/publication_overrides.json", overrides)
    merge.atomic_json(root / "google_scholar_crawler/results/gs_data.json", raw)
    merge.atomic_json(root / "_data/publications.json", merge.merge_snapshot(raw, overrides))
    return raw


class FigureTests(unittest.TestCase):
    def test_vector_figure_on_page_three_excludes_surrounding_text(self):
        pdf = vector_pdf(page_number=3)
        png, details = images.extract_figure(pdf)
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertEqual(details["page"], 3)
        self.assertGreater(details["bbox"][1], 115)
        self.assertLess(details["bbox"][3], 270)
        self.assertLess(details["bbox"][0], 50)
        self.assertGreater(details["bbox"][2], 550)
        self.assertGreater(fitz.Pixmap(png).width, 1000)

    def test_two_column_crop_excludes_other_figure(self):
        _, details = images.extract_figure(vector_pdf(two_columns=True))
        self.assertLess(details["bbox"][2], 300)

    def test_figure_ten_and_body_mentions_are_not_figure_one(self):
        for caption in ("Figure 10. Not the requested figure.", "We discuss Figure 1 below."):
            with self.subTest(caption=caption), self.assertRaises(ValueError):
                images.extract_figure(vector_pdf(caption=caption))

    def test_text_only_caption_does_not_produce_a_page_screenshot(self):
        with fitz.open() as document:
            page = document.new_page()
            page.insert_text((50, 100), "Figure 1. There are no graphics here.")
            with self.assertRaises(ValueError):
                images.extract_figure(document.tobytes())


class DownloadTests(unittest.TestCase):
    def test_publisher_urls_preserve_paper_identity_and_arxiv_version(self):
        self.assertEqual(images.pdf_url("https://arxiv.org/abs/2501.12345v2"), URL)
        self.assertEqual(images.pdf_url(URL + ".pdf"), URL)
        self.assertEqual(images.pdf_url("https://openreview.net/forum?id=abc&noteId=other"), "https://openreview.net/pdf?id=abc")
        self.assertEqual(images.pdf_url("https://openaccess.thecvf.com/content/CVPR2026/html/A_paper.html"),
                         "https://openaccess.thecvf.com/content/CVPR2026/papers/A_paper.pdf")
        self.assertEqual(images.pdf_url("https://link.springer.com/chapter/10.1007/chapter_1"),
                         "https://link.springer.com/content/pdf/10.1007/chapter_1.pdf")
        self.assertIsNone(images.pdf_url("https://arxiv.org.evil.example/abs/2501.12345"))
        self.assertIsNone(images.pdf_url("file:///private/paper.pdf"))

    def test_html_parser_ignores_navigation_anchors_and_account_actions(self):
        page = "https://link.springer.com/chapter/10.1007/chapter_1"
        parser = images.PDFLinks(page)
        parser.feed('''<a href="#authors">Authors</a><a>Empty</a>
          <a href="/chapter/10.1007/chapter_1/save-research?token=example">Save</a>
          <a href="/chapter/10.1007/another">Related article</a>
          <a href="/content/pdf/10.1007/chapter_1.pdf">Download PDF</a>''')
        self.assertEqual(parser.links, ["https://link.springer.com/content/pdf/10.1007/chapter_1.pdf"])

    def test_publisher_pdf_metadata_and_pdf_cache(self):
        landing = "https://publisher.example/article"
        target = "https://publisher.example/paper.pdf"
        html = b'<meta name="citation_pdf_url" content="/paper.pdf">'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(images, "fetch", side_effect=[(html, landing), (vector_pdf(), target)]) as fetch:
                data, url = images.load_pdf([landing], root, title=TITLE)
                self.assertEqual(url, target)
                self.assertEqual(fetch.call_count, 2)
            with patch.object(images, "fetch", side_effect=AssertionError("Unexpected download")):
                cached, _ = images.load_pdf([target], root, network=False, title=TITLE)
            self.assertEqual(data, cached)

    def test_html_paywall_and_unrelated_pdf_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(images, "fetch", return_value=(b"<html>Sign in</html>", URL)):
                with self.assertRaisesRegex(ValueError, "instead of a PDF"):
                    images.load_pdf([URL], Path(folder))
            with patch.object(images, "fetch", return_value=(vector_pdf(), URL)):
                with self.assertRaisesRegex(ValueError, "title does not match"):
                    images.load_pdf([URL], Path(folder), title="A completely different publication")


class PipelineTests(unittest.TestCase):
    def test_default_sync_generates_image_and_second_run_uses_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepare(root)
            pdf = vector_pdf()
            with patch.object(images, "fetch", return_value=(pdf, URL)) as download:
                # Exercise the coordinator's default image stage using an
                # existing source snapshot so this regression needs no Scholar.
                def worker(command, **kwargs):
                    self.assertIn("publication_images.py", command[1])
                    images.sync_images(root)
                with patch.object(sync, "ROOT", root), patch.object(sync, "configured_scholar_id", return_value=AUTHOR), \
                     patch.object(sync.subprocess, "run", side_effect=worker):
                    result = sync.sync(images_only=True)
                self.assertEqual(download.call_count, 1)
            papers = {paper["id"]: paper for paper in result["publications"]}
            self.assertEqual(papers[MANUAL]["image"], "images/curated.png")
            self.assertTrue((root / papers[AUTO]["image"]).exists())
            manifest = merge.read_json(root / "_data/publication_images.json")
            self.assertEqual(manifest[AUTO]["pdf_sha256"], hashlib.sha256(pdf).hexdigest())
            self.assertEqual(manifest[AUTO]["page"], 1)
            with patch.object(images, "fetch", side_effect=AssertionError("Cache should avoid downloads")):
                report = images.sync_images(root)
            self.assertEqual(report["counts"]["cached"], 1)
            self.assertEqual(report["counts"]["manual"], 1)

    def test_failed_refresh_keeps_image_manifest_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = prepare(root)
            with patch.object(images, "fetch", return_value=(vector_pdf(), URL)):
                images.sync_images(root)
            data_path = root / "_data/publications.json"
            manifest = root / "_data/publication_images.json"
            before = data_path.read_bytes(), manifest.read_bytes()
            with patch.object(images, "fetch", side_effect=OSError("HTTP 403")):
                report = images.sync_images(root, refresh=True)
            self.assertEqual(report["counts"]["unavailable"], 1)
            self.assertEqual(before, (data_path.read_bytes(), manifest.read_bytes()))
            previous = merge.read_json(data_path)
            again = merge.merge_snapshot(raw, merge.read_json(root / "_data/publication_overrides.json"), previous)
            self.assertEqual(again, previous)

    def test_offline_replay_never_downloads(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepare(root)
            with patch.object(images, "fetch", side_effect=AssertionError("Offline must not access network")) as fetch:
                report = images.sync_images(root, network=False)
                fetch.assert_not_called()
            self.assertEqual(report["counts"]["offline"], 1)

    def test_explicit_blank_override_disables_auto_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepare(root)
            merge.atomic_json(root / "_data/publication_overrides.json", {AUTO: {"image": ""}, MANUAL: {"image": "images/curated.png"}})
            with patch.object(images, "fetch", side_effect=AssertionError("Disabled image should not download")) as fetch:
                report = images.sync_images(root)
                fetch.assert_not_called()
            self.assertEqual(report["counts"]["disabled"], 1)

    def test_image_timeout_does_not_fail_metadata_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prepare(root)
            with patch.object(sync, "ROOT", root), patch.object(sync, "configured_scholar_id", return_value=AUTHOR), \
                 patch.object(sync.subprocess, "run", side_effect=subprocess.TimeoutExpired("images", 1)):
                data = sync.sync(images_only=True, image_timeout=1)
            self.assertEqual(data["total_citations"], 3)
            self.assertTrue(merge.read_json(root / ".local/publication-image-status.json")["incomplete"])


if __name__ == "__main__":
    unittest.main()
