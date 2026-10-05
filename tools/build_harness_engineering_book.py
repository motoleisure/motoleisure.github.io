#!/usr/bin/env python3
"""Build the Harness Engineering payload from the translated markdown.

Source: /Users/tim/my-sys/Understanding_Harness_Engineering_temp/output.md —
Chinese translation of the 48-page technical handbook "Understanding Harness
Engineering" (@techNmak), produced by the translate-book pipeline (13 chunks,
glossary-consistent terms, section headings restored from the PDF's wrapped
long titles).

The book has no LaTeX (only inline pseudo-notation such as
`y ~ p_theta(. | c)` and `C(H) != H`, which stay as plain text) and no real
figures — the original's diagram boxes survive as standalone `[label]` lines.
Runs of those lines are regrouped into `<pre>` diagram blocks so the reader
keeps the book's box-and-arrow layouts instead of a stack of one-line
paragraphs.

Chapters: the 43 numbered sections are grouped into 10 reader chapters along
the book's own running-head part boundaries.

Output: assets/books/harness-engineering.bin (plain JSON payload, free book).
"""
import html as html_mod
import json
import os
import re

import markdown as md

SRC = "/Users/tim/my-sys/Understanding_Harness_Engineering_temp/output.md"
SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_OUT = os.path.join(SITE_DIR, "assets", "books", "harness-engineering.bin")

SLUG = "harness-engineering"
TITLE = "理解智能体执行框架工程"
AUTHOR = "@techNmak · Understanding AI 系列（中文译本）"
BLURB = ("一次模型调用为什么还不是智能体？智能体执行框架到底控制了什么？"
         "从智能体循环、工具接口、上下文与沙箱，到验证、恢复、预算与评估——"
         "一本讲透模型外围那套控制机制的简明技术手册。")

# (chapter title, first `## ` heading of the chapter, next chapter's heading or None)
SPLITS = [
    ("导言：从模型调用到执行框架",   "## 1 一次模型调用并不等于一个智能体",   "## 4 模型、执行框架、会话、工具与沙箱"),
    ("模型、会话、工具与沙箱",       "## 4 模型、执行框架、会话、工具与沙箱", "## 7 工具是模型输入的一部分"),
    ("工具设计：接口、数量与结果",   "## 7 工具是模型输入的一部分",           "## 11 MCP 是互操作层，而不是完整的智能体循环"),
    ("MCP、上下文与渐进披露",        "## 11 MCP 是互操作层，而不是完整的智能体循环", "## 14 持久历史与活动上下文是不同的状态面"),
    ("状态面、压缩与执行环境",       "## 14 持久历史与活动上下文是不同的状态面", "## 19 沙箱是隔离边界，而不是编排器"),
    ("沙箱、审批与遏制隔离",         "## 19 沙箱是隔离边界，而不是编排器",   "## 23 停止条件是执行框架的一部分"),
    ("停止条件、预算与验证",         "## 23 停止条件是执行框架的一部分",     "## 28 反馈循环给智能体外部证据"),
    ("反馈、持久性与幂等",           "## 28 反馈循环给智能体外部证据",       "## 35 机制比文字更强，适用于可强制的规则"),
    ("可强制执行性、可观测性与评估", "## 35 机制比文字更强，适用于可强制的规则", "## 41 常见误解"),
    ("误解、生产心智模型与参考文献", "## 41 常见误解",                       None),
]

# A standalone `[label]` line — a diagram box from the source PDF.
BOX_RE = re.compile(r"^\[[^\[\]]+\]$")


def stash_diagrams(text):
    """Group runs of consecutive `[label]` box lines into one placeholder.

    Blank lines inside a run are tolerated so a broken-up diagram still merges.
    The original's flow diagrams (Task -> Assemble context -> Model -> ...)
    survive as a single block instead of N one-line paragraphs.
    """
    diagrams = []
    lines = text.split("\n")
    out, run, i = [], [], 0

    def flush():
        if not run:
            return
        diagrams.append("\n".join(run))
        out.append(f"\n\n@@DIAGRAM{len(diagrams) - 1}@@\n\n")
        run.clear()

    while i < len(lines):
        ln = lines[i]
        if BOX_RE.match(ln.strip()):
            run.append(ln.strip()[1:-1])
        elif not ln.strip() and run:
            # peek: keep consuming only if the next non-blank line is a box
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and BOX_RE.match(lines[j].strip()):
                i = j
                continue
            flush()
        else:
            flush()
            out.append(ln)
        i += 1
    flush()
    return "\n".join(out), diagrams


def md_to_html(text):
    """Markdown -> HTML with code/diagram protected from markdown rules."""
    text, diagrams = stash_diagrams(text)

    fences = []

    def fence_repl(m):
        fences.append(m.group(2))
        return f"\n\n@@FENCE{len(fences) - 1}@@\n\n"

    text = re.sub(r"``` ?(\w*)\n(.*?)```", fence_repl, text, flags=re.S)

    codes = []

    def code_repl(m):
        codes.append(m.group(1))
        return f"@@CODE{len(codes) - 1}@@"

    text = re.sub(r"`([^`\n]+)`", code_repl, text)

    html = md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])

    for i, body in enumerate(fences):
        esc = html_mod.escape(body)
        html = html.replace(
            f"@@FENCE{i}@@",
            f'<pre class="fence"><code>{esc}</code></pre>')
    html = re.sub(r"<p>(<pre class=\"fence\">.*?</pre>)</p>", r"\1", html, flags=re.S)

    for i, body in enumerate(codes):
        html = html.replace(f"@@CODE{i}@@", f"<code>{html_mod.escape(body)}</code>")

    # diagram blocks -> dark code cards (same treatment the MoE reader uses for
    # its ASCII diagrams)
    for i, body in enumerate(diagrams):
        block = ('<pre><code class="language-text">'
                 + html_mod.escape(body) + "</code></pre>")
        html = html.replace(f"<p>@@DIAGRAM{i}@@</p>", block)
        html = html.replace(f"@@DIAGRAM{i}@@", block)

    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def build():
    text = open(SRC, encoding="utf-8").read()
    # payload carries the book title; drop the leading `# ` heading
    text = re.sub(r"^# .+?\n", "", text, count=1)

    # front matter: book title plate + "本手册要阐明什么", up to section 1
    marks = []
    for title, start, end in SPLITS:
        s = text.find("\n" + start + "\n")
        if s < 0:
            raise SystemExit(f"split start not found: {start!r}")
        s += 1
        e = text.find("\n" + end + "\n", s) if end else len(text)
        if end and e < 0:
            raise SystemExit(f"split end not found: {end!r}")
        marks.append((title, s, e if e < 0 else e + 1))

    front = text[: marks[0][1]]

    chapters = [{
        "id": "ch000",
        "title": TITLE,
        "html": md_to_html(front),
    }]

    for k, (title, s, e) in enumerate(marks):
        body = text[s:e]
        # the split's own heading lines are demoted to h3 inside the chapter
        # (chapter title lives in the TOC), but keep the numbered section
        # structure visible for the reader.
        html = md_to_html(body)
        html = re.sub(r"<h2>(.*?)</h2>", r"<h3>\1</h3>", html)
        chapters.append({"id": f"ch{k + 1:03d}", "title": title, "html": html})

    payload = {
        "slug": SLUG,
        "title": TITLE,
        "author": AUTHOR,
        "blurb": BLURB,
        "chapters": chapters,
    }
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with open(PAYLOAD_OUT, "wb") as f:
        f.write(blob)

    print(f"payload: {len(blob) // 1024}KB -> {PAYLOAD_OUT}")
    for ch in chapters:
        h = ch["html"]
        print(f"  {ch['id']} {ch['title']}: {len(h) // 1024}KB "
              f"| h3={h.count('<h3>')} pre={h.count('<pre')} "
              f"table={h.count('<table')} p={h.count('<p>')}")
    print("figures:", sum(c["html"].count("<figure") for c in chapters),
          "| fences:", sum(c["html"].count('<pre class="fence">') for c in chapters),
          "| diagrams:", sum(c["html"].count('<pre><code class="language-text">') for c in chapters))
    leftovers = re.findall(r"\{\.[^}]*\}|\{target=[^}]*\}|@@[A-Z]+\d+@@",
                           "".join(c["html"] for c in chapters))
    print("unresolved tokens:", len(leftovers), leftovers[:5])


if __name__ == "__main__":
    build()
