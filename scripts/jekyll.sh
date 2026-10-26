#!/usr/bin/env bash
set -euo pipefail
site_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$site_root"
if [[ -x "$site_root/.local/gems/bin/bundle" ]]; then
  export GEM_HOME="$site_root/.local/gems"
  export GEM_PATH="$GEM_HOME"
  export BUNDLE_PATH="$site_root/vendor/bundle"
  exec "$GEM_HOME/bin/bundle" exec jekyll "$@"
fi
exec bundle exec jekyll "$@"
