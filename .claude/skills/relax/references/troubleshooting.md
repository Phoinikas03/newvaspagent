# 结构松弛常见报错与处理方案

## 离子步未收敛（达到 NSW 上限）

### 现象
`check_convergence.py` 输出 `nsw_reached: true`，`ionic_converged: false`。

**处理方案（依次尝试）**：
1. 将 CONTCAR 复制为 POSCAR（`cp CONTCAR POSCAR`），增大 NSW 后续算
2. 检查 `max_force_eV_A` 是否接近 EDIFFG——若已接近（差距 < 2 倍），放宽 EDIFFG（如从 -0.01 改为 -0.02）后续算
3. 检查结构是否合理：原子间距过近可能导致无法收敛，考虑重建初始结构

---

## BRIONS: POTIM 警告

### 现象
```
BRIONS problems: POTIM should be increased
```
或
```
WARNING: Sub-Space-Matrix is not hermitian in DAV
```

**处理**：将 `POTIM` 从 0.5 减小到 0.3（甚至 0.1），或将 `IBRION` 从 2 改为 1（quasi-Newton 方法）。若结构变化剧烈，也可先用 MD 预弛豫（`IBRION=0`）几步再换回 CG。

---

## 电子步不收敛

### 现象
OUTCAR 中 `electronic_converged: false`，且各电子步能量振荡不下降。

**处理方案**：
1. 增大 `NELM`（如从 60 改为 100）
2. 将 `ALGO` 从 `Fast` 改为 `Normal`，或从 `Normal` 改为 `All`（更稳定）
3. 检查 `SIGMA`：金属用过小的 SIGMA（如 0.01）会导致费米面展宽不足，改为 0.2
4. 若是磁性体系，检查 `MAGMOM` 初始磁矩设置是否合理

---

## ZBRENT: fatal error in bracketing

### 现象
```
ZBRENT: fatal error in bracketing
please rerun with smaller EDIFF, or copy CONTCAR to POSCAR and rerun
```

**处理**：
- 若计算正常结束（`ionic_converged: true`）：**安全忽略**，继续使用结果
- 若未完成：将 CONTCAR 复制为 POSCAR，减小 `EDIFF`（如从 1E-5 改为 1E-6）后重新运行

---

## 负频率 / 鞍点结构

### 现象
松弛完成后检查声子谱出现虚频（imaginary frequency），或计算过程中结构出现不合理形变。

**原因**：结构陷入局部极小值或鞍点，松弛未达到真正基态。

**处理**：
1. 沿虚频振动方向对 CONTCAR 施加小扰动，重新松弛
2. 换用更好的初始结构（如从 Materials Project 下载已知稳定相）
3. 降低 `EDIFFG`（更严格的收敛标准）

---

## 内存不足 / LAPACK 错误

### 现象
```
LAPACK: Routine ZPOTRF failed!
```
或程序被 OOM kill。

**处理**：
1. 添加 `NCORE = 4`（或按节点核数调整）开启轨道并行
2. 降低 `ENCUT` 至 ENMAX × 1.0（牺牲少量精度）
3. 增加计算节点数或内存

---

## 赝势与 POSCAR 元素顺序不匹配

### 现象
```
POSCAR and POTCAR are inconsistent
```

**处理**：检查 POSCAR 第六行的元素顺序是否与 POTCAR 中各赝势的顺序完全一致。调用 `setup_vasp_inputs` 重新生成 POTCAR 通常可自动修复。

---

## 晶格参数异常变化（体积爆炸/坍缩）

### 现象
松弛过程中体积变化超过 30%，或晶格角度出现极端变化。

**原因**：初始结构与真实基态差异过大，或 `ISIF=3` 对某些体系不稳定。

**处理**：
1. 先用 `ISIF=2`（仅优化原子位置）运行几十步，再改为 `ISIF=3` 全优化
2. 对 2D 材料确认使用 `ISIF=2` 或 `ISIF=4`，避免 z 方向晶格被优化
3. 检查初始结构的合理性（键长、键角是否在物理范围内）
