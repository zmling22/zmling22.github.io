"""Fetch Scholar metadata; PDF figures are handled by scripts/sync_publications.py."""
from scholarly import scholarly
import argparse
import copy
import sys
import json
from datetime import datetime, timezone
import os
from pathlib import Path


def fetch_author(scholar_id, refresh_details=False):
    scholarly.set_timeout(12)
    scholarly.set_retries(1)
    print(f"Fetching Google Scholar profile {scholar_id}...", flush=True)
    author = scholarly.search_author_id(scholar_id)
    scholarly.fill(author, sections=["basics", "indices", "counts", "publications"])
    if not author.get("publications"):
        raise ValueError("Scholar returned no publications")
    print(f"Profile returned {len(author['publications'])} papers; fetching details...", flush=True)
    cache_path = Path(__file__).parent / "results/gs_data.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cached = cache.get("publications", {}) if cache.get("scholar_id") == scholar_id else {}
    except (OSError, ValueError):
        cached = {}
    for publication in author["publications"]:
        key = publication["author_pub_id"]
        summary = copy.deepcopy(publication["bib"])
        old = cached.get(key, {})
        if not refresh_details and old.get("filled") and old.get("profile_bib") == summary:
            publication["bib"] = old["bib"]
            for field in ("pub_url", "eprint_url", "detail_updated"):
                if field in old:
                    publication[field] = old[field]
            publication["filled"] = True
        else:
            print(f"  {summary.get('title')}", flush=True)
            try:
                scholarly.fill(publication)
                publication["detail_updated"] = datetime.now(timezone.utc).isoformat()
            except Exception as error:
                print(f"  Detail unavailable; keeping profile metadata: {error}", flush=True)
                if old.get("filled"):
                    publication["bib"] = dict(old["bib"], title=summary["title"])
                    for field in ("pub_url", "eprint_url"):
                        if field in old:
                            publication[field] = old[field]
                publication["filled"] = False
        publication["profile_bib"] = summary
    author["publications"] = {paper["author_pub_id"]: paper for paper in author["publications"]}
    author["updated"] = datetime.now(timezone.utc).isoformat()
    return author


def main():
    parser = argparse.ArgumentParser(description="Fetch a Scholar snapshot with bounded retries.")
    parser.add_argument("--scholar-id", default=os.environ.get("GOOGLE_SCHOLAR_ID"))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--refresh-details", action="store_true")
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from merge_publications import atomic_json, configured_scholar_id, validate_snapshot
    scholar_id = args.scholar_id or configured_scholar_id()
    author = fetch_author(scholar_id, args.refresh_details)
    validate_snapshot(author, scholar_id)
    atomic_json(args.output_dir / "gs_data.json", author)
    atomic_json(args.output_dir / "gs_data_shieldsio.json", {
        "schemaVersion": 1, "label": "citations", "message": str(author["citedby"])})
    print(f"Saved {len(author['publications'])} papers to {args.output_dir / 'gs_data.json'}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Scholar fetch failed: {error}", file=sys.stderr)
        sys.exit(1)
