# HSE06 计算参数说明

## 材料体系
- **材料**：AlN（氮化铝）
- **材料类型**：标准共价半导体
- **晶系**：六方晶系

## HSE06 参数选择

### 标准参数（适用于 AlN）
```
LHFCALC = .TRUE.
HFSCREEN = 0.2       # HSE06 标准屏蔽参数（Å⁻¹）
AEXX     = 0.25      # HSE06 标准精确交换混合比例
```

### 参数说明
- **HFSCREEN = 0.2**：屏蔽长程 HF 交换作用的参数，0.2 Å⁻¹ 对应 HSE06 标准值
- **AEXX = 0.25**：精确交换混合比例，HSE06 标准为 0.25
- **ALGO = Damped**：推荐用于大体系；与 TIME=0.4 配合使用
- **PRECFOCK = Fast**：加速 HF 积分，精度略降但通常可接受

### 参考文献
根据 `bandgap/references/hse_params.md`，AlN 属于「标准共价半导体」类别，使用默认 HSE06 参数（HFSCREEN=0.2, AEXX=0.25）效果良好。

## 计算策略

### 第一阶段：PBE 静态自洽计算
- **目标**：获得高质量波函数（WAVECAR）和电荷密度（CHGCAR）
- **参数**：ENCUT=350 eV, KSPACING=0.25 Å⁻¹
- **状态**：✓ 已完成，能量收敛

### 第二阶段：HSE06 高精度计算
- **目标**：基于 PBE 波函数热启动，获得准确带隙
- **关键设置**：
  - `ISTART = 1`：从 PBE WAVECAR 读取初始波函数
  - `ICHARG = 2`：从 CHGCAR 读取电荷密度
  - ENCUT、KSPACING 与 PBE 完全一致
- **预期耗时**：15-30 分钟（单卡 GPU）

## 与 PBE 的一致性检查

| 参数 | PBE | HSE06 | 一致性 |
|-----|-----|-------|--------|
| ENCUT | 350 eV | 350 eV | ✓ |
| KSPACING | 0.25 Å⁻¹ | 0.25 Å⁻¹ | ✓ |
| KGAMMA | .TRUE. | .TRUE. | ✓ |
| ISMEAR | 0 | 0 | ✓ |
| SIGMA | 0.05 | 0.05 | ✓ |

---

**生成时间**：2026-04-19 00:40 UTC
