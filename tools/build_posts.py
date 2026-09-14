#!/usr/bin/env python3
"""Build blog articles from markdown sources into the site's article template.

Usage: python3 tools/build_posts.py

Reads:   /Volumes/JD5-1TB/tim/Documents/pi-output/article/*.md
Writes:  blog/<slug>/index.html
         assets/images/posts/<slug>/<n>.avif   (converted illustrations)
         assets/images/posts/<slug>/cover.svg  (1200x630 generated cover)
"""

import glob
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
    ("16-FrontierAgent接入DSH插件实录-公众号文章-v1.md", "frontier-dsh-plugin",
     "我把 FrontierAgent 做成了 DSH 的插件：零额外密钥 + 8 个踩坑实录", "2026-09-03",
     "上一篇把 FrontierAgent 装上了 Mac，但它一直是座孤岛。这篇记录把它做成 DSH 插件的全过程——对话框里一条 /frontier 派活，复用当前模型跑完，结果自动回到对话；「能跑」和「跑得对」之间隔着 8 个坑。", "开发实录"),
    ("17-prompt_caching_公众号文章.md", "prompt-caching",
     "你的 AI Agent 正在偷偷烧钱？搞懂「提示词缓存」，费用直接降 90%", "2026-09-08",
     "你以为每次提问都要为 5 万 token 的上下文全价买单？其实只要用对缓存：命中部分按一折计费，写对缓存边界、避开动态内容，成本能砍到接近零。", "深度长文"),
    ("18-Epiplexity认知复杂度-Wilson演讲精读-公众号文章-v2.md", "epiplexity",
     "模型越大，偏见越强：一场颠覆直觉的 AI 基础理论演讲讲了什么", "2026-09-10",
     "Andrew Gordon Wilson 一个多小时的演讲，开场就让全场 70% 的人选错。Epiplexity（认知复杂度）解释了为什么模型越大越该「挑食」：只啃难而有规律的数据，而不是对所有数据都认真学。", "深度长文"),
    ("19-DeepSeek-V4.1-Flash-Engram-LPDDR-公众号文章-v1.md", "deepseek-engram-lpddr",
     "用 LPDDR 取代 HBM：DeepSeek 4.1 Flash 架构里被所有人忽略的关键细节", "2026-09-11",
     "舆论都在看跑分，硬件分析师 GDP 指出真正的主角：约 196B 参数的 Engram 嵌入驻留主机内存 LPDDR5，把最贵的 HBM 省了下来。这是中国大模型实验室集体转向的新方向。", "深度长文"),
    ("20-稀疏注意力长度外推-ICLR2026精读-公众号文章-v1.md", "sparse-attention-extrapolation",
     "训练 64 个 token，外推 1000 倍仍拿 95 分：ICLR 2026 找到了长文本的病根", "2026-09-11",
     "softmax 必须给每个 token 分一点概率，序列越长越「弥散」；α-entmax 能把无关 token 精确清零。只训 64 长度的模型外推 1000 倍仍拿 95.3%，softmax 跌到 3%。", "深度长文"),
    ("21-软件工厂开源为什么不卖钱-ColeMurray精读-公众号文章-v1.md", "software-factory-opensource",
     "他开源了「软件工厂」却不卖钱：一个反共识选择背后的算盘", "2026-09-12",
     "当所有人都在把 AI coding agent 卖成 SaaS、按席位收费、token 加价转卖，前亚马逊工程师 Cole Murray 偏说这条路走不通，把整套软件工厂开源白送——价值在组织流程，不在基建。", "深度长文"),
    ("22-GPT-Live-1精读-官方vs推断-公众号文章-v1.md", "gpt-live-1-reverse",
     "他用 0.05 美元/分钟，反推出 OpenAI 语音模型的整套架构", "2026-09-12",
     "OpenAI 发了全双工语音模型 GPT-Live-1，官方没公布任何架构细节。一个 NVIDIA 语音研究员只看 API、定价和第三方评测，就把内部结构推了个八九不离十——再用官方原文逐条核验。", "深度长文"),
    ("23-语音agent评测框架-CRAWL-WALK-RUN与τ-Voice精读-公众号文章-v1.md", "voice-agent-eval",
     "语音 agent 为什么比文本 agent 难测 10 倍？CRAWL-WALK-RUN 评测框架全拆解", "2026-09-12",
     "OpenAI 给 GPT-Live-1 配了开源评测框架，把语音 agent 评估拆成「爬行—行走—奔跑」三档；τ-Voice 论文用 278 个真实任务测出：全双工语音 agent 只保留了文本能力的 30%–45%。", "深度长文"),
    ("24-谁该拥有你的学习闭环-Presence的Codex循环vs开源自建-公众号文章-v1.md", "learning-loop-presence",
     "谁该拥有你的学习闭环：OpenAI 用 Codex 10 天降了 15% 转接率，但有个更深的押注", "2026-09-12",
     "生产会话暴露缺口→Codex 提议修复→团队测试批准→上线：这套闭环和 Cole Murray 开源的 OpenInspect 是同一种架构，区别只在——你租用闭环，还是拥有闭环。", "深度长文"),
    ("25-GPT-Live-1架构图解教程-从全双工音频到工具调用全流程-公众号文章-v1.md", "gpt-live-1-architecture",
     "GPT-Live-1 架构图解教程：从全双工音频流到工具调用全流程", "2026-09-12",
     "用 10 张图逐步拆解 GPT-Live-1 的完整实现架构：音频怎么流进流出、委托怎么发生、工具怎么执行、结果怎么确认说回用户——每一张图对应一个架构层，看完就能动手搭。", "深度长文"),
    ("26-FrogNano精读-在线任务合成标定与SWE-RL横向对比-公众号文章-v1.md", "frognano",
     "4B 小模型怎么追平 70B？FrogNano 的「在线任务合成」标定细节与硬对比", "2026-09-12",
     "微软 Froggy Team 的 4B coding agent，不蒸馏、只靠 RL 在在线合成的任务上训练，把 SWE-bench Verified 做到 61.5%。往里钻两层：TaskPilot 怎么贴着能力前沿合任务，以及和 SWE-RL、Agent-RLVR 的硬对比。", "深度长文"),
    ("27-GPT-Live-1活样本-HeyGen-LiveAvatar集成逐行拆解-公众号文章-v1.md", "liveavatar-gpt-live",
     "把 GPT-Live-1 跑通的最小活样本：HeyGen 仓库逐行拆解", "2026-09-13",
     "HeyGen 的 liveavatar-gpt-live-demos（MIT）用 GPT-Live-1 驱动实时数字人，开箱是日语家教。clone 下来逐文件精读源码：架构图里的每一根线，在真实代码里长什么样。", "开发实录"),
]

GITHUB_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.55 0-.27-.01-1.17-.02-2.12-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.69 1.25 3.35.96.1-.75.4-1.25.72-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.26 5.66.41.36.78 1.06.78 2.14 0 1.54-.01 2.79-.01 3.17 0 .31.21.67.8.55A11.51 11.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"/></svg>'
MAIL_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/></svg>'
X_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.66l-5.21-6.82-5.97 6.82H1.67l7.73-8.84L1.25 2.25h6.83l4.71 6.23 5.45-6.23Zm-1.16 17.52h1.83L7.08 4.13H5.12l11.96 15.64Z"/></svg>'


def read_article(path):
    text = open(path, encoding="utf-8").read()
    # strip WeChat layout comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # pipe tables need a blank line before the header row, or python-markdown
    # renders them as plain text (part 20 of the inference series)
    out, fence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            fence = not fence
            out.append(ln)
            continue
        if (not fence and ln.lstrip().startswith("|") and out
                and out[-1].strip() and not out[-1].lstrip().startswith("|")):
            out.append("")
        out.append(ln)
    return "\n".join(out)


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
            # last resort: search sibling illustration folders by filename,
            # preferring a folder numbered like the article (17-prompt_caching
            # references "assets/prompt-caching-illustrations/..." which only
            # exists on disk as "17-prompt-caching-illustrations/...")
            hits = glob.glob(os.path.join(src_dir, "*",
                                          os.path.basename(rel)))
            if len(hits) > 1:
                m = re.match(r"\d+", os.path.basename(src_md_path))
                if m:
                    pref = [h for h in hits if os.path.basename(
                        os.path.dirname(h)).startswith(m.group(0) + "-")]
                    if pref:
                        hits = pref
            if len(hits) == 1:
                src = hits[0]
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
    os.makedirs(os.path.dirname(out), exist_ok=True)
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
  <link rel="icon" href="{pfx}assets/images/favicon.ico">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:url" content="https://motoleisure.github.io/blog/{slug}/">
  <meta property="og:description" content="{desc}">
  <meta property="og:image" content="https://motoleisure.github.io/assets/images/posts/{slug}/cover.svg">
  <meta name="twitter:card" content="summary_large_image">
  <!-- Inter is self-hosted in assets/css/style.css via @font-face -->
  <link rel="stylesheet" href="{pfx}assets/css/style.css">
</head>
<body>
  <a class="skip-link" href="#main">跳到主要内容</a>

  <header class="site-header">
    <div class="container container--wide header-inner">
      <a class="wordmark" href="{pfx}">
        <span class="wordmark-dot" aria-hidden="true"></span>
        Agent's Photolog
      </a>
      <nav class="header-nav" aria-label="站点导航">
        <a class="icon-link" href="https://github.com/chenyuqing" target="_blank" rel="noopener" aria-label="GitHub">
          {github_svg}
        </a>
        <span class="header-divider" aria-hidden="true"></span>
        <a class="nav-link" href="{pfx}">博客</a>
        <span class="header-divider" aria-hidden="true"></span>
        <a class="nav-link" href="{pfx}pelican/">鹈鹕测试</a>
        <span class="header-divider" aria-hidden="true"></span>
        <a class="nav-link" href="{pfx}books/">书架</a>
      </nav>
    </div>
  </header>

  <main id="main">
    <div class="container container--narrow">
      <article class="article-wrap">
        <a class="back-link" href="{pfx}">← 全部文章</a>

        <h1 class="article-title">{title}</h1>

        <div class="article-meta">
          <img class="avatar" src="{pfx}assets/images/avatar.avif" alt="Tim Chan 的头像">
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
    html = re.sub(r'<img(?![^>]*class="avatar")(?![^>]*loading=)[^>]*/>',
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
        pfx="../../", title=html_mod.escape(title), slug=slug,
        desc=html_mod.escape(excerpt),
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


# ------------------------------------------------------------------
# 28-llm-inference-series: a 20-part series published as one hub page
# + 20 part pages, so the homepage gets a single card instead of 20.
# Parts live at blog/<hub>/<part>/, one level deeper than normal posts
# (hence the ../../../ asset prefix).

SERIES_DIR = os.path.join(SRC_DIR, "28-llm-inference-series")
SERIES = {
    "slug": "llm-inference-series",
    "title": "成为 LLM Inference Engineer 全景指南（20 篇系列）",
    "date": "2026-09-14",
    "tag": "深度长文",
    "excerpt": "从推理生命周期原理讲到生产部署、成本优化与证据体系，再用 34 项技术全图查漏补缺——20 篇讲透 LLM 推理工程的岗位、原理与实战。",
    "parts": [
        ("01-序章-为什么需要inference-engineer.md", "why-inference-engineer"),
        ("02-推理基础原理-prefill-decode生命周期.md", "prefill-decode-lifecycle"),
        ("03-KV-Cache深度解析-PagedAttention命中率真相.md", "kv-cache-pagedattention"),
        ("04-量化全景-精度延迟成本三角.md", "quantization-triangle"),
        ("05-推理框架横评-vLLM-SGLang-TensorRT-llama-MLX.md", "inference-frameworks"),
        ("06-连续批处理与调度-iteration-level-batching抢占优先级.md", "continuous-batching"),
        ("07-Attention算子优化-FlashAttention-PagedAttention-RingAttention.md", "attention-kernels"),
        ("08-投机解码-Speculative-Decoding-draft-model-EAGLE-Medusa.md", "speculative-decoding"),
        ("09-硬件与显存预算-GPU层级-Apple统一内存-多卡并行.md", "hardware-memory-budget"),
        ("10-可观测性与基准测试-TTFT-TPOT-Inference-Lab实证.md", "observability-benchmarks"),
        ("11-成本优化实战-autoscaling-spot-路由-预算门控.md", "cost-optimization"),
        ("12-生产部署-SLO-负载测试-故障模式-灰度回滚.md", "production-slo"),
        ("13-前沿技术-Disaggregated-PrefixCaching进阶-ChunkedPrefill-MoE服务.md", "frontier-techniques"),
        ("14-证据体系-可信推理评估流水线-Inference-Lab方法论.md", "evidence-pipeline"),
        ("15-学习路径与资源地图-从入门到精通-职业市场.md", "learning-path"),
        ("16-长上下文注意力变体-稀疏滑动膨胀-低秩潜空间-MLA-YOCO.md", "long-context-attention"),
        ("17-缓存感知路由与KV分层存储-GPU-HBM-RAM-SSD-tier.md", "cache-aware-routing"),
        ("18-算子融合与kernel选型-torch.compile-CUDA-graphs-autotuning.md", "kernel-fusion"),
        ("19-训练侧边界认知-QAT-activation-ckpt-sequence-packing-mixed-precision-DDP-ZeRO-流水线调度.md", "training-side-boundary"),
        ("20-Atlas交叉导航表-业务压力到技术与文章映射.md", "atlas-navigation"),
    ],
}


def clean_lead(text):
    """Strip markdown emphasis/links so an excerpt reads as plain text."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("`", "").strip()


def series_part_meta(path):
    """(h1 title, lead from first blockquote line) of a series part."""
    title, lead = None, None
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if title is None and ln.startswith("# "):
            title = ln[2:].strip()
        if lead is None and ln.startswith(">"):
            lead = clean_lead(ln.lstrip("> ").strip())
        if title and lead:
            break
    return title or "", lead or ""


def render_md(md, src_dir, src_md_path, slug):
    """Shared markdown -> html pipeline (images, code, tables, title strip)."""
    if "![" in md:
        used = set()
        md = convert_images(md, src_dir, src_md_path, slug, used)
    md, stash = highlight_code(md)
    html = markdown.markdown(
        md, extensions=["tables", "fenced_code", "sane_lists"])
    html = restore_codeblocks(html, stash)
    html = re.sub(
        r'<p><img(?![^>]*class="avatar")[^>]*/></p>',
        lambda m: '<figure>' + m.group(0).replace('/>', ' loading="lazy" />') + '<figcaption>' +
        (re.search(r'alt="([^"]*)"', m.group(0)).group(1)) + '</figcaption></figure>',
        html)
    html = re.sub(r'<img(?![^>]*class="avatar")(?![^>]*loading=)[^>]*/>',
                  lambda m: m.group(0).replace('/>', ' loading="lazy" />'), html)
    html = html.replace('<table>', '<div class="table-wrap"><table>')
    html = html.replace('</table>', '</table></div>')
    html = re.sub(r'<p>@@CODE(\d+)@@</p>', r'@@CODE\1@@', html)
    html = re.sub(r'<p>(<pre><code>.*?</code></pre>)</p>', r'\1', html, flags=re.S)
    html = re.sub(r"<h1>.*?</h1>", "", html, count=1, flags=re.S)
    return html


def build_series():
    hub = SERIES["slug"]
    hub_dir = os.path.join(SITE_DIR, "blog", hub)
    os.makedirs(hub_dir, exist_ok=True)
    cover = make_cover(hub, SERIES["title"], SERIES["tag"])
    date_cn = (f"{SERIES['date'][:4]} 年 {int(SERIES['date'][5:7])} 月 "
               f"{int(SERIES['date'][8:10])} 日")

    toc, metas = [], []
    for fname, slug in SERIES["parts"]:
        title, lead = series_part_meta(os.path.join(SERIES_DIR, fname))
        metas.append((fname, slug, title, lead))
        num, sep, rest = title.partition(" · ")
        label = rest if sep else title
        toc.append(f'      <li><a href="{slug}/">{html_mod.escape(label)}</a></li>')

    hub_body = (
        "<p>整个系列共 <strong>20 篇</strong>：01–15 是核心一圈，从推理生命周期原理"
        "一路讲到生产部署、成本优化、证据体系；16–20 依 34 项技术全图查漏补缺，"
        "以交叉导航表收官。按顺序读即可，每篇末尾有上下篇导航。</p>\n"
        "        <h2>系列目录</h2>\n        <ol>\n" + "\n".join(toc) +
        "\n        </ol>")

    page = PAGE_TMPL.format(
        pfx="../../", title=html_mod.escape(SERIES["title"]), slug=hub,
        desc=html_mod.escape(SERIES["excerpt"]), date=SERIES["date"],
        date_cn=date_cn, lead=html_mod.escape(SERIES["excerpt"]),
        body=hub_body,
        github_svg=GITHUB_SVG, mail_svg=MAIL_SVG, x_svg=X_SVG,
    )
    with open(os.path.join(hub_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  built blog/{hub}/index.html (series hub)")

    for i, (fname, slug, title, lead) in enumerate(metas):
        md = read_article(os.path.join(SERIES_DIR, fname))
        body = render_md(md, SERIES_DIR, os.path.join(SERIES_DIR, fname),
                         f"{hub}-{slug}")
        nav = ['<a class="back-link" href="../">系列目录</a>']
        if i > 0:
            nav.insert(0, f'<a class="back-link" href="../{metas[i-1][1]}/">← 上一篇</a>')
        if i < len(metas) - 1:
            nav.append(f'<a class="back-link" href="../{metas[i+1][1]}/">下一篇 →</a>')
        body += '\n        <p>' + "　·　".join(nav) + "</p>"

        page = PAGE_TMPL.format(
            pfx="../../../", title=html_mod.escape(title), slug=f"{hub}/{slug}",
            desc=html_mod.escape(lead), date=SERIES["date"],
            date_cn=date_cn, lead=html_mod.escape(lead),
            body=body,
            github_svg=GITHUB_SVG, mail_svg=MAIL_SVG, x_svg=X_SVG,
        )
        pdir = os.path.join(hub_dir, slug)
        os.makedirs(pdir, exist_ok=True)
        with open(os.path.join(pdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
    print(f"  built {len(metas)} series part pages")
    return cover


# All posts for the homepage grid: 16 generated from ARTICLES + 2 hand-written.
# cover is the SVG path (posts/<slug>/cover.svg, except the two hand-written
# ones which live at assets/images/cover-*.svg).
HANDWRITTEN = [
    {"slug": "two-github-accounts",
     "title": "一台电脑同时使用两个 GitHub 账号", "date": "2026-08-31",
     "excerpt": "用 SSH Host 别名把账号写进 remote URL：给第二个账号配一把专属密钥，推拉代码自动走对应身份，不存在“忘了切换账号”这回事。",
     "cover": "assets/images/cover-two-github-accounts.svg"},
    {"slug": "hello-again",
     "title": "重构了这个博客：告别 2015，换上新装", "date": "2026-08-31",
     "excerpt": "旧站是 2015 年用 Hexo 生成的，停更在 2018 年。这次连根拔起，删掉所有旧文章，手写静态页面重新出发——顺便记录一下新设计是怎么来的。",
     "cover": "assets/images/cover-hello-again.svg"},
]


def all_posts():
    """ARTICLES converted to dicts + series hub + hand-written posts."""
    posts = [{"slug": slug, "title": title, "date": date, "excerpt": excerpt,
              "cover": f"assets/images/posts/{slug}/cover.svg"}
             for _src, slug, title, date, excerpt, _tag in ARTICLES]
    posts.append({"slug": SERIES["slug"], "title": SERIES["title"],
                  "date": SERIES["date"], "excerpt": SERIES["excerpt"],
                  "cover": f"assets/images/posts/{SERIES['slug']}/cover.svg"})
    posts.extend(HANDWRITTEN)
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def render_homepage():
    """Rebuild the homepage card grid in index.html from all_posts()."""
    idx = os.path.join(SITE_DIR, "index.html")
    doc = open(idx, encoding="utf-8").read()

    cards = []
    for i, p in enumerate(all_posts()):
        esc_t = p["title"].replace("&", "&amp;").replace("<", "&lt;")
        esc_e = p["excerpt"].replace("&", "&amp;").replace("<", "&lt;")
        # LCP: the first (newest) cover above the fold should load eagerly
        img_attrs = 'loading="lazy"'
        if i == 0:
            img_attrs = 'loading="eager" fetchpriority="high"'
        cards.append(f'''          <a class="editorial-card" href="blog/{p['slug']}/">
            <img class="cover" src="{p['cover']}" alt="" {img_attrs}>
            <div class="card-body">
              <time datetime="{p['date']}">{p['date'][:4]} 年 {int(p['date'][5:7])} 月 {int(p['date'][8:10])} 日</time>
              <h2 class="card-title">{esc_t}</h2>
              <p class="card-excerpt">{esc_e}</p>
            </div>
          </a>''')

    grid_open = '<div class="editorial-grid rise rise-2" id="post-grid">'
    grid_end = '</div>\n        <p class="no-results">没有匹配的文章，换个关键词试试。</p>'

    start = doc.find(grid_open)
    end = doc.find(grid_end)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(f"Could not locate grid in {idx}")

    new_grid = grid_open + '\n\n' + '\n\n'.join(cards) + '\n\n        ' + grid_end
    doc = doc[:start] + new_grid + doc[end + len(grid_end):]
    open(idx, "w", encoding="utf-8").write(doc)
    print(f"  render_homepage(): {len(cards)} cards written to index.html")


if __name__ == "__main__":
    main()
    build_series()
    render_homepage()
