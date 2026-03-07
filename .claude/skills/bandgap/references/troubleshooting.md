# 常见报错与处理方案

## 可安全忽略的报错

### ZBRENT: fatal error in bracketing
```
ZBRENT: fatal error in bracketing
please rerun with smaller EDIFF, or copy CONTCAR to POSCAR and rerun
```
**原因**：离子步在收敛判据附近震荡，属于已知的数值问题。  
**处理**：若 `vasprun.xml` 已完整生成且 OUTCAR 包含最终能量/带结构信息，视为计算成功，**直接忽略此报错**，继续后处理。

---

## 电子步不收敛

### 现象
```
WARNING: Sub-Space-Matrix is not hermitian in DAV
```
或 OUTCAR 中未出现 `reached required accuracy`，但已达到 `NELM` 上限。

**处理方案（依次尝试）**：
1. 增大 `NELM`（如从 60 改为 100）
2. 放宽 `EDIFF`（如从 `1E-6` 改为 `1E-5`）
3. 将 `ALGO` 从 `Damped` 改为 `All`（更稳定但更慢）
4. 检查 `SIGMA` 是否过大（半导体建议 0.01~0.05）

---

## HSE 计算内存不足

### 现象
```
LAPACK: Routine ZPOTRF failed!
```
或程序直接被 OOM kill。

**处理方案**：
1. 减小 K 点密度
2. 添加 `NCORE = 4`（或根据节点核数调整）以并行化轨道计算
3. 将 `PRECFOCK = Fast` 改为默认（去掉该行）观察内存变化
4. 增加计算节点数

---

## WAVECAR 读取失败

### 现象
```
WAVECAR: reading failed
```
**原因**：PBE 和 HSE 阶段的 KPOINTS 或 ENCUT 不一致，导致波函数格式不匹配。  
**处理**：确保 HSE 阶段的 `ENCUT` 和 K 点网格与 PBE SCF 阶段完全一致；若不一致，删除 WAVECAR 并将 HSE 的 `ISTART` 改回 `0`（从头计算，代价是失去 PBE 热启动优势）。

---

## 带隙为 0（金属化）

### 现象
`gap.py` 输出 `energy_eV: 0.0`，但材料已知是半导体/绝缘体。

**排查步骤**：
1. 检查 `ISMEAR`：静态计算应为 `0`（Gaussian），避免使用 `ISMEAR=1` 或 `2`（Methfessel-Paxton）
2. 检查 `SIGMA` 是否过大（应 ≤ 0.05 eV）
3. 检查 K 点是否足够密（带隙可能在高对称点之间）
4. 确认 `LHFCALC=.TRUE.` 已正确写入 HSE INCAR

---

## HSE 计算极慢或无进展

**常见原因**：
- K 点过多：HSE 计算量与 K 点数的平方成正比
- `ALGO=All` 在大体系下极慢：改用 `ALGO=Damped` + `TIME=0.4`
- `PRECFOCK=Normal`：改为 `Fast` 以加速（带隙精度影响通常 < 0.05 eV）
