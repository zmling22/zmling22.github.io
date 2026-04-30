from scholarly import scholarly
import jsonpickle
import json
from datetime import datetime
import os
import re
import mimetypes
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_DIR = Path("results/publication-images")


class SocialImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attr_map = {key.lower(): value for key, value in attrs if key and value}
        property_name = (attr_map.get("property") or attr_map.get("name") or "").lower()
        if property_name in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            content = attr_map.get("content")
            if content:
                self.images.append(content)


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


def find_social_image(url):
    try:
        with request_url(url) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None
            html = response.read(1024 * 1024).decode("utf-8", errors="ignore")
    except Exception as error:
        print(f"Failed to read publication page {url}: {error}")
        return None

    parser = SocialImageParser()
    parser.feed(html)
    for image_url in parser.images:
        absolute_url = urljoin(url, image_url)
        if absolute_url.startswith(("http://", "https://")):
            return absolute_url
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
        for url in publication_urls(publication):
            image_url = find_social_image(url)
            if not image_url:
                continue
            image_path = download_image(image_url, title)
            if image_path:
                image_map[normalized_title(title)] = image_path
                break
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
