# 截断能与 K 点收敛测试准则

面向 **单胞静态单点能**（`NSW=0`，体积/结构已固定），目标：相邻测试步之间的总能量差 **≤ 1 meV/atom**（按单胞原子数换算）。

## 路径说明

- 本 Skill 根目录：`.claude/skills/workflow-convergence/`（或项目内绝对路径）。
- 运行脚本时若当前工作目录在 `runs/<timestamp>/`，请使用 **Skill 内脚本的绝对路径**，例如：
  - `python /.../newvaspagent/.claude/skills/run-vasp/scripts/check_convergence.py .`

## 截断能 ENCUT 测试

1. **起点**：先读当前体系 `POTCAR` 中各元素的 **ENMAX**，取最大者；`ENCUT` 一般取 **max(ENMAX) × 1.3** 作为上限扫描区间的上界参考。
2. **扫描序列（示例）**：在 `INCAR` 中固定 **较密** 的 K 点间距（例如 `KSPACING = 0.15`，并**确保不写或删除 KPOINTS 文件**），对 ENCUT 做递增，例如（eV）：
   - `250, 300, 350, 400, 450, 500`（轻元素可适当降低下限；含 d/f 元素宜提高上限）
3. **判定**：对每步计算 `ΔE = E(n+1) - E(n)`，换算为 **meV/atom**；当 **|ΔE| ≤ 1 meV/atom** 时，取 **较大** 的该 ENCUT 作为收敛值（宁大勿小，避免 Pulay 误差）。
4. **记录**：在 `Convergence_Report.md` 中列表记录每步 ENCUT、总能量、ΔE(meV/atom)。

## KSPACING 测试 (K 点网格间距)

1. **固定**：上一步得到的 **收敛 ENCUT**。
2. **扫描**：优先在 `INCAR` 中用 **`KSPACING`**（倒易空间中 K 点的间距，单位 $\text{\AA}^{-1}$）扫描，**不写 KPOINTS 文件**。数值越小，网格越密。
   - **推荐序列**：`0.30, 0.25, 0.20, 0.15, 0.10`。
   - **防卡死警告**：对于大多数体系（包括金属），`0.15` 到 `0.10` 通常已经足够达到 1 meV/atom 的精度。**禁止将 KSPACING 设置得极小（例如低于 0.08）**，否则会产生难以计算的超巨大 K 点网格导致进程卡死。
3. **判定**：同样以 **1 meV/atom** 作为相邻两步能量差阈值；收敛后取 **较小** 的 KSPACING 值用于后续生产计算（在精度与成本间折中）。
4. **一致性**：后续所有需要能量可比的一步计算（例如 EOS 的各 `scale_*`、带隙的多步静态）须在 **INCAR** 中使用 **相同的 ENCUT 和 KSPACING**，并**确保工作目录下不存在会覆盖设置的 KPOINTS 文件**（除非你有意使用 KPOINTS）。

## 其他建议

- **ISMEAR**：金属常用 `ISMEAR=1` 或 `2` 配合较小 `SIGMA`；绝缘体常用 `ISMEAR=0` 与 `SIGMA=0.05`。与静态单点测试保持一致即可。
- **KGAMMA**：使用 `KSPACING` 时，推荐在 `INCAR` 中设置 `KGAMMA = .TRUE.` 以强制生成以 Gamma 点为中心的网格。
- **PREC**：静态能量对比建议 `PREC = Accurate`。
- 若体系磁性复杂，需在收敛测试与后续生产中 **统一自旋设置**（`ISPIN`、`MAGMOM` 等）。
