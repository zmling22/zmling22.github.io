from scholarly import scholarly
import jsonpickle
import json
from datetime import datetime
import os
import re
import mimetypes
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 30 * 1024 * 1024
REQUEST_TIMEOUT = 8
IMAGE_DIR = Path("results/publication-images")
MIN_TEASER_AREA = 80_000
MANUAL_IMAGE_TITLES = {
    "world knowledge-enhanced reasoning using instruction-guided interactor in autonomous driving",
    "fast-structext: an efficient hourglass transformer with modality-guided dynamic token merge for document understanding",
    "in-context compositional generalization for large vision-language models",
    "compositional substitutivity of visual reasoning for visual question answering",
}


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
    return urlopen(request, timeout=REQUEST_TIMEOUT)


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


def pdf_url_from_url(url):
    if re.search(r"\.pdf(?:$|[?#])", url, re.IGNORECASE):
        return url
    arxiv_id = arxiv_id_from_url(url)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return None


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


def pdf_url_from_publication(publication, title):
    for url in publication_urls(publication):
        pdf_url = pdf_url_from_url(url)
        if pdf_url:
            return pdf_url

    arxiv_id = arxiv_id_from_publication(publication, title)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return None


def read_pdf(url):
    try:
        with request_url(url) as response:
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and content_type not in {"application/pdf", "application/x-pdf", "binary/octet-stream"}:
                return None
            data = response.read(MAX_PDF_BYTES + 1)
            if len(data) > MAX_PDF_BYTES:
                print(f"Skipping large PDF {url}")
                return None
            return data
    except Exception as error:
        print(f"Failed to download PDF {url}: {error}")
        return None


def extract_teaser_from_pdf(pdf_bytes, title):
    try:
        import fitz
    except ImportError as error:
        print(f"PyMuPDF is unavailable: {error}")
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        print(f"Failed to open PDF for {title}: {error}")
        return None

    best = None
    try:
        for page_index in range(min(3, doc.page_count)):
            page = doc[page_index]
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 1 or not block.get("image"):
                    continue
                bbox = block.get("bbox", [0, 0, 0, 0])
                width = max(0, bbox[2] - bbox[0])
                height = max(0, bbox[3] - bbox[1])
                area = width * height
                if area < MIN_TEASER_AREA:
                    continue
                if best is None or area > best["area"]:
                    best = {
                        "area": area,
                        "image": block["image"],
                        "extension": block.get("ext", "png"),
                    }
    finally:
        doc.close()

    if not best:
        return None

    extension = best["extension"]
    if extension == "jpeg":
        extension = "jpg"
    path = IMAGE_DIR / f"{slugify(title)}.{extension}"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(best["image"])
    return str(path.relative_to("results"))


def extract_teaser_image(publication, title):
    pdf_url = pdf_url_from_publication(publication, title)
    if not pdf_url:
        return None
    pdf_bytes = read_pdf(pdf_url)
    if not pdf_bytes:
        return None
    return extract_teaser_from_pdf(pdf_bytes, title)


def download_image(image_url, title):
    # Kept for compatibility if future sources provide a verified figure URL.
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
    return None


def build_publication_image_map(publications):
    image_map = {}
    for publication in publications:
        title = publication.get("bib", {}).get("title")
        if not title:
            continue
        if normalized_title(title) in MANUAL_IMAGE_TITLES:
            continue
        image_path = extract_teaser_image(publication, title)
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
