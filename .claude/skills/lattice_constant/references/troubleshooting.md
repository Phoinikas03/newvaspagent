# 常见问题与处理（晶格常数 / EOS 工作流）

## 1. 电子步不收敛（`electronic_converged: false`）

**现象**：`check_convergence.py` 显示未达到 `aborting loop because EDIFF is reached`，或 OUTCAR 末尾显示达到最大电子步。

**可尝试**：

- 在 `INCAR` 中增大 **`NELM`**（如 80–120）。
- 调整 **`ALGO`**：`Normal` → `Fast` 或 `All`/`Damped`（按体系金属/绝缘性质选择）。
- 略放宽 **`EDIFF`** 做预收敛（仅用于排查，正式 EOS 点应回到严格设置）。
- 检查 **`AMIN`、`BMIX`** 等混合参数是否过激；金属可尝试 `IMIX=4` 等（需与文献/经验一致）。
- 确认 **`CHGCAR/WAVECAR`**：若上一轮电荷很差，删除后从头 SCF。

## 2. `fit_eos.py` 报错或 R² 很差

**现象**：拟合发散、`curve_fit` 失败、或 `R_squared < 0.99`。

**排查**：

- 某几个 `scale_*` 点的 **OUTCAR** 中能量/体积是否异常（SCF 未收敛、中途 Kill）。
- **缩放范围**是否覆盖能量最低点：若能量仍单调下降/上升，需 **扩大 scale 范围**或增加点数。
- 各点 **ENCUT / KPOINTS / POTCAR** 是否完全一致（否则能量不可比）。
- 确认全部为 **真静态计算**（`NSW=0`，`ISIF=2`，无离子步）。

## 3. 能量随 ENCUT 或 K 点剧烈跳动

- 检查是否混用了不同 **POTCAR 版本或泛函**。
- 检查 **`PREC`、`LREAL`** 是否在各计算中一致。
- 低 **ENCUT** 下金属体系可能出现锯齿状收敛，应 **提高 ENCUT** 直至 1 meV/atom 准则满足。

## 4. Pulay 应力 / 体积与能量不一致

- EOS 各点 **禁止**在计算中改变晶胞优化设置；应固定几何，仅通过 **scale 后的 POSCAR** 改变体积。
- **不要在不同点上使用不同 ENCUT**。

## 5. 路径与脚本找不到

- 工作目录在 `runs/...` 时，请用 **绝对路径** 调用 Skill 内脚本，例如：
  - `python .../lattice_constant/scripts/check_convergence.py .`
- `templates/INCAR_static` 位于 `lattice_constant/templates/`，复制到各 `scale_*` 目录后再改 `ENCUT`。

## 6. Materials Project mp-id 与结构不符

- 搜索到的 mp-id 可能不是目标 **纯相/结构**（例如氧化物 vs 单质）。应用 **`get_poscar_from_md`** 后检查 **POSCAR 元素与空间群**是否与用户目标一致，必要时换 mp-id 或换数据库条目。
