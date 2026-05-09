# TiPbO3 结构松弛 INCAR 参数说明

## 材料特性
- **化学式**: TiPbO3 (钙钛矿结构)
- **晶格**: 立方晶系，a = 7.938 Å (2×2×2 超胞)
- **原子数**: 7 Ti + 8 Pb + 24 O = 39 原子
- **电子结构**: Ti⁴⁺ (3d⁰) 氧化物，半导体/绝缘体特性

## 关键参数选择依据

### ISMEAR / SIGMA
- **ISMEAR = 0, SIGMA = 0.05**
- 依据: TiPbO3 为氧化物半导体，使用 Gaussian 展宽避免人工展宽污染价带顶/导带底
- 参考: `references/incar_params.md` - 半导体/绝缘体推荐值

### DFT+U 参数
- **LDAU = .TRUE., LDAUTYPE = 2**
- **LDAUL = 2 -1 -1** (Ti: d轨道=2; Pb, O: 不加U)
- **LDAUU = 4.2 0 0** (Ti: Ueff=4.2 eV)
- 依据: Ti 3d 轨道存在强关联效应，TiO₂ 的 MP 推荐值为 4.2 eV
- 参考: `references/incar_params.md` - DFT+U 参数参考表

### ENCUT
- **ENCUT = 520 eV**
- 依据: 取 POTCAR 中最大 ENMAX × 1.3，消除 Pulay 应力
- 参考: VASP 官方 Volume Relaxation 指南

### ISIF
- **ISIF = 3**
- 依据: 块体材料全弛豫（原子位置 + 晶胞形状 + 体积）
- 参考: `references/incar_params.md` - ISIF 选择指南

### IBRION / POTIM
- **IBRION = 2, POTIM = 0.5**
- 依据: 共轭梯度法最稳健，适合初始结构可能偏离平衡态的情况

### KSPACING
- **KSPACING = 0.20, KGAMMA = .TRUE.**
- 依据: 对 7.9 Å 晶格常数，约对应 4×4×4 K 点网格
- 注: 未做系统 ENCUT/KSPACING 收敛测试

## 未做系统收敛测试说明
本次计算未进行 ENCUT/KSPACING 系统收敛测试（1 meV/atom 标准）。
若需生产级精度或与后续 EOS/带隙计算对齐，建议先执行 `convergence` skill。

## 文件来源
- POSCAR: `/mnt/data_x3/xiazeyu/newvaspagent/data/relax/TiPbO3`
- INCAR 模板: `templates/INCAR_relax_full`
- 参数参考: `references/incar_params.md`
