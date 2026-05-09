# HSE INCAR 参数说明

## Ga₂O₃ HSE06 计算

### 参数来源

| 参数 | 值 | 来源 |
|------|-----|------|
| ENCUT | 520 eV | 收敛测试结果 |
| KSPACING | 0.15 Å⁻¹ | 收敛测试结果 |
| HFSCREEN | 0.2 | HSE06 标准值 |
| AEXX | 0.25 | HSE06 标准值（氧化物适用） |
| ALGO | All | 氧化物推荐，更稳定 |
| PRECFOCK | Fast | 加速HF积分，精度影响<0.05 eV |

### PBE → HSE 参数一致性

- ENCUT: 520 eV (两阶段一致)
- KSPACING: 0.15 Å⁻¹ (两阶段一致)
- KGAMMA: .TRUE. (两阶段一致)

### 热启动

- ISTART = 1: 从PBE的WAVECAR读取初始波函数
- ICHARG = 2: 从CHGCAR读取电荷密度

### 并行设置

- KPAR = 8: 对应8张GPU
- MPI rank = 8: 与GPU数一致

### 参考文献

HSE参数参考: `.claude/skills/bandgap/references/hse_params.md`
