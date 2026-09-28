#!/usr/bin/env python3
"""Build the KV Cache article payload from the translated markdown.

Source: /Users/tim/my-sys/kv-cache-article-temp/output.md — Chinese translation
of Outcome School blog "KV Cache in LLMs" (Amit Shekhar), produced by the
translate-book pipeline.

The article is short (18KB) with no real images (only 1x1 tracking GIF and
blank calibre SVGs) — payload is a single chapter, images dropped, junk
author-header markup stripped.

Output: assets/books/kv-cache-in-llms.bin (plain JSON payload, free book).
"""
import html as html_mod
import json
import os
import re

import markdown as md

SRC = "/Users/tim/my-sys/kv-cache-article-temp/output.md"
SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_OUT = os.path.join(SITE_DIR, "assets", "books", "kv-cache-in-llms.bin")

TITLE = "KV Cache：LLM 里的键值缓存"
AUTHOR = "Amit Shekhar · Outcome School（中文译本）"
BLURB = ("KV 缓存是什么、为什么只缓存键和值、能快多少、内存代价怎么权衡，"
         "以及提示词缓存、attention sink 与 PagedAttention 的来龙去脉——一篇讲透的入门文章。")


def md_to_html(text):
    """Markdown -> HTML with math/code protected (no math here, but keep
    the fence/code-span stash so example strings survive markdown rules)."""
    fences = []

    def fence_repl(m):
        fences.append(m.group(2))
        return f"\n\n@@FENCE{len(fences)-1}@@\n\n"

    text = re.sub(r"``` ?(\w*)\n(.*?)```", fence_repl, text, flags=re.S)

    codes = []

    def code_repl(m):
        codes.append(m.group(1))
        return f"@@CODE{len(codes)-1}@@"

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

    # the calibre link-attribute syntax {target="_blank" rel="..."} leaks as
    # literal text; strip it (urls already kept in the href part). After
    # markdown conversion the quotes may appear as &quot; entities.
    html = re.sub(r"\{[^}]*target=&?q?u?o?t?;?_blank&q?u?o?t?;?[^}]*\}", "", html)
    html = re.sub(r"\{target=[^}]*\}", "", html)
    html = re.sub(r"\{\.h[^}]*\}", "", html)

    html = re.sub(r"<p>\s*</p>", "", html)
    # drop a leading 作者-only paragraph (author header leftover)
    html = re.sub(r"^<p>作者</p>\s*", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


def drop_pipeline_fences(text):
    """The author header (姓名/发布于 definition list) was exported by calibre
    as a definition-list encoded inside a code fence — raw pipeline markup,
    not content. Drop such fences before markdown conversion."""
    def fence_repl(m):
        lang, body = m.group(1), m.group(2)
        if "姓名" in body or "发布于" in body:
            return ""
        return m.group(0)
    return re.sub(r"``` ?(\w*)\n(.*?)```", fence_repl, text, flags=re.S)


def clean(text):
    """Strip translation-pipeline junk: author avatar header, hero image,
    broken image refs, tags footer."""
    text = drop_pipeline_fences(text)
    # drop the entire author header: from the "作者" line until (and including)
    # the hero-image line — calibre definition-list markup, junk for the payload
    lines = text.split("\n")
    out_hdr = []
    skipping = False
    for ln in lines:
        if ln.strip() == "作者":
            skipping = True
            continue
        if skipping:
            # stop skipping at the first real prose line after the hero image
            if ln.strip().startswith("KV 缓存是") or (ln.strip() and not ln.startswith((":", " ", "![", "[!", "[["))):
                skipping = False
            else:
                continue
        out_hdr.append(ln)
    lines = out_hdr
    out = []
    for ln in lines:
        # author-header block: definition-list avatar markup lines
        if re.search(r'!\[[^\]]*\]\((images/|/_next/image)', ln):
            continue
        # broken promo link the export flattened: **text**(url){attrs}
        ln = re.sub(r"\*\*([^*]+)\*\*\((https?://[^)]+)\)\{[^}]*\}",
                    r'[\1](\2)', ln)
        out.append(ln)
    return "\n".join(out)


def build():
    text = open(SRC, encoding="utf-8").read()
    # drop the h1 (payload title carries it)
    text = re.sub(r"^# .+?\n", "", text, count=1)
    text = clean(text)
    html = md_to_html(text)

    payload = {
        "slug": "kv-cache-in-llms",
        "title": TITLE,
        "author": AUTHOR,
        "blurb": BLURB,
        "chapters": [
            {"id": "ch001", "title": TITLE, "html": html},
        ],
    }
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with open(PAYLOAD_OUT, "wb") as f:
        f.write(blob)
    print(f"payload: {len(blob)//1024}KB -> {PAYLOAD_OUT}")
    print("figures:", html.count("<figure"), "| fences:", html.count('<pre class="fence">'),
          "| headings:", html.count("<h2>"), "+", html.count("<h3>"))
    leftover = re.findall(r'\{\.h[^}]*\}|\{target="[^}]*"[^}]*\}', html)
    print("attribute leftovers:", len(leftover))
    imgs = re.findall(r'<img', html)
    print("img tags:", len(imgs))


if __name__ == "__main__":
    build()
