#!/usr/bin/env python3
"""Build the encrypted book module from EPUB sources.

Pipeline per book:
  EPUB -> extract chapters (spine order) -> clean/inline-rewrite HTML
       -> images converted to AVIF -> one JSON payload -> AES-GCM encrypt

The payload JSON: {book meta, chapters: [{id, title, html}], images inlined
as base64 data URIs. Encrypted with PBKDF2-SHA256 (150k iters) + AES-GCM.
Output: assets/books/<slug>.bin  (salt[16] | iv[12] | ciphertext)

Decryption happens client-side (books/*/index.html) via WebCrypto; the
password never ships with the repo.
"""

import base64
import hashlib
import html as html_mod
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(SITE_DIR, "assets", "books")
IMG_DIR = os.path.join(SITE_DIR, "assets", "images", "books")

PASSWORD = "789wadu123"
PBKDF2_ITERS = 150_000

BOOKS = [
    {
        "slug": "designing-ai-systems",
        "title": "设计 AI 系统",
        "title_en": "Designing AI Systems",
        "author": "Suhas Suresha",
        "blurb": "从平台、SDK、模型服务到记忆与上下文管理，一本面向工程师的 AI 系统设计实战指南。",
        "epub": "/Users/tim/my-sys/Designing-AI-Systems_temp/book.epub",
        "cover": "assets/images/books/cover-designing-ai-systems.svg",
        "max_img_w": 900,
        "strategy": "dais-map",  # scrambled MEAP export; explicit file map below
    },
    {
        "slug": "illustrated-ai-agents",
        "title": "AI 智能体图解",
        "title_en": "An Illustrated Guide to AI Agents",
        "author": "Maarten Grootendorst",
        "blurb": "图解 AI 智能体的内部构造：大语言模型、记忆、工具、规划与多智能体协作。",
        "epub": "/Users/tim/my-sys/An-Illustrated-Guide-to-AI-Agents_temp/book.epub",
        "cover": "assets/images/books/cover-illustrated-ai-agents.svg",
        "max_img_w": 900,
        "strategy": "chapters",  # nav is corrupt; split files in spine order,
        # chapter boundaries = <h2><strong>第N章 …</strong></h2> (第四章 variant too)
    },
]


# ---------------------------------------------------------------- EPUB parse

def parse_epub(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    opf_path = next(n for n in names if n.endswith(".opf"))
    root = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
    opf = z.read(opf_path).decode("utf-8")

    manifest = {}
    for m in re.finditer(r'<item\s+([^>]*?)/?>', opf):
        attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1)))
        if "id" in attrs and "href" in attrs:
            manifest[attrs["id"]] = attrs

    spine_ids = re.findall(r'idref="([^"]+)"', re.search(
        r"<spine[^>]*>(.*?)</spine>", opf, re.S).group(1))

    def full(href):
        return f"{root}/{href}" if root else href

    meta_title = re.search(r"<dc:title[^>]*>([^<]+)</dc:title>", opf)

    chapters = []
    for sid in spine_ids:
        item = manifest.get(sid)
        if not item or item.get("media-type") != "application/xhtml+xml":
            continue
        if "nav" in item["href"] or "title" in item["id"].lower():
            continue
        html = z.read(full(item["href"])).decode("utf-8")
        chapters.append({"href": item["href"], "html": html})
    return z, root, chapters, (meta_title.group(1) if meta_title else None)


def extract_title(html):
    m = (re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
         or re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
         or re.search(r"<title>([^<]+)</title>", html, re.S))
    t = re.sub(r"<[^>]+>", "", m.group(1)) if m else ""
    t = re.sub(r"\{#[^}]*\}", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_body(html):
    """Return inner content of <body>, dropping scripts/styles."""
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<link[^>]*>", "", body)
    return body


# ------------------------------------------------------------- image convert

_img_counter = [0]


def convert_image(src_bytes, ext, book_slug, max_w):
    """Convert image bytes to AVIF, return (site-relative path, b64 of file)."""
    _img_counter[0] += 1
    name = f"{book_slug}-{_img_counter[0]:04d}.avif"
    dst = os.path.join(IMG_DIR, name)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
        tf.write(src_bytes)
        tmp_in = tf.name
    try:
        if ext in (".svg",):
            # keep vector art as-is (no scaling win), store raw
            with open(dst.replace(".avif", ".svg"), "wb") as f:
                f.write(src_bytes)
            site_rel = f"assets/images/books/{os.path.basename(dst).replace('.avif', '.svg')}"
            return site_rel
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in, "-vf", f"scale='min({max_w},iw)':-2",
             "/tmp/_bk.png"], check=True, capture_output=True)
        subprocess.run(
            ["avifenc", "--min", "30", "--max", "63", "-j", "4",
             "/tmp/_bk.png", dst], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # fallback: keep original bytes as png
        shutil.copyfile(tmp_in, dst.replace(".avif", ext))
        site_rel = f"assets/images/books/{os.path.basename(dst).replace('.avif', ext)}"
        os.path.exists(dst) and os.remove(dst)
        return site_rel
    finally:
        os.unlink(tmp_in)
    return f"assets/images/books/{name}"


def inline_images(body, z, root, book_slug, max_w, img_map):
    """Rewrite <img src> to site AVIF paths, then inline them as data URIs
    (payload is self-contained; reader injects into sandboxed DOM)."""
    def repl(m):
        attrs, src = m.group(1), m.group(2)
        if src.startswith(("http", "data:")):
            return m.group(0)
        path = f"{root}/{src}" if root else src
        path = os.path.normpath(path).replace("\\", "/")
        try:
            raw = z.read(path)
        except KeyError:
            return m.group(0)
        ext = os.path.splitext(src)[1].lower()
        site_rel = img_map.get(path)
        if not site_rel:
            site_rel = convert_image(raw, ext, book_slug, max_w)
            img_map[path] = site_rel
        with open(os.path.join(SITE_DIR, site_rel), "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        mime = "image/svg+xml" if site_rel.endswith(".svg") else "image/avif"
        return f'<img {attrs}src="data:{mime};base64,{b64}">'
    return re.sub(r'<img([^>]*?)src="([^"]+)"([^>]*)>', repl, body)


# ------------------------------------------------------------------ ordering
# 两本 MEAP 导出的 EPUB 各有不同的结构缺陷，分别用显式策略重建阅读序：
#
# Designing AI Systems：物理文件顺序彻底乱（ch003 是第5章、ch008 是第1章…），
# 且混杂 2KB 的目录概要文件；正文还跨文件延续（第5章 = ch012 尾 + ch013-015）。
# 真实结构已人工核对，用显式映射（含 ch008/ch012/ch016 文件内切割点）最可靠。
#
# An Illustrated Guide to AI Agents：nav 损坏，但 spine 顺序的 split 文件是
# 正序；章边界 = <h2><strong>第N章 …</strong></h2>（兼容"第四章"），其余
# 文件并入当前章，开头无章标的归前言。

DAIS_PREFIX = "EPUB/text/"


def _h2_pos(html, pat):
    m = re.search(pat, html)
    return m.start() if m else None


def chapters_dais(z):
    """Explicit file->chapter mapping for the scrambled MEAP export."""
    def rd(name):
        return z.read(DAIS_PREFIX + name).decode("utf-8")

    ch001 = rd("ch001.xhtml")
    ch002 = rd("ch002.xhtml")
    ch006 = rd("ch006.xhtml")
    ch008 = rd("ch008.xhtml")
    ch010 = rd("ch010.xhtml")
    ch011 = rd("ch011.xhtml")
    ch012 = rd("ch012.xhtml")
    ch013 = rd("ch013.xhtml")
    ch014 = rd("ch014.xhtml")
    ch015 = rd("ch015.xhtml")
    ch016 = rd("ch016.xhtml")

    b = lambda body: extract_body(body)

    # ch002: keep only 欢迎 + 本书内容 (stop before chapter-1 outline)
    m = re.search(r'<h2[^>]*>\s*1 为什么你的', ch002)
    front2 = ch002[:m.start()] if m else ch002

    # ch008 internal split
    p1 = _h2_pos(ch008, r"<h2[^>]*>\s*本章内容")
    p2 = _h2_pos(ch008, r"<h2[^>]*>\s*2 基于平台构建")

    # ch012 internal split
    p5 = _h2_pos(ch012, r"<h2[^>]*>\s*第5章 数据服务")

    # ch016 internal split
    q6 = _h2_pos(ch016, r"<h2[^>]*>\s*6\.1\s")
    q7 = _h2_pos(ch016, r"<h2[^>]*>\s*7\.1\s")
    q9 = _h2_pos(ch016, r"<h2[^>]*>\s*9 构建 AI 助手")

    return [
        {"title": "前言",
         "body": re.sub(r"ch\d+\.xhtml", "", b(ch001) + b(front2))},
        {"title": "第1章 为什么你的 AI 项目需要一个平台",
         "body": b(ch008[p1:p2])},
        {"title": "第2章 基于平台构建：SDK 与 API 设计",
         "body": b(ch008[p2:])},
        {"title": "第3章 模型服务：你平台通向 AI 模型的网关",
         "body": b(ch010)},
        {"title": "第4章 会话服务：教会你的 AI 记住对话",
         "body": b(ch011) + b(ch012[:p5])},
        {"title": "第5章 数据服务：教会 AI 你的组织知道什么",
         "body": b(ch012[p5:]) + b(ch013) + b(ch014) + b(ch015)},
        {"title": "第6章 工具与护栏：让 AI 行为安全且受控",
         "body": b(ch016[q6:q7])},
        {"title": "第7章 可观测性与实验：看见并改进 AI 的所作所为",
         "body": b(ch016[q7:q9])},
        {"title": "第8章 工作流服务：编排与部署 AI 应用（MEAP 撰写中，暂为概要）",
         "body": b(ch006)},
        {"title": "第9章 构建 AI 助手：让平台发挥作用",
         "body": b(ch016[q9:])},
    ]


CH_RE = re.compile(
    r"<h2[^>]*>\s*<strong[^>]*>\s*(第\s*[一二三四五六七八九十\d]+\s*章[^<]*)</strong\s*>",
    re.I,
)
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10}


def chapters_by_heading(spine_chapters):
    """Split spine-ordered files at <h2><strong>第N章…</strong></h2> marks.
    Files without a chapter mark append to the previous chapter; leading
    files go to 前言."""
    out = []
    pending_front = []
    for ch in spine_chapters:
        html = extract_body(ch["html"])
        marks = [(m.start(), re.sub(r"\s+", " ", m.group(1)).strip())
                 for m in CH_RE.finditer(html)]
        if not marks:
            if out:
                out[-1]["body"] += html
            else:
                pending_front.append(html)
            continue
        for idx, (pos, t) in enumerate(marks):
            end = marks[idx + 1][0] if idx + 1 < len(marks) else len(html)
            out.append({"title": t, "body": html[pos:end]})
    if pending_front:
        out.insert(0, {"title": "前言", "body": "".join(pending_front)})
    return out


# --------------------------------------------------------- content polishing

def polish(body):
    """Clean up MEAP/pandoc artifacts and upgrade presentation structures.

    - strip pandoc line-number anchors (<a href="#cbN-M">) inside code
    - wrap <pre> blocks in <figure class="code-listing"> and pull the
      preceding "代码清单 N.N ..." / "Listing N.N ..." paragraph in as
      <figcaption>
    - mark figure-ish paragraphs that follow an image as <p class="img-caption">
    - drop page-separator divs (print-edition page break markers)
    - neutralise internal #cb anchors in links
    """
    # pandoc line anchors: <a href="#cb1-1" aria-hidden="true" ...></a>
    body = re.sub(r'<a href="#cb[^"]*"[^>]*>\s*</a>', "", body)

    # page separators (print page breaks)
    body = re.sub(r'<div class="page-separator[^"]*">.*?</div>', "", body, flags=re.S)

    # internal dead anchors -> plain spans (keep text)
    body = re.sub(r'<a href="#([^"]*)">(.*?)</a>',
                  lambda m: m.group(2) if m.group(1).startswith("cb") else m.group(0),
                  body)

    # flatten bracket-wrapped code lines inside <pre> blocks
    body = decode_pre_lines(body)

    # re-attach table rows the export dumped as a pipe-text line-block
    body = repair_split_table(body)

    # code listing captions: a paragraph immediately before <pre> that starts
    # with 代码清单/Listing/清单 + number becomes the listing's figcaption
    cap_re = re.compile(
        r'<p>([^<]*(?:代码清单|Listing|清单)\s*[\d.]+[^<]*)</p>\s*(<pre[^>]*>)',
        re.S)

    def cap_repl(m):
        cap = m.group(1).strip()
        return (f'<div class="listing-cap">{cap}</div>{m.group(2)}')

    body = cap_re.sub(cap_repl, body)

    # wrap pre + optional caption in a figure card
    body = re.sub(
        r'(<div class="listing-cap">.*?</div>)?(<pre[^>]*>.*?</pre>)',
        lambda m: f'<figure class="code-listing">{m.group(1) or ""}{m.group(2)}</figure>',
        body, flags=re.S)

    # image captions: paragraph right after <img ...> that starts with
    # 图 N.N / Figure N.N becomes a caption paragraph
    cap_txt = re.compile(r"^[\[\s]*(?:<[^>]+>)*\s*(图|Figure)\s*\d")

    def _with_caption_class(ptag):
        """Insert img-caption class, merging with any existing class attr."""
        m = re.match(r'<p([^>]*)class="([^"]*)"([^>]*)>', ptag)
        if m:
            return f'<p{m.group(1)}class="img-caption {m.group(2)}"{m.group(3)}>'
        return ptag.replace("<p", '<p class="img-caption"', 1)

    def _caption_text(inner):
        """Caption inner HTML with the print-artifact [ ] brackets removed."""
        inner = re.sub(r"^\s*\[", "", inner)
        inner = re.sub(r"\]\s*$", "", inner)
        return inner

    def img_repl(m):
        img, ptag, inner = m.group(1), m.group(2), m.group(3)
        txt = re.sub(r"<[^>]+>", "", inner).strip()
        if cap_txt.match(txt):
            cap_tag = _with_caption_class(ptag)
            return f"{img}{cap_tag}{inner}</p>"
        return m.group(0)
    def img_repl2(m):
        pre_close, attrs, post_open, ptag, inner = (
            m.group(1) or "", m.group(2), m.group(3) or "",
            m.group(4), m.group(5))
        txt = re.sub(r"<[^>]+>", "", inner).strip()
        img = f"<img{attrs}>"
        if cap_txt.match(txt):
            cap_tag = _with_caption_class(ptag)
            return (f'<figure class="book-figure">{img}</figure>'
                    f'{cap_tag}{_caption_text(inner)}</p>')
        return f"{pre_close}{img}{post_open}{ptag}{inner}</p>"

    body = re.sub(
        r'(</p>\s*)?<img([^>]*)>(\s*</p>)?\s*(<p[^>]*>)(.*?)(</p>)',
        img_repl2, body, flags=re.S)

    # Some MEAP exports have listings flattened into "[line]" paragraphs
    # (no <pre>/<code> at all). Rebuild them: a run of consecutive paragraphs
    # whose content is bracketed code segments becomes one code block.
    # Pre/figure regions are exempt — their bracket lines were already
    # decoded in place by decode_pre_lines().
    parts = re.split(
        r'(<figure class="code-listing">.*?</figure>|<pre[^>]*>.*?</pre>)',
        body, flags=re.S)
    for _i in range(0, len(parts), 2):
        parts[_i] = rebuild_flat_listings(parts[_i])
    body = "".join(parts)

    body = typography_pass(body)

    # flattened listings may keep their caption as a bold paragraph right
    # above the rebuilt figure — fold it in as the listing caption
    body = re.sub(
        r'<p><strong>((?:代码)?清单\s*[\d.]+[^<]*)</strong></p>\s*'
        r'<figure class="code-listing">',
        lambda m: f'<figure class="code-listing"><div class="listing-cap">{m.group(1).strip()}</div>',
        body)

    # drop empty paragraphs left behind
    body = re.sub(r"<p>\s*</p>", "", body)
    return body


# bracketed inline-code segment used by flattened listings, e.g.
# "[platform.models.chat( #B]" — also allows one level of nested
# brackets ([policies=["a", "b"]]) and inline markup like <em>…</em>
FLAT_SEG = r"\[(?:[^\[\]<>]|<[^>]+>|\[(?:[^\[\]<>]|<[^>]+>)*\])*\]"

STRONG_CODE = re.compile(r'<strong class="calibre3">([^<]*)</strong>')
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ANN_END = re.compile(r"#[A-Z]\s*$")
BLOCK_RE = re.compile(
    r"<p[^>]*>.*?</p>"
    r'|(?:<strong class="calibre3">[^<]*</strong>\s*)+'
    r"|" + FLAT_SEG, re.S)


def _entity(text):
    return (text.replace("&amp;", "&").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))


def _decode_flat(inner):
    """Decode one [..] segment: drop print wrap marker ➥, then decode
    nested bracket tokens recursively (the export wraps every code token
    in its own [...] pair), resolve backslash escapes, strip styling."""
    inner = inner.replace("➥", "").strip()
    return _decode_inner(inner).lstrip()


def _plain(text):
    """Plain-text decode of non-token fragment: \<em>X</em> is an
    underscore the export wrapped with its tail text; \\X escapes keep
    the punctuation (real code brackets), any other backslash marks an
    underscore the export destroyed (__init__ -> \_\_init\_\_)."""
    text = re.sub(r"\\<em[^>]*>(.*?)</em>", lambda m: "_" + m.group(1), text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\\([#{}\[\]|>&])", r"\1", text)
    text = text.replace("\\", "_")
    return _entity(text)


def _decode_inner(inner):
    out = []
    pos = 0
    trailing = ""
    if inner.endswith("\\"):
        # the escaped real ] sits under this token's closing marker
        inner = inner[:-1]
        trailing = "]"
    for m in re.finditer(FLAT_SEG, inner):
        gap = inner[pos:m.start()]
        prepend = ""
        if gap.endswith("\\"):
            # the escaped real [ sits under this token's opening marker
            gap = gap[:-1]
            prepend = "["
        out.append(_plain(gap))
        out.append(prepend + _decode_inner(m.group(0)[1:-1]))
        pos = m.end()
    out.append(_plain(inner[pos:]))
    return "".join(out) + trailing


def decode_pre_lines(body):
    """Inside <pre> blocks, MEAP exports wrap flattened lines as
    '<span id="cbN">[code]</span>'. Decode them in place (keeping the
    surrounding pre intact) so rebuild_flat_listings never sees them."""
    def pre_repl(m):
        inner = m.group(2)

        def span_repl(s):
            decoded = _decode_flat(s.group(1))
            if not decoded.strip():
                return ""
            return (decoded.replace("&", "&amp;")
                    .replace("<", "&lt;").replace(">", "&gt;"))

        inner = re.sub(r'<span id="cb[^"]*">\s*\[(.*)\]\s*</span>',
                       span_repl, inner)
        return m.group(1) + inner + m.group(3)

    return re.sub(r"(<pre[^>]*>)(.*?)(</pre>)", pre_repl, body, flags=re.S)


def repair_split_table(body):
    """MEAP export truncated one table (dais 表 1.1): rows after the first
    few were dumped as a <div class="line-block"> of pipe-separated text
    right after </table>. Parse the rows back and append them to the
    preceding table's tbody."""
    def repl(m):
        table, block = m.group(1), m.group(2)
        ncols = table.count("<th>") or 3
        rows = []
        for line in re.split(r"<br\s*/?>|\n", block):
            line = re.sub(r"<[^>]+>", "", line).strip()
            if not line or "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            while cells and not cells[-1]:
                cells.pop()
            if cells:
                rows.append(cells)
        if not rows:
            return m.group(0)
        trs = "".join(
            "<tr>" + "".join(
                f"<td>{_entity(c)}</td>" for c in (r + [""] * (ncols - len(r)))[:ncols]
            ) + "</tr>" for r in rows)
        return table.replace("</tbody>", trs + "</tbody>")

    return re.sub(
        r'(<table.*?</table>)\s*<div class="line-block">(.*?)</div>',
        repl, body, flags=re.S)


def _block_pieces(block):
    """Split a block into (code pieces, leftover prose text, origin).
    Strong tokens are only code when free of CJK (otherwise they are
    bold headings). origin: 'p' for paragraph blocks, 'loose' otherwise
    — loose blocks continue the previous source line."""
    pieces = []
    rest = block
    for m in re.finditer(STRONG_CODE.pattern + "|" + FLAT_SEG, block):
        tok_src = m.group(0)
        if tok_src.startswith("<strong"):
            tok = _entity(re.sub(r"<[^>]+>", "", STRONG_CODE.match(tok_src).group(1))).strip()
            if CJK_RE.search(tok):
                return None, None, None
        else:
            tok = _decode_flat(tok_src[1:-1])
        if tok:
            pieces.append(tok)
    rest = re.sub(STRONG_CODE.pattern + "|" + FLAT_SEG, "", block)
    rest = re.sub(r"<[^>]+>", "", rest).strip()
    origin = "p" if block.startswith("<p") else "loose"
    return pieces, rest, origin


KEYWORD_START = re.compile(
    r"^(?:return|def|class|if|elif|else|for|while|import|from|with|try|"
    r"except|raise|print|yield|assert|del|global|@)\b")


def _join_pieces(pieces):
    """Join code fragments of one source line. Word-char boundaries get a
    space (print re-wraps split words), statements/annotations start a new
    line, everything else butts together."""
    line = ""
    for tok in pieces:
        if not tok:
            continue
        if not line:
            line = tok
        elif ANN_END.search(line) or KEYWORD_START.match(tok):
            line += "\n" + tok
        elif tok.startswith("#"):
            line += " " + tok
        elif line.endswith("#"):
            line += " " + tok
        elif line.endswith(")") and tok.startswith("self."):
            line += "\n" + tok
        elif re.search(r"[)\]}]$", line) and re.match(r"[a-z_]", tok):
            line += "\n" + tok
        elif re.search(r"[\w$]$", line) and re.match(r"[\w$]", tok):
            line += " " + tok
        else:
            line += tok
    return line


def rebuild_flat_listings(body):
    """Merge runs of flattened code paragraphs into <figure> cards.

    Handles both MEAP shapes: '[line]' paragraphs (Designing AI Systems)
    and strong-token + '[tok]' lines (Illustrated Guide). A run is a
    maximal sequence of code-ish blocks separated only by whitespace.
    A lone block only counts when its decoded text has no CJK.
    """
    parts = []
    pos = 0
    for m in BLOCK_RE.finditer(body):
        gap = body[pos:m.start()]
        if gap:
            parts.append(("gap", gap))
        parts.append(("blk", m.group(0)))
        pos = m.end()
    tail = body[pos:]
    if tail:
        parts.append(("gap", tail))

    out = []
    i, n = 0, len(parts)
    while i < n:
        kind, val = parts[i]
        if kind != "blk":
            out.append(val)
            i += 1
            continue
        run = []
        blocks = []
        while i < n:
            kind, val = parts[i]
            if kind == "blk":
                pieces, rest, origin = _block_pieces(val)
                if pieces and rest == "":
                    run.append((origin, pieces))
                    blocks.append(val)
                    i += 1
                    continue
                break
            elif kind == "gap" and val.strip() == "":
                # cross the whitespace gap only if another code-ish block
                # follows; otherwise stop so the gap is preserved
                j = i + 1
                if j < n and parts[j][0] == "blk":
                    pieces, rest, _ = _block_pieces(parts[j][1])
                    if pieces and rest == "":
                        i += 1
                        continue
                break
            else:
                break
        if not run:
            out.append(val)
            i += 1
            continue
        if len(run) == 1 and CJK_RE.search(
                _join_pieces([p for _, ps in run for p in ps])):
            # bracket-wrapped CJK prose: export artifact of callout/note
            # text — unwrap the brackets into a callout paragraph
            inner = re.sub(r"^<p[^>]*>|</p>$", "", blocks[0], flags=re.S)
            inner = re.sub(FLAT_SEG,
                           lambda m: _decode_flat(m.group(0)[1:-1]), inner)
            inner = re.sub(r"<[^>]+>", "", inner)
            out.append(f'<p class="callout">{_entity(inner.strip())}</p>')
            continue
        out.append(render_flat_listing(run))
    return "".join(out)


def render_flat_listing(runs):
    """Render collected code lines as a code-listing figure. 'loose'
    blocks (unwrapped strong/segment runs) continue the previous line."""
    lines = []
    origins = []
    for origin, pieces in runs:
        if origin == "p" or not lines or origins[-1] != "loose":
            lines.append(pieces)
            origins.append(origin)
        else:
            lines[-1].extend(pieces)
    lines = [_join_pieces(pieces) for pieces in lines]
    lines = [ln for ln in lines if ln.strip()]
    esc = ("\n".join(lines).replace("&", "&amp;")
           .replace("<", "&lt;").replace(">", "&gt;"))
    return f'<figure class="code-listing"><pre><code>{esc}</code></pre></figure>'


def _heading_for(num, text):
    level = "h3" if num.count(".") >= 2 else "h2"
    return f"<{level}>{num} {text.strip()}</{level}>"


CODE_SPLIT = re.compile(
    r'(<figure class="code-listing">.*?</figure>|<pre[^>]*>.*?</pre>)', re.S)


def typography_pass(body):
    """Residual typography cleanup after structure rebuilding:
    pandoc anchor leaks, citation/ref brackets, inline code, fake bold
    subheads, curly quotes inside code, stray running-header h2."""
    # pandoc anchor attribute leaks (some sit inside code figures)
    body = re.sub(r"\s*\{#[^}]*\}", "", body)
    # dangling "[\\" fragment before a rebuilt figure
    body = re.sub(r"\[\\(?=<figure)", "", body)

    # calibre export mangled a few oreil.ly short links (escaped tags
    # inside the attribute); rebuild the cluster as a plain link
    def link_fix(m):
        url = m.group("u1") + m.group("u2")
        text = (m.group("text") or "").strip()
        tail = (m.group("tail") or "").split("&gt;")[-1]
        tail = tail.replace("[", "").replace("]", "").lstrip()
        if not text:
            return tail
        return f'<a href="{url}">{_entity(text)}</a>{tail}'
    body = re.sub(
        r'<a href="(?P<u1>https?://[^"]*?)&lt;em&gt;(?P<u2>[^"<>]*?)”&gt;'
        r'(?:\[(?P<text>[^<&]+?)&lt;/a&gt;\])?'
        r'.*?(?P<tail>[^<]*)</a>',
        link_fix, body, flags=re.S)

    # running-header artifact: '<h2>第N章</h2>' mid-chapter (not the
    # chapter's own title, which sits within the first 300 chars)
    def h2_guard(m):
        return "" if m.start() > 300 else m.group(0)
    body = re.sub(r'(?:<section[^>]*>\s*)?<h2[^>]*>\s*第\s*\d+\s*章\s*</h2>\s*',
                  h2_guard, body)

    parts = CODE_SPLIT.split(body)
    for i in range(0, len(parts), 2):
        t = parts[i]
        # citation markers [[1]] -> superscript
        t = re.sub(r"\[\[(\d+)\]\]", r'<sup class="cite">\1</sup>', t)
        # cross-references: [图 2-14] / [第2章] -> plain text
        t = re.sub(r"\[(图\s*\d+(?:[-–]\d+)?)\]", r"\1", t)
        t = re.sub(r"\[(第\s*\d+\s*章)\]", r"\1", t)
        # print line-wrap brackets: leading [ before CJK and trailing ]
        # after CJK are wrap markers, not content
        t = re.sub(r"(<p[^>]*>)\[(?=\s*[\u4e00-\u9fff])", r"\1", t)
        t = re.sub(r"([\u4e00-\u9fff。，、])\](\s*</p>)", r"\1\2", t)
        # a stray ] right after CJK with no opening [ left in the paragraph
        def _stray_close(m):
            seg = m.group(1)
            return m.group(0) if seg.count("[") > seg.count("]") else \
                m.group(2) + m.group(3)
        t = re.sub(r"(<p[^>]*>)(.*?)(</p>)",
                   lambda m: m.group(0) if "[" in m.group(2) else
                   re.sub(r"([\u4e00-\u9fff。，、])\s*\] ", r"\1 ", m.group(0)),
                   t, flags=re.S)
        # escaped brackets from token-flattened code leaking into prose:
        # paired \\..\\ with non-CJK content are real code brackets
        def _pair_unescape(m):
            inner = m.group(1)
            return "[" + inner + "]" if not CJK_RE.search(inner) else m.group(0)
        t = re.sub(r"\\\[([^\\\[\]<>]{0,80})\\\]", _pair_unescape, t)
        # ANSI escapes and brackets adjacent to inline tags
        t = re.sub(r"\\\[(?=\d)", "[", t)
        t = re.sub(r"\\\[(?=<)", "[", t)
        t = re.sub(r"\[\\(?=<)", "[", t)
        t = re.sub(r"(?<=>)\\\]", "]", t)
        # ANSI-colored string constants -> code badge
        t = re.sub(r'"\\033[^"<]{1,12}"',
                   lambda m: f"<code>{_entity(m.group(0))}</code>", t)

        # inline code: split out existing code spans so they are not
        # re-processed, then unescape brackets inside them
        subparts = re.split(r"(<code>.*?</code>)", t, flags=re.S)
        for j in range(0, len(subparts), 2):
            subparts[j] = re.sub(
                r"\[([^\[\]<>]{1,120})\]",
                lambda m: (m.group(0) if CJK_RE.search(m.group(1))
                           else f"<code>{_entity(m.group(1))}</code>"),
                subparts[j])
            subparts[j] = re.sub(r"\[\](\s*)", r"\1", subparts[j])
        for j in range(1, len(subparts), 2):
            subparts[j] = (subparts[j].replace("\\[", "[")
                           .replace("\\]", "]"))
        t = "".join(subparts)
        # standalone \\ / \\ mentions are literal token syntax -> badges
        t = t.replace("\\[", '<code>\\[</code>').replace(
            "\\]", '<code>\\]</code>')
        # bold-paragraph subheads -> real headings (X.Y -> h2, X.Y.Z -> h3)
        t = re.sub(r"<p><strong>(\d+(?:\.\d+)+)\s+([^<]+)</strong></p>",
                   lambda m: _heading_for(m.group(1), m.group(2)), t)
        # loose bold section headings (calibre export) -> h3
        t = re.sub(
            r'(?<=[\n\r])\s*<strong class="calibre3">([^<]+)</strong>'
            r'(?=\s*(?:[\n\r]|$))',
            lambda m: f"\n<h3>{m.group(1).strip()}</h3>\n", t)
        parts[i] = t
    for i in range(1, len(parts), 2):
        # straighten curly quotes inside code blocks
        def straighten(m):
            inner = (m.group(2).replace("“", '"').replace("”", '"')
                     .replace("‘", "'").replace("’", "'"))
            inner = re.sub(r"\\([#{}\[\]|>&()])", r"\1", inner)
            return f"<pre{m.group(1)}>{inner}</pre>"
        parts[i] = re.sub(r"<pre([^>]*)>(.*?)</pre>", straighten,
                          parts[i], flags=re.S)
    return "".join(parts)


# -------------------------------------------------------------------- crypto

def encrypt_payload(obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    salt = get_random_bytes(16)
    key = PBKDF2(PASSWORD, salt, dkLen=32, count=PBKDF2_ITERS,
                 hmac_hash_module=SHA256)
    iv = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ct, tag = cipher.encrypt_and_digest(data)
    blob = salt + iv + tag + ct
    return blob


# ---------------------------------------------------------------------- main

def build_book(book):
    slug = book["slug"]
    print(f"→ {slug} (strategy={book['strategy']})")
    z, root, chapters_raw, meta_title = parse_epub(book["epub"])
    img_map = {}

    if book["strategy"] == "dais-map":
        raw = chapters_dais(z)
    else:
        raw = chapters_by_heading(chapters_raw)

    chapters = []
    for ch in raw:
        title = re.sub(r"\{#[^}]*\}", "", ch["title"]).strip()
        title = re.sub(r"\s+", " ", title)
        title = re.sub(r"^(第\s*\d+\s*章)\s*\.\s*", r"\1 ", title)
        body = ch["body"]
        body = inline_images(body, z, root, slug, book["max_img_w"], img_map)
        body = polish(body)
        if len(body) < 400 and "<img" not in body:
            continue
        chapters.append({"id": f"ch{len(chapters)+1:03d}", "title": title[:80],
                         "html": body})

    payload = {
        "slug": slug, "title": book["title"], "author": book["author"],
        "chapters": chapters,
    }
    blob = encrypt_payload(payload)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{slug}.bin")
    with open(out, "wb") as f:
        f.write(blob)
    print(f"   chapters: {len(chapters)}, payload {len(blob)//1024}KB -> {out}")
    return len(chapters)


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    _img_counter[0] = 0
    for book in BOOKS:
        build_book(book)
    print("done.")


if __name__ == "__main__":
    main()
