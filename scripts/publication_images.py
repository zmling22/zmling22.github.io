#!/usr/bin/env python3
"""Resolve public PDFs and render the figure above a Figure 1 caption."""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import fitz

from merge_publications import ROOT, atomic_json, http_url, read_json

EXTRACTOR_VERSION = 1
MAX_PDF_BYTES = 64 * 1024 * 1024
MAX_HTML_BYTES = 2 * 1024 * 1024
CAPTION = re.compile(r"^(?:Figure|Fig\.?)\s*1(?:\s|[.:])", re.IGNORECASE)


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def pdf_url(url):
    """Known publishers' landing pages, including versioned arXiv IDs."""
    if not http_url(url):
        return None
    parsed = urlsplit(url)
    host, path = parsed.hostname, parsed.path
    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.fullmatch(r"/(?:abs|pdf|html)/((?:\d{4}\.\d{4,5}|[a-zA-Z.-]+/\d{7})(?:v\d+)?)(?:\.pdf)?", path)
        if match:
            return "https://arxiv.org/pdf/" + match[1]
    if host == "openaccess.thecvf.com" and "/html/" in path and path.endswith(".html"):
        return urlunsplit((parsed.scheme, parsed.netloc, path.replace("/html/", "/papers/")[:-5] + ".pdf", "", ""))
    if host in {"openreview.net", "www.openreview.net"} and path in {"/forum", "/pdf"}:
        identifier = parse_qs(parsed.query).get("id", [""])[0]
        if identifier:
            return "https://openreview.net/pdf?" + urlencode({"id": identifier})
    if host in {"link.springer.com", "link.springernature.com"} and re.fullmatch(r"/chapter/10\.\d{4,9}/[^/]+", path):
        return urlunsplit((parsed.scheme, parsed.netloc, path.replace("/chapter/", "/content/pdf/", 1) + ".pdf", "", ""))
    if path.lower().endswith(".pdf") or "/content/pdf/" in path:
        return url
    return None


class PDFLinks(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.links = base, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = None
        if tag == "meta" and attrs.get("name", "").lower() == "citation_pdf_url":
            value = attrs.get("content")
        elif tag == "a" and attrs.get("href"):
            # Only literal download links, never landing pages, fragment
            # anchors, account actions or their inferred PDF counterparts.
            link = urlsplit(urljoin(self.base, attrs["href"]))
            if link.path.lower().endswith(".pdf") or re.match(r"^/(?:content/)?pdf(?:/|$)", link.path):
                value = urlunsplit((link.scheme, link.netloc, link.path, link.query, ""))
        elif tag == "link" and attrs.get("type") == "application/pdf":
            value = attrs.get("href")
        if value and http_url(urljoin(self.base, value)):
            self.links.append(urljoin(self.base, value))


def fetch(url, limit):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; academic-homepage-figure-sync)"})
    with urlopen(request, timeout=20) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"Response exceeds {limit // 1024 // 1024} MiB")
        return data, response.geturl()


def source_urls(paper, raw):
    values = [paper.get("links", {}).get(k) for k in ("pdf", "paper")]
    values += [raw.get(k) for k in ("eprint_url", "pub_url", "url")]
    return list(dict.fromkeys(value for value in values if http_url(value)))


def log_url(url):
    # Publisher redirects can contain transient account/session query tokens.
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def verify_pdf(data, title=""):
    if not data.startswith(b"%PDF-"):
        raise ValueError("Server returned a web page instead of a PDF (access may be restricted)")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds size limit")
    with fitz.open(stream=data, filetype="pdf") as document:
        if document.needs_pass or not document.page_count:
            raise ValueError("PDF is encrypted or empty")
        if title:
            normalize = lambda text: re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", text).casefold())
            expected = normalize(title)
            actual = normalize(document.metadata.get("title", "") or "")
            first_page = normalize(document[0].get_text()[:4000])
            if expected != actual and expected not in first_page:
                raise ValueError("PDF title does not match this publication; refusing a possibly unrelated PDF")


def load_pdf(urls, root, network=True, refresh=False, title=""):
    candidates = list(dict.fromkeys(pdf_url(url) for url in urls if pdf_url(url)))
    attempted, errors = set(), []

    def try_candidates():
        for candidate in candidates[:8]:
            if candidate in attempted:
                continue
            attempted.add(candidate)
            cache = root / ".local/publication-pdfs" / (hashlib.sha256(candidate.encode()).hexdigest() + ".pdf")
            try:
                if cache.exists() and not refresh:
                    data = cache.read_bytes()
                elif network:
                    data, _ = fetch(candidate, MAX_PDF_BYTES)
                else:
                    continue
                verify_pdf(data, title)
                atomic_bytes(cache, data)
                return data, candidate
            except Exception as error:
                errors.append(f"{log_url(candidate)}: {error}")
        return None

    result = try_candidates()
    if result:
        return result
    if network:
        # Only explicit PDF metadata/links from the paper's landing page are used.
        # There is no title-based fuzzy matching that could select another paper.
        for url in urls[:3]:
            if url in attempted:
                continue
            try:
                data, final_url = fetch(url, MAX_HTML_BYTES)
                if data.startswith(b"%PDF-"):
                    verify_pdf(data, title)
                    return data, final_url
                parser = PDFLinks(final_url)
                parser.feed(data.decode("utf-8", errors="replace"))
                candidates.extend(link for link in parser.links if link not in candidates)
                result = try_candidates()
                if result:
                    return result
            except Exception as error:
                errors.append(f"{log_url(url)}: {error}")
    raise ValueError("; ".join(errors[-3:]) or "No downloadable PDF found in paper links/cache")


def expanded(rect, padding):
    return fitz.Rect(rect.x0 - padding, rect.y0 - padding, rect.x1 + padding, rect.y1 + padding)


def overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def graphic_groups(rects):
    """Join nearby vector paths and raster tiles into complete visual regions."""
    groups = []
    for rect in rects:
        group = fitz.Rect(rect)
        changed = True
        while changed:
            changed = False
            remaining = []
            for other in groups:
                if expanded(group, 4).intersects(expanded(other, 4)):
                    group |= other
                    changed = True
                else:
                    remaining.append(other)
            groups = remaining
        groups.append(group)
    return groups


def figure_region(page, caption, lines):
    """Find graphics immediately above the caption; refuse text-only guesses."""
    rects = [fitz.Rect(item["bbox"]) for item in page.get_image_info()]
    rects += [fitz.Rect(item["rect"]) for item in page.get_drawings()]
    # Inflate zero-width paths so thin vector arrows/lines are still included.
    rects = [expanded(r, 0.4) if r.width < 1 or r.height < 1 else r for r in rects]
    rects = [r & page.rect for r in rects if r.y1 <= caption.y0 + 1 and r.y1 > 20
             and max(r.width, r.height) > 3 and r.width < page.rect.width * .98]
    groups = graphic_groups(rects)
    nearby = [r for r in groups if 0 <= caption.y0 - r.y1 <= 48
              and overlap(r.x0, r.x1, caption.x0, caption.x1) > 10
              and r.width >= 65 and r.height >= 35]
    if not nearby:
        return None
    nearest_gap = min(caption.y0 - r.y1 for r in nearby)
    region = fitz.Rect(max((r for r in nearby if caption.y0 - r.y1 <= nearest_gap + 12), key=lambda r: r.get_area()))
    # Disjoint panels on the same row should travel together.
    for other in groups:
        gap = max(other.x0 - region.x1, region.x0 - other.x1, 0)
        if gap <= 24 and overlap(region.y0, region.y1, other.y0, other.y1) >= min(region.height, other.height) * .65:
            region |= other
    graphics = fitz.Rect(region)
    for bounds, text in lines:
        # Use the original graphic bounds, so adjacent prose cannot grow the
        # crop one line at a time. A nearby author/email line is outside it.
        if bounds.y1 < graphics.y0 - 3:
            continue
        if bounds.y1 < caption.y0 and expanded(graphics, 7).intersects(bounds):
            if overlap(bounds.x0, bounds.x1, region.x0, region.x1) >= bounds.width * .8:
                region |= bounds
    # A background panel around an abstract is not a figure.
    prose = [text for bounds, text in lines if region.contains(bounds) and len(text) > 100]
    if len(prose) >= 3 or region.get_area() < 5000 or region.height > page.rect.height * .8:
        return None
    region = expanded(region, 2) & page.rect
    region.y1 = min(region.y1, caption.y0 - 1)
    return region


def extract_figure(pdf):
    with fitz.open(stream=pdf, filetype="pdf") as document:
        if document.needs_pass:
            raise ValueError("Password-protected PDF")
        for index in range(min(len(document), 12)):
            page = document[index]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]
            lines = [(fitz.Rect(line["bbox"]), "".join(span["text"] for span in line["spans"]).strip())
                     for block in blocks for line in block.get("lines", [])]
            for block in blocks:
                text = " ".join("".join(s["text"] for s in line["spans"]).strip() for line in block.get("lines", []))
                if not CAPTION.match(text):
                    continue
                caption = fitz.Rect(block["bbox"])
                region = figure_region(page, caption, lines)
                if region is None:
                    continue
                scale = min(3, 1400 / region.width)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=region, colorspace=fitz.csRGB, alpha=False)
                return pixmap.tobytes("png"), {"page": page.number + 1, "bbox": [round(x, 2) for x in region],
                                              "caption": text, "method": "figure-1-caption", "extractor_version": EXTRACTOR_VERSION}
    raise ValueError("Could not confidently locate Figure 1 and its complete graphics in the first 12 pages")


def sync_images(root=ROOT, network=True, refresh=False):
    output = root / "_data/publications.json"
    data = read_json(output)
    raw = read_json(root / "google_scholar_crawler/results/gs_data.json")["publications"]
    overrides = read_json(root / "_data/publication_overrides.json")
    manifest_path = root / "_data/publication_images.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    report = {"attempted_at": datetime.now(timezone.utc).isoformat(), "network": network, "papers": {}}
    atomic_json(root / ".local/publication-image-status.json", report)
    for paper in data["publications"]:
        key = paper["id"]
        status = report["papers"][key] = {}
        if "image" in overrides.get(key, {}):
            status["status"] = "manual" if overrides[key]["image"] else "disabled"
        else:
            urls = source_urls(paper, raw.get(key, {}))
            entry = manifest.get(key, {})
            image_path = entry.get("image", "")
            if (not refresh and image_path.startswith("images/publications/") and (root / image_path).is_file()
                    and entry.get("sources") == urls and entry.get("extractor_version") == EXTRACTOR_VERSION):
                changed = paper.get("image") != image_path
                paper["image"] = image_path
                status["status"] = "cached"
                if changed:
                    atomic_json(output, data)
            else:
                print(f"Figure 1: {paper['title']}", flush=True)
                try:
                    download_urls = urls
                    if entry.get("sources") == urls and http_url(entry.get("pdf_url")):
                        download_urls = list(dict.fromkeys([entry["pdf_url"]] + urls))
                    pdf, url = load_pdf(download_urls, root, network=network, refresh=refresh, title=paper["title"])
                    png, details = extract_figure(pdf)
                    image_path = "images/publications/" + hashlib.sha256(key.encode()).hexdigest()[:20] + "-figure-1.png"
                    atomic_bytes(root / image_path, png)
                    manifest[key] = dict(details, image=image_path, pdf_url=url, sources=urls,
                                         pdf_sha256=hashlib.sha256(pdf).hexdigest())
                    atomic_json(manifest_path, manifest)
                    paper["image"] = image_path
                    atomic_json(output, data)
                    status.update(status="generated", image=image_path, page=details["page"])
                    print(f"  Saved page {details['page']} Figure 1 -> {image_path}", flush=True)
                except Exception as error:
                    status.update(status="unavailable" if network else "offline", error=str(error))
                    print(f"  Keeping existing image: {error}", flush=True)
        atomic_json(root / ".local/publication-image-status.json", report)
    counts = {kind: sum(p["status"] == kind for p in report["papers"].values())
              for kind in ("generated", "cached", "manual", "disabled", "unavailable", "offline")}
    report["counts"] = counts
    atomic_json(root / ".local/publication-image-status.json", report)
    print("Figure extraction complete: " + ", ".join(f"{count} {kind}" for kind, count in counts.items() if count), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use existing images/PDF cache only")
    parser.add_argument("--refresh", action="store_true", help="Download PDFs and regenerate automatic images")
    args = parser.parse_args()
    if args.offline and args.refresh:
        parser.error("--refresh requires network access")
    try:
        sync_images(network=not args.offline, refresh=args.refresh)
    except Exception as error:
        print(f"Image processing failed; publication metadata remains available: {error}", file=sys.stderr)
        sys.exit(1)
