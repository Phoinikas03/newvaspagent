# HSE 计算参数参考

## 标准 HSE06 参数（适用于大多数材料）

```
LHFCALC = .TRUE.
HFSCREEN = 0.2       # 屏蔽参数 (Å⁻¹)，HSE06 标准值
AEXX     = 0.25      # 精确交换混合比例，HSE06 标准值
ALGO     = Damped    # 推荐用于大体系；小体系可用 All
TIME     = 0.4       # 与 ALGO=Damped 配合使用
PRECFOCK = Fast      # 加速 HF 积分，精度略降但通常可接受
```

---

## 按材料类型的经验参数

| 材料类型 | HFSCREEN | AEXX | ALGO | 备注 |
|---------|---------|------|------|------|
| 标准共价半导体（Si、Ge、GaAs）| 0.2 | 0.25 | Damped | HSE06 默认，效果良好 |
| 氧化物宽带隙（ZnO、TiO₂、Al₂O₃）| 0.2 | 0.25~0.30 | All | 带隙仍可能低估，可适当增大 AEXX |
| 2D 材料（MoS₂、WS₂、h-BN）| 0.2 | 0.25 | Damped | K 点密度要求高，建议加密 |
| 钙钛矿（MAPbI₃、CsPbBr₃）| 0.2 | 0.25 | All | 需加 SOC（LSORBIT=.TRUE.） |
| 磁性材料（Fe₂O₃、NiO）| 0.2 | 0.25 | All | 需加 ISPIN=2、MAGMOM 初始磁矩 |
| 强关联体系（含 d/f 轨道）| 0.2 | 0.25 | All | 考虑加 DFT+U，或用 HSE+U |

---

## 参数说明

- **HFSCREEN**：屏蔽长程 HF 交换作用的参数，0.2 Å⁻¹ 对应 HSE06，0.0 对应 PBE0（全程精确交换，计算量更大）。
- **AEXX**：精确交换混合比例。HSE06 标准为 0.25；若带隙系统性低估，可尝试 0.30~0.35。
- **ALGO=Damped vs All**：
  - `All`：更稳定，适合小体系或难以收敛的情况
  - `Damped`：更快，适合大体系，需配合 `TIME=0.4`
- **PRECFOCK=Fast**：降低 HF 积分的精度以加速计算，通常对带隙影响 < 0.05 eV；若需要高精度，改为 `Normal`。
