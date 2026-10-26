#!/usr/bin/env python3
"""Fetch Scholar, validate and merge a snapshot, then publish it locally."""
import argparse
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from merge_publications import ROOT, atomic_json, configured_scholar_id, merge_snapshot, read_json, validate_snapshot


def sync(input_path=None, timeout=240, refresh_details=False, images=True,
         image_timeout=240, refresh_images=False, images_only=False):
    scholar_id = configured_scholar_id()
    output = ROOT / "_data/publications.json"
    with tempfile.TemporaryDirectory(prefix="scholar-sync-") as temporary:
        if images_only:
            source = ROOT / "google_scholar_crawler/results/gs_data.json"
        elif input_path:
            source = Path(input_path)
        else:
            command = [sys.executable, str(ROOT / "google_scholar_crawler/main.py"), "--scholar-id", scholar_id, "--output-dir", temporary]
            if refresh_details:
                command.append("--refresh-details")
            subprocess.run(command, check=True, timeout=timeout, cwd=ROOT)
            source = Path(temporary) / "gs_data.json"
        data = read_json(source)
        validate_snapshot(data, scholar_id)
        merged = merge_snapshot(data, read_json(ROOT / "_data/publication_overrides.json"), read_json(output) if output.exists() else None)
        # Validate everything before changing any published data.
        atomic_json(ROOT / "google_scholar_crawler/results/gs_data.json", data)
        atomic_json(output, merged)
        # Publish valid metadata first. Image failures/timeouts are non-fatal;
        # the worker saves each success atomically, preserving earlier images.
        if images:
            image_status_path = ROOT / ".local/publication-image-status.json"
            atomic_json(image_status_path, {"attempted_at": datetime.now(timezone.utc).isoformat(), "papers": {}})
            command = [sys.executable, str(ROOT / "scripts/publication_images.py")]
            if input_path:
                command.append("--offline")
            if refresh_images:
                command.append("--refresh")
            try:
                subprocess.run(command, check=True, timeout=image_timeout, cwd=ROOT)
            except (OSError, subprocess.SubprocessError) as error:
                print(f"Image stage incomplete; metadata and completed images retained: {error}", file=sys.stderr)
                image_status = read_json(image_status_path)
                image_status.update(error=str(error), incomplete=True)
                atomic_json(image_status_path, image_status)
            merged = read_json(output)
        return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="Offline replay: saved snapshot and cached images/PDFs only")
    source.add_argument("--images-only", action="store_true", help="Reuse the saved Scholar snapshot and fetch missing PDF figures")
    parser.add_argument("--timeout", type=int, default=240, help="Total live-fetch deadline in seconds")
    parser.add_argument("--refresh-details", action="store_true", help="Refresh every paper's details, including cached ones")
    parser.add_argument("--skip-images", action="store_true", help="Only sync metadata; keep existing images")
    parser.add_argument("--refresh-images", action="store_true", help="Re-download PDFs and regenerate automatic images; preserve manual images")
    parser.add_argument("--image-timeout", type=int, default=240, help="Separate image-stage deadline in seconds")
    args = parser.parse_args()
    if args.refresh_images and (args.skip_images or args.input):
        parser.error("--refresh-images cannot be combined with --skip-images or offline --input")
    if args.timeout <= 0 or args.image_timeout <= 0:
        parser.error("Timeouts must be positive")
    mode = "images-only" if args.images_only else "offline" if args.input else "live"
    status = {"attempted_at": datetime.now(timezone.utc).isoformat(), "mode": mode}
    try:
        data = sync(args.input, args.timeout, args.refresh_details, not args.skip_images,
                    args.image_timeout, args.refresh_images, args.images_only)
        status.update(success=True, updated=data["updated"], publications=len(data["publications"]))
        if not args.skip_images and (ROOT / ".local/publication-image-status.json").exists():
            status["images"] = read_json(ROOT / ".local/publication-image-status.json")
        print(f"{mode} sync complete: {data['source_count']} Scholar papers, {len(data['publications'])} displayed, {data['total_citations']} citations.")
        print(f"Data timestamp: {data['updated']}")
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        status.update(success=False, error=str(error))
        print(f"Sync failed; existing homepage data retained: {error}", file=sys.stderr)
    atomic_json(ROOT / ".local/scholar-sync-status.json", status)
    return 0 if status["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
