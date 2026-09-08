#!/usr/bin/env python3
"""Render companion Markdown into standalone community HTML (Python-Markdown)."""
from pathlib import Path
import html
import markdown

root = Path(__file__).resolve().parents[1] / "releases/2.1.0-rc.2/install-v1"
for name in ("INSTALL", "DOWNLOADS", "DATASETS"):
    text = (root / (name + ".md")).read_text()
    for linked in ("INSTALL", "DOWNLOADS", "DATASETS"):
        text = text.replace(linked + ".md", linked + ".html")
    body = markdown.markdown(text, extensions=["fenced_code", "tables", "toc"])
    title = html.escape(text.splitlines()[0].lstrip("# "))
    output = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<meta name="color-scheme" content="dark"><title>' + title + '</title>'
              '<link rel="stylesheet" href="../assets/release.css"></head><body>'
              '<a class="skip-link" href="#main">Skip to guide</a>'
              '<header class="site-header"><nav class="nav shell" aria-label="Guide navigation">'
              '<a class="brand" href="index.html"><img src="../assets/bdag-community-logo.svg" alt="" width="42" height="42">'
              '<span><strong>BlockDAG RC2</strong><small>Installation companion v1</small></span></a>'
              '<div class="nav-links"><a href="INSTALL.html">Install</a><a href="DOWNLOADS.html">Download</a>'
              '<a href="DATASETS.html">Datasets</a><a href="AGENTS.md">AI agents</a></div></nav></header>'
              '<main id="main" class="section shell guide"><article class="glass">' + body + '</article></main>'
              '<footer><div class="shell"><a href="../index.html">Community release page</a> · '
              '<a href="' + name + '.md">Plain-text source</a></div></footer></body></html>\n')
    (root / (name + ".html")).write_text(output)
