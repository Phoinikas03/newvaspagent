# Nb3Sn 结构松弛 INCAR 参数说明

## 材料信息
- **化学式**: Nb3Sn (A15 相)
- **原子数**: 23 Nb + 8 Sn = 31 atoms
- **晶格**: 四方晶系，a ≈ 10.65 Å, c ≈ 5.32 Å

## 参数选择依据

### 电子结构类型
Nb3Sn 是 A15 相超导材料，属于**金属**体系。因此：
- `ISMEAR = 1` (Methfessel-Paxton)：改善金属费米面附近的 K 点采样
- `SIGMA = 0.2`：较大展宽，改善收敛性

### 磁性与强关联
- Nb3Sn 为非磁性材料，无需 `ISPIN` / `MAGMOM`
- Nb 的 d 电子不属于强关联体系，无需 DFT+U

### 优化策略
- `ISIF = 3`：块体材料全弛豫（原子位置 + 晶胞形状 + 体积）
- `IBRION = 2`：共轭梯度法，稳健可靠
- `NSW = 200`：足够应对复杂结构
- `EDIFFG = -0.02`：力收敛标准 0.02 eV/Å

### 截断能与 K 点
- `ENCUT = 520 eV`：基于 Nb POTCAR ENMAX (~400 eV) × 1.3，消除 Pulay 应力
- `KSPACING = 0.20 Å⁻¹`：默认值，金属体系可收紧至 0.15

## 收敛测试说明
**未进行系统 ENCUT/KSPACING 收敛测试**。本次计算使用模板默认参数，适用于几何结构优化。若后续需要精确能量对比（EOS、带隙等），建议重新进行收敛测试。

## 参考来源
- VASP Wiki: [ISMEAR 选择指南](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
- VASP Wiki: [体积松弛与 Pulay 应力](https://vasp.at/wiki/Volume_relaxation)
- 本 skill `references/incar_params.md` 金属体系参数表