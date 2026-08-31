# Agent's Photolog — 内容规范

本站是一个纯静态博客（无构建框架）：HTML 手写/脚本生成，一个 CSS 文件，部署在 GitHub Pages。
本文档定义内容发布的规范，**发布新文章前请先读完**。

## 目录结构

```
index.html                      # 首页（博客列表，手动维护卡片网格）
blog/<slug>/index.html          # 每篇文章一个目录
assets/css/style.css            # 全站唯一样式表
assets/images/
  favicon.ico                   # 站点图标（兼作者头像）
  cover-*.svg                   # 首页两张早期文章封面
  posts/<slug>/                 # 每篇文章的图片资源（AVIF + 封面）
tools/build_posts.py            # 文章构建脚本（Markdown → HTML）
CONTENT.md                      # 本文档
```

## 文章发布流程

1. **源稿**：Markdown 文章放在本机 `~/Documents/pi-output/article/`（或任意目录）。
2. **注册**：在 `tools/build_posts.py` 的 `ARTICLES` 列表追加一行：
   `(源文件名, slug, 标题, 日期, 摘要, 标签)`。
3. **构建**：`python3 tools/build_posts.py`，生成 `blog/<slug>/index.html`
   和 `assets/images/posts/<slug>/` 下的全部图片（自动转 AVIF）。
4. **首页**：在 `index.html` 的 `#post-grid` 里加一张卡片（按日期倒序插入），
   卡片结构照抄现有卡片，`data-title` / `data-excerpt` 供搜索过滤用。
5. **提交**：`git add -A && git commit && git push origin main:master`。

## slug 规范

- 全小写英文，短横线分隔，体现主题（如 `float-bits`、`dsh-input-history`）。
- 不用日期前缀；排序由卡片日期决定。

## 图片规范（重要）

本站文章以图文为主，图片是体积大头。**所有位图一律转 AVIF**，这是硬性规范：

| 规则 | 要求 |
|---|---|
| 格式 | 位图/插画 → **AVIF**（`avifenc --min 30 --max 63`）；矢量图形 → SVG |
| 尺寸 | 正文图最长边 ≤ 1200px（构建脚本自动缩放）；封面固定 1200×630 |
| 命名 | `assets/images/posts/<slug>/01.avif`、`02.avif`…（脚本自动编号） |
| 封面 | `<slug>/cover.svg`，1200×630，站点色板（墨蓝 `#00172e` / 靛蓝 `#4f46e5` / 浅蓝 `#eef6fd`），虚线框 + 标签胶囊 + 标题 |
| 引用 | 正文图一律 `<figure><img loading="lazy" alt="…"><figcaption>…</figcaption></figure>`，alt 必填 |
| 体积 | 单张 AVIF 目标 ≤ 30KB（插画类实际 12–20KB）；整篇图片总量控制在 200KB 内 |

禁止直接提交 PNG/JPG 原图。AVIF 浏览器支持已覆盖全部现代浏览器（Chrome/Edge/Firefox/Safari 16+）。

### 为什么是 AVIF

同一张插画，PNG 原稿约 100–200KB，AVIF（质量 30–63 区间）约 12–20KB，
**体积降到 1/8 以下且观感无损失**，对图文为主的站点是最划算的格式。

## 文章页模板

所有文章页共用同一结构（构建脚本已内置），手动写新页面时照抄 `blog/float-bits/index.html`：

- `<title>`/`og:title`：`文章标题 - Agent's Photolog`
- 正文区 `.prose`，最大宽 46rem（`container--narrow`）
- 代码块 Night Owl 配色，`.tok-k/.tok-s/.tok-c/...` 高亮 span
- 页脚社交：GitHub → `chenyuqing`，X → `scottone2`，邮箱 → `motoleisure@gmail.com`，纯图标无文字

## 写作约定

- 语言：中文为主，技术名词保留英文。
- 每篇必有：标题（H1，模板渲染）、导语（2–3 句）、小节 H2。
- 公众号源稿里的 `<!-- 排版说明 -->` 注释构建时自动剔除，无需手动删。
- 引用块（`>`）用于强调卡片，构建后自动带浅蓝底色样式。

## 已知事项

- 文章《two-github-accounts》正文中的 `motoleisure404` 是教程示例内容，非链接，保留原样。
- `tonghua/` 与 `apple-support/` 是 App 合规页面，与博客独立，**不要动**。
- 远程分支是 `master`（历史原因），本地是 `main`，推送用 `git push origin main:master`。
