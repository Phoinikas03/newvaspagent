---
name: simple-skill-creator
description: >
  创建、编辑或改进 AI Skill 的 meta-agent。以下场景必须触发本 skill，不得自行处理：
  1. 用户要求创建新 skill；
  2. 用户要求打开网页编辑器查看或编辑某个 SKILL.md（唯一方式是运行 serve_skill.py，Agent 不得仅描述内容或让用户自行打开）；
  3. 用户要求根据任务轨迹改进已有 skill（启动 diff_skill.py 进行逐条审阅）；
  4. 用户提到"skill 编辑器"、"预览 skill"、"修改 SKILL.md" 等；
  5. Agent 自身在完成一个任务后判断需要沉淀经验——无论该任务是否用到了已有 skill。
  尤其包括：任务没有任何 skill 覆盖，Agent 靠组合已有 skill 或自行摸索完成了它，
  应把该轨迹沉淀为一个新 skill（路径 C）。此场景由 Agent 主动发起，不需要用户提出。
---

# Agile Skill Creator

> **重要**：如果用户要求"打开网页编辑器"或"查看/编辑某个 SKILL.md"，**必须直接执行路径 A 的 A4 步骤（运行 serve_skill.py）**，不得仅描述 SKILL.md 内容后让用户自行处理。

你是一个帮助构建自定义 Skill 的 meta-agent，支持三条工作路径：

- **路径 A — 新 Skill（对话驱动）**：对话起草 → 网页编辑确认 → 完成
- **路径 B — 改进已有 Skill（轨迹驱动）**：分析任务轨迹 → 生成改进版 → 逐条审阅 → 写回
- **路径 C — 从轨迹沉淀新 Skill（自蒸馏）**：任务完成且无 skill 覆盖它 → 压缩轨迹 →
  起草新 skill → 逐条审阅 → 写回。**由 Agent 主动发起**，是自演化的核心路径

选择依据：目标 skill 已存在选 B，不存在且刚跑完一个可复用的任务选 C，纯需求讨论选 A。

## 目录结构

```
simple-skill-creator/
├── SKILL.md
└── scripts/
    ├── quick_validate.py       ← 格式验证（name/description/frontmatter 合法性）
    ├── serve_skill.py          ← 网页编辑器（左侧编辑 + 右侧预览 + 保存）
    ├── diff_skill.py           ← 变更审阅器（逐条 Accept/Reject + 写回）
    └── extract_trajectory.py   ← 轨迹压缩器（log.jsonl → 摘要 + 失败清单）
```

## 轨迹从哪里来

每个工作区的完整执行记录在 `<workspace>/log.jsonl`（旧会话可能仍是 `log.txt`，同样可读）。
**不要直接 Read 它**——单个工作区动辄几百 KB，且含大量重复注入的 SKILL 正文。先压缩：

```bash
cd "<repo_root>"
python .claude/skills/simple-skill-creator/scripts/extract_trajectory.py \
  <workspace目录> -o /tmp/traj.md
```

实测压缩到原体积的 5–13%。加 `--errors-only` 只看概览和失败清单，那是改进 skill 的主要依据。

---

## 路径 A：创建新 Skill

### A1. 需求探索

不要立即写 SKILL，先通过对话收集：
1. 这个 Skill 要让 Claude 能做什么？输入和预期输出是什么？
2. 什么情况下应该触发它？
3. 是否依赖特定工具、MCP server 或执行环境？
4. 若需求模糊，提 1-2 个针对性问题，等用户确认后再进入下一步

### A2. 起草 SKILL.md（渐进式加载结构）

**Metadata（frontmatter）**
- `name`：kebab-case，≤ 64 字符
- `description`：触发时机 + 功能描述，≤ 1024 字符，不含 `<>`。写得具体，让 Claude 明确知道何时调用

**Core Logic（正文，≤ 500 行）**
- 用祈使句写指令；解释"为什么"而不是堆砌 MUST/NEVER
- 定义清晰的输出格式（用模板或示例）

**Bundled Resources（按需加载）**
- `scripts/`：确定性脚本（避免每次重写）
- `references/`：大型参考文档
- `templates/`：INCAR 模板、文档模板等

### A3. 格式验证

草稿写入文件后，先快速验证格式是否合法：

```bash
python scripts/quick_validate.py <skill目录>
```

若输出 `✗` 错误，根据提示修正（常见问题：name 含大写或空格、description 超过 1024 字符、frontmatter 含非法字段）。验证通过后再启动编辑器。

### A4. 启动网页编辑器

验证通过后，**你必须实际调用 Bash 工具执行以下命令，不得假设已执行或直接声称已启动**。

`BASE_DIR` 来自 Skill 加载时第一行显示的 `Base directory for this skill: ...`。

```bash
BASE_DIR=<从加载信息中读取的 Base directory>
TARGET_SKILL_DIR=<目标 skill 目录路径>
nohup python "$BASE_DIR/scripts/serve_skill.py" "$TARGET_SKILL_DIR" > /tmp/skill_view.log 2>&1 &
sleep 2 && grep '^URL=' /tmp/skill_view.log
```

**必须验证**：若 grep 有输出（如 `URL=http://...`），说明启动成功，将该 URL 告知用户；若输出为空，说明启动失败，执行 `cat /tmp/skill_view.log` 排查原因后重试。

向用户说明：
- 左侧可直接编辑 Markdown，右侧实时预览
- **Ctrl+S** 或点击"保存"写回文件
- 编辑完成后告知 Agent，Agent 可以继续读取最新版本

> **SSH 远程用户**：需先在本地开启端口转发
> `ssh -L 8700:localhost:8700 user@server`，再访问 `http://localhost:8700`

等待用户反馈，根据文字反馈补充调整后，询问是否需要测试验证。若不需要，跳到 A5。

### A5.（可选）测试验证

若用户希望测试：让用户提供一个真实测试场景，按照 SKILL 指令执行，向用户展示输出，收集反馈，重复直到满意。

### A6. 收尾

```bash
# 停止编辑器服务
kill $(grep '^PID=' /tmp/skill_view.log | cut -d= -f2) 2>/dev/null
```

告知用户最终 SKILL 的位置。

---

## 路径 B：根据任务轨迹改进已有 Skill

适用场景：用户用某个 Skill 完成了一次任务，希望把执行中遇到的问题、规避方案、注意事项补充进 Skill。

### B1. 读取旧 SKILL 和轨迹

```bash
SKILL_DIR=<skill目录路径>
TRAJ_FILE=<轨迹文件路径>   # 如 logs/20260306_192442.txt
```

读取 `$SKILL_DIR/SKILL.md` 和轨迹文件内容。

### B2. 分析轨迹，生成改进版 SKILL

重点关注：
- **错误和重试**：哪些步骤失败了？原因是什么？如何规避？
- **隐式知识**：Agent 在执行中"发现"的、但原 SKILL 没有写明的事项
- **冗余步骤**：Agent 每次都要从头做的事，是否可以抽象成 `scripts/` 中的脚本

改进原则：
- 泛化而非过拟合（不要只针对这一次任务的特定值）
- 精简：删掉在执行中没有实际效果的指令
- 解释原因：把"踩坑经验"转化为 Skill 能理解的"为什么"

快照旧版，将改进版写入 SKILL.md：

```bash
SNAPSHOT=/tmp/SKILL_snapshot_$(date +%s).md
cp "$SKILL_DIR/SKILL.md" "$SNAPSHOT"
echo "Snapshot: $SNAPSHOT"
# 然后将新版写入 $SKILL_DIR/SKILL.md
```

### B3. 启动变更审阅器

**你必须实际调用 Bash 工具执行以下命令，不得假设已执行或直接声称已启动**。

`BASE_DIR` 来自 Skill 加载时第一行显示的 `Base directory for this skill: ...`。

```bash
BASE_DIR=<从加载信息中读取的 Base directory>
nohup python "$BASE_DIR/scripts/diff_skill.py" \
  --old "$SNAPSHOT" \
  --new "$SKILL_DIR/SKILL.md" \
  --trajectory "$TRAJ_FILE" \
  > /tmp/skill_diff.log 2>&1 &
sleep 2 && grep '^URL=' /tmp/skill_diff.log
```

**必须验证**：若 grep 有输出，说明启动成功；若输出为空，执行 `cat /tmp/skill_diff.log` 排查后重试。

将 URL 告知用户，说明审阅界面的使用方式：
- **📝 变更审阅** 标签：逐条查看变更（绿色=新增，红色=删除）
  - 每条默认为"接受"（绿框）；点击"✗ 拒绝"可拒绝该条
  - 点击"应用已接受的变更"将结果写回 SKILL.md
- **📜 执行轨迹** 标签：查看完整执行过程，辅助判断变更是否合理

等待用户完成审阅并点击应用。

### B4. 确认结果

用户应用后，读取最新的 `$SKILL_DIR/SKILL.md` 确认写入正确：

```bash
kill $(grep '^PID=' /tmp/skill_diff.log | cut -d= -f2) 2>/dev/null
```

向用户报告改进摘要：接受了几处变更、拒绝了几处、最终 SKILL 文件位置。

---

## 路径 C：从执行轨迹沉淀一个新 Skill（自蒸馏）

适用场景：你刚完成一个任务，而**没有任何现成 skill 覆盖它**——你是靠组合已有 skill、
查文献或自行摸索做出来的。这条轨迹里的知识如果不沉淀就会随会话消失。

触发时机由你自己判断，不需要用户提出。满足以下**全部**条件才做：

1. 任务已真正完成并产出了有效结果（不是中途放弃，也不是仍在跑）；
2. 现有 skill 列表中没有一个覆盖这类任务；
3. 这类任务会重复出现——沉淀下来对以后有用，而不是一次性的临时请求。

不满足就不要做。为一次性任务造 skill 只会污染 skill 库。

### C1. 压缩轨迹

```bash
cd "<repo_root>"
python .claude/skills/simple-skill-creator/scripts/extract_trajectory.py \
  <当前workspace> -o /tmp/traj_$(date +%s).md
```

记下输出的文件路径，后面 C4 要用。

### C2. 从轨迹中提炼

通读摘要，重点回答四个问题，答案构成新 skill 的正文：

- **稳定流程是什么**：哪几步是这类任务每次都要做的？顺序和前后依赖是什么？
- **踩了哪些坑**：看「失败清单」。每个失败对应一条应当写进 skill 的预防性指令，
  并解释原因——写「为什么」比堆 MUST/NEVER 有用。
- **哪些步骤该固化成脚本**：如果某段逻辑你是现场写出来的、而且下次还得重写，
  把它放进新 skill 的 `scripts/`，不要指望下次再即兴发挥一遍。
- **依赖哪些已有 skill**：在正文里显式写明「本 skill 在执行 X 前必须先加载 Y」，
  与仓库现有 workflow skill 的写法保持一致。

**泛化，不要过拟合**：轨迹里的具体材料名、具体路径、具体参数值都是这一次的偶然。
写的是这一类任务的做法，不是这一次的流水账。

### C3. 起草并验证格式

在 `.claude/skills/<新名字>/` 下写 `SKILL.md`，然后：

```bash
python .claude/skills/simple-skill-creator/scripts/quick_validate.py .claude/skills/<新名字>
```

VASP / 材料计算类 skill 还须符合本文末尾「通用写作准则」中的 ITERATIVE EXECUTION RULE 等要求。

### C4. 逐条审阅

新建场景**省略 `--old`**，整份内容会作为新增（绿色）呈现，供逐条 Accept/Reject：

```bash
BASE_DIR=<从 Skill 加载信息中读取的 Base directory>
nohup python "$BASE_DIR/scripts/diff_skill.py" \
  --new .claude/skills/<新名字>/SKILL.md \
  --trajectory /tmp/traj_<你在C1记下的>.md \
  > /tmp/skill_new.log 2>&1 &
sleep 2 && grep '^URL=' /tmp/skill_new.log
```

**必须验证**：grep 有输出才算启动成功；为空则 `cat /tmp/skill_new.log` 排查后重试。
把 URL 告知用户，说明「📜 执行轨迹」标签可对照原始执行过程判断每条指令是否站得住。

### C5. 收尾

用户应用后读回 `SKILL.md` 确认，然后停掉服务：

```bash
kill $(grep '^PID=' /tmp/skill_new.log | cut -d= -f2) 2>/dev/null
```

向用户报告：新 skill 的位置、它覆盖什么任务、从轨迹里吸收了哪几条教训。

> **新 skill 何时生效**：skill 列表在会话启动时确定。新写入的 skill 通常要等下一次
> 会话才会出现在可调用列表中。报告时说明这一点，不要声称当前会话就能立刻调用它。

---

## 通用写作准则

- **可泛化**：好的 Skill 处理的是一类问题，不只是用户当前的例子
- **description 是触发关键**：写得具体但不冗长，让 Claude 能在合适的时机自动调用
- 若多个测试用例都独立产生了类似的辅助脚本，应将其提取到 `scripts/` 中统一维护
- **VASP / 材料计算类 Skill**：须在正文中写明与项目 system_prompt 一致的 **ITERATIVE EXECUTION RULE**（禁止 `for`/`while` 或 monolithic 脚本一次提交多点、多阶段、多目录 VASP；每步单独核查后再继续），并与 Skill **`run-vasp`** 的探针、**STRICT HARDWARE ALIGNMENT**、`vasp_runner.py --dirs` 分批策略对齐。措辞可参考同仓库 `workflow-relax`、`workflow-electronic-structure`、`workflow-eos-lattice-constant`、`research-literature` 等已有「执行方式」「核心原则」段落。
