import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import merge_publications as merge
import sync_publications as sync

AUTHOR = "25-QBtwAAAAJ"
PAPER = AUTHOR + ":example"


def snapshot():
    return {"scholar_id": AUTHOR, "updated": "2026-10-23T07:00:00+00:00", "citedby": 3,
            "publications": {PAPER: {"author_pub_id": PAPER, "bib": {
                "title": "Changed title from Scholar", "author": "A and Mingliang Zhai",
                "pub_year": "2026"}, "num_citations": 3, "pub_url": "https://example.org/paper"}}}


class MergeTests(unittest.TestCase):
    def test_curated_fields_survive_title_change_and_citations_update(self):
        curated = {PAPER: {"title": "Curated title", "authors": ["Correct Author"],
                          "image": "images/paper.png", "links": {"code": "https://example.org/code"}}}
        merged = merge.merge_snapshot(snapshot(), curated)["publications"][0]
        self.assertEqual(merged["title"], "Curated title")
        self.assertEqual(merged["authors"], ["Correct Author"])
        self.assertEqual(merged["image"], "images/paper.png")
        self.assertEqual(merged["citations"], 3)
        self.assertEqual(merged["links"]["code"], "https://example.org/code")
        self.assertEqual(merged["links"]["paper"], "https://example.org/paper")

    def test_new_papers_added_old_omissions_retained(self):
        previous = merge.merge_snapshot(snapshot(), {})
        newer = snapshot()
        second = AUTHOR + ":new"
        newer["publications"] = {second: dict(newer["publications"][PAPER], author_pub_id=second)}
        result = merge.merge_snapshot(newer, {}, previous)
        papers = {paper["id"]: paper for paper in result["publications"]}
        self.assertEqual(set(papers), {PAPER, second})
        self.assertFalse(papers[PAPER]["in_latest_snapshot"])
        self.assertTrue(papers[second]["in_latest_snapshot"])

    def test_empty_and_wrong_author_rejected(self):
        empty = snapshot()
        empty["publications"] = {}
        with self.assertRaises(ValueError):
            merge.validate_snapshot(empty, AUTHOR)
        with self.assertRaises(ValueError):
            merge.validate_snapshot(snapshot(), "someone-else")

    def test_zero_citations_and_unsafe_urls(self):
        data = snapshot()
        data["publications"][PAPER]["num_citations"] = 0
        data["publications"][PAPER]["pub_url"] = "javascript:alert(1)"
        result = merge.merge_snapshot(data, {})["publications"][0]
        self.assertEqual(result["citations"], 0)
        self.assertEqual(result["links"]["paper"], "")

    def test_merge_is_idempotent(self):
        first = merge.merge_snapshot(snapshot(), {})
        self.assertEqual(first, merge.merge_snapshot(snapshot(), {}, first))

    def test_link_only_overrides_survive_sync_without_freezing_metadata(self):
        curated = {PAPER: {"links": {"project": "https://example.org/project",
                                    "code": "https://example.org/code"}}}
        previous = merge.merge_snapshot(snapshot(), curated)
        previous["publications"][0]["image"] = "images/publications/figure.png"
        newer = snapshot()
        newer["publications"][PAPER]["bib"]["title"] = "Updated title"
        newer["publications"][PAPER]["num_citations"] = 5
        paper = merge.merge_snapshot(newer, curated, previous)["publications"][0]
        self.assertEqual(paper["title"], "Updated title")
        self.assertEqual(paper["citations"], 5)
        self.assertEqual(paper["image"], "images/publications/figure.png")
        self.assertEqual(paper["links"]["paper"], "https://example.org/paper")
        for label, url in curated[PAPER]["links"].items():
            self.assertEqual(paper["links"][label], url)

    def test_live_curated_entries_are_all_present(self):
        overrides = merge.read_json(merge.ROOT / "_data/publication_overrides.json")
        data = merge.read_json(merge.ROOT / "_data/publications.json")
        papers = {paper["id"]: paper for paper in data["publications"]}
        for key, curated in overrides.items():
            self.assertIn(key, papers)
            for field in ("title", "authors", "venue", "year", "image", "order"):
                if field in curated:
                    self.assertEqual(papers[key][field], curated[field])
            for label, url in curated.get("links", {}).items():
                self.assertEqual(papers[key]["links"][label], url)


class FailureTests(unittest.TestCase):
    def test_failed_fetch_and_invalid_snapshot_do_not_change_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "_data/publications.json"
            raw = root / "google_scholar_crawler/results/gs_data.json"
            merge.atomic_json(output, merge.merge_snapshot(snapshot(), {}))
            merge.atomic_json(raw, snapshot())
            before = (output.read_bytes(), raw.read_bytes())
            malformed = root / "invalid.json"
            malformed.write_text('{"scholar_id":"wrong"}')
            with patch.object(sync, "ROOT", root), patch.object(sync, "configured_scholar_id", return_value=AUTHOR):
                with self.assertRaises(ValueError):
                    sync.sync(malformed)
                with patch.object(sync.subprocess, "run", side_effect=subprocess.TimeoutExpired("fetch", 1)):
                    with self.assertRaises(subprocess.TimeoutExpired):
                        sync.sync(timeout=1)
            self.assertEqual(before, (output.read_bytes(), raw.read_bytes()))


if __name__ == "__main__":
    unittest.main()
