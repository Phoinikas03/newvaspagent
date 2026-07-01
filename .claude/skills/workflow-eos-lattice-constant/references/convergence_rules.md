# 截断能与 K 点收敛准则（已迁移）

本准则的**完整内容与维护**已迁移至独立 skill **`convergence`**（YAML `name`: `vasp-convergence`）。

请阅读：

`newvaspagent/.claude/skills/workflow-convergence/references/convergence_rules.md`

执行工作流时请 **载入 `Skill: convergence`**（或项目内对应 skill 名称），按该 skill 完成 **ENCUT / KSPACING** 收敛与 **`Convergence_Report.md`**，再回到本 skill 继续 EOS 步骤。
