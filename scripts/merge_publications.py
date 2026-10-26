#!/usr/bin/env python3
"""Merge validated Scholar data with curated fields; never rewrite about.md."""
import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    try:
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configured_scholar_id():
    import yaml
    config = yaml.safe_load((ROOT / "_config.yml").read_text(encoding="utf-8"))
    url = config.get("author", {}).get("googlescholar", "")
    scholar_id = parse_qs(urlparse(url).query).get("user", [""])[0]
    if not scholar_id:
        raise ValueError("Missing author.googlescholar user ID in _config.yml")
    return scholar_id


def validate_snapshot(data, scholar_id):
    if not isinstance(data, dict) or not scholar_id or data.get("scholar_id") != scholar_id:
        raise ValueError("Scholar profile ID does not match the configured author")
    publications = data.get("publications")
    if not isinstance(publications, dict) or not publications:
        raise ValueError("Empty or invalid publications; keeping previous data")
    if not data.get("updated"):
        raise ValueError("Missing fetch timestamp")
    if type(data.get("citedby")) is not int or data["citedby"] < 0:
        raise ValueError("Invalid total citation count")
    for key, publication in publications.items():
        if not key.startswith(scholar_id + ":") or not isinstance(publication, dict):
            raise ValueError("Invalid publication identity")
        if publication.get("author_pub_id") != key:
            raise ValueError("Publication key does not match author_pub_id")
        bib = publication.get("bib")
        if not isinstance(bib, dict):
            raise ValueError("Invalid publication metadata")
        title = bib.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Publication is missing a title")
        if type(publication.get("num_citations")) is not int or publication["num_citations"] < 0:
            raise ValueError("Publication is missing a valid citation count")


def http_url(value):
    parsed = urlparse(value) if isinstance(value, str) else None
    return value if parsed and parsed.scheme in ("http", "https") and parsed.netloc else ""


def authors_list(value):
    if isinstance(value, list):
        return [str(author).strip() for author in value if str(author).strip()]
    return [author.strip() for author in re.split(r"\s+and\s+|,\s*", str(value or "")) if author.strip()]


def normalize_publication(key, publication):
    bib = publication["bib"]
    year = str(bib.get("pub_year") or bib.get("year") or "")
    link = next((http_url(publication.get(field)) for field in ("eprint_url", "pub_url", "url") if http_url(publication.get(field))), "")
    return {
        "id": key, "title": bib["title"].strip(), "year": int(year) if year.isdigit() else 0,
        "authors": authors_list(bib.get("author") or bib.get("authors")),
        "venue": bib.get("venue") or bib.get("journal") or bib.get("conference") or bib.get("citation") or "",
        "citations": publication["num_citations"], "image": "",
        "links": {"paper": link, "scholar": "https://scholar.google.com/citations?view_op=view_citation&citation_for_view=" + key},
        "in_latest_snapshot": True,
    }


def merge_snapshot(data, overrides, previous=None):
    previous = previous or {}
    validate_snapshot(data, data.get("scholar_id"))
    if previous and previous.get("scholar_id") != data["scholar_id"]:
        raise ValueError("Previous data belongs to a different Scholar profile")
    existing = {paper["id"]: paper for paper in previous.get("publications", [])}
    result = []
    for key, publication in data["publications"].items():
        paper = normalize_publication(key, publication)
        # Automatic figures survive metadata-only runs and PDF download failures.
        paper["image"] = existing.get(key, {}).get("image", "")
        curated = overrides.get(key, {})
        for field in ("title", "authors", "venue", "year", "image", "order"):
            if field in curated:
                paper[field] = curated[field]
        for label, url in curated.get("links", {}).items():
            if http_url(url):
                paper["links"][label] = url
        result.append(paper)
    # A transient omission must not delete existing or manually maintained papers.
    for key, paper in existing.items():
        if key not in data["publications"]:
            result.append(dict(paper, in_latest_snapshot=False))
    ids = {paper["id"] for paper in result}
    for key, curated in overrides.items():
        if key not in ids and curated.get("title"):
            result.append({"id": key, "year": 0, "authors": [], "venue": "", "image": "", "links": {},
                           **curated, "citations": None, "in_latest_snapshot": False})
    result.sort(key=lambda paper: (-int(paper.get("year") or 0), paper.get("order", 999), -(paper.get("citations") or 0), paper["title"]))
    return {"schema_version": 1, "scholar_id": data["scholar_id"], "updated": data["updated"],
            "total_citations": data["citedby"], "source_count": len(data["publications"]), "publications": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "google_scholar_crawler/results/gs_data.json")
    parser.add_argument("--output", type=Path, default=ROOT / "_data/publications.json")
    args = parser.parse_args()
    try:
        data = read_json(args.input)
        validate_snapshot(data, configured_scholar_id())
        merged = merge_snapshot(data, read_json(ROOT / "_data/publication_overrides.json"), read_json(args.output) if args.output.exists() else None)
        atomic_json(args.output, merged)
        print(f"Saved {len(merged['publications'])} publications to {args.output}")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Merge failed; previous data retained: {error}\n")


if __name__ == "__main__":
    main()
