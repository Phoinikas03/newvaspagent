# 结构松弛 INCAR 参数参考

## 目录
1. [通用参数说明](#通用参数说明)
2. [按材料类型的关键参数](#按材料类型的关键参数)
3. [ISMEAR / SIGMA 选择指南](#ismear--sigma-选择指南)
4. [ISIF 选择指南](#isif-选择指南)
5. [DFT+U 参数参考](#dftu-参数参考)
6. [官方参考链接汇总](#官方参考链接汇总)

---

## 通用参数说明

| 参数 | 典型值 | 说明 |
|------|--------|------|
| `ENCUT` | ENMAX × 1.3 | 取 POTCAR 中所有元素最大 ENMAX 的 1.3 倍。为了消除晶胞体积变化时带来的 Pulay 应力（[参考 VASP 体积松弛指南](https://vasp.at/wiki/Volume_relaxation)）。 |
| `EDIFF` | 1E-6 | 电子步收敛标准（结构松弛时 1E-5 通常也足够）。 |
| `EDIFFG` | -0.02 ~ -0.01 | 负值表示力收敛阈值（eV/Å）；正值表示能量收敛（eV）。推荐用负值。 |
| `NSW` | 100 ~ 300 | 最大离子步数；复杂体系可设到 500。 |
| `IBRION` | 2 | **共轭梯度法（CG）**，最稳健，适合**初始结构较差**、离平衡态较远的体系；若初始结构已经很好（受力较小），可用 `IBRION = 1`（quasi-Newton）以加快收敛。 |
| `POTIM` | 0.5 | CG 步长；若出现 BRIONS 警告导致不收敛或原子跑飞，可减小到 0.3 或更低。 |
| `ISIF` | 3 | 见下方 ISIF 选择指南。 |
| `PREC` | Accurate | 标准精度，松弛通常够用，能有效避免基组截断误差。 |
| `ALGO` | Normal | 常规迭代算法。`Fast` 速度更快，但对某些含过渡金属或磁性体系可能不稳定。 |

---

## 按材料类型的关键参数

### 金属
ISMEAR = 1        # Methfessel-Paxton 一阶展宽
SIGMA  = 0.2      # 较大展宽，改善 K 点收敛
ENCUT  = 400~520  # 视元素而定，或取 ENMAX * 1.3

### 半导体 / 绝缘体
ISMEAR = 0        # Gaussian 展宽
SIGMA  = 0.05     # 小展宽，避免人工展宽污染价带顶/导带底附近的真实电子态
ENCUT  = 400~520

### 磁性材料（铁磁/反铁磁）
ISPIN  = 2
MAGMOM = ...      # 每个原子的初始磁矩，例如 Fe: 5, Ni: 2, O: 0
ISMEAR = 1 或 0   # 金属用 1，半导体/绝缘体用 0

常见初始磁矩参考：
| 元素 | 推荐 MAGMOM |
|------|------------|
| Fe   | 5.0        |
| Co   | 3.0        |
| Ni   | 2.0        |
| Mn   | 5.0        |
| Cr   | 3.0        |
| 非磁 | 0.0        |

### 2D 材料（单层/少层）
ISMEAR = 0
SIGMA  = 0.05
LDIPOL = .TRUE.   # 偶极修正（对极性 2D 材料极其重要）
IDIPOL = 3        # 偶极修正方向（3 = z 方向，即垂直于 2D 平面）
ISIF   = 2 或 4   # 通常不优化 z 方向晶格常数，避免真空层坍缩

*注意：真空层厚度通常需要 ≥ 15 Å，防止周期性镜像相互作用。*

### 强关联体系（含 d/f 轨道的氧化物、稀土等）
LDAU   = .TRUE.
LDAUTYPE = 2      # Dudarev 方法（最常用，仅需提供 U-J 的有效值 Ueff）
LDAUL  = ...      # 各元素的 l 量子数（d=2, f=3, s/p 等其他=-1）
LDAUU  = ...      # 各元素的 U 值（eV）
LDAUJ  = 0 0 ...  # Dudarev 方法中 J 设为 0 即可
LDAUPRINT = 0

*常见 DFT+U 参数见本文件末尾 DFT+U 参数参考。*

### 含 Van der Waals 弱相互作用（层状材料、分子晶体）
IVDW = 11         # DFT-D3 (Grimme) 校正，适用性广
# 或
IVDW = 12         # DFT-D3(BJ) 阻尼校正，对层状材料和分子晶体通常表现更好

---

## ISMEAR / SIGMA 选择指南

正确选择展宽方法对能量和力的计算精度至关重要（[参考 VASP 官方 ISMEAR 选择规范](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)）。

| 体系类型 | ISMEAR | SIGMA | 备注 |
|---------|--------|-------|------|
| 金属 | 1 | 0.1~0.2 | Methfessel-Paxton，改善费米面附近的 K 点采样。**绝不能用于半导体**。 |
| 半导体（带隙 > 0.5 eV）| 0 | 0.05 | Gaussian，最安全的兜底方案。避免由于人工展宽导致带隙变小或产生虚假态。 |
| 绝缘体（带隙 > 2 eV）| 0 | 0.01~0.05 | 同上，SIGMA 可以设置得更小。 |
| 未知类型（探索性）| 0 | 0.05 | **最安全的结构松弛兜底方案**。若计算完成后检查 DOS 发现是金属，再改用 `ISMEAR=1` 重新计算。 |
| 精确 DOS 或静态全能计算 | -5 | / | Tetrahedron 方法（Blöchl 校正）。非常精确，但**严禁用于金属体系的结构松弛**（会导致求导计算力出错），且要求足够的 K 点网格。 |
| 分子/孤立原子（非周期）| 0 | 0.01 | 极小的 Gaussian 展宽。 |

---

## ISIF 选择指南

| ISIF | 优化内容 | 适用场景 |
|------|---------|---------|
| 2 | 仅原子位置 | 晶格常数已知、仅需优化原子坐标（如表面、界面吸附、缺陷），以及 **2D 材料松弛**。 |
| 3 | 原子位置 + 晶胞形状 + 体积 | 块体材料的标准全弛豫，最常用。 |
| 4 | 原子位置 + 晶胞形状（固定体积）| 适用于通过状态方程（EOS）扫描体积获取准确体模量的计算。 |
| 7 | 仅体积（固定形状和原子坐标）| 单纯的晶胞体积收缩/膨胀测试。 |

---

## DFT+U 参数参考

以下为文献常用值（基于 Dudarev 方法，有效值 Ueff = U - J）。U 值的选取往往取决于你关注的物理量（如带隙、氧化还原电位或晶格常数），推荐优先参考目标材料的原始文献。

| 化合物/元素 | 轨道 | Ueff (eV) | 来源与说明 |
|-----------|------|----------|---------|
| FeO, Fe₂O₃ (Fe) | d | 4.0 ~ 5.3 | MP 数据库对大多数 Fe 氧化物取 5.3 |
| NiO (Ni) | d | 6.0 ~ 6.4 | MP 数据库取 6.2 |
| CoO (Co) | d | 3.3 ~ 5.0 | MP 数据库取 3.32 |
| MnO (Mn) | d | 3.9 ~ 4.5 | MP 数据库取 3.9 |
| TiO₂ (Ti) | d | 4.2 | Materials Project (MP) 推荐值 |
| VO₂ (V) | d | 3.1 ~ 3.25| MP 数据库取 3.25 |
| CeO₂ (Ce) | f | 5.0 | Ce 的 f 轨道强关联经典取值 |

*注：以上部分数值参考自 Materials Project 数据库的拟合标准。完整元素 U 值配置请查阅：[Materials Project Hubbard U Values](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values)*

---

## 官方参考链接汇总
* [VASP Wiki: K 点数量与 Smearing 展宽方法指导](https://vasp.at/wiki/Number_of_k_points_and_method_for_smearing)
* [VASP Wiki: 体积松弛与 Pulay 应力消除 (Volume Relaxation)](https://vasp.at/wiki/Volume_relaxation)
* [VASP Wiki: 离子松弛算法 (IBRION)](https://vasp.at/wiki/IBRION)
* [Materials Project: GGA+U 计算中 U 值的选取方法与列表](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values)