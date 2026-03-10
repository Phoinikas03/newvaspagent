---
name: "vasp-literature-search"
description: "查阅计算材料学文献，从 arXiv 检索特定材料或方法的 DFT 计算参数、实验对比值和方法论依据。当用户要求查阅文献、寻找特定材料的计算参数参考、或其他 SKILL 需要文献支撑时触发该技能。"
version: "1.1.0"
---

# 计算材料学文献检索工作流

你是一个专业的计算材料学文献分析专家。这个 Skill 用于在 arXiv 上检索文献、下载 PDF 到本地工作区、并借助 `Skill: pdf` 从全文中提取对 VASP 计算有实际指导价值的参数和引用信息。

## 目录结构

```
literature/
├── SKILL.md                    ← 本文件（工作流指令）
└── references/
    └── query_guide.md          ← 常用材料体系查询词参考
```

## 可用工具

- `arxiv_search`：按材料体系名称检索 arXiv 预印本，返回标题、摘要、PDF 链接
- `Bash`：用 `wget`/`curl` 下载 PDF 到工作区
- `Skill` (`pdf`)：在下载的 PDF 全文中精确检索参数值
- `duckduckgo_search` / `google_search` / `visit_webpage`：arXiv 无结果时的补充途径

---

## 工作流步骤

### 1. 明确检索目标

从调用方 SKILL 的上下文确认（无需再问用户）：

| 目标类型 | 期望提取的内容 |
|---------|--------------|
| **计算参数** | ENCUT、ISMEAR、LDAUU、HFSCREEN 等具体数值 |
| **实验对比值** | 带隙 / 晶格常数 / 磁矩的实验测量值 |
| **方法论验证** | HSE06 / DFT+U 在类似体系上的精度表现 |

---

### 2. arXiv 检索

**查询原则：只写材料体系名称，不堆砌方法关键词。**

查阅 `Read references/query_guide.md` 获取各材料类型的标准写法，然后调用：

```
arxiv_search(query="<化学式或材料体系名>", max_results=8)
```

示例：
- `"SrTiO3"` —— 不写 HSE06、band gap、VASP 等
- `"LiCoO2"` —— 不写 DFT+U、Hubbard
- `"MoS2 monolayer"` —— 仅在必要时加限定词区分体系

arXiv API 会按相关性排序，返回结果已包含标题、摘要、PDF 直链。

---

### 3. 筛选论文（仅读摘要）

对返回列表，**只看标题和摘要**，选出 1-3 篇，标准：

**优选**：
- 化学式或材料名精确出现在标题/摘要中
- 摘要中提到具体数值（如 `U = 3.5 eV`、`band gap = 1.8 eV`）
- 计算类论文（含"DFT"、"first-principles"、"ab initio"）
- 发表年份 ≥ 2018

**跳过**：
- 纯实验、纯综述、与目标物理量无关的论文

---

### 4. 下载 PDF 到工作区

对选定论文，从返回结果的 `pdf_link` 字段获取直链，用 `Bash` 下载：

```bash
mkdir -p <workspace>/literature
# arxiv pdf_link 格式通常为 https://arxiv.org/pdf/XXXX.XXXXX
wget -q "<pdf_link>" -O "<workspace>/literature/<arxiv_id>.pdf"
```

下载后确认文件非空：
```bash
ls -lh <workspace>/literature/
```

---

### 5. PDF 全文检索参数

调用 `Skill: pdf`，对每篇下载的 PDF 执行全文检索，目标章节：
- `Computational Details` / `Methods` / `Calculation Details`
- 论文中的表格（参数往往集中列出）
- `Supplemental Material`（附录，参数更详细）

提取并记录：
```
arXiv ID：XXXX.XXXXX
标题：...
材料：...
提取的参数：
  ENCUT = ... eV
  ISMEAR = ...，SIGMA = ...
  U(<元素>-<轨道>) = ... eV
  HFSCREEN = ... / AEXX = ...
  带隙（计算值，本文方法）= ... eV
  带隙（实验值，引用来源）= ... eV
VASP 版本：...（若有）
交换关联泛函：...
```

---

### 6. 补充搜索（arXiv 无结果时）

若 arXiv 未找到有效结果，依次尝试：

1. `google_search("site:materialsproject.org <材料名>")` —— 查 MP 数据库计算结果
2. `google_search("VASP wiki <参数名>")` + `visit_webpage(VASP Wiki URL)` —— 查官方推荐值

---

### 7. 输出引用块

整理为可直接插入 `INCAR_explanation.md` 的 Markdown 块：

```markdown
## 文献参考

### 计算参数依据
| 参数 | 取值 | 来源 |
|------|------|------|
| ENCUT | 520 eV | [1] 表 S1 |
| U(Co-3d) | 3.5 eV | [2] Computational Details |
| HFSCREEN | 0.2 Å⁻¹ | HSE06 默认，Heyd et al. 2003 |

### 实验对比值
| 物理量 | 实验值 | 本次计算值 | 来源 |
|--------|--------|-----------|------|
| 带隙 | 1.12 eV | 1.08 eV | [1] |

### 参考文献
[1] Author et al., *Journal*, Year. arXiv:XXXX.XXXXX  （本地：literature/XXXX.XXXXX.pdf）
[2] Author et al., *Journal*, Year. arXiv:YYYY.YYYYY  （本地：literature/YYYY.YYYYY.pdf）
```

---

## 核心原则

- **查询词极简**：只写材料体系，让相关性排序自动过滤；堆砌关键词反而会漏掉相关论文
- **先下载再精读**：PDF 存本地后由 `Skill: pdf` 精确检索，比 `visit_webpage` 更可靠
- **每个数值必须有来源**：标注 arXiv ID + 章节位置，方便用户复核
- **区分计算值与实验值**：两者都记录，但在引用块中明确标注，不得混淆
- **精不在多**：1-2 篇高质量文献优于 5 篇泛泛而谈的综述
