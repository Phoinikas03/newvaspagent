# VASP + phonopy 声子各阶段 INCAR 关键设置

> 这些是各阶段的**最小关键 tag**。INCAR 的完整生成请经 `incar-builder` 组合工作流基线，并行/性能参数经 `incar-performance`。所有 INCAR 用 `setup_vasp_inputs` 生成 POTCAR/POSCAR，并建议用 KSPACING（避免 KPOINTS 文件）。

## Stage B 收敛测试（单胞）
| tag | 值 | 说明 |
|---|---|---|
| IBRION | -1 | 静态 |
| NSW | 0 | 单点 |
| ISMEAR | 0 / SIGMA 0.05 | 绝缘体（离子晶体）用 0；金属用 1 + SIGMA 0.2 |
| PREC | Accurate | |
| ENCUT / KSPACING | 扫描 | 相邻 ΔE ≤ 1 meV/atom |

## Stage A 弛豫（workflow-relax）
| tag | 值 | 说明 |
|---|---|---|
| IBRION | 2 | 共轭梯度 |
| ISIF | 3 | 同时优化晶胞+离子（得到平衡晶格常数） |
| EDIFFG | 负值 | 力收敛判据，如 -0.01 |

## Stage D DFPT（介电 + Born 电荷，生成 BORN）
| tag | 值 | 说明 |
|---|---|---|
| LEPSILON | .TRUE. | DFPT 介电张量 + Born 有效电荷 |
| IBRION | -1 | 不松弛 |
| NSW | 0 | 静态 |
| ISIF | 2 | |
| PREC | Accurate | |
| EDIFF | 1E-6 | 介电/Born 需更严电子收敛 |
| ENCUT / KSPACING | 收敛值 | 介电收敛比能量慢，不要用粗网格 |

## Stage F 超胞力计算（有限位移法）
| tag | 值 | 说明 |
|---|---|---|
| IBRION | -1 | **严禁弛豫** |
| NSW | 0 | 静态单点 |
| ISIF | 2 | 固定晶胞 |
| PREC | Accurate | 力必须精确 |
| EDIFF | 1E-6 | 高精度电子收敛 |
| ENCUT / KSPACING | 收敛值 | 与能量基准一致 |

### 为什么力计算必须 `IBRION=-1` / `NSW=0`
有限位移法的核心假设是：被测力 = 该位移下晶格的恢复力。若原子在计算中再次弛豫（`NSW>0`），测到的就是弛豫后另一套结构的力，二阶力常数矩阵随之失真，声子频率和 DOS 都会出错。

### 为什么 EDIFF 要 1E-6
力的精度受电子密度收敛支配。粗 `EDIFF`（如 1E-4）会在力常数里引入可观噪声，尤其对光学支高频段。声子计算建议 `EDIFF=1E-6`、`PREC=Accurate`。

## 常用 phonopy 命令（v4+）
```bash
# 生成超胞位移（setup 操作已从 phonopy 移到 phonopy-init）
phonopy-init --dim 2 2 2 -c POSCAR-unitcell -d

# 从位移构型 vasprun.xml 提取力 → FORCE_SETS（需同目录有 phonopy_disp.yaml + SPOSCAR）
phonopy-init -f fc_001/vasprun.xml fc_002/vasprun.xml

# 拟合力常数（--nac 已移除；--dim 不再用于主命令；--fc-symmetry 改名 --fc-spg-symmetry）
phonopy --writefc --fc-spg-symmetry

# 生成 BORN（只打印到 stdout，必须重定向）
phonopy-vasp-born > BORN
```

## 单位
- phonopy 频率/能量内部用 **THz**；换算 cm⁻¹ 乘 `33.356`。
- 声子频率也可用 meV（1 THz = 4.136 meV）。

## 离子性判断（是否需 NAC）
- 组成含强电负性差（如 Mg-O、Zn-O、Ga-N、金属-卤素），且结构非中心对称 → 有净的 Born 电荷 → **需要 NAC**。
- 纯非极性（C、Si、Ge 等金刚石/石墨结构，或金属）→ 无需 BORN / NAC。
- 判断最可靠依据：DFPT 算出的 Born 电荷是否显著非零；若接近 0 则 NAC 影响可忽略。
