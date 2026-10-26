
<h1 align="center">
AcadHomepage
</h1>

<div align="center">

[![](https://img.shields.io/github/stars/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io)
[![](https://img.shields.io/github/forks/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io)
[![](https://img.shields.io/github/issues/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io)
[![](https://img.shields.io/github/license/RayeRen/acad-homepage.github.io)](https://github.com/RayeRen/acad-homepage.github.io/blob/main/LICENSE)  | [English README](../README.md) 

</div>

<p align="center">一个现代、响应式的个人学术主页</p>


<p align="center">
    <br>
    <img src="./screenshot.png" width="100%"/>
    <br>
</p>

一些例子：
- [样例页面](https://rayeren.github.io/acad-homepage.github.io/)
- [作者的个人主页](https://rayeren.github.io/)

## 主要特点
- **自动更新谷歌学术引用**: 借助谷歌学术爬虫和github action功能，本仓库可以自动更新作者的引用数和论文引用数。
- **支持谷歌Analytics**: 你可以通过简单的配置来实现使用谷歌Analytics跟踪网页的流量。
- **响应式的**: 此主页会针对不同的屏幕尺寸自动调整布局。
- **美观而简约**: 此主页美观而简约，适合个人学术主页的搭建。
- **搜索引擎优化**: 搜索引擎优化 (SEO) 帮助搜索引擎轻松找到您在主页上发布的信息，然后将其与类似网站进行排名，并获得排名优势。

## 当前仓库：本地论文同步

论文内容由 `_data/publications.json` 统一提供，Jekyll 在构建时生成完整 HTML。人工维护的标题、作者、会议名称、配图、项目和代码链接保存在 `_data/publication_overrides.json`，使用 Scholar 论文 ID 匹配。个人介绍、教育经历等仍在 `_pages/about.md` 中编辑。

首次安装 Python 依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r google_scholar_crawler/requirements.txt
```

本地 Jekyll 环境安装完成后，一条命令抓取并构建，再启动预览：

```bash
bash sync_publications.sh
bash run_server.sh
```

访问 `http://127.0.0.1:4000`。Scholar ID 自动从 `_config.yml` 的 `author.googlescholar` 链接读取。每次更新论文列表和引用数；未变化的论文复用详情缓存，新论文及变化条目会获取详情。需要全量刷新详情时使用 `bash sync_publications.sh --refresh-details`。

抓取超时、空列表、数据格式错误或作者 ID 不匹配时，不覆盖已有首页数据。暂时从 Scholar 消失的论文也会保留，等待人工核对。执行状态写入 `.local/scholar-sync-status.json`。`--input path/to/gs_data.json` 可离线重放已有数据，只使用图片/PDF 缓存、不访问网络，保留原始抓取时间。

正常同步会为缺图论文自动提取 PDF 的 Figure 1。支持解析 arXiv、CVF、OpenReview、Springer 的论文链接，以及出版商页面中明确提供的 PDF 元数据或链接。在 PDF 前 12 页定位 Figure 1 图注，合并图注上方的矢量图、位图、文字标注和子图，渲染为完整 PNG。无法可靠定位图形或无法下载 PDF 时记录原因，不用整页截图代替。版面识别采用启发式规则，新增图片应在本地预览中检查。

`_data/publication_overrides.json` 中的人工 `image` 优先保留；显式设置 `"image": ""` 可关闭某篇论文的自动配图。生成的图片位于 `images/publications/`，PDF 来源、校验值、页码及裁剪坐标记录在 `_data/publication_images.json`。下载的 PDF 缓存在被 Git 忽略的 `.local/publication-pdfs/`。下次同步复用成功图片；失败时保留旧图，继续更新论文信息和构建网站。提图有独立的 240 秒超时（`--image-timeout`），单个 PDF 上限为 64 MiB。每篇论文的处理结果见 `.local/publication-image-status.json`。

```bash
bash sync_publications.sh --images-only     # 使用已有论文列表，仅补齐配图
bash sync_publications.sh --skip-images     # 只更新论文信息，保留现有图片
bash sync_publications.sh --images-only --refresh-images  # 重新下载并提取自动配图
```

本地 Ruby 环境准备方式见英文 README；`scripts/jekyll.sh` 自动优先使用项目内的 `.local/gems` 和 `vendor/bundle`。验证命令：`.venv/bin/python -m unittest discover -s tests -v`。

简历导出也读取同一份论文数据。只验证 LaTeX 源码、保留现有下载文件时运行：

```bash
RESUME_OUTPUT_DIR=.local/resume-check SKIP_PDF=1 ruby scripts/export_resume.rb
```

编译 PDF 仍需安装 XeLaTeX/latexmk。当前只打通本地流程；原有 GitHub 工作流仍将原始数据写到 `google-scholar-stats` 分支，尚未接入新的快照构建和部署流程，也未重新启用定时运行。下方是原模板的配置说明。

## 原模板配置（旧 Scholar 工作流）

1. Fork本仓库到`USERNAME/USERNAME.github.io`，其中`USERNAME`是你的github用户名。
1. 配置谷歌学术引用爬虫：
    1. 在你的谷歌学术引用页面的url里找到你的谷歌学术ID：例如，在url https://scholar.google.com/citations?user=SCHOLAR_ID 中，`SCHOLAR_ID`部分即为你的谷歌学术ID。
    1. 在github本仓库页面的`Settings -> Secrets -> Actions -> New repository secret`中，添加`GOOGLE_SCHOLAR_ID`变量：`name=GOOGLE_SCHOLAR_ID`、`value=SCHOLAR_ID`。
    1. 在github本仓库页面的`Action`中，点击*"I understand my workflows, go ahead and enable them"*启用workflows by clicking *"。本action将会谷歌学术引用的统计量数据`gs_data.json`到本仓库的`google-scholar-stats`分支中。每次修改main分支的内容会触发该action。本action也会在每天08:00 UTC定时触发。
1. 使用 [favicon-generator](https://redketchup.io/favicon-generator)生成favicon（网页icon文件），并下载所有文件到`REPO/images`。
1. 修改主页配置文件[_config.yml](../_config.yml):
    1. `title`: 主页标题
    1. `description`: 主页的描述
    1. `repository`: USER_NAME/REPO_NAME  
    1. `google_analytics_id` (可选的): 谷歌Analytics ID
    1. SEO相关的键值 (可选的): 从搜索引擎的控制台里获得对应的ID (例如：Google, Bing and Baidu)，然后粘贴到这里。
    1. `author`: 主页作者信息，包括其他网页、Email、所在城市、大学等。
    1. `google_scholar_stats_use_cdn`: 使用CDN读取存储于`https://raw.githubusercontent.com/`的google scholar引用统计数据，防止中国大陆地区被墙无法访问的情况。但是CDN有缓存，因此`google_scholar_stats_use_cdn : True`时，引用数据更新会有延迟。
    1. 更多的配置信息在注释中有详细描述。
1. 将你的主页内容添加到 [_pages/about.md](../_pages/about.md).
1. 你的主页将会被部署到`https://USERNAME.github.io`.

## 本地调试

1. 使用`git clone`将本项目克隆到本地。
1. 安装Jekyll的构建环境，包括`Ruby`、`RubyGems`、`GCC`和`Make`。可参考[该教程](https://jekyllrb.com/docs/installation/#requirements)。
1. 运行 `bash run_server.sh` 来启动Jekyll实时重载服务器。
1. 在浏览器里打开 [http://127.0.0.1:4000](http://127.0.0.1:4000)。如果你修改了网页的源码，服务器会自动重新编译并刷新页面。
1. 当你修改完毕你的页面以后, 使用`git`命令，`commit`你的改动并`push`到你的github仓库中。

## 导出简历

运行下面的命令，可以根据 `_config.yml`、`_pages/about.md` 和 `_data/publications.json` 自动导出 LaTeX 简历源码：

```bash
ruby scripts/export_resume.rb
```

导出文件位于 `resume/Mingliang_Zhai_CV.tex`。如果本地安装了 `xelatex` 或 `latexmk`，脚本会同时编译生成 `resume/Mingliang_Zhai_CV.pdf`。

仓库也内置了 **Export Resume** GitHub Actions 工作流，可以手动触发；当主页内容变化时也会自动运行，并把 `.tex` 和 `.pdf` 作为 artifact 上传。

# Acknowledges

- AcadHomepage incorporates Font Awesome, which is distributed under the terms of the SIL OFL 1.1 and MIT License.
- AcadHomepage is influenced by the github repo [mmistakes/minimal-mistakes](https://github.com/mmistakes/minimal-mistakes), which is distributed under the MIT License.
- AcadHomepage is influenced by the github repo [academicpages/academicpages.github.io](https://github.com/academicpages/academicpages.github.io), which is distributed under the MIT License.
