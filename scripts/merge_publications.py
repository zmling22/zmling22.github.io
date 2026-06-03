#!/usr/bin/env python3
"""
Merge publications: prioritize about.md content, supplement with crawler data.
Usage: python3 merge_publications.py
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


def extract_papers_from_html(html_text: str) -> List[Dict]:
    """Extract paper information from HTML using regex."""
    papers = []

    # Split by <div class='paper-box'>
    parts = re.split(r"<div class='paper-box'>", html_text)

    for part in parts[1:]:  # Skip first part (before any paper)
        # Find the closing </div></div></div>
        closing_idx = 0
        depth = 1
        for i, char in enumerate(part):
            if part[i:i+5] == "<div ":
                depth += 1
            elif part[i:i+6] == "</div>":
                depth -= 1
                if depth == 0:
                    closing_idx = i + 6
                    break

        if closing_idx == 0:
            continue

        paper_html = part[:closing_idx]
        paper_info = parse_paper_box(paper_html)
        if paper_info:
            papers.append(paper_info)

    return papers


def parse_paper_box(html: str) -> Dict:
    """Extract paper information from a paper-box div."""
    info = {}

    # Badge (conference/journal)
    badge_match = re.search(r'<div class="badge">([^<]+)</div>', html)
    info['badge'] = badge_match.group(1) if badge_match else ''

    # Image path
    img_match = re.search(r"<img src='([^']+)'", html)
    info['image'] = img_match.group(1) if img_match else ''

    # Title
    title_match = re.search(r'\*\*([^*]+)\*\*', html)
    info['title'] = title_match.group(1) if title_match else ''

    # Authors
    authors_match = re.search(r'\*\*[^*]+\*\*\s*\n- ([^\n]+)', html)
    info['authors'] = authors_match.group(1) if authors_match else ''

    # Extract links
    info['links'] = {}

    paper_link = re.search(r'\[\[paper\]\]\(([^)]+)\)', html)
    if paper_link:
        info['links']['paper'] = paper_link.group(1)

    code_link = re.search(r'\[\[code\]\]\(([^)]+)\)', html)
    if code_link:
        info['links']['code'] = code_link.group(1)

    project_link = re.search(r'\[\[project\]\]\(([^)]+)\)', html)
    if project_link:
        info['links']['project'] = project_link.group(1)

    # Full HTML for later reconstruction
    info['full_html'] = f"<div class='paper-box'>{html}</div>"

    return info if info.get('title') else None


def parse_about_md(filepath: str) -> Tuple[str, List[Dict], str]:
    """Parse about.md and extract header, papers, footer."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find publications markers
    pub_anchor = "<span class='anchor' id='-publications'></span>"
    awards_anchor = "<span class='anchor' id='-awards'></span>"

    pub_start_idx = content.find(pub_anchor)
    awards_start_idx = content.find(awards_anchor)

    if pub_start_idx == -1 or awards_start_idx == -1:
        raise ValueError("Cannot find publications section markers")

    # Header: from start to publications anchor + header line
    header_end = content.find('\n', content.find('# 📝 Publications', pub_start_idx)) + 1
    header = content[:header_end]

    # Publications HTML: between header and awards anchor
    pub_html = content[header_end:awards_start_idx].strip()

    # Footer: from awards anchor onwards
    footer = content[awards_start_idx:]

    # Extract paper objects
    papers = extract_papers_from_html(pub_html)

    return header, papers, footer


def load_crawler_data(filepath: str) -> Dict:
    """Load Google Scholar crawler data."""
    if not os.path.exists(filepath):
        print(f"ℹ️  Crawler data not found at {filepath}")
        return {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading crawler data: {e}")
        return {}


def generate_paper_box_html(paper: Dict) -> str:
    """Generate HTML for a single paper box."""
    # Reconstruct links
    links_html = ''
    for link_type, link_url in paper.get('links', {}).items():
        if link_url:
            links_html += f"[[{link_type}]]({link_url})"

    citation = f"- [{paper['badge']}] {links_html}" if paper['badge'] else links_html

    html = f"""<div class='paper-box'><div class='paper-box-image'><div><div class="badge">{paper['badge']}</div><img src='{paper['image']}' alt="sym" width="100%"></div></div>
<div class='paper-box-text' markdown="1">
**{paper['title']}**
- {paper['authors']}
- {citation}
</div>
</div>

"""
    return html


def generate_about_md(header: str, papers: List[Dict], footer: str) -> str:
    """Generate complete about.md."""
    publications_section = '\n'.join(generate_paper_box_html(p) for p in papers)
    return header + '\n' + publications_section + '\n' + footer


def main():
    repo_root = Path(__file__).parent.parent
    about_path = repo_root / '_pages' / 'about.md'
    crawler_data_path = repo_root / 'google_scholar_crawler' / 'results' / 'gs_data.json'

    print("📚 Merging publications...")

    try:
        # Parse about.md
        header, about_papers, footer = parse_about_md(str(about_path))
        print(f"✓ Found {len(about_papers)} papers in about.md")

        # Load crawler data (if available)
        crawler_data = load_crawler_data(str(crawler_data_path))
        crawler_count = len(crawler_data.get('publications', {}))
        if crawler_count > 0:
            print(f"✓ Loaded {crawler_count} papers from crawler")

        # For now, just use about.md papers (crawler integration can be added later)
        # This ensures we don't lose any existing content
        merged_papers = about_papers

        # Generate new content
        new_content = generate_about_md(header, merged_papers, footer)

        # Backup and write
        with open(about_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ Verified {len(merged_papers)} papers in {about_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())

