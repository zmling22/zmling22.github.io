from scholarly import scholarly
import jsonpickle
import json
from datetime import datetime
import os
import re
import mimetypes
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_DIR = Path("results/publication-images")
FIGURE_KEYWORDS = (
    "architecture",
    "framework",
    "pipeline",
    "overview",
    "method",
    "model",
    "network",
    "approach",
    "system",
)


class ArxivFigureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.figure_depth = 0
        self.caption_depth = 0
        self.current = None
        self.figures = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_map = {key.lower(): value for key, value in attrs if key and value}
        if tag == "figure":
            if self.figure_depth == 0:
                self.current = {"images": [], "caption": ""}
            self.figure_depth += 1
        elif tag == "img" and self.figure_depth and self.current is not None:
            src = attr_map.get("src")
            if src:
                self.current["images"].append(src)
        elif tag in {"figcaption", "caption"} and self.figure_depth:
            self.caption_depth += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"figcaption", "caption"} and self.caption_depth:
            self.caption_depth -= 1
        elif tag == "figure" and self.figure_depth:
            self.figure_depth -= 1
            if self.figure_depth == 0 and self.current:
                if self.current["images"]:
                    self.figures.append(self.current)
                self.current = None

    def handle_data(self, data):
        if self.caption_depth and self.current is not None:
            self.current["caption"] += data + " "


def normalized_title(title):
    return re.sub(r"\s+", " ", title or "").strip().lower()


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", normalized_title(value))
    return slug.strip("-")[:90] or "publication"


def request_url(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; zmling22.github.io publication image crawler)"
        },
    )
    return urlopen(request, timeout=15)


def publication_urls(publication):
    urls = []
    for key in ("pub_url", "eprint_url", "url"):
        value = publication.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
    return list(dict.fromkeys(urls))


def arxiv_id_from_url(url):
    match = re.search(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})(?:v[0-9]+)?", url)
    return match.group(1) if match else None


def arxiv_id_from_publication(publication, title):
    for url in publication_urls(publication):
        arxiv_id = arxiv_id_from_url(url)
        if arxiv_id:
            return arxiv_id

    query = quote(f'ti:"{title}"')
    api_url = f"https://export.arxiv.org/api/query?search_query={query}&start=0&max_results=1"
    try:
        with request_url(api_url) as response:
            xml = response.read(1024 * 1024)
        root = ET.fromstring(xml)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", namespace)
        if entry is None:
            return None
        entry_title = "".join(entry.findtext("atom:title", default="", namespaces=namespace).split()).lower()
        expected_title = "".join(title.split()).lower()
        if entry_title != expected_title:
            return None
        identifier = entry.findtext("atom:id", default="", namespaces=namespace)
        return arxiv_id_from_url(identifier)
    except Exception as error:
        print(f"Failed to search arXiv for {title}: {error}")
        return None


def read_html(url):
    try:
        with request_url(url) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None
            return response.read(2 * 1024 * 1024).decode("utf-8", errors="ignore")
    except Exception as error:
        print(f"Failed to read arXiv HTML {url}: {error}")
        return None

def figure_score(figure):
    caption = re.sub(r"\s+", " ", figure.get("caption", "")).lower()
    return sum(1 for keyword in FIGURE_KEYWORDS if keyword in caption)


def find_arxiv_figure_image(arxiv_id):
    html_sources = [
        f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}",
        f"https://arxiv.org/html/{arxiv_id}",
    ]
    for html_url in html_sources:
        html = read_html(html_url)
        if not html:
            continue
        parser = ArxivFigureParser()
        parser.feed(html)
        ranked_figures = sorted(
            (figure for figure in parser.figures if figure_score(figure) > 0),
            key=figure_score,
            reverse=True,
        )
        for figure in ranked_figures:
            image_url = urljoin(html_url, figure["images"][0])
            if image_url.startswith(("http://", "https://")):
                return image_url
    return None


def download_image(image_url, title):
    try:
        with request_url(image_url) as response:
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                return None

            extension = mimetypes.guess_extension(content_type) or ".jpg"
            if extension == ".jpe":
                extension = ".jpg"
            path = IMAGE_DIR / f"{slugify(title)}{extension}"
            data = response.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                print(f"Skipping large image for {title}: {image_url}")
                return None
            IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return str(path.relative_to("results"))
    except Exception as error:
        print(f"Failed to download image {image_url}: {error}")
        return None


def build_publication_image_map(publications):
    image_map = {}
    for publication in publications:
        title = publication.get("bib", {}).get("title")
        if not title:
            continue
        arxiv_id = arxiv_id_from_publication(publication, title)
        if not arxiv_id:
            continue
        image_url = find_arxiv_figure_image(arxiv_id)
        if not image_url:
            continue
        image_path = download_image(image_url, title)
        if image_path:
            image_map[normalized_title(title)] = image_path
    return image_map

author: dict = scholarly.search_author_id(os.environ['GOOGLE_SCHOLAR_ID'])
scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
name = author['name']
author['updated'] = str(datetime.now())

for publication in author['publications']:
    try:
        scholarly.fill(publication)
    except Exception as error:
        print(f"Failed to fill publication {publication.get('author_pub_id')}: {error}")

publication_image_map = build_publication_image_map(author['publications'])
author['publications'] = {v['author_pub_id']:v for v in author['publications']}
print(json.dumps(author, indent=2))
os.makedirs('results', exist_ok=True)
with open(f'results/gs_data.json', 'w') as outfile:
    json.dump(author, outfile, ensure_ascii=False)

with open(f'results/publication_images.json', 'w') as outfile:
    json.dump(publication_image_map, outfile, ensure_ascii=False, indent=2)

shieldio_data = {
  "schemaVersion": 1,
  "label": "citations",
  "message": f"{author['citedby']}",
}
with open(f'results/gs_data_shieldsio.json', 'w') as outfile:
    json.dump(shieldio_data, outfile, ensure_ascii=False)
