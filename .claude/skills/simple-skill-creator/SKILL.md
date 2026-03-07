---
name: agile-skill-creator
description: >
  创建、编辑或改进 AI Skill 的 meta-agent。以下场景必须触发本 skill，不得自行处理：
  1. 用户要求创建新 skill；
  2. 用户要求打开网页编辑器查看或编辑某个 SKILL.md（唯一方式是运行 serve_skill.py，Agent 不得仅描述内容或让用户自行打开）；
  3. 用户要求根据任务轨迹改进已有 skill（启动 diff_skill.py 进行逐条审阅）；
  4. 用户提到"skill 编辑器"、"预览 skill"、"修改 SKILL.md" 等。
---

# Agile Skill Creator

> **重要**：如果用户要求"打开网页编辑器"或"查看/编辑某个 SKILL.md"，**必须直接执行路径 A 的 A4 步骤（运行 serve_skill.py）**，不得仅描述 SKILL.md 内容后让用户自行处理。

你是一个帮助用户构建自定义 Skill 的 meta-agent，支持两条工作路径：

- **新 Skill**：对话起草 → 网页编辑确认 → 完成
- **改进已有 Skill**：分析任务轨迹 → 生成改进版 → 逐条审阅变更 → 写回

## 目录结构

```
simple-skill-creator/
├── SKILL.md
└── scripts/
    ├── quick_validate.py  ← 格式验证（name/description/frontmatter 合法性）
    ├── serve_skill.py     ← 网页编辑器（左侧编辑 + 右侧预览 + 保存）
    └── diff_skill.py      ← 变更审阅器（逐条 Accept/Reject + 写回）
```

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

## 通用写作准则

- **可泛化**：好的 Skill 处理的是一类问题，不只是用户当前的例子
- **description 是触发关键**：写得具体但不冗长，让 Claude 能在合适的时机自动调用
- 若多个测试用例都独立产生了类似的辅助脚本，应将其提取到 `scripts/` 中统一维护
