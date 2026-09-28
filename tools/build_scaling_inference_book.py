#!/usr/bin/env python3
"""Build the Scaling Book Part 7 (Transformer inference) payload from markdown.

Source: /Users/tim/my-sys/scaling-book/part7-inference.md — Chinese translation
of Google DeepMind "How To Scale Your Model" Part 7.

Pipeline: split by h2 into chapters (some h2 groups too large get an extra
split at a top-level h3) -> per-chunk markdown rendering with math/code
stash (same approach as tools/build_llm_inference_book.py) -> <details>
blocks rendered recursively (python-markdown leaves inner markdown raw)
-> image refs rewritten to site AVIF/animated-AVIF assets.

Output: assets/books/scaling-inference.bin (plain JSON payload, free book).
"""
import html as html_mod
import json
import os
import re

import markdown as md

SRC = "/Users/tim/my-sys/scaling-book/part7-inference.md"
SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_OUT = os.path.join(SITE_DIR, "assets", "books", "scaling-inference.bin")
IMG_PREFIX = "../../assets/images/books/scaling-inference"

TITLE = "Transformer 推理全解"
AUTHOR = "Google DeepMind · How To Scale Your Model（中文译本）"
BLURB = ("译自 DeepMind《How To Scale Your Model》Part 7：从 roofline 模型出发，"
         "推算 prefill/decode、KV 缓存、批处理、P-D 分离与多芯片并行的每一笔账。")

# Chapters: split h2 groups manually. The intro h2 (推理基础) and 附录 h2 are
# long, so their biggest h3 subsections become their own chapters.
SPLITS = [
    # (chapter title, start line marker (h2/h3 line prefix), end marker or None)
    ("Transformer 推理基础", "## Transformer 推理基础", "### 线性操作：瓶颈在哪？"),
    ("线性操作与注意力：瓶颈在哪", "### 线性操作：瓶颈在哪？", "### LLM 延迟与吞吐的理论估计"),
    ("延迟、吞吐与内存的理论估计", "### LLM 延迟与吞吐的理论估计", "### 为 LLaMA 2-13B 建模吞吐与延迟"),
    ("为 LLaMA 2-13B 建模吞吐与延迟", "### 为 LLaMA 2-13B 建模吞吐与延迟", "## 提升生成吞吐与延迟的若干技巧"),
    ("提升生成吞吐与延迟的若干技巧", "## 提升生成吞吐与延迟的若干技巧", "## 把推理分布到多块加速器上"),
    ("把推理分布到多块加速器上", "## 把推理分布到多块加速器上", "## 设计一个有效的推理引擎"),
    ("设计一个有效的推理引擎", "## 设计一个有效的推理引擎", "## 习题"),
    ("习题", "## 习题", "## 附录"),
    ("附录", "## 附录", None),
]


def md_to_html(text):
    """Markdown -> HTML with math/code protected from markdown rules."""
    # 0. stash image refs FIRST so alt-text $..$ never becomes math tokens
    #    (a math token expanded inside an alt attribute breaks the img tag)
    imgs = []

    def img_stash(m):
        imgs.append((m.group(1), m.group(2)))
        return f"@@IMG{len(imgs)-1}@@"

    text = re.sub(r"!\[([^\]]*)\]\((assets/[^)]+)\)", img_stash, text)

    fences = []

    def fence_repl(m):
        fences.append(m.group(2))
        return f"\n\n@@FENCE{len(fences)-1}@@\n\n"

    text = re.sub(r"```(\w*)\n(.*?)```", fence_repl, text, flags=re.S)

    codes = []

    def code_repl(m):
        codes.append(m.group(1))
        return f"@@CODE{len(codes)-1}@@"

    text = re.sub(r"`([^`\n]+)`", code_repl, text)

    maths = []

    def display_repl(m):
        maths.append(("display", m.group(1).strip()))
        return f"@@MATH{len(maths)-1}@@"

    text = re.sub(r"\$\$(.+?)\$\$", display_repl, text, flags=re.S)

    def inline_repl(m):
        maths.append(("inline", m.group(1)))
        return f"@@MATH{len(maths)-1}@@"

    text = re.sub(r"\$([^$\n]+?)\$", inline_repl, text)

    html = md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])

    for i, body in enumerate(fences):
        esc = html_mod.escape(body)
        html = html.replace(
            f"@@FENCE{i}@@",
            f'<pre class="fence"><code>{esc}</code></pre>')
    html = re.sub(r"<p>(<pre class=\"fence\">.*?</pre>)</p>", r"\1", html, flags=re.S)

    for i, body in enumerate(codes):
        html = html.replace(f"@@CODE{i}@@", f"<code>{html_mod.escape(body)}</code>")

    for i, (alt, fname) in enumerate(imgs):
        stem = os.path.splitext(os.path.basename(fname))[0]
        fig = (f'<figure><img src="{IMG_PREFIX}/{stem}.avif" '
               f'alt="{html_mod.escape(alt)}" loading="lazy">'
               f'<figcaption>{html_mod.escape(alt)}</figcaption></figure>')
        html = re.sub(r"<p>\s*@@IMG%d@@\s*</p>" % i, lambda m: fig, html)
        html = html.replace(f"@@IMG{i}@@", fig)

    for i, (kind, body) in enumerate(maths):
        if kind == "display":
            frag = f'<div class="math-display">$$&#10;{html_mod.escape(body)}&#10;$$</div>'
        else:
            frag = f'<span class="math-inline">${html_mod.escape(body)}$</span>'
        html = re.sub(r"<p>\s*@@MATH%d@@\s*</p>" % i, lambda m: frag, html)
        html = html.replace(f"@@MATH{i}@@", frag)

    html = html.replace("<table>", '<div class="table-wrap"><table>')
    html = html.replace("</table>", "</table></div>")

    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def render_details(body):
    """Replace <details> blocks with tokens; return (body, rendered_blocks).

    python-markdown leaves block-level HTML untouched, so inner markdown
    (lists, $math$, code spans) would stay raw. We render the inner
    content with md_to_html NOW and return the rendered blocks separately;
    build() splices them back AFTER the outer md_to_html pass — otherwise
    the outer pass would re-stash the fragments' $$..$$ and produce nested
    .math-display divs with double-escaped entities.
    """
    rendered = []
    parts = re.split(r"(<details>\n<summary>.*?</summary>\n.*?</details>)", body, flags=re.S)
    out = []
    for part in parts:
        if part.startswith("<details>"):
            m = re.match(
                r"<details>\n<summary>(.*?)</summary>\n(.*?)</details>",
                part, flags=re.S)
            inner_html = md_to_html(m.group(2))
            rendered.append(
                f'<details class="qa"><summary>{m.group(1)}</summary>'
                f'<div class="qa-body">{inner_html}</div></details>')
            out.append(f"\n\n@@DET{len(rendered)-1}@@\n\n")
        else:
            out.append(part)
    return "".join(out), rendered


def build():
    text = open(SRC, encoding="utf-8").read()
    lines = text.split("\n")

    # find line indexes of each split marker
    marks = []
    for title, start, end in SPLITS:
        s = next(i for i, l in enumerate(lines) if l.strip() == start)
        e = None
        if end:
            e = next(i for i, l in enumerate(lines) if l.strip() == end)
        marks.append((title, s, e))

    chapters = []
    for k, (title, s, e) in enumerate(marks):
        chunk = lines[s:e if e is not None else len(lines)]
        body = "\n".join(chunk)
        # drop the split's own heading lines (chapter title lives in payload)
        body = re.sub(r"^#{2,3} .+?\n", "", body, count=1)
        # strip the leading blockquote (translation credits shown in reader)
        if body.lstrip().startswith(">"):
            body = body.split("\n\n", 1)[1] if "\n\n" in body else ""

        body, details_html = render_details(body)
        html = md_to_html(body)
        for i, block in enumerate(details_html):
            html = re.sub(r"<p>\s*@@DET%d@@\s*</p>" % i, lambda m: block, html)
            html = html.replace(f"@@DET{i}@@", block)

        chapters.append({
            "id": f"ch{len(chapters)+1:03d}",
            "title": title,
            "html": html,
        })
        print(f"  ch{len(chapters)} {title}: {len(html)//1024}KB")

    payload = {
        "slug": "scaling-inference",
        "title": TITLE,
        "author": AUTHOR,
        "blurb": BLURB,
        "chapters": chapters,
    }
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with open(PAYLOAD_OUT, "wb") as f:
        f.write(blob)
    print(f"payload: {len(blob)//1024}KB, {len(chapters)} chapters -> {PAYLOAD_OUT}")


if __name__ == "__main__":
    build()
