#!/usr/bin/env python3
"""Build blog articles from markdown sources into the site's article template.

Usage: python3 tools/build_posts.py

Reads:   /Volumes/JD5-1TB/tim/Documents/pi-output/article/*.md
Writes:  blog/<slug>/index.html
         assets/images/posts/<slug>/<n>.avif   (converted illustrations)
         assets/images/posts/<slug>/cover.svg  (1200x630 generated cover)
"""

import html as html_mod
import os
import re
import subprocess
import sys

import markdown

SRC_DIR = "/Volumes/JD5-1TB/tim/Documents/pi-output/article"
SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_IMG_DIR = os.path.join(SITE_DIR, "assets", "images", "posts")

# article registry: (source file, slug, title, date, excerpt, tag, accent for cover)
ARTICLES = [
    ("00-pi介绍-公众号文章-v1.md", "pi-intro",
     "我在用一个 AI 助手，它可以随时塞进新工具", "2026-06-03",
     "工具太散，切换即打断。pi 是一个支持注册自定义工具的 AI agent：写一个 TypeScript 文件放进目录，AI 就知道它的存在——说一句话，什么都能做。", "AI 工具"),
    ("01-SenseVoice接入pi-公众号文章-v2.md", "sensevoice-pi",
     "我把本地语音识别接进了 AI 编程助手，全程踩坑实录", "2026-06-03",
     "把 SenseVoice 本地语音识别模型直接接进 pi 的工具系统：说一句话自动转录，结果回到对话继续加工，敏感内容不过云端。", "AI 工具"),
    ("02-小红书生图接入pi-公众号文章-v1.md", "image-gen-pi",
     "又往 AI 助手里塞了一个工具：现在它能帮我出小红书配图了", "2026-06-03",
     "把出图这件事搬进对话窗口：接一个 gpt-image-2 的图片生成工具，写完稿顺手一句话出图，思路不再被打断。", "AI 工具"),
    ("03-VoxCPM配音接入pi-公众号文章-v1.md", "voxcpm-pi",
     "我把声音克隆配音接进了 AI 助手，现在它能直接出视频", "2026-06-03",
     "口播稿到字幕视频是一条完整流水线：解析稿件、分段合成、对齐时间轴、渲染合并。把它整个接进 pi，压缩成一句话的事。", "AI 工具"),
    ("04-Qwen3VL视觉接入pi-公众号文章-v1.md", "qwen3vl-pi",
     "DeepSeek V4 推理能力拉满，但它是个「睁眼瞎」", "2026-06-03",
     "推理模型换到 DeepSeek V4 之后，发现它看不见图。给 pi 接上 Qwen3-VL 视觉工具：识图、读截图、看 UI，让 agent 重新睁开眼。", "AI 工具"),
    ("05-后台服务调度-公众号文章-v1.md", "service-manager",
     "工具装多了，内存告急——我给 pi 加了个「管家」", "2026-06-03",
     "本地模型一个比一个大，全开机内存直接打满。做一个后台服务调度工具：AI 按需拉起、用完即停，内存交给管家管。", "AI 工具"),
    ("06-硬字幕提取接入pi-公众号文章-v1.md", "hard-subtitle",
     "视频里的字幕，我让 AI 自己读出来了", "2026-06-04",
     "硬字幕烧在画面里，复制不出来。OCR 逐帧提取接进 pi：扔进去一个视频，字幕文本直接回到对话里。", "AI 工具"),
    ("07-硬盘扫描接入pi-公众号文章-v1.md", "disk-scan",
     "硬盘快满了，我让 AI 帮我找出问题在哪", "2026-06-04",
     "256GB 的 Mac Mini 用了一年多就报警磁盘不足。做一个硬盘扫描工具接进 pi，让 AI 自己去找大文件和垃圾目录。", "AI 工具"),
    ("08-主讲者检测接入pi-公众号文章-v2.md", "speaker-detect",
     "双人播客的视频版，怎么让画面跟着说话人切换", "2026-06-05",
     "对话视频的镜头该给谁？把主讲者检测接进 pi：检测每段时间谁在说话，自动生成画面切换点，视频版一条流水线出来。", "AI 工具"),
    ("09-SeedVC声音克隆-公众号文章-v1.md", "seedvc-voice-clone",
     "我把声音克隆搭了个网页界面，全程踩坑实录", "2026-06-05",
     "SeedVC 可以用一段录音换音色、保语气。把模型封装成本地服务搭个网页界面，再接进 pi，配音的中间地带被填上了。", "AI 工具"),
    ("10-LLM推理效率教程精读-公众号文章-v1.md", "llm-efficiency",
     "B200 一半时间在等内存：一篇 160 页的 LLM 推理效率教程讲了什么", "2026-06-29",
     "Alex Smola 的 161 页教程《Efficiency in LLMs》，从芯片讲到 KV 压缩。两个晚上读完，整理成一篇能看完的中文摘要，保留量化直觉和关键结论。", "深度长文"),
    ("11-浮点数可视化学习-公众号文章-v1.md", "float-bits",
     "为什么 0.1 存不进计算机？我做了个「拆开看」的工具，10 分钟搞懂 FP8", "2026-08-26",
     "0.1 + 0.2 为什么不等于 0.3？把浮点数拆成三段二进制格子，做了五个可交互的插画，从 IEEE 754 一路看到 FP8。", "深度长文"),
    ("12-DSH输入历史插件-公众号文章-v1.md", "dsh-input-history",
     "给 Web 对话框装一个 ↑ 键：我在 DeepSeek Harness 上写「输入历史」插件的完整记录", "2026-08-28",
     "终端里 ↑ 调出上一条命令是肌肉记忆，Web 对话框里却什么都没有。用纯插件方式补上它：一百来行代码，读穿了半个框架。", "开发实录"),
    ("13-dsh-remote-web-gateway-cloudflare-tunnel.md", "dsh-remote-gateway",
     "DSH 远程控制实战：无需 VPS，用 Cloudflare Tunnel 把电脑工作台装进手机", "2026-08-24",
     "电脑上的 DSH 工作台只听本机，出门在外够不着。用 Cloudflare Named Tunnel 配认证网关：需要时手机扫码访问，不用时一键关闭。", "开发实录"),
    ("14-FrontierAgent-Mac本地部署与踩坑实录.md", "frontieragent-mac",
     "我在 Mac 上部署了开源 Agent「FrontierAgent」：全程实操 + 7 个踩坑实录", "2026-08-26",
     "不需要 GPU，不需要 Docker Desktop，一台普通 Mac 就能跑。「能装上」和「装得顺」之间隔着 7 个坑，每一个的现象、根因和解法都在这里。", "开发实录"),
    ("15-词嵌入与注意力机制-公众号文章-v1.md", "embedding-attention",
     "「忘记密码」和「登录信息忘了」，大模型为什么知道是一回事？", "2026-08-31",
     "两句话没有一个词相同，意思却一样——大模型靠的是词嵌入和注意力。用四张图讲清：意义怎么变成向量，注意力怎么打分。", "深度长文"),
]

GITHUB_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.55 0-.27-.01-1.17-.02-2.12-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.69 1.25 3.35.96.1-.75.4-1.25.72-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.26 5.66.41.36.78 1.06.78 2.14 0 1.54-.01 2.79-.01 3.17 0 .31.21.67.8.55A11.51 11.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"/></svg>'
MAIL_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/></svg>'
X_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.66l-5.21-6.82-5.97 6.82H1.67l7.73-8.84L1.25 2.25h6.83l4.71 6.23 5.45-6.23Zm-1.16 17.52h1.83L7.08 4.13H5.12l11.96 15.64Z"/></svg>'


def read_article(path):
    text = open(path, encoding="utf-8").read()
    # strip WeChat layout comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text


def convert_images(md_text, src_dir, src_md_path, slug, used_files):
    """Rewrite image refs; convert each referenced png to AVIF in site assets.

    Relative paths are resolved against the source markdown's own directory
    (articles keep illustrations in sibling folders).
    """
    out_dir = os.path.join(POSTS_IMG_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    counter = [0]
    mapping = {}

    def repl(m):
        alt, rel = m.group(1), m.group(2)
        src = os.path.normpath(os.path.join(src_dir, rel))
        if not os.path.exists(src):
            # some articles reference images relative to a sibling asset
            # folder named after the markdown file (without extension)
            stem = os.path.splitext(os.path.basename(src_md_path))[0]
            alt_src = os.path.normpath(
                os.path.join(src_dir, stem, rel))
            if os.path.exists(alt_src):
                src = alt_src
        if not os.path.exists(src):
            print(f"  !! missing image: {rel}", file=sys.stderr)
            return f"!!missing {rel}!!"
        counter[0] += 1
        dst = os.path.join(out_dir, f"{counter[0]:02d}.avif")
        used_files.add(src)
        if src not in mapping:
            tmp = "/tmp/_avif_scaled.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", src, "-vf",
                 "scale='min(1200,iw)':-2", tmp],
                check=True, capture_output=True)
            subprocess.run(
                ["avifenc", "--min", "30", "--max", "63", "-j", "4",
                 tmp, dst],
                check=True, capture_output=True)
            mapping[src] = True
        return f"![{alt}](../../assets/images/posts/{slug}/{counter[0]:02d}.avif)"

    md_text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, md_text)
    return md_text


def highlight_code(md_text):
    """Pre-highlight fenced code blocks into our Night Owl token spans."""
    # temporarily swap fenced blocks out of markdown processing
    stash = []
    def stash_repl(m):
        stash.append((m.group(1) or "", m.group(2)))
        return f"\n\n@@CODE{len(stash)-1}@@\n\n"

    md_text = re.sub(r"```(\w*)\n(.*?)```", stash_repl, md_text, flags=re.S)
    return md_text, stash


def restore_codeblocks(html_text, stash):
    for i, (lang, body) in enumerate(stash):
        block = highlight_plain(lang, body)
        html_text = html_text.replace(f"@@CODE{i}@@", block)
    return html_text


def highlight_plain(lang, body):
    body_esc = html_mod.escape(body)
    lines = []
    for line in body_esc.split("\n"):
        line = re.sub(r"(\s)(#.*)$", r'\1<span class="tok-c">\2</span>', line)
        line = re.sub(r'(&quot;.*?&quot;|&#x27;.*?&#x27;)',
                      r'<span class="tok-s">\1</span>', line)
        lines.append(line)
    return ('<pre><code>' + "\n".join(lines) + "</code></pre>")


def make_cover(slug, title, tag):
    """Generate a deterministic 1200x630 SVG cover in site palette."""
    out = os.path.join(POSTS_IMG_DIR, slug, "cover.svg")
    if os.path.exists(out):
        return out
    # pick accent hue by hash of slug for variety within the palette
    accents = ["#4f46e5", "#2563eb", "#0d9488", "#b45309", "#be185d"]
    accent = accents[sum(ord(c) for c in slug) % len(accents)]
    short = title if len(title) <= 18 else title[:17] + "…"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-label="{html_mod.escape(title)}">
  <rect width="1200" height="630" fill="#eef6fd"/>
  <g stroke="#b2d5ff" stroke-width="2" opacity="0.55">
    <path d="M120 90 v24 M108 102 h24"/><path d="M1080 130 v24 M1068 142 h24"/>
    <path d="M170 520 v24 M158 532 h24"/><path d="M1020 500 v24 M1008 512 h24"/>
  </g>
  <g fill="#b2d5ff" opacity="0.8">
    <circle cx="90" cy="300" r="5"/><circle cx="1110" cy="330" r="5"/>
  </g>
  <rect x="150" y="90" width="900" height="450" rx="18" fill="none" stroke="{accent}" stroke-width="2.5" stroke-dasharray="10 12" opacity="0.45"/>
  <rect x="440" y="150" width="320" height="52" rx="26" fill="#00172e"/>
  <text x="600" y="185" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="24" font-weight="600" fill="#ffffff" letter-spacing="4">{html_mod.escape(tag)}</text>
  <text x="600" y="400" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="64" font-weight="600" fill="#00172e" letter-spacing="-2">{html_mod.escape(short)}</text>
  <rect x="560" y="440" width="80" height="10" rx="5" fill="{accent}"/>
</svg>'''
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    return out


PAGE_TMPL = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - Agent's Photolog</title>
  <meta name="description" content="{desc}">
  <meta name="author" content="Tim Chan">
  <link rel="canonical" href="https://motoleisure.github.io/blog/{slug}/">
  <link rel="icon" href="../../assets/images/favicon.ico">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:url" content="https://motoleisure.github.io/blog/{slug}/">
  <meta property="og:description" content="{desc}">
  <meta property="og:image" content="https://motoleisure.github.io/assets/images/posts/{slug}/cover.svg">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Inter is self-hosted in assets/css/style.css via @font-face -->
  <link rel="stylesheet" href="../../assets/css/style.css">
</head>
<body>
  <a class="skip-link" href="#main">跳到主要内容</a>

  <header class="site-header">
    <div class="container container--wide header-inner">
      <a class="wordmark" href="../../">
        <span class="wordmark-dot" aria-hidden="true"></span>
        Agent's Photolog
      </a>
      <nav class="header-nav" aria-label="站点导航">
        <a class="icon-link" href="https://github.com/chenyuqing" target="_blank" rel="noopener" aria-label="GitHub">
          {github_svg}
        </a>
        <span class="header-divider" aria-hidden="true"></span>
        <a class="nav-link" href="../../">博客</a>
      </nav>
    </div>
  </header>

  <main id="main">
    <div class="container container--narrow">
      <article class="article-wrap">
        <a class="back-link" href="../../">← 全部文章</a>

        <h1 class="article-title">{title}</h1>

        <div class="article-meta">
          <img class="avatar" src="../../assets/images/avatar.avif" alt="Tim Chan 的头像">
          <div class="who">
            <span class="name">Tim Chan</span>
            <time class="date" datetime="{date}">发布于 {date_cn}</time>
          </div>
        </div>

        <p class="article-lead">{lead}</p>

        <div class="prose">
{body}
        </div>
      </article>
    </div>
  </main>

  <footer class="site-footer">
    <div class="container footer-inner">
      <p class="footer-mission">AI时代的Photolog，和你的agent交个朋友。</p>
      <div class="footer-links">
        <a href="https://github.com/chenyuqing" target="_blank" rel="noopener" aria-label="GitHub">
          {github_svg}
        </a>
        <a href="mailto:motoleisure@gmail.com" aria-label="邮件">
          {mail_svg}
        </a>
        <a href="https://x.com/scottone2" target="_blank" rel="noopener" aria-label="X">
          {x_svg}
        </a>
      </div>
      <div class="footer-bottom">
        <span>© 2026 Tim Chan. 保留所有权利。</span>
        <span>Agent's Photolog</span>
      </div>
    </div>
  </footer>

</body>
</html>
'''


def build_one(src_file, slug, title, date, excerpt, tag):
    src_path = os.path.join(SRC_DIR, src_file)
    md = read_article(src_path)

    used = set()
    md = convert_images(md, os.path.dirname(src_path), src_path, slug, used)
    md, stash = highlight_code(md)

    # markdown -> html
    html = markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    html = restore_codeblocks(html, stash)

    # Wrap content images in a <figure>. Markdown leaves the image inside a
    # <p>; ideally we'd move it out, but figure cannot legally nest in <p>.
    # We push it: strip the enclosing <p> around a lone image, then wrap.
    html = re.sub(
        r'<p><img(?![^>]*class="avatar")[^>]*/></p>',
        lambda m: '<figure>' + m.group(0).replace('/>', ' loading="lazy" />') + '<figcaption>' +
        (re.search(r'alt="([^"]*)"', m.group(0)).group(1)) + '</figcaption></figure>',
        html)
    # images inside blockquote etc. keep their place, just get lazy loading
    html = re.sub(r'<img(?![^>]*class="avatar")[^>]*/>',
                  lambda m: m.group(0).replace('/>', ' loading="lazy" />'), html)

    # wide tables get a horizontal-scroll wrapper
    html = html.replace('<table>', '<div class="table-wrap"><table>')
    html = html.replace('</table>', '</table></div>')

    # code blocks stashed as @@CODEn@@ paragraphs get wrapped in <p>; unwrap
    html = re.sub(r'<p>@@CODE(\d+)@@</p>', r'@@CODE\1@@', html)
    html = re.sub(r'<p>(<pre><code>.*?</code></pre>)</p>', r'\1', html, flags=re.S)

    # strip the first h1 (title is in template)
    html = re.sub(r"<h1>.*?</h1>", "", html, count=1, flags=re.S)

    # remove the first hr right after title if present
    html = re.sub(r'^\s*(<hr\s*/?>)?\s*', "", html)

    # lead paragraph: use excerpt
    date_cn = f"{date[:4]} 年 {int(date[5:7])} 月 {int(date[8:10])} 日"

    cover = make_cover(slug, title, tag)

    page = PAGE_TMPL.format(
        title=html_mod.escape(title), slug=slug, desc=html_mod.escape(excerpt),
        date=date, date_cn=date_cn, lead=html_mod.escape(excerpt),
        body=html,
        github_svg=GITHUB_SVG, mail_svg=MAIL_SVG, x_svg=X_SVG,
    )

    out_dir = os.path.join(SITE_DIR, "blog", slug)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  built blog/{slug}/index.html  ({len(html)//1024}KB prose, {len(used)} imgs)")
    return cover


def main():
    os.makedirs(POSTS_IMG_DIR, exist_ok=True)
    covers = []
    for src, slug, title, date, excerpt, tag in ARTICLES:
        print(f"→ {slug}")
        cover = build_one(src, slug, title, date, excerpt, tag)
        covers.append((slug, title, date, excerpt, tag, cover))
    print("\nAll done.")
    for c in covers:
        print(" ", c[1])


if __name__ == "__main__":
    main()
