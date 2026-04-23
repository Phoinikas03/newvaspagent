# HSE 计算参数参考

## 标准 HSE06 参数（适用于大多数材料）

```text
LHFCALC = .TRUE.
HFSCREEN = 0.2
AEXX     = 0.25
ALGO     = Damped
TIME     = 0.4
PRECFOCK = Fast
```

## 按材料类型的经验参数

| 材料类型 | HFSCREEN | AEXX | ALGO | 备注 |
|---------|---------|------|------|------|
| 标准共价半导体（Si、Ge、GaAs）| 0.2 | 0.25 | Damped | HSE06 默认，效果良好 |
| 氧化物宽带隙（ZnO、TiO₂、Al₂O₃）| 0.2 | 0.25~0.30 | All | 带隙仍可能低估，可适当增大 AEXX |
| 2D 材料（MoS₂、WS₂、h-BN）| 0.2 | 0.25 | Damped | K 点密度要求高，建议加密 |
| 钙钛矿（MAPbI₃、CsPbBr₃）| 0.2 | 0.25 | All | 常需配合 SOC |
| 磁性材料（Fe₂O₃、NiO）| 0.2 | 0.25 | All | 需加 ISPIN=2、MAGMOM |
| 强关联体系（含 d/f 轨道）| 0.2 | 0.25 | All | 考虑 DFT+U 或 HSE+U |

## 参数说明

- `HFSCREEN`：HSE06 标准为 `0.2`，`0.0` 时接近 PBE0
- `AEXX`：标准值 `0.25`；若带隙系统性低估，可尝试 `0.30~0.35`
- `ALGO = All`：更稳，但更慢
- `ALGO = Damped`：更快，适合大体系，需配合 `TIME = 0.4`
- `PRECFOCK = Fast`：通常可显著提速，但极少数体系需改回 `Normal`
