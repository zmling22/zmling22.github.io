#!/usr/bin/env bash
set -euo pipefail
site_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$site_root"
if [[ ! -x .venv/bin/python ]]; then
  printf '%s\n' 'Create the local environment first:' 'python3 -m venv .venv' '.venv/bin/python -m pip install -r google_scholar_crawler/requirements.txt' >&2
  exit 1
fi
.venv/bin/python scripts/sync_publications.py "$@"
bash scripts/jekyll.sh build
