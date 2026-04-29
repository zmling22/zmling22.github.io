#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "yaml"

ROOT = File.expand_path("..", __dir__)
CONFIG_PATH = File.join(ROOT, "_config.yml")
ABOUT_PATH = File.join(ROOT, "_pages", "about.md")
OUT_DIR = File.join(ROOT, "resume")
TEX_PATH = File.join(OUT_DIR, "Mingliang_Zhai_CV.tex")
PDF_PATH = File.join(OUT_DIR, "Mingliang_Zhai_CV.pdf")

SECTION_KEYS = {
  "biography" => "Biography",
  "educations" => "Education",
  "publications" => "Publications",
  "awards" => "Honors and Awards",
  "internships" => "Internship"
}.freeze

def latex_escape(text)
  text.to_s
      .gsub("\\", "\\textbackslash{}")
      .gsub("&", "\\&")
      .gsub("%", "\\%")
      .gsub("$", "\\$")
      .gsub("#", "\\#")
      .gsub("_", "\\_")
      .gsub("{", "\\{")
      .gsub("}", "\\}")
      .gsub("~", "\\textasciitilde{}")
      .gsub("^", "\\textasciicircum{}")
end

def inline_md_to_latex(text)
  protected = []
  protect = lambda do |latex|
    token = "@@LATEX#{protected.length}@@"
    protected << latex
    token
  end

  value = text.to_s.strip
  value = value.gsub(%r{<a\s+href="[^"]+"[^>]*>\s*<img[^>]*>\s*</a>}m, "")
  value = value.gsub(%r{<img[^>]*>}, "")
  value = value.gsub(%r{<a\s+href="([^"]+)"[^>]*>(.*?)</a>}m) do
    label = inline_md_to_latex(Regexp.last_match(2))
    label.empty? ? "" : protect.call("\\href{#{Regexp.last_match(1)}}{#{label}}")
  end
  value = value.gsub(/\[\[([^\]]+)\]\]\(([^)]+)\)/) do
    protect.call("\\href{#{Regexp.last_match(2)}}{[#{latex_escape(Regexp.last_match(1))}]}")
  end
  value = value.gsub(/\[([^\]]+)\]\(([^)]+)\)/) do
    protect.call("\\href{#{Regexp.last_match(2)}}{#{latex_escape(Regexp.last_match(1))}}")
  end
  value = value.gsub(/\*\*([^*]+)\*\*/) { protect.call("\\textbf{#{latex_escape(Regexp.last_match(1))}}") }
  value = value.gsub(/\*([^*]+)\*/) { protect.call("\\textit{#{latex_escape(Regexp.last_match(1))}}") }
  value = value.gsub(/`([^`]+)`/) { protect.call("\\texttt{#{latex_escape(Regexp.last_match(1))}}") }
  value = value.gsub(%r{</?[^>]+>}, "")

  escaped = latex_escape(value)
  protected.each_with_index { |latex, index| escaped = escaped.gsub("@@LATEX#{index}@@", latex) }
  escaped
end

def strip_front_matter(markdown)
  markdown.sub(/\A---\n.*?\n---\n/m, "")
end

def extract_sections(markdown)
  sections = {}
  current = nil

  strip_front_matter(markdown).each_line do |line|
    if line =~ /<span class='anchor' id='-([^']+)'><\/span>/
      current = Regexp.last_match(1)
      sections[current] = []
      next
    end

    sections[current] << line if current
  end

  sections.transform_values { |lines| lines.join.strip }
end

def clean_section(markdown)
  markdown.lines.reject { |line| line.strip.start_with?("#") }.join.strip
end

def biography_to_latex(markdown)
  lines = clean_section(markdown).lines.map(&:strip).reject(&:empty?)
  bullets = lines.select { |line| line.start_with?("- ") }
  paragraphs = lines.reject { |line| line.start_with?("- ") }
  body = paragraphs.join(" ")
  output = [inline_md_to_latex(body)]

  unless bullets.empty?
    items = bullets.map { |line| "\\item #{inline_md_to_latex(line.delete_prefix("- "))}" }
    output << "\\begin{itemize}[leftmargin=*]\n#{items.join("\n")}\n\\end{itemize}"
  end

  output.join("\n\n")
end

def list_to_latex(markdown)
  items = clean_section(markdown).lines.map do |line|
    stripped = line.strip
    next unless stripped.start_with?("- ")

    "\\item #{inline_md_to_latex(stripped.delete_prefix("- "))}"
  end.compact
  return "" if items.empty?

  "\\begin{itemize}[leftmargin=*]\n#{items.join("\n")}\n\\end{itemize}"
end

def publications_to_latex(markdown)
  entries = markdown.scan(%r{<div class='paper-box-text' markdown="1">(.*?)</div>}m).flatten
  items = entries.map do |entry|
    lines = entry.lines.map(&:strip).reject(&:empty?)
    title = lines.find { |line| line.start_with?("**") } || lines.first
    details = lines.reject { |line| line == title }.map do |line|
      next unless line.start_with?("- ")

      inline_md_to_latex(line.delete_prefix("- "))
    end.compact

    body = ["\\textbf{#{inline_md_to_latex(title.gsub(/\A\*\*|\*\*\z/, ""))}}"]
    body.concat(details)
    "\\item #{body.join("\\\\\n")}"
  end
  return "" if items.empty?

  "\\begin{enumerate}[leftmargin=*]\n#{items.join("\n")}\n\\end{enumerate}"
end

def section_body(key, markdown)
  case key
  when "biography"
    biography_to_latex(markdown)
  when "publications"
    publications_to_latex(markdown)
  else
    list_to_latex(markdown)
  end
end

def build_tex(config, sections)
  author = config.fetch("author", {})
  name = [author["name"], author["name_zh"]].compact.join(" ")
  email = author["email"]
  scholar = author["googlescholar"]
  location = author["location"]
  bio = author["bio"]

  section_tex = SECTION_KEYS.map do |key, title|
    body = section_body(key, sections.fetch(key, ""))
    next if body.empty?

    "\\section*{#{latex_escape(title)}}\n#{body}"
  end.compact.join("\n\n")

  <<~TEX
    % Auto-generated by scripts/export_resume.rb. Edit _config.yml and _pages/about.md, then regenerate.
    \\documentclass[11pt,a4paper]{article}
    \\usepackage[margin=1.8cm]{geometry}
    \\usepackage{ctex}
    \\usepackage{enumitem}
    \\usepackage[hidelinks]{hyperref}
    \\usepackage{titlesec}
    \\usepackage{xcolor}

    \\setlength{\\parindent}{0pt}
    \\setlength{\\parskip}{0.45em}
    \\setlist{nosep}
    \\titleformat{\\section}{\\large\\bfseries\\color{black}}{}{0em}{}[\\titlerule]

    \\begin{document}

    \\begin{center}
      {\\LARGE\\bfseries #{latex_escape(name)}}\\\\[0.4em]
      #{[email && "\\href{mailto:#{email}}{#{latex_escape(email)}}", scholar && "\\href{#{scholar}}{Google Scholar}", location && latex_escape(location), bio && latex_escape(bio)].compact.join(" \\quad ")}
    \\end{center}

    #{section_tex}

    \\end{document}
  TEX
end

def compiler
  ENV["LATEX_COMPILER"] || %w[xelatex latexmk].find { |cmd| system("command -v #{cmd} >/dev/null 2>&1") }
end

def compile_pdf
  cmd = compiler
  return warn("LaTeX compiler not found. Generated #{TEX_PATH}, but skipped PDF compilation.") unless cmd

  compile_cmd =
    if File.basename(cmd) == "latexmk"
      [cmd, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", File.basename(TEX_PATH)]
    else
      [cmd, "-interaction=nonstopmode", "-halt-on-error", File.basename(TEX_PATH)]
    end

  _stdout, stderr, status = Open3.capture3(*compile_cmd, chdir: OUT_DIR)
  abort(stderr) unless status.success?
  puts "Generated #{PDF_PATH}" if File.exist?(PDF_PATH)
end

FileUtils.mkdir_p(OUT_DIR)
config = YAML.load_file(CONFIG_PATH)
sections = extract_sections(File.read(ABOUT_PATH))
File.write(TEX_PATH, build_tex(config, sections))
puts "Generated #{TEX_PATH}"
compile_pdf
