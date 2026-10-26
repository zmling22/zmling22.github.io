#!/usr/bin/env bash
set -euo pipefail
site_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$site_root/scripts/jekyll.sh" serve --host 127.0.0.1 "$@"
