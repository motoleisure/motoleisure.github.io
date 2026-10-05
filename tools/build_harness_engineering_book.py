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

# The book's concept formulas. output.md keeps readable pseudo-notation
# because the same file also feeds the standalone PDF/EPUB/DOCX builds —
# putting raw LaTeX there would leak \sim / \text{} into those formats. The web
# reader typesets these as real KaTeX instead.
#
# ``$$...$$`` on its own line -> display math; ``$...$`` inside a line -> inline.
MATH_SUBS = [
    # §1  model invocation
    ("y ~ p_theta(. | c)",
     "$$\ny \\sim p_\\theta(\\cdot \\mid c)\n$$"),
    # §1  agent system decomposition
    ("agent system ~= model + harness + environment",
     "$$\n\\text{agent system} \\approx \\text{model} + \\text{harness} "
     "+ \\text{environment}\n$$"),
    # §2  the four evolving objects (definition list -> inline math + gloss)
    ("- s_t = 第 t 步之前持久或工作状态",
     "- $s_t$ = 第 t 步之前持久或工作状态"),
    ("- c_t = G(s_t) = 为下一次模型调用选出的上下文",
     "- $c_t = G(s_t)$ = 为下一次模型调用选出的上下文"),
    ("- a_t = M(c_t) = 模型输出，其中可能包含一个行动请求",
     "- $a_t = M(c_t)$ = 模型输出，其中可能包含一个行动请求"),
    ("- o_t = E(a_t) = 行动执行时环境产生的观察结果",
     "- $o_t = E(a_t)$ = 行动执行时环境产生的观察结果"),
    # §2  state update rule
    ("s_(t+1) = U(s_t, a_t, o_t)",
     "$$\ns_{t+1} = U(s_t, a_t, o_t)\n$$"),
    # §7  tool cost decomposition
    ("C_tool = C_selection + C_observation",
     "$$\nC_{\\text{tool}} = C_{\\text{selection}} + C_{\\text{observation}}\n$$"),
    # §7  the two costs, spelled out in the following prose
    ("C_selection 是选出正确工具和参数的难度。C_observation 是返回结果所带来的上下文与推理负担。",
     "$C_{\\text{selection}}$ 是选出正确工具和参数的难度。"
     "$C_{\\text{observation}}$ 是返回结果所带来的上下文与推理负担。"),
    # §15  compaction is lossy
    ("设 H 为一段历史，C(H) 为压缩后的表示。一般而言：C(H) ≠ H",
     "设 H 为一段历史，C(H) 为压缩后的表示。一般而言：\n\n$$\nC(H) \\neq H\n$$"),
    # §22  observation provenance
    ("o_i = (content, source, trust, time, permissions)",
     "$$\no_i = (\\text{content}, \\text{source}, \\text{trust}, "
     "\\text{time}, \\text{permissions})\n$$"),
    # §23  completion vs termination
    ("task complete ≠ turn budget exhausted",
     "$$\n\\text{task complete} \\neq \\text{turn budget exhausted}\n$$"),
    # §24  budget vector
    ("B = (B_turns, B_tokens, B_time, B_cost, B_tools, B_concurrency) "
     "这个向量是我们的概念记号。",
     "$$\nB = (B_{\\text{turns}}, B_{\\text{tokens}}, B_{\\text{time}}, "
     "B_{\\text{cost}}, B_{\\text{tools}}, B_{\\text{concurrency}})\n$$\n\n"
     "这个向量是我们的概念记号。"),
    # §31  idempotency
    ("f(f(s)) = f(s)", "$$\nf(f(s)) = f(s)\n$$"),
    # §37  measured agent performance
    ("measured agent performance = F(model, harness, environment, task, grader) "
     "这不是一个统计模型，只是一个关于依赖关系的提醒。改变执行框架可以在不改变模型权重的情况下改变结果。改变环境也能如此。",
     "$$\n\\text{measured agent performance} = F(\\text{model}, "
     "\\text{harness}, \\text{environment}, \\text{task}, \\text{grader})\n$$\n\n"
     "这不是一个统计模型，只是一个关于依赖关系的提醒。改变执行框架可以在不改变模型权重的情况下改变结果。改变环境也能如此。"),
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


def apply_math(text):
    """Turn the book's concept formulas into KaTeX source.

    output.md keeps readable pseudo-notation (it also feeds the PDF/EPUB
    builds), so the LaTeX lives here rather than in the translation.
    """
    for old, new in MATH_SUBS:
        if old not in text:
            raise SystemExit(f"math rule target not found: {old[:48]!r}")
        text = text.replace(old, new)
    return text


def md_to_html(text):
    """Markdown -> HTML with math/code/diagram protected from markdown rules.

    Math is stashed *before* markdown runs: python-markdown would otherwise
    read the underscores in ``$s_t$`` / ``$C_selection$`` as emphasis and split
    the formula across list/paragraph rules."""
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

    # display math, then inline (order matters: $$..$$ must not be eaten by $..$)
    maths = []

    def display_repl(m):
        maths.append(("display", m.group(1).strip()))
        return f"@@MATH{len(maths) - 1}@@"

    text = re.sub(r"\$\$(.+?)\$\$", display_repl, text, flags=re.S)

    def inline_repl(m):
        maths.append(("inline", m.group(1)))
        return f"@@MATH{len(maths) - 1}@@"

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

    for i, body in enumerate(diagrams):
        block = ('<pre><code class="language-text">'
                 + html_mod.escape(body) + "</code></pre>")
        html = html.replace(f"<p>@@DIAGRAM{i}@@</p>", block)
        html = html.replace(f"@@DIAGRAM{i}@@", block)

    # restore math: display -> centred div, inline -> span, KaTeX-ready
    for i, (kind, body) in enumerate(maths):
        if kind == "display":
            frag = f'<div class="math-display">$$&#10;{html_mod.escape(body)}&#10;$$</div>'
        else:
            frag = f'<span class="math-inline">${html_mod.escape(body)}$</span>'
        html = re.sub(r"<p>\s*@@MATH%d@@\s*</p>" % i, lambda m: frag, html)
        html = html.replace(f"@@MATH{i}@@", frag)

    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def build():
    text = open(SRC, encoding="utf-8").read()
    # payload carries the book title; drop the leading `# ` heading
    text = re.sub(r"^# .+?\n", "", text, count=1)
    # concept formulas -> KaTeX source (fails loudly if a target moved)
    text = apply_math(text)

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
          "| diagrams:", sum(c["html"].count('<pre><code class="language-text">') for c in chapters),
          "| math:", sum(c["html"].count('<div class="math-display">') for c in chapters),
          "display +", sum(c["html"].count('<span class="math-inline">') for c in chapters), "inline")
    leftovers = re.findall(r"\{\.[^}]*\}|\{target=[^}]*\}|@@[A-Z]+\d+@@",
                           "".join(c["html"] for c in chapters))
    print("unresolved tokens:", len(leftovers), leftovers[:5])


if __name__ == "__main__":
    build()
