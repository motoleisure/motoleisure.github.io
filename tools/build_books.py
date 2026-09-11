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
    print(f"→ {slug}")
    z, root, chapters_raw, meta_title = parse_epub(book["epub"])
    img_map = {}
    chapters = []
    for ch in chapters_raw:
        title = extract_title(ch["html"]) or f"第 {len(chapters)+1} 章"
        body = extract_body(ch["html"])
        body = inline_images(body, z, root, slug, book["max_img_w"], img_map)
        if len(body) < 400 and "<img" not in body:
            continue  # skip blank fragments
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
