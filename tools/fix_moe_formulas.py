#!/usr/bin/env python3
"""Fix shattered math formulas in the MoE handbook translated markdown.

The calibre PDF→HTMLZ conversion shattered multi-line formulas into
disconnected bracket fragments. This script reconstructs them as proper
LaTeX ($$...$$ and $...$), strips running headers and diagram brackets,
splits into chapters, and rebuilds the payload JSON.
"""
import json
import os
import re
import sys

import markdown as md

TEMP_DIR = "/Users/tim/my-sys/Understanding_Mixture_of_Experts_Handbook_07_temp"
OUTPUT_MD = os.path.join(TEMP_DIR, "output.md")
PAYLOAD_OUT = "/Volumes/JD5-1TB/tim/my-sys/motoleisure.github.io/assets/books/moe-handbook.bin"

# ── multi-line formula replacements (exact string match on the broken text) ──

MULTILINE_FORMULAS = [
    # MoE summation: [*N*] / formula / [*i*] [*i*] / [*i*][=1]
    (
        "[*N*]\n\nMoE( X *x* ) = *G* (*x*)*E* (*x*) *.*\n\n[*i*] [*i*]\n\n[*i*][=1]",
        "$$\\text{MoE}(x) = \\sum_{i=1}^{N} G_i(x)\\, E_i(x)$$",
    ),
    # Top-k output (chunk 2): *y* X = *g* ˜ ... / [*i*] [*i*] / [*i*][∈S]...
    (
        "*y* X = *g* ˜ (*x*)*E* (*x*)*.*\n\n[*i*] [*i*]\n\n[*i*][∈S][(][*x*][)]",
        "$$y = \\sum_{i \\in S(x)} \\tilde{g}_i(x)\\, E_i(x)$$",
    ),
    # Softmax (chunk 2): *p*[*i*](*x*) = ... / [*j*][=1]
    (
        "*p*[*i*](*x*) = *.* P [*N*] [*h*] *e e*[*h*][*i*] [*j*]\n\n[*j*][=1]",
        "$$p_i(x) = \\frac{e^{h_i}}{\\sum_{j=1}^{N} e^{h_j}}$$",
    ),
    # Top-k output (chunk 2, second): *y* X = *p* ˜ ...
    (
        "*y* X = *p* ˜ (*x*)*E* (*x*)*.*\n\n[*i*] [*i*]\n\n[*i*] [∈S][(][*x*][)]",
        "$$y = \\sum_{i \\in S(x)} \\tilde{p}_i(x)\\, E_i(x)$$",
    ),
    # Switch aux loss (chunk 6): *L* X = *αN f P* / [*aux] [*i*] [*i*] / [*i*][=1]
    (
        "*L* X = *αN f P* ,\n[*aux] [*i*] [*i*]\n\n[*i*][=1]",
        "$$L_{\\text{aux}} = \\alpha N \\sum_{i=1}^{N} f_i P_i$$",
    ),
    # Importance loss (chunk 6): *L* [2] = *w* CV(Importance( *X* ))*.*
    (
        "*L* [2] = *w* CV(Importance( *X* ))*.*\n[importance] [importance]",
        "$$L_{\\text{importance}} = w \\cdot \\text{CV}(\\text{Importance}(X))^2$$",
    ),
]

# ── inline formula replacements ──

INLINE_FORMULAS = [
    # FFN
    ("FFN(*x*) = *W*[2] *ϕ*(*W*[1]*x*)*,*",
     "$$\\text{FFN}(x) = W_2 \\, \\phi(W_1 x)$$"),
    # Expert list
    ("*E*[1](*x*)*, E*[2](*x*)*, . . . , E*[*N*] (*x*)*.*",
     "$$E_1(x),\\ E_2(x),\\ \\ldots,\\ E_N(x)$$"),
    # Support set
    ("S(*x*) = {*i* : *G*[*i*](*x*) ̸= 0}",
     "$$S(x) = \\{i : G_i(x) \\neq 0\\}$$"),
    # h' attention
    ("*h* [′] = *h* + Attention(Norm(*h*))*,*",
     "$$h' = h + \\text{Attention}(\\text{Norm}(h))$$"),
    # h'' FFN
    ("*h* [′′] [′] [′] = *h* + FFN(Norm( *h*))*.*",
     "$$h'' = h + \\text{FFN}(\\text{Norm}(h))$$"),
    # h'' MoE
    ("*h* [′′] [′] [′] = *h* + MoE(Norm( *h* ))*.*",
     "$$h'' = h + \\text{MoE}(\\text{Norm}(h))$$"),
    # Router matrix W
    ("*W* [*d*][×][*N*] [*r*] R ∈ *.*",
     "$$W \\in \\mathbb{R}^{d \\times N \\times r}$$"),
    # Router logit h
    ("*h* [*N*] = *xW* [*r*] R ∈ *.*",
     "$$h = xW, \\quad h \\in \\mathbb{R}^{N \\times r}$$"),
    # h vector
    ("*h* = \\[2*.*0*,* 1*.*2*,* 0*.*1*,* −0*.*4\\]*.*",
     "$$h = [2.0,\\ 1.2,\\ 0.1,\\ -0.4]$$"),
    # p vector
    ("*p* ≈ \\[0*.*5919*,* 0*.*2659*,* 0*.*0885*,* 0*.*0537\\]*.*",
     "$$p \\approx [0.5919,\\ 0.2659,\\ 0.0885,\\ 0.0537]$$"),
    # p1
    ("*p* ˜[1] = ≈ 0*.*6900*,*",
     "$$\\tilde{p}_1 \\approx 0.6900$$"),
    # p2
    ("*p* ˜[2] = ≈ 0*.*3100*.*",
     "$$\\tilde{p}_2 \\approx 0.3100$$"),
    # G(x)
    ("*G*(*x*) ≈ \\[0*.*6900*,* 0*.*3100*,* 0*,* 0\\]*.*",
     "$$G(x) \\approx [0.6900,\\ 0.3100,\\ 0,\\ 0]$$"),
    # y
    ("*y* = 0*.*6900*E*[1](*x*) + 0*.*3100*E*[2](*x*)*,*",
     "$$y = 0.6900 \\cdot E_1(x) + 0.3100 \\cdot E_2(x)$$"),
    ("*y* ≈ \\[1*.*3100*,* 0*.*1201\\]*.*",
     "$$y \\approx [1.3100,\\ 0.1201]$$"),
    # E vectors
    ("*E*[1](*x*) = \\[1*.*0*,* −0*.*5\\]*,* *E*[2](*x*) = \\[2*.*0*,* 1*.*5\\]*.*",
     "$$E_1(x) = [1.0,\\ -0.5], \\quad E_2(x) = [2.0,\\ 1.5]$$"),
    # R matrix
    ("*R* [*T*] [×][*N*] ∈ { 0 *,* 1 } *,*",
     "$$R \\in \\{0, 1\\}^{T \\times N}$$"),
    # Shazeer noisy gate
    ("*H*[*i*](*x*) = (*xW*[*g*])[*i*] + *ϵ*[*i*] Softplus((*xW*[*noise*])[*i*])*,*",
     "$$H_i(x) = (xW_g)_i + \\epsilon_i\\, \\text{Softplus}((xW_{\\text{noise}})_i)$$"),
    # KeepTopK
    ("*G*(*x*) = Softmax(KeepTopK(*H* (*x*)*, k*))*.*",
     "$$G(x) = \\text{Softmax}(\\text{KeepTopK}(H(x),\\ k))$$"),
    # Switch routing
    ("*y* = *p* [∗] [∗] [*i*] ( *x* ) *E* [∗] [*i*] ( *x* ) *, i* = arg max *p*[*i*](*x*)*.*",
     "$$y = p_{i^*}(x)\\, E_{i^*}(x), \\quad i^* = \\arg\\max\\, p_i(x)$$"),
    # TopK
    ("S(*x*) = TopK(*p*(*x*)*, k*)*.*",
     "$$S(x) = \\text{TopK}(p(x),\\ k)$$"),
    # f_i (Switch)
    ("*f* [*i*] = **1**{arg max *p*(*x*) = *i*}\n*T*\n[*x*][∈][*B*]\n1 X",
     "$$f_i = \\frac{1}{T} \\sum_{x \\in B} \\mathbf{1}\\{\\arg\\max\\, p(x) = i\\}$$"),
    # P_i (Switch)
    ("*P*[*i*] = *p*[*i*](*x*)\n*T* [*x*][∈][*B*]\n1 X",
     "$$P_i = \\frac{1}{T} \\sum_{x \\in B} p_i(x)$$"),
    # DeepSeek bias
    ("*s*[*i,t*] + *b*[*i*]*,*",
     "$$s_{i,t} + b_i$$"),
    # Toy FFN dense
    ("2 × 1024 × 4096 = 8*,*388*,*608",
     "$$2 \\times 1024 \\times 4096 = 8{,}388{,}608$$"),
    ("2 × 1024 × 2048 = 4*,*194*,*304",
     "$$2 \\times 1024 \\times 2048 = 4{,}194{,}304$$"),
    ("8 × 4*,*194*,*304 = 33*,*554*,*432",
     "$$8 \\times 4{,}194{,}304 = 33{,}554{,}432$$"),
    ("2 × 4*,*194*,*304 = 8*,*388*,*608",
     "$$2 \\times 4{,}194{,}304 = 8{,}388{,}608$$"),
    # Uniform case
    ("*N* X *f P* = 1*.*00*.*\n[*i*] [*i*]",
     "$$N \\sum_i f_i P_i = 1.00$$"),
    ("*N* X *f P* = 4(0*.*20 + 0*.*075 + 0*.*05) = 1*.*30*.*\n[*i*] [*i*]",
     "$$N \\sum_i f_i P_i = 4(0.20 + 0.075 + 0.05) = 1.30$$"),
    # For perfectly uniform
    ("For perfectly uniform *f* = *P* = \\[0*.*25*,* 0*.*25*,* 0*.*25*,* 0*.*25\\],",
     "For perfectly uniform $f = P = [0.25, 0.25, 0.25, 0.25]$,"),
    # Assignment matrix
    ("*R* [*t,i*] = 1",
     "$R_{t,i} = 1$"),
    # Column sums
    ("\\[3*,* 2*,* 2*,* 1\\]*.*",
     "$[3, 2, 2, 1]$"),
]


def fix_formulas(text):
    """Apply all formula replacements."""
    for old, new in MULTILINE_FORMULAS:
        if old in text:
            text = text.replace(old, new)
        else:
            # try with slight whitespace variations
            old_compact = re.sub(r'\n\n+', '\n', old)
            if old_compact in text:
                text = text.replace(old_compact, new)

    for old, new in INLINE_FORMULAS:
        if old in text:
            text = text.replace(old, new)
        # don't warn on missing — some formulas may not appear in translated text

    return text


def strip_running_headers(text):
    """Remove [理解混合专家] [\\@techNmak] [N] running header lines."""
    hdr = r'\[理解混合专家\]\s*\[\\@techNmak\]\s*\[\d+\]\s*'
    # running header + **bold** title → ## title
    text = re.sub(r'^' + hdr + r'\*\*(.+?)\*\*\s*$', r'## \1', text, flags=re.M)
    # running header + plain title → ## title
    text = re.sub(r'^' + hdr + r'(.+?)\s*$', r'## \1', text, flags=re.M)
    # ## heading with running header prefix → clean ## heading
    text = re.sub(r'^##\s*' + hdr + r'(.+)$', r'## \1', text, flags=re.M)
    # standalone running header line (no title)
    text = re.sub(r'^' + hdr + r'$', '', text, flags=re.M)
    # standalone research anchors
    text = re.sub(r'^\[研究锚点[：:].*\]', '', text, flags=re.M)
    # standalone page numbers
    text = re.sub(r'^\[\d+\]\s*$', '', text, flags=re.M)
    return text


def _is_formula_fragment(s):
    """True if a bracket line is a formula fragment, not a diagram element."""
    # Formula fragments: [*i*] [*i*], [*i*][=1], [aux] [*i*] [*i*],
    # [*i*][∈S][(][*x*][)], [*N*], [importance] [importance], etc.
    if re.match(r'^\[\*?\w\*?\]\s*\[?\*?\w\*?\]?\s*$', s):
        return True
    if re.match(r'^\[\*?\w\*?\]\[=\d+\]$', s):
        return True
    if re.match(r'^\[\*?\w\*?\]\[∈S\]', s):
        return True
    if 'aux' in s and '辅助' not in s:
        return True
    if 'importance' in s:
        return True
    # [*N*] alone (superscript limit)
    if re.match(r'^\[\*N\*\]$', s):
        return True
    # [*i*] [*i*] (subscripts)
    if re.match(r'^\[\*i\*\]\s*\[\*i\*\]$', s):
        return True
    return False


def _clean_diagram_line(s):
    """Strip brackets and italic markers from a diagram line for cleaner display."""
    # [*E*][1] → E₁, [*x*] → x, [路由器] → 路由器
    s = re.sub(r'\[\*?(\w)\*?\]\[(\d+)\]', lambda m: m.group(1) + m.group(2), s)
    s = re.sub(r'\[\*(\w)\*\]', r'\1', s)  # [*x*] → x
    s = re.sub(r'\[([^\]]*)\]', r'\1', s)   # [text] → text
    return s.strip()


def preserve_diagrams(text):
    """Wrap runs of [bracket] diagram lines in ``` code blocks.

    The calibre conversion turned PDF diagrams into bracket text.
    Instead of destroying them, preserve as monospace ASCII art.
    Formula fragments (subscripts, summation limits) are excluded.
    """
    lines = text.split('\n')
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()
        # Check if this line is a diagram element
        is_diagram = (
            stripped.startswith('[')
            and '$' not in stripped
            and not stripped.startswith('## ')
            and '理解混合专家' not in stripped
            and '研究锚点' not in stripped
            and '\\@techNmak' not in stripped
            and not _is_formula_fragment(stripped)
        )
        if is_diagram:
            # Start a code block
            out.append('```text')
            out.append(_clean_diagram_line(stripped))
            i += 1
            # Collect following blank lines and bracket lines
            while i < len(lines):
                next_stripped = lines[i].strip()
                if next_stripped == '':
                    i += 1
                    continue
                elif (next_stripped.startswith('[')
                      and '$' not in next_stripped
                      and '理解混合专家' not in next_stripped
                      and '研究锚点' not in next_stripped
                      and not _is_formula_fragment(next_stripped)):
                    out.append(_clean_diagram_line(next_stripped))
                    i += 1
                else:
                    break
            out.append('```')
            out.append('')
            continue
        # Also remove standalone formula fragment lines
        if _is_formula_fragment(stripped):
            i += 1
            continue
        out.append(ln)
        i += 1
    return '\n'.join(out)


def fix_timeline_table(text):
    """Convert the plain-text timeline table to a markdown table."""
    # Pattern: 年份 工作 持久的理念 followed by data rows
    if '年份 工作 持久的理念' in text:
        text = text.replace(
            '年份 工作 持久的理念\n\n1991 Jacobs 等人 跨局部专家的学习门控\n\n2017 Shazeer 等人 稀疏 Top-*k* 条件计算 2020 GShard 超大规模分布式 Transformer MoE\n\n2022 Switch Top-1 路由与简化的稀疏执行\n\n2024+ 现代 LLM MoE 新的专家粒度、负载均衡和服务设计',
            '| 年份 | 工作 | 持久的理念 |\n|------|------|------------|\n| 1991 | Jacobs 等人 | 跨局部专家的学习门控 |\n| 2017 | Shazeer 等人 | 稀疏 Top-*k* 条件计算 |\n| 2020 | GShard | 超大规模分布式 Transformer MoE |\n| 2022 | Switch | Top-1 路由与简化的稀疏执行 |\n| 2024+ | 现代 LLM MoE | 新的专家粒度、负载均衡和服务设计 |'
        )
    return text


def fix_matrix(text):
    """Fix the broken assignment matrix rendering."""
    # The matrix is broken across lines with bracket chars
    text = text.replace(
        " \n\n1 1 0 0\n\n  1 0 1 0\n\n*R*   = *.*     0 1 1 0  \n\n1 0 0 1",
        "```text\nR = ⎡1 1 0 0⎤\n    ⎢1 0 1 0⎥\n    ⎢0 1 1 0⎥\n    ⎣1 0 0 1⎦\n```"
    )
    return text


def fix_h_primes(text):
    """Fix h-prime notation: *h* [′] and *h* [′′] [′] [′]."""
    text = text.replace(
        "*h* [′] = *h* + Attention(Norm(*h*))*,*",
        "$$h' = h + \\text{Attention}(\\text{Norm}(h))$$"
    )
    text = text.replace(
        "*h* [′′] [′] [′] = *h* + FFN(Norm( *h*))*.*",
        "$$h'' = h + \\text{FFN}(\\text{Norm}(h))$$"
    )
    text = text.replace(
        "*h* [′′] [′] [′] = *h* + MoE(Norm( *h* ))*.*",
        "$$h'' = h + \\text{MoE}(\\text{Norm}(h))$$"
    )
    return text


def clean_inline_subscripts(text):
    """Convert *X*[*i*] inline subscript patterns to $X_i$ in non-display context."""
    # *E*[*i*](*x*) → $E_i(x)$ (but not inside $$...$$)
    def sub_repl(m):
        var = m.group(1)
        idx = m.group(2)
        rest = m.group(3)
        return f'${var}_{{{idx}}}({rest})$'

    # Be conservative — only convert clean patterns not already in $$
    # *E*[*i*](*x*) pattern
    text = re.sub(r'\*E\*\[\*i\*\]\(\*x\*\)', r'$E_i(x)$', text)
    text = re.sub(r'\*G\*\[\*i\*\]\(\*x\*\)', r'$G_i(x)$', text)
    text = re.sub(r'\*E\*\[\*j\*\]\(\*x\*\)', r'$E_j(x)$', text)
    text = re.sub(r'\*G\*\[\*j\*\]\(\*x\*\)', r'$G_j(x)$', text)
    # *W*[2] → $W_2$ etc
    text = re.sub(r'\*W\*\[\*?(\d+)\*?\]', r'$W_{\1}$', text)
    text = re.sub(r'\*p\*\[\*i\*\]\(\*x\*\)', r'$p_i(x)$', text)
    text = re.sub(r'\*H\*\[\*i\*\]\(\*x\*\)', r'$H_i(x)$', text)
    text = re.sub(r'\*f\*\s*\[\*i\*\]', r'$f_i$', text)
    text = re.sub(r'\*P\*\[\*i\*\]', r'$P_i$', text)
    text = re.sub(r'\*R\*\s*\[\*t*,\s*i\*\]', r'$R_{t,i}$', text)
    # *d*[model] → $d_{\text{model}}$
    text = re.sub(r'\*d\*\[model\]', r'$d_{\\text{model}}$', text)
    text = re.sub(r'\*d\*\[\*?model\*?\]', r'$d_{\\text{model}}$', text)
    text = re.sub(r'\*d\*\[ff\]', r'$d_{\\text{ff}}$', text)
    text = re.sub(r'\*d\*\[\*?ff\*?\]', r'$d_{\\text{ff}}$', text)
    # *b* batch size
    text = re.sub(r'批大小为 \*b\*', r'批大小为 $b$', text)
    # *N* experts
    text = re.sub(r'\*N\* 个专家', r'$N$ 个专家', text)
    text = re.sub(r'\*k\* 个', r'$k$ 个', text)
    text = re.sub(r'\*k\* ≪ \*N\*', r'$k \\ll N$', text)
    text = re.sub(r'\*T\* 个 token', r'$T$ 个 token', text)
    return text


def split_chapters(text):
    """Split markdown into chapters by ## headings."""
    chapters = []
    current_title = None
    current_body = []

    for ln in text.split('\n'):
        if ln.startswith('## ') and not ln.startswith('### '):
            if current_title is not None:
                chapters.append((current_title, '\n'.join(current_body).strip()))
            current_title = ln[3:].strip()
            current_body = []
        elif ln.startswith('# '):
            # main title — skip (it's in the reader header)
            continue
        else:
            if current_title is not None:
                current_body.append(ln)
            else:
                current_body.append(ln)

    if current_title is not None:
        chapters.append((current_title, '\n'.join(current_body).strip()))

    return chapters


def fix_html_formulas(html):
    """Post-process HTML to fix formula fragments that survived markdown conversion.

    The calibre conversion shattered multi-line formulas into separate <p> tags
    and scattered bracket fragments. This reconstructs them into LaTeX.
    """
    # 1. Tilde + variable: ˜ <em>p</em> → $\tilde{p}$
    html = re.sub(r'˜\s*<em>(\w)</em>', lambda m: r'$\tilde{' + m.group(1) + r'}$', html)
    # <em>p</em> ˜ → $\tilde{p}$
    html = re.sub(r'<em>(\w)</em>\s*˜', lambda m: r'$\tilde{' + m.group(1) + r'}$', html)

    # 2. Broken summation fragments in <p> tags:
    sum_pattern = re.compile(
        r'<p><em>y</em>\s*X\s*=\s*'
        r'(?:<em>g</em>|<em>p</em>|\$\\tilde\{[gp]\}\$)\s*'
        r'\(?\s*<em>x</em>\s*\)?\s*'
        r'<em>E</em>\s*\(\s*<em>x</em>\s*\)\s*'
        r'<em>\.</em>\s*</p>'
        r'(?:\s*<p>.*?</p>\s*){0,4}',
        re.S)
    html = sum_pattern.sub(
        lambda m: r'$$y = \sum_{i \in S(x)} \tilde{p}_i(x)\, E_i(x)$$', html)

    # 3. <em>p</em> ˜[1] = ≈ 0*.*6900 → $$\tilde{p}_1 \approx 0.6900$$
    html = re.sub(
        r'<em>p</em>\s*˜?\s*\[?(\d+)\]?\s*=\s*≈\s*0\*\.\*(\d+)',
        lambda m: r'$$\tilde{p}_' + m.group(1) + r' \approx 0.' + m.group(2) + r'$$',
        html)
    html = re.sub(
        r'\$\\tilde\{p\}\$\[?(\d+)\]?\s*≈\s*0\*\.\*(\d+)',
        lambda m: r'$$\tilde{p}_' + m.group(1) + r' \approx 0.' + m.group(2) + r'$$',
        html)
    html = re.sub(
        r'\$\\tilde\{p\}\$\s*\[?1\]?\s*≈\s*0\*\.\*6900\*?,?\s*\*?\s*\$\\tilde\{p\}\$\s*\[?2\]?\s*≈\s*0\*\.\*3100\*',
        lambda m: r'$$\tilde{p}_1 \approx 0.6900, \quad \tilde{p}_2 \approx 0.3100$$',
        html)

    # 4. Fix S(x) braces
    html = html.replace('$$S(x) = {i :', '$$S(x) = \\{i :')
    html = html.replace('G_i(x) \\neq 0}$$', 'G_i(x) \\neq 0\\}$$')
    html = html.replace('G_i(x) \neq 0}$$', 'G_i(x) \\neq 0\\}$$')

    # 5. Remove leftover bracket-fragment <p> tags
    html = re.sub(r'<p><strong><em>\w</em>\][^<]*</strong>\*?</p>', '', html)
    html = re.sub(r'<p>\[<em>\w</em>\]\[.*?\]\[.*?\]</p>', '', html)
    html = re.sub(r'<p>\[<em>\w</em>\]\[∈S\]\[\(\]\[<em>x</em>\]\[\)\]</p>', '', html)
    html = re.sub(r'<p>\[\d+\.\d+\]</p>', '', html)
    html = re.sub(r'<p>\[<em>\w</em>\]\[\d+\]\[\(\]\[<em>x</em>\]\[\)\]</p>', '', html)

    # 6. Fix leftover "X =" (mangled Σ)
    html = re.sub(r'<em>y</em>\s+X\s*=\s*', r'$y = $', html)
    html = re.sub(r'<em>N</em>\s+X\s*=\s*', r'$N = $', html)

    # 7. Fix inline subscript patterns that survived markdown
    html = re.sub(r'<em>E</em>\[(\d+)\]\(\*x\*\)', lambda m: r'$E_{' + m.group(1) + r'}(x)$', html)
    html = re.sub(r'<em>E</em>\[<em>(\d+)</em>\]\(\*x\*\)', lambda m: r'$E_{' + m.group(1) + r'}(x)$', html)
    html = re.sub(r'<em>G</em>\[<em>i</em>\]\(\*x\*\)', r'$G_i(x)$', html)
    html = re.sub(r'<em>E</em>\[<em>i</em>\]\(\*x\*\)', r'$E_i(x)$', html)

    # 8. Clean up italic periods
    html = re.sub(r'<em>\.</em>', '.', html)

    # 9. Remove empty <p></p>
    html = re.sub(r'<p>\s*</p>', '', html)

    # 10. Remove <pre> blocks that only contain formula fragments (not real diagrams)
    def clean_pre(m):
        content = m.group(1)
        # If the <pre> block contains formula fragments, remove it entirely
        if re.search(r'\[\*i\*\]|\[\*N\*\]\s*$|\[aux\]|\[∈S\]|\[importance\]', content):
            return ''
        return m.group(0)
    html = re.sub(r'<pre><code[^>]*>(.*?)</code></pre>', clean_pre, html, flags=re.S)

    # 11. Remove any remaining standalone bracket-fragment <p> tags
    html = re.sub(r'<p>\[\*?\w\*?\]\s*\[\*?\w\*?\]</p>', '', html)
    html = re.sub(r'<p>\[\*?\w\*?\]\[.*?\]</p>', '', html)

    return html


def main():
    text = open(OUTPUT_MD, encoding='utf-8').read()

    # 1. Fix formulas
    text = fix_formulas(text)
    text = fix_h_primes(text)
    print(f"  formulas fixed")

    # 2. Strip running headers
    text = strip_running_headers(text)
    print(f"  running headers stripped")

    # 3. Preserve diagrams as code blocks
    text = preserve_diagrams(text)
    print(f"  diagrams preserved")

    # 4. Fix tables and matrices
    text = fix_timeline_table(text)
    text = fix_matrix(text)
    print(f"  tables/matrices fixed")

    # 5. Clean inline subscripts
    text = clean_inline_subscripts(text)
    print(f"  inline subscripts converted")

    # 5. Clean up excess blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r'^\s*$', '', text, flags=re.M)

    # 6. Split into chapters
    chapters = split_chapters(text)
    print(f"  chapters: {len(chapters)}")

    # 7. Convert each chapter to HTML
    payload_chapters = []
    for title, body in chapters:
        if len(body) < 400 and '$' not in body:
            continue
        # Clean title: strip ## prefix, running header remnants
        title = title.lstrip('#').strip()
        title = re.sub(r'\[理解混合专家\]\s*\[\\@techNmak\]\s*\[\d+\]\s*', '', title)
        title = re.sub(r'\s+', ' ', title)[:80]

        # Convert markdown to HTML
        html = md.markdown(body, extensions=['tables', 'fenced_code', 'sane_lists'])

        # Post-process HTML to fix remaining broken formula fragments
        html = fix_html_formulas(html)

        # Wrap tables
        html = html.replace('<table>', '<div class="table-wrap"><table>')
        html = html.replace('</table>', '</table></div>')

        payload_chapters.append({
            "id": f"ch{len(payload_chapters)+1:03d}",
            "title": title or f"第{len(payload_chapters)+1}节",
            "html": html,
        })

    # 8. Build payload
    payload = {
        "slug": "moe-handbook",
        "title": "理解混合专家",
        "author": "@techNmak",
        "chapters": payload_chapters,
    }

    blob = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    with open(PAYLOAD_OUT, 'wb') as f:
        f.write(blob)
    print(f"  payload: {len(blob)//1024}KB, {len(payload_chapters)} chapters → {PAYLOAD_OUT}")

    # Print chapter titles for verification
    for i, ch in enumerate(payload_chapters):
        print(f"    ch{i+1}: {ch['title'][:60]} ({len(ch['html'])} bytes)")


if __name__ == '__main__':
    main()
