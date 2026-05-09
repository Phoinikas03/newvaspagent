# HSE06 INCAR 参数说明

## 计算体系
- **材料**: BN (六方晶系)
- **计算类型**: HSE06杂化泛函能带结构计算

---

## 参数来源

### ENCUT 和 KSPACING
- **来源**: ENCUT/KSPACING收敛测试
- **ENCUT**: 550 eV
- **KSPACING**: 0.15 Å⁻¹
- **说明**: PBE和HSE两阶段使用完全相同的参数，确保WAVECAR兼容性

### HSE06标准参数
- **来源**: `.claude/skills/bandgap/references/hse_params.md`
- **材料类型**: 2D材料/宽带隙半导体
- **HFSCREEN**: 0.2 Å⁻¹ (HSE06标准屏蔽参数)
- **AEXX**: 0.25 (精确交换混合比例)

### 算法选择
- **ALGO**: Damped
- **TIME**: 0.4
- **理由**: BN体系较小，Damped算法效率高且稳定

### 加速选项
- **PRECFOCK**: Fast
- **说明**: 加速HF积分计算，对带隙影响<0.05 eV

---

## 关键参数一致性检查

| 参数 | PBE SCF | HSE06 | 一致性 |
|------|---------|-------|--------|
| ENCUT | 550 eV | 550 eV | ✅ |
| KSPACING | 0.15 Å⁻¹ | 0.15 Å⁻¹ | ✅ |
| KGAMMA | .TRUE. | .TRUE. | ✅ |
| ISMEAR | 0 | 0 | ✅ |
| SIGMA | 0.05 | 0.05 | ✅ |

---

## 热启动设置

- **ISTART**: 1 (从WAVECAR读取初始波函数)
- **ICHARG**: 2 (从CHGCAR读取电荷密度)
- **WAVECAR来源**: PBE SCF计算
- **CHGCAR来源**: PBE SCF计算

---

## 参考文档

1. HSE参数参考: `.claude/skills/bandgap/references/hse_params.md`
2. 收敛测试报告: `convergence_test/Convergence_Report.md`

---

**生成时间**: 2026-04-20
