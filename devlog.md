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

### 2026-09-12 修正：表格被导出器截断成管道文本

表 1.1（原型与生产系统差距）的 `<table>` 只剩前 3 行，其余 5 行被导出器
倾倒进紧随其后的 `<div class="line-block">`（`|` 分隔 + `<br/>` 换行）。
新增 `repair_split_table()`：识别 `</table>` 后紧跟的 line-block，按行
拆分单元格、剔除尾部空列、按表头列数补齐，重新插回前一个表格的
`<tbody>`。全书仅此一处 line-block；修复后表格 3 列 8 行完整渲染。
教训：看到"管道符文本段落"先查它是不是被截断表格的残余，行块紧跟
`</table>` 是判别特征。

### 2026-09-12 排查补遗：第四种清单形态 + 参考文献误伤

全面清扫又发现并修复：

1. **无括号纯文本清单**（第四种形态）：`class DocumentParser(ABC):` 这类
   代码行直接以 `<p>` 段落存在，无括号无 strong 标记。
   `rebuild_plain_listings()`：连续 ≥3 段无 CJK 且含代码标点的段落
   → 合并成代码卡（dais 新增 ~50 张）。
2. **特殊 token 双重转义**：`\&lt;\|think\|\&gt;`（Gemma/Toolformer 的
   `<|think|>` 等）→ 还原为 `<code><|think|></code>` 徽章（15 处）。
3. **代码内 markdown 加粗**：`**提示**`/`**清单 9.15 …**` 在 er/st/op
   span 里的残留 → 剥掉星号（含 span 边界形态）。
4. **`\n`、`__init__`、`_executeaction`** 等转义标识符在散文里的提及
   → `<code>` 徽章。
5. **误伤回修**：参考文献条目（`1 Russell, Stuart…2021.`）被纯文本
   清单规则误当代码 → 加引文签名排除（编号开头 / 含年份且无代码
   标点）；纯 CJK 的括号 run（图题列表）→ 转 callout 而非代码卡。

最终审计（两本书）：锚点/转义括号/➥/`**`/双转义/line-block 全部 0；
dais 264 代码卡、illu 432 代码卡、112 标注框、64 引注。

### 2026-09-12 修正：markdown 围栏代码块（第五种清单形态）

用户报告 ```python 围栏代码以纯文本显示。这是图解书的第五种清单形态：
每行代码一个 p 标签，围栏用弯引号，导出器还把 __init__ 的下划线吃进
空 em 标签对里。

rebuild_fenced_listings()：扫描围栏开行，逐段收集到围栏闭行（允许
单行块，如模型输出、目录树），拼成代码卡；空 em 对还原为下划线对，
弯引号由 straighten 转直，缩进保留。图解书新增约 53 张代码卡。

dais 的 pre 里也有围栏残留（```python 作为代码行，有时还包着高亮
span）→ decode_pre_lines 里一并剔除。

已知残留（源数据结构缺陷，暂不处理）：章节开头的"本章将揭开…"
导读框被导出器拆成 h2+段落跨元素断句，渲染为一个大标题 + 续段，
属书源结构问题非标记垃圾。

### 约定

- 本地预览服务器端口统一用 **8899**（`python3 -m http.server 8899`），
  不再使用 8765。

### 2026-09-13 新书：AI 与教育（MIT 报告）接入书架

来源：https://aiandeducation.mit.edu/report/ （MIT 教学与研究训练中
AI 使用特设委员会报告，2026-08-13）。流程：

1. curl 抓取页面 → 提取 entry-content、链接绝对化 → calibre 转 EPUB
   （convert.py 只收 pdf/docx/epub，网页需先过 calibre）。
2. translate-book 技能管线：46 chunks、20 条术语表（MIT 保留、特设
   委员会、生成式 AI、人名音译、p-set=问题集、UROP/住校教育等）、
   子代理按 3 个/批翻译（并发上限实际约 3，超限报 captcha/
   concurrency 错误，等待后重试即可）、每批 record + merge meta。
3. merge_and_build 产出 book.epub（输出四格式），EPUB 结构干净：
   spine 直接可用（strategy="spine"，新策略：spine 顺序 + 跳过
   <1500 字符无图标题残片）。
4. 书架接入：BOOKS 第三条目 + 新封面 SVG + 阅读器页
   （books/ai-education-report/，从图解书复制替换书字段）+ 书架
   第三张卡。payload 101KB，4 章，同一密码体系。

教训：translate-book 的 meta 校验很严——used_term_sources 必须是
字符串数组、new_entities 必须有 source，占位空对象会被隔离；
decode_pre_lines 会误伤参考文件里含 [] 的行，注意区分。

### 2026-09-13 书架扩充：李博杰两本 PDF 书 + 分类重组

新增《深入理解 AI Agent》《深入理解 AI Infra》（李博杰，LaTeX/ElegantBook
PDF）。PDF 无法直接进 convert 管线，走 calibre：

- ebook-convert PDF → EPUB（--enable-heuristics），spine 按页碎片化
  （78/65 个分片），但 PDF 书签完整保留在 toc.ncx。
- 新策略 **pdf-toc**：解析 ncx 顶层书签（第 N 章/前言/后记），用
  calibre 页码锚点 id="page_NN" 在拼接正文流上定位切章；引言章里的
  印刷目录在 `>目录<` 处截断。注意切点要取锚点**标签闭合之后**，
  否则标签残余会变成可见文本。
- 数学公式密集，关闭 plain-listings 规则（plain_listings: False），
  避免公式段被误判为代码卡；代码以段落形式呈现。

书架按类别重组为三组：**智能体开发**（深入理解 AI Agent、AI 智能体
图解）、**系统与基础设施**（深入理解 AI Infra、设计 AI 系统）、
**报告与政策**（AI 与教育）。书架页用 .cat-title 分组标题。

payload：ai-agents-in-depth 2258KB/12 章；ai-infra-book 3667KB/13 章。
已知限制：TikZ 矢量图在 PDF→EPUB 中退化为散落文字，公式/图表阅读
体验不如原 PDF；正文段落完好。

### 2026-09-13 书架改版：小封面 + 小象吉祥物（illo 方案 A）

用户反馈封面太大。用 illo 技能（xiaoxiang 小象角色包 + storybook-plush
风格，站点配色映射）生成三张设计图纸供审核，用户选定方案 A
（象管理员上架：小封面书架排 + 大封面缩小箭头叙事）。

实现：
- 书卡从大竖图改为**横向布局**：封面 74×111px 在左，信息在右；
  分类分组保留（智能体开发 / 系统与基础设施 / 报告与政策）。
- 从方案 A 裁出小象管理员（stool + 大书道具）作为书架页头吉祥物
  （shelf-mascot，120px 宽圆角卡）。
- 生成管线注意：illo 输出路径要写真实仓库路径；本次误写到
  /Users/tim/my-sys/motoleisure.github.io（mkdir -p 建出的杂散目录，
  已清理归位）。落选方案 B/C 移至 ~/my-sys/shelf-design-review/。

设计资产：assets/images/shelf-design/{design-A-librarian.png（设计底稿）,
xiaoxiang-librarian.png（页面吉祥物）}。

### 2026-09-13 返工：书架布局回滚重做 + 密码策略调整

小象方案上线后被否（页头断裂、全宽横卡无书架感，"比之前还烂"）。
用 headless Chrome 截图自检后推倒重做：

- 移除小象吉祥物（用户明确不要）及相关 CSS/资产；
- 书卡恢复竖版（封面在上、信息在下），但网格改为
  repeat(auto-fill, minmax(200px,1fr))、封面比例 2/3、简介 3 行
  截断——比初版封面小约 45%，且保持书卡密度与观感；
- **密码策略**：仅《AI 智能体图解》《设计 AI 系统》保留密码。
  build_books 增加 protected 标志，未保护书直接输出明文 JSON
  payload；三个阅读器页移除锁屏/解密逻辑，改为 fetch+JSON 直读，
  书架卡片标签区分 🔒 密码解锁 / 📖 免费阅读。
- 教训：**改版必须先 headless 截图自检再交付**，上一版就是没看
  就发；同时避免用多层小补丁叠改 CSS，必要时整段重写。

### 2026-09-13 修正：李博杰两本书的图与代码块（换官方源）

用户指出两本书的图和代码块都不对。根因：PDF→calibre EPUB 这条路
天然保不住结构——TikZ 图退化为散落文字、代码行丢失换行并与中文
解释混排、还有转义的假 &lt;code&gt; 标签。

根治 = 换官方源（两本都是开源书，Apache 2.0）：

1. **深入理解 AI Agent**：bojieli/ai-agent-book Releases 有官方
   zh-CN EPUB（pandoc 生成，每章一个文件、58 个代码块、114 张图）。
   → 直接换源 + spine 策略重建。
2. **深入理解 AI Infra**：bojieli/ai-infra-book 仓库 manuscripts/
   有全部 13 章 markdown + chNN/ 配图（SVG）。→ 浅克隆 + pandoc
   3.11 自建 EPUB（--epub-chapter-level=1），477 张 SVG 图入册。

两个管线 bug 顺带修掉：

- **inline_images 路径解析**：pandoc EPUB 的媒体引用是相对章节目录
  （text/../media/file9.svg），原实现按 OPF 根解析，normpath 把
  EPUB/../ 爬出去导致 KeyError、图片引用原样残留（图全裂）。
  → 按"章节目录解析 + 挂 OPF 根"双候选解析。
- **图片外置模式**：477 张 SVG 若内联 data URI，payload 会到 32MB。
  新增 external_images 标志：图片写成站点文件，payload 存相对引用
  （同源加载 + 浏览器缓存），payload 回落到 1.2MB/2.6MB。

验证（headless 截图，注意 --virtual-time-budget 会把图片加载掐早、
产生假裂图，去掉该参数重截才作数）：图 1-1/1-2/2-1 彩色 SVG 图
完整渲染，代码块带语法高亮，正文排版正常。

payload：agents 2470KB/12 章/58 代码块/114 图；infra 2626KB/
13 章/477 图。附带收益：设计 AI 系统的图片此前也因路径问题静默
裂着，本次一并修复（payload 971→1763KB）。
