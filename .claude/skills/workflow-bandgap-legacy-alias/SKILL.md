---
name: "workflow-bandgap-legacy-alias"
description: "兼容旧 bandgap 入口。该 skill 现已升级为更通用的 workflow-electronic-structure：统一处理静态 SCF、band structure、DOS、PBE/HSE 带隙等电子结构任务。若用户提到 bandgap，可按原来的 PBE→HSE 带隙流程执行，但主入口应优先理解为 workflow-electronic-structure。"
---

# Legacy Alias: bandgap -> workflow-electronic-structure

`bandgap` 现在是兼容旧工作流的入口说明，主能力已经升级并迁移到：

```text
.claude/skills/workflow-electronic-structure/
```

## 如何理解这个别名

- 如果用户说“算 bandgap / HSE band gap”，仍可沿用旧的两步法：
  1. PBE SCF
  2. PBE 收敛检查
  3. 准备 HSE
  4. **单独询问用户是否继续**
  5. 若有 GPU，**单独询问 GPU 卡数**
  6. 再通过 `run-vasp` 提交 HSE

- 如果用户的意图已经扩展到：
  - band structure
  - DOS / PDOS
  - 静态电子结构
  - 更一般的电子结构分析

  则应直接按 `workflow-electronic-structure` skill 执行。

## 仍然必须保留的旧规则

1. 正式运行必须通过 `run-vasp`
2. 涉及 GPU / `KPAR` / `NCORE` / `NPAR` 时必须先走 `incar-performance`
3. POTCAR 必须通过 `setup_vasp_inputs` 生成，并遵守 `workflow-electronic-structure` 的 POTCAR 强制规则；含 `Ga/In/Sn/Pb` 的体系必须确认实际使用 `Ga_d/In_d/Sn_d/Pb_d`
4. HSE 启动前必须有单独确认回合
5. 有 GPU 时必须问清 GPU 数量
6. PBE 前置计算必须保存 `WAVECAR/CHGCAR`：`LWAVE = .TRUE.` 且 `LCHARG = .TRUE.`；若看到 `.FALSE.`，必须先改正再提交 PBE
7. PBE 与 HSE 之间必须保证 `POTCAR`、`ENCUT` 与 K 点口径一致
8. 若旧 HSE run 可能仍活着，不能在同一目录里补开第二个活跃进程
9. 出错或卡住时优先用 `vasp-error-recovery` 诊断，再决定是否 terminate + rerun

## 提交前硬提醒

PBE -> HSE 带隙任务的 PBE `INCAR` 必须保留热启动文件：

```text
LWAVE  = .TRUE.
LCHARG = .TRUE.
```

若模板或模型生成 `LWAVE = .FALSE.` 或 `LCHARG = .FALSE.`，必须先改成 `.TRUE.` 再提交 PBE。

## 参考

- 主 skill：`workflow-electronic-structure`
- 运行编排：`run-vasp`
- 性能调优：`incar-performance`
- 报错恢复：`vasp-error-recovery`
