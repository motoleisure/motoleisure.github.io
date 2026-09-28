#!/usr/bin/env python3
"""Build the LLM Inference Handbook book payload from translated markdown sources.

Source: /Users/tim/my-sys/llm-inference-book/ (README.md + 7 chapter files,
56 sections). Clean markdown: native $$...$$ / $...$ LaTeX, pipe tables,
fenced code blocks, no images.

Pipeline per file:
  strip code fences and code spans -> stash $$...$$ blocks and $...$ spans
  (python-markdown would otherwise treat math _/* as emphasis and split
  inline math across list/paragraph rules) -> markdown -> HTML -> post-process
  (tables wrapped for horizontal scroll, math restored, KaTeX-ready).

Output: assets/books/llm-inference-handbook.bin (plain JSON payload,
chapters = README intro + one chapter per file, sections kept as h2).
"""
import html as html_mod
import json
import os
import re

import markdown as md

SRC_DIR = "/Users/tim/my-sys/llm-inference-book"
SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_OUT = os.path.join(SITE_DIR, "assets", "books", "llm-inference-handbook.bin")

CHAPTERS = [
    ("README.md", "LLM 推理手册"),
    ("01-llm-inference-basics.md", "第 1 章 LLM 推理入门"),
    ("02-getting-started.md", "第 2 章 起步：规划与选型"),
    ("03-inference-optimization.md", "第 3 章 推理优化"),
    ("04-kernel-optimization.md", "第 4 章 内核优化"),
    ("05-model-preparation.md", "第 5 章 模型准备"),
    ("06-model-interaction.md", "第 6 章 模型交互"),
    ("07-infrastructure-and-operations.md", "第 7 章 基础设施与运维"),
]


def md_to_html(text):
    """Markdown -> HTML with math/code protected from markdown rules."""
    # 1. stash fenced code blocks (lang kept for reference)
    fences = []

    def fence_repl(m):
        fences.append(m.group(2))
        return f"\n\n@@FENCE{len(fences)-1}@@\n\n"

    text = re.sub(r"```(\w*)\n(.*?)```", fence_repl, text, flags=re.S)

    # 2. stash inline code spans so their $ characters are not touched
    codes = []

    def code_repl(m):
        codes.append(m.group(1))
        return f"@@CODE{len(codes)-1}@@"

    text = re.sub(r"`([^`\n]+)`", code_repl, text)

    # 3. stash display math $$...$$ (single-line and multi-line blocks)
    maths = []

    def display_repl(m):
        maths.append(("display", m.group(1).strip()))
        return f"@@MATH{len(maths)-1}@@"

    text = re.sub(r"\$\$(.+?)\$\$", display_repl, text, flags=re.S)

    # 4. stash inline math $...$ (same line, non-empty, no $ inside)
    def inline_repl(m):
        maths.append(("inline", m.group(1)))
        return f"@@MATH{len(maths)-1}@@"

    text = re.sub(r"\$([^$\n]+?)\$", inline_repl, text)

    # 5. escape stray backslash-dollar price markers so markdown keeps them
    text = text.replace(r"\$", "&dollar;")

    # 6. markdown -> html
    html = md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])

    # 7. restore code fences (plain pre; replace bare token first — it sits
    # inside a wrapping <p> — then unwrap that paragraph, since <pre> may
    # not legally nest inside <p>)
    for i, body in enumerate(fences):
        esc = html_mod.escape(body)
        html = html.replace(
            f"@@FENCE{i}@@",
            f'<pre class="fence"><code>{esc}</code></pre>')
    html = re.sub(r"<p>(<pre class=\"fence\">.*?</pre>)</p>", r"\1", html, flags=re.S)

    # 8. restore inline code spans
    for i, body in enumerate(codes):
        html = html.replace(
            f"@@CODE{i}@@",
            f"<code>{html_mod.escape(body)}</code>")

    # 9. restore math: display -> centered div, inline -> span, KaTeX-ready
    for i, (kind, body) in enumerate(maths):
        if kind == "display":
            frag = f'<div class="math-display">$$&#10;{html_mod.escape(body)}&#10;$$</div>'
        else:
            frag = f'<span class="math-inline">${html_mod.escape(body)}$</span>'
        # unwrap a paragraph that only wraps this token (lambda: frag may
        # contain backslashes from LaTeX, which re.sub would read as escapes)
        html = re.sub(r"<p>\s*@@MATH%d@@\s*</p>" % i, lambda m: frag, html)
        html = html.replace(f"@@MATH{i}@@", frag)

    # 10. wrap tables for horizontal scroll
    html = html.replace("<table>", '<div class="table-wrap"><table>')
    html = html.replace("</table>", "</table></div>")

    # cleanup: empty paragraphs left by stashed tokens
    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def build():
    chapters = []
    for fname, fallback_title in CHAPTERS:
        path = os.path.join(SRC_DIR, fname)
        text = open(path, encoding="utf-8").read()

        # strip the leading h1 (chapter title lives in the payload title)
        text = re.sub(r"^# .+?\n", "", text, count=1)

        # README payload keeps its internal structure; chapter files are one
        # chapter each — title from the h1, body = everything below
        title = fallback_title

        html = md_to_html(text)
        chapters.append({
            "id": f"ch{len(chapters)+1:03d}",
            "title": title,
            "html": html,
        })
        print(f"  {fname}: {len(html)//1024}KB html")

    payload = {
        "slug": "llm-inference-handbook",
        "title": "LLM 推理手册",
        "author": "Modular · LLM Inference Handbook（中文整理版）",
        "chapters": chapters,
    }
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    os.makedirs(os.path.dirname(PAYLOAD_OUT), exist_ok=True)
    with open(PAYLOAD_OUT, "wb") as f:
        f.write(blob)
    print(f"payload: {len(blob)//1024}KB, {len(chapters)} chapters -> {PAYLOAD_OUT}")


if __name__ == "__main__":
    build()
