# Li₄Ti₅O₁₂ 结构优化 INCAR 参数说明

## 材料体系分析

| 属性 | 分析结果 |
|------|---------|
| 化学式 | Li₄Ti₅O₁₂ (尖晶石结构) |
| 原子数 | 41 原子 (Li:7, Ti:10, O:24) |
| 电子结构 | 半导体/绝缘体（带隙约 2-3 eV） |
| 过渡金属 | Ti⁴⁺ (3d⁰ 配置，无未配对电子) |
| 磁性 | 非磁性体系 |
| DFT+U | 不需要（Ti⁴⁺ d⁰ 配置） |

## 关键参数选择依据

### ENCUT = 520 eV
- **来源**: Ti 的 POTCAR ENMAX ≈ 400 eV
- **计算**: 400 × 1.3 = 520 eV
- **理由**: 消除晶胞体积变化时的 Pulay 应力（参考 [VASP Volume Relaxation Guide](https://vasp.at/wiki/Volume_relaxation)）

### ISMEAR = 0, SIGMA = 0.05
- **来源**: `references/incar_params.md` - 半导体/绝缘体
- **理由**: Gaussian 展宽，小 SIGMA 避免人工展宽污染价带顶/导带底
- **注意**: Li₄Ti₅O₁₂ 是绝缘体，绝不能用 ISMEAR=1（Methfessel-Paxton）

### ISIF = 3
- **来源**: `references/incar_params.md` - 块体材料全弛豫
- **理由**: 同时优化原子位置、晶胞形状和体积

### IBRION = 2, POTIM = 0.5
- **来源**: `references/incar_params.md` - 共轭梯度法
- **理由**: CG 算法最稳健，适合初始结构可能偏离平衡态的情况

### KSPACING = 0.20
- **来源**: 模板默认值
- **理由**: 绝缘体标准 K 点密度
- **注意**: 未进行系统 ENCUT/KSPACING 收敛测试

### NCORE = 4
- **来源**: 模板默认值
- **理由**: 典型并行设置，实际应根据计算节点核数调整

## 未进行的测试

- **ENCUT/KSPACING 收敛测试**: 用户选择跳过，使用模板默认参数
- **如需严格收敛**: 可后续调用 `convergence` skill 进行 1 meV/atom 收敛测试

## 参考文档

- `references/incar_params.md` - INCAR 参数参考表
- `templates/INCAR_relax_full` - 全松弛模板
