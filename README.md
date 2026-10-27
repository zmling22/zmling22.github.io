
<h1 align="center">
AcadHomepage
</h1>

<div align="center">

[![](https://img.shields.io/github/stars/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io)
[![](https://img.shields.io/github/forks/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io)
[![](https://img.shields.io/github/issues/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io)
[![](https://img.shields.io/github/license/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io/blob/main/LICENSE)  | [中文文档](./docs/README-zh.md) 
</div>

<p align="center">A Modern and Responsive Academic Personal Homepage</p>

<p align="center">
    <br>
    <img src="docs/screenshot.png" width="100%"/>
    <br>
</p>

Some examples:
- [Demo Page](https://rayeren.github.io/acad-homepage.github.io/)
- [Personal Homepage of the author](https://rayeren.github.io/)

## Key Features
- **Automatically update google scholar citations**: using the google scholar crawler and github action, this REPO can update the author citations and publication citations automatically.
- **Support Google analytics**: you can trace the traffics of your homepage by easy configuration.
- **Responsive**: this homepage automatically adjust for different screen sizes and viewports.
- **Beautiful and Simple Design**: this homepage is beautiful and simple, which is very suitable for academic personal homepage.
- **SEO**: search Engine Optimization (SEO) helps search engines find the information you publish on your homepage easily, then rank it against similar websites.

## Local publication sync (this repository)

The homepage now renders `_data/publications.json` at Jekyll build time. Curated titles, authors, venue labels, images and project/code links are stored in `_data/publication_overrides.json`, keyed by Google Scholar publication ID. Other sections remain in `_pages/about.md`.

Set up Python once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r google_scholar_crawler/requirements.txt
```

With the Jekyll dependencies installed, fetch and rebuild with:

```bash
bash sync_publications.sh
bash run_server.sh
```

Open `http://127.0.0.1:4000`. The sync command reads the Scholar ID from `author.googlescholar` in `_config.yml`. It refreshes the publication list and citation counts, reuses cached article details when the profile entry is unchanged, and fetches new/changed articles. Use `bash sync_publications.sh --refresh-details` to refresh all details. No credentials are needed for the public profile.

Invalid/empty responses, a wrong profile ID, or a fetch timeout fail without replacing the existing homepage snapshot. Missing papers are retained pending manual review. Attempts are recorded in `.local/scholar-sync-status.json`; `updated` always describes the successful source snapshot. `--input path/to/gs_data.json` replays a saved snapshot using only cached images/PDFs, with no network requests and no new fetch timestamp.

Normal sync also fills missing illustrations from PDF Figure 1. It resolves arXiv, CVF, OpenReview and Springer paper URLs and explicit PDF links in publisher metadata. It searches the first 12 PDF pages for a Figure 1 caption, groups the vector/raster graphics above it, and renders the entire region (including labels and subpanels) as a PNG. Ambiguous layouts and inaccessible PDFs are reported rather than replaced with arbitrary page screenshots. This is a layout heuristic; review newly generated figures in the local preview.

Manual `image` entries in `_data/publication_overrides.json` always win; an explicit empty `image` disables automatic extraction for that paper. Generated PNGs are stored in `images/publications/`, with source URL, PDF hash, page and crop coordinates in `_data/publication_images.json`. Downloaded PDFs stay in the ignored `.local/publication-pdfs/` cache. Successful images are reused; failed downloads/extractions keep the existing image and do not stop metadata updates or site builds. The image stage has a separate 240-second deadline (`--image-timeout`) and a 64 MiB PDF limit. Per-paper results are in `.local/publication-image-status.json`.

```bash
bash sync_publications.sh --images-only     # Fill missing figures using the saved Scholar list
bash sync_publications.sh --skip-images     # Update metadata only; preserve all images
bash sync_publications.sh --images-only --refresh-images  # Re-download/re-extract automatic figures
```

For an isolated Ruby installation like the one prepared locally here:

```bash
env GEM_HOME="$PWD/.local/gems" GEM_PATH="$PWD/.local/gems" gem install bundler -v 2.2.19 --no-document
env GEM_HOME="$PWD/.local/gems" GEM_PATH="$PWD/.local/gems" BUNDLE_PATH="$PWD/vendor/bundle" .local/gems/bin/bundle install
```

`scripts/jekyll.sh` uses that environment when available, otherwise your normal Bundler installation. Regression checks: `.venv/bin/python -m unittest discover -s tests -v`.

## Scheduled publication sync

**Sync Publications** (`.github/workflows/sync_publications.yaml`) runs on Mondays and Thursdays at 08:17 UTC / 16:17 Asia/Shanghai, with 3–4 days between runs. It can also be started from Actions → Sync Publications → Run workflow. It reads the public Scholar profile from `_config.yml`; no Scholar secret is required.

The workflow installs pinned Python dependencies, checks the sync code, fetches and validates live Scholar data, extracts missing PDF Figure 1 illustrations, and commits `_data/publications.json`, `_data/publication_images.json` and `images/publications/` to `main`. Scholar details and downloaded PDFs are cached. A failed fetch stops the job without publishing incomplete metadata. Individual PDF failures retain existing images and are listed in the run summary and diagnostic artifact.

**Deploy Homepage** (`.github/workflows/pages.yaml`) builds and deploys the site on pushes to `main`. The sync workflow also calls it explicitly after its data commit: commits made with `GITHUB_TOKEN` do not start push workflows. Set Settings → Pages → Source to **GitHub Actions**. The old `Get Citation Data` workflow has been removed; the `google-scholar-stats` branch is no longer used. Local sync commands never push or deploy.

GitHub may delay scheduled starts. If the repository has no activity for 60 days, GitHub can disable its schedule; re-enable **Sync Publications** in Actions if that happens. Successful syncs commit their fresh source timestamp even when the paper list is unchanged.

## Personal pixel favicon

The favicon is a pixel portrait based on the existing profile photo. The generated master is `images/pixel-avatar.png`; the built-in image-generation prompt is saved in `scripts/favicon-prompt.txt`. To export the 16/32 px browser icons, multi-size ICO, Apple touch icon and Android icons on macOS, run `swift scripts/export_favicons.swift`. The exporter uses nearest-neighbor sampling to preserve pixel edges. When replacing the artwork again, update the icon version in `_includes/head/custom.html` and `images/site.webmanifest` to refresh browser caches.

## Site setup

1. Fork this REPO and rename to `USERNAME.github.io`, where `USERNAME` is your github USERNAME.
1. Set your public Google Scholar URL in `author.googlescholar` in `_config.yml`. Enable **Sync Publications** in Actions and select **GitHub Actions** as the Pages source, as described above.
1. Generate favicon using [favicon-generator](https://redketchup.io/favicon-generator) and download all generated files to `REPO/images`.
1. Modify the configuration of your homepage `_config.yml`:
    1. `title`: the title of your homepage
    1. `description`: the description of your homepage
    1. `repository`: USER_NAME/REPO_NAME  
    1. `google_analytics_id` (optional): google analytics ID
    1. SEO Related keys (optional): get these keys from search engine consoles (e.g. Google, Bing and Baidu) and paste here.
    1. `author`: the author information of this homepage, including some other websites, emails, city and univeristy.
    1. More configuration details are described in the comments.
1. Add your homepage content in `_pages/about.md`.
    1. You can use html+markdown syntax just same as jekyll.
    1. Maintain publication corrections and links in `_data/publication_overrides.json`, then run the local sync command above.
1. Your page will be published at `https://USERNAME.github.io`.

## Debug Locally

1. Clone your REPO to local using `git clone`.
1. Install Jekyll building environment, including `Ruby`, `RubyGems`, `GCC` and `Make` following [the installation guide](https://jekyllrb.com/docs/installation/#requirements).
1. Run `bash run_server.sh` to start Jekyll livereload server.
1. Open http://127.0.0.1:4000 in your browser.
1. If you change the source code of the website, the livereload server will automatically refresh.
1. When you finish the modification of your homepage, `commit` your changings and `push` to your remote REPO using `git` command.

## Export Resume

Run the following command to export a LaTeX resume from `_config.yml`, `_pages/about.md`, and `_data/publications.json`:

```bash
ruby scripts/export_resume.rb
```

For a source-only check without changing the downloaded CV, use `RESUME_OUTPUT_DIR=.local/resume-check SKIP_PDF=1 ruby scripts/export_resume.rb`. PDF compilation requires a local TeX installation.

The generated files are written to `resume/Mingliang_Zhai_CV.tex` and, when `xelatex` or `latexmk` is installed, `resume/Mingliang_Zhai_CV.pdf`.

GitHub Actions also provides a manual **Export Resume** workflow and automatically uploads the `.tex` and `.pdf` files as workflow artifacts when the homepage content changes.

# Acknowledges

- AcadHomepage incorporates Font Awesome, which is distributed under the terms of the SIL OFL 1.1 and MIT License.
- AcadHomepage is influenced by the github repo [mmistakes/minimal-mistakes](https://github.com/mmistakes/minimal-mistakes), which is distributed under the MIT License.
- AcadHomepage is influenced by the github repo [academicpages/academicpages.github.io](https://github.com/academicpages/academicpages.github.io), which is distributed under the MIT License.
