---
name: "vasp-literature-retrieval"
description: "为计算材料学任务结构化检索与整理文献：实验晶格常数、带隙、DFT/HSE/VASP 参数、DFT+U、EOS 方法等。在 relax、bandgap、lattice_constant、convergence 等技能要求「先查文献」或本地 references 未覆盖时触发；统一使用本 skill 规定的检索顺序与 arXiv 查询规范，输出带引用的摘要并可写入用户指定的工作区 Markdown。"
version: "1.0.0"
---

# 文献检索与引用整理 (Literature Retrieval)

你是一个专业的计算材料学助手。本 Skill 规定如何**系统化**使用可用搜索工具查找论文与数据，并把结果整理成可供下游步骤使用的**结构化说明**（含引用线索），而不是零散摘句。

## 目录结构

```
literature/
├── SKILL.md                    ← 本文件
└── references/
    └── query_guide.md          ← arXiv 查询词写法（材料名为主，少堆方法关键词）
```

## 何时触发

- 用户或上游 skill 需要：**实验对比值**（晶格常数、带隙、弹性常数等）、**推荐计算参数**（ENCUT、K 点、HSE、`LDAUU`、杂化参数等）、**方法学说明**（EOS 形式、收敛判据引用）。
- 其它 skill 写明「仅当本地 `references/*.md` 未覆盖时调用 `Skill: literature`」时——**先读本 skill**，再按下列流程检索，**不要**跳过本 skill 直接乱用 `arxiv_search`（避免查询词不当、结果不可复现）。

## 可用工具（与当前 Agent MCP 一致）

- `arxiv_search`：开放获取预印本，标题/摘要/PDF 链接
- `google_search`：网页与学术线索
- `duckduckgo_search`：通用网页检索
- `visit_webpage`：打开 URL 抽取正文（用于摘要页、期刊页、数据表）
- `Write` / `Edit`：将整理后的块写入工作区文件（如 `INCAR_explanation.md`、`HSE_INCAR_explanation.md`、`Convergence_Report.md` 附录等）

若运行环境后续增加 `semanticscholar_search`，可在 **arXiv 结果不足**时作为补充，仍须遵守下文「查询词」原则。

---

## 检索流程

### 1. 明确检索目标（每次调用本 skill 时先写清）

向用户或从上下文提取并内化：

- **材料体系**：化学式或矿物名/结构标签（如 `"SrTiO3"`、立方钙钛矿）。
- **检索目标类型**（可多选）：实验值 / DFT 计算参数 / 方法综述 / 带隙与光学实验 / 结构数据。
- **写入目标**（若上游 skill 已指定）：例如「追加到 `INCAR_explanation.md`」——最终必须用 **`Write`/`Edit`** 落盘。

### 2. arXiv 查询前必读

`Read references/query_guide.md`。

核心原则：**查询词以材料体系为主，不要堆砌 `HSE VASP DFT+U` 等**（详见该文件表格与反例）。

### 3. 搜索顺序（建议）

1. **`arxiv_search`**：用 `query_guide.md` 中的推荐句式发 **1～3 次**查询；优先读摘要中与目标相关的句子，记录 **论文标识**（arXiv id / 标题 / 年份）。
2. 若摘要信息不足：对选中的条目用 **`visit_webpage`** 打开 PDF 页面或期刊页面（若有），抓取**数值与条件**（温度、实验方法、计算泛函）。
3. **`google_search` 或 `duckduckgo_search`**：用于补实验手册、数据库页面、综述（例如「材料名 + experimental lattice constant」），仍应用**简短查询词**，避免一整句英文堆砌。

### 4. 输出格式（回复用户或写入文件时采用）

使用 Markdown，至少包含：

- **检索目标**（一句话）
- **推荐数值或参数区间**（带单位；若有多篇不一致，列出范围并说明分歧可能原因）
- **参考文献列表**：每条条目含 **标题、作者或年份（若可得）、来源（arXiv:xxxx / DOI / URL）**
- **不确定性说明**：实验 vs 计算、体相 vs 薄膜、是否含掺杂等。

若上游要求「引用块追加到某文件」，将上述块作为一节追加，并保证与材料体系、计算任务一致。

### 5. 与其它 Skill 的衔接

- **`convergence`**：本 skill **不**替代收敛测试；仅提供文献中的 ENCUT/K 点经验作**初值参考**，真正收敛仍以该 skill 与 `Convergence_Report.md` 为准。
- **`lattice_constant`**：实验晶格常数对比值优先通过本 skill 或 Materials Project 实验数据交叉核对。
- **`relax` / `bandgap`**：当 `references/incar_params.md`、`hse_params.md` 等未覆盖时，用本 skill 补参数与实验带隙引用。

---

## 核心原则

- **查询词克制**：遵守 `query_guide.md`，材料名为核；避免一条查询里塞满方法缩写。
- **可溯源**：每条关键数值尽量对应**可点击的链接或 arXiv id**，避免「某文献说约 3 eV」而无出处。
- **不编造**：工具未返回的内容不得凭记忆补全具体数值；若未找到，明确写「未检索到可靠来源」。
- **不替代计算**：文献参数是参考；与用户确认的 **VASP 实际输入**仍以各计算 skill 与 `setup_vasp_inputs`、`run_vasp` 为准。

---

## 与「ITERATIVE EXECUTION RULE」的关系

本 skill **不涉及**在单脚本中循环提交 VASP。若检索目的是为**下一步**收敛或 EOS 提供参数，真正跑 VASP 时须遵守项目 system prompt 与 **`run_vasp`** skill，逐点提交、逐步核查。
