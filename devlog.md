# Agent's Photolog — 开发日志

记录站点功能开发过程，供后续维护参考。

## 2026-09-04 · 鹈鹕测试模块上线

### 背景

在同一个提示词下测试不同 AI 模型的 SVG 动画能力，做成站点导航中「博客」的对等栏目「鹈鹕测试」。

### 提示词

每篇测试使用同一句提示词，图库页顶部可见展示 + 复制按钮：

> 创建一个HTML，内容是SVG绘制一个鹈鹕骑自行车的2D动画

### 目录结构

```
pelican/
  index.html                        # 图库页（提示词展示 + 卡片网格 + 复制按钮）
  20260904-01/index.html            # openrouter/glm-5.2(free) 测试页
  20260904-02/index.html            # nvidia/kimi-k3 测试页
  20260904-03/index.html            # 千刀/opus-5 测试页
assets/images/pelican/
  20260904-01.svg                   # 对应封面（1200×630）
  20260904-02.svg
  20260904-03.svg
```

### Slug 规范

鹈鹕测试条目用日期 slug：`YYYYMMDD-NN`（同日多篇按序号递增），与博客的
主题 slug 不同，互不干扰。

### 测试条目

| 序号 | 模型 | 风格特点 | 动画技术 |
|---|---|---|---|
| `20260904-01` | openrouter/glm-5.2(free) | 夕阳海边，鹈鹕骑橙色自行车 | 轮子/曲柄/腿 IK 24 步关键帧、嗉囊晃动、围巾飘带、背景视差、阳光脉动；自带 Web Audio 合成配乐 |
| `20260904-02` | nvidia/kimi-k3 | 蓝天白云，白色鹈鹕从右向左横穿画面 | `.rider-group` 横移动画 + 车轮 spin + 腿/翅膀/头独立动画 |
| `20260904-03` | 千刀/opus-5 | 沿海公路，戴安全帽的鹈鹕骑行 | 2-Leg IK 反向运动学解算、齿比 2:1、多层视差卷轴、链条/海鸥/速度线 |

### 模型命名规范（重要）

测试条目的模型名必须包含**供应商前缀**，不能漏掉：

- ✅ `openrouter/glm-5.2(free)`
- ✅ `nvidia/kimi-k3`
- ✅ `千刀/opus-5`
- ❌ `GLM-5.2`（漏掉供应商）
- ❌ `Kimi K3`（漏掉供应商）

供应商前缀出现在三处：图库卡片标题、测试页 `<h1>` 标题、测试页
`<title>`/`og:title` 元数据，以及封面 SVG 的标签胶囊。

### 页面结构

每个测试页是独立的 SVG + CSS 动画页面，无外部依赖（除 GIF 导出用的
gifshot CDN）。结构：

```
<header>  站点导航（GitHub 图标 | 分隔 | 博客 | 分隔 | 鹈鹕测试）
<main>
  .pelican-head          ← 返回链接 + h1 标题 + 副标题
  .pelican-stage
    .pelican-wrap
      .pelican-frame     ← SVG 动画画布（圆角、阴影、overflow:hidden）
      .pelican-bar       ← 按钮栏（GIF 导出 / 配乐）
      .pelican-hint      ← 操作提示
<footer>  站点页脚
<style id="pel-anim-style">  ← 布局样式 + 动画关键帧（GIF 导出时读取此块）
<script>                     ← GIF 导出逻辑
```

**坑提醒**：重写测试页时不要只保留 `<style id="pel-anim-style">` 里的动画
关键帧而漏掉 `.pelican-head` / `.pelican-stage` / `.pelican-frame` /
`.pel-btn` 等布局样式——否则 SVG 和按钮会以浏览器默认样式渲染，格式全乱。
参照 `20260904-01` 的完整 `<style>` 块。

### 封面 SVG 规范

每篇测试配一张 `assets/images/pelican/<slug>.svg` 封面：

- 尺寸 1200×630，与博客封面一致
- 内容是该测试场景的静态快照（非动画截图），取鹈鹕骑车的中心构图
- 标签胶囊：深蓝底（`#00172e`）圆角矩形，白字，写完整模型名（含供应商）
- 鹈鹕身体用白色/暖白渐变填充，**禁止用背景渐变色填充身体**（会导致隐形）

### GIF 导出

每个测试页的「导出 GIF」按钮实现动画帧捕获 → gifshot 合成 → 下载。

- 分辨率 720×435（opus-5 因 viewBox 不同用 675×375）
- 帧率 24fps
- 原理：遍历所有动画元素，用 `animation-delay` 负值定位到每一帧时刻，
  `pause` 后 `requestAnimationFrame` 双次等待渲染，再用
  `ctx.drawImage(svg, 0, 0, W, H)` 把 DOM SVG 直接画到 canvas，
  `toDataURL` 存帧，最后 `gifshot.createGIF` 合成
- 限制：`drawImage(svg)` 能捕获 CSS 动画的当前 transform 状态，但 SMIL
  动画和 `transform-box: fill-box` 的精确原点在某些浏览器下可能不完美

### 导航接入

以下页面的导航栏均已加入「鹈鹕测试」链接：
- `index.html`、`404.html`
- `pelican/index.html` 及子页面（`../` 指向图库）
- 全部 `blog/*/index.html`（`../../pelican/` 指向图库）
- `tools/build_posts.py` 的 `PAGE_TMPL`（新构建的文章自动带上）

### 发布流程

```bash
# 1. 创建 pelican/<slug>/index.html（含站点外壳 + 动画 SVG + GIF 导出）
# 2. 创建 assets/images/pelican/<slug>.svg 封面
# 3. 在 pelican/index.html 的 #pelican-grid 按日期倒序插入卡片
# 4. 提交推送
git add -A
git commit -m "Add <slug> pelican test: <vendor/model>"
git push origin main:master
```

### 已知事项

- 测试页的动画源码来自各模型原始输出，**原样保留，不要手改**（包括模型
  没画完的部分）。需要适配的只是站点外壳：header/footer/布局样式/GIF 按钮。
- `tonghua/` 与 `apple-support/` 是 App 合规页面，**不要动**。
- 远程分支是 `master`，本地是 `main`，推送用 `git push origin main:master`。

## 2026-09-11 · 书籍模块上线（密码解锁在线阅读）

### 背景

私人书架：把两本 AI 主题书籍做成站点内在线阅读器，密码保护。

### 书目

| slug | 书名 | 作者 | 章节 | payload |
|---|---|---|---|---|
| `designing-ai-systems` | 设计 AI 系统 | Suhas Suresha | 15 | 1.3MB |
| `illustrated-ai-agents` | AI 智能体图解 | Maarten Grootendorst | 70 | 5.5MB |

### 加密方案（核心）

- 构建：`tools/build_books.py` 把 EPUB 章节转成 JSON payload，用
  **PBKDF2-SHA256（15 万次迭代）+ AES-GCM** 加密成 `assets/books/<slug>.bin`
  （格式：`salt[16] | iv[12] | tag[16] | ciphertext`）
- 页面：`books/<slug>/` 阅读器用 WebCrypto 同参数派生密钥解密，密码错误
  直接 GCM 校验失败，无绕过路径；仓库里没有密码只有密文
- 密码在构建脚本 `PASSWORD` 常量中（不入库——脚本本身已入库，密码在同一
  文件里；如需轮换：改 `PASSWORD` 重新跑构建即可）
- 解锁状态存 sessionStorage（关标签页后重输）

### 图片处理

EPUB 内 400+ 张插图全部按站规转 AVIF（`assets/images/books/`，共 4MB，
源图约 60MB），阅读器渲染时以 data URI 内联进 payload。

### 目录结构

```
books/
  index.html                        # 书架（两张封面卡 + 锁标签）
  designing-ai-systems/index.html   # 阅读器（noindex）
  illustrated-ai-agents/index.html
assets/books/*.bin                  # 加密 payload
assets/images/books/                # 章节插图 AVIF + 封面 SVG
tools/build_books.py                # 构建脚本（换书/换密码改这里重跑）
```

### 阅读器功能

- 左侧 sticky 章节目录（移动端折叠为单列）、上一章/下一章、进度提示
- 章节样式复用站点排版（Night Owl 代码块、表格横向滚动、引用卡片）

### 换密码 / 换书流程

```bash
# 改 tools/build_books.py 里的 PASSWORD 或 BOOKS 列表，然后：
python3 tools/build_books.py
git add -A && git commit -m "Rebuild books payload" && git push origin main:master
```

### 已知事项

- 阅读器页 `<meta name="robots" content="noindex">`，sitemap 只收书架页
- sessionStorage 解锁是按域存储：解锁一本后，另一本仍需输入密码（各书
  payload 独立加密；如需"解锁一次全站通"，把两本 payload 用同一把派生
  密钥并在 sessionStorage 放密码即可，暂不做）
- `books/` 页面不进博客搜索与首页网格（独立模块，与 blog 并列）

### 2026-09-11 修正：章节顺序错误

初版直接按 EPUB spine 顺序切章，两本书都错了（用户指出）：

- **设计 AI 系统**：MEAP 导出的 spine 物理顺序就是乱的（ch003 是第5章、
  ch008 是第1章），还混有 2KB 的目录概要文件，第5章正文甚至跨 4 个文件。
  → 改为显式文件→章映射（`chapters_dais()`），ch008/ch012/ch016 三个
  大文件按 h2 锚点内部切割，概要文件跳过。第8章 MEAP 尚未写完，如实
  保留概要并标注"MEAP 撰写中"。
- **AI 智能体图解**：nav 损坏但 spine 的 split 文件是正序，初版按文件
  切成 76 段碎粒（h1/h2 混切）。→ 改为按 `<h2><strong>第N章…` 边界
  聚合（`chapters_by_heading()`），兼容"第四章"写法，前言归并。

现在两本分别为 10 章（前言+1-9）和 11 章（前言+1-10），目录序与纸质
版一致。教训：**MEAP/早期版本的 EPUB 不能信任 spine 顺序，先人工核对
章节结构再写切分逻辑。**

### 2026-09-11 内容展示优化（图片 / 代码块 / 图表）

用户指出"代码被压成一段段 [方括号文本]"。排查结论：

1. **两种清单形态**。MEAP 导出里一半清单是正常 `<pre class="sourceCode">`
   （pandoc 高亮 + 行号锚点），另一半被压扁成连续的 `<p>[行文本]</p>` 段落
   （无任何 code 标记）。后者是导出工具的产物，`[ ]` 是行片段标记。
   → `rebuild_flat_listings()`：把"连续 ≥2 段纯 bracket 段落"或"单段但
   含 ≥3 个 bracket 片段且无散文残留"重建成 `figure.code-listing`；
   片段拼接时去掉续行符 `➥`，支持一层嵌套方括号（`policies=["a"]`）。
   散文里的行内 `[code]`（后面带中文正文）不受影响。

2. **清单标题**。`代码清单 N.N` / `清单 N.N` 的加粗段落折叠为代码卡顶部的
   `.listing-cap`（深色标题栏）。压扁清单重建后同样补折叠。

3. **图解书图注**。calibre 排版的图注是 `[<em>图 1-1. …</em>]` —— 带方括号
   包裹且 p 标签已有 class。原 `img_repl2` 只认裸 `图 N`，且 `.replace("<p>…")`
   对带 class 的 p 失效。→ `cap_txt` 允许前导 `[`，`_with_caption_class()`
   合并 class，`_caption_text()` 去掉包裹括号。315 张图全部转为
   `figure.book-figure` + `p.img-caption`。

4. **阅读器 CSS**：`.code-listing` 深色卡（Night Owl 色）、pandoc token
   配色（kw/st/co/op/fl/va…）、`.book-figure` 居中带 hairline 边、
   `.img-caption` 居中弱化、表格与 `colgroup` 清理。

产物：设计 AI 系统 220 个代码清单卡、图解书 315 个图注；两 payload 重建
（1003KB / 5370KB）。散文段落零误伤（全书校验 leftover=0）。

### 2026-09-12 排版专项 review（第二轮 polish）

以排版视角全面审计两本 payload，发现并修复 8 类问题：

1. **pandoc 锚点泄漏**（16 处）：正文/标题里残留 `{#chapter-xxx .calibre20}`
   可见文本 → 全局剥离（含 figure 内部 3 处）。
2. **第三种清单形态**（图解书）：代码被拆成 `<strong class="calibre3">from</strong>
   <strong>import</strong> [LLM][, ][TinyAgent]` 的 strong 词元 + bracket token
   混排。`rebuild_flat_listings()` v2 统一处理三种形态（dais 行段落 / illu
   token 段落 / loose strong 行）；递归解码嵌套 token，`\[` `\]` `\{` `\|`
   是被转义的真实代码括号，孤立 `\` 是被导出器吃掉的下划线
   （`__init__` → `\_​_init\_​_`）。`return`/`self.` 等关键词前自动换行。
3. **行内代码**：散文中 `[platform.data.search()]` 等 2100+ 处括号标识符
   → `<code>`（内含 CJK 的引用/图号另走引用规则，不误伤）。
4. **伪标题**：`<p><strong>2.1.2 …</strong></p>` → 真 `<h3>`（X.Y.Z）/`<h2>`
   （X.Y），共 117+204 个标题层级修正；calibre 加粗小节标题 → h3。
5. **引用标记**：`[[1]]` → `<sup class="cite">1</sup>`（64 处）。
6. **交叉引用**：`[图2-8]`、`[第2章]` 括号剥离。
7. **标注框**：注意/提示框正文（bracket 包裹的 CJK 段落）→
   `<p class="callout">`（103 处）。
8. **杂项**：目录标题「第 9 章.」句点、代码块内弯引号 → 直引号（45 块）、
   打印页眉伪影 `<h2>第6章</h2>`（章中出现）、oreil.ly 短链被
   `<em>` 劈开 + 转义标签垃圾（3 处，重建成正常 `<a>`）。

阅读器 CSS 新增：`.callout` 标注卡、`sup.cite`、行内 `<code>` 徽章、
h4、`text-autospace`（中西文间距）。

最终审计：dais 270 代码卡/1136 行内 code/117 h2；illu 344 代码卡/
194 h3/64 引用/99 callout；anchor 泄漏与 bracket 残留均为 0。

### 2026-09-12 修正：`\[` / `\]` 转义残留（194 处）

用户发现正文和代码里仍有 `[\`、`\]` 垃圾文本。排查出四类根因：

1. **pre 内转义**（dais 161 处）：MEAP 导出在 `<pre>` 里也用了 `\[Span\]`
   `\[\]` 这类转义——且发现一个 353KB 的巨型 pre，其中混着大量
   `<span id="cbN">[...]</span>` 包裹的压扁行。
2. **压扁行在 pre 内**：此前 rebuild 会在 pre 里生成嵌套 figure（HTML
   非法）。新增 `decode_pre_lines()`：pre 内的括号包裹行**原地解码**
   （去 span 壳、还原转义、实体转义后写回），同时 rebuild 拆分 body、
   **豁免 pre/figure 区域**，不再越界处理。
3. **位置性转义**：`\033\[35m`（ANSI，`\[` 前是数字）、`\[<span…`
   （标签前）、`…</span>\]`（标签后）→ 按上下文还原为真实括号；
   ANSI 字符串常量提升为 `<code>` 徽章。
4. **合法的 token 提及**：图解书第6章讲解 Toolformer 的 `\[` `\]` 标记
   token——这是**内容本身**，不能删，转为 `<code>\[</code>` 徽章显示。

另修复：`_block_pieces` 的 rest 计算剔除 `[\\  ]` 换行续接噪音
（此前导致 `Scorer = Callable[[str, dict], bool | float]` 整行漏出）；
`<code>` 内的 `\[`/`\]` 还原；行内 code 处理拆分出既有 code span
防止嵌套污染。

最终审计：两本书 `\[`/`\]` 残留 **0**（保留 10 处合法 token 徽章）。
`list[Span] = []`、`Callable[[str, dict], bool | float]` 等类型注解
全部还原。教训：**导出器的转义规则要按"前字符 + 后字符"上下文区分
语义**——同一个 `\[`， preceded-by-数字 是转义、preceded-by-空格 是内容。
