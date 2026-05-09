# Pt(111)/CO Adsorption Summary

工作目录：`/mnt/data_x3/xiazeyu/newvaspagent/runs/ads_PtCO_supervised`

## 计算体系

本次计算包含 8 个几何优化体系：

- `CO`：气相 CO 分子
- `surface`：洁净 Pt(111) slab，16 个 Pt 原子
- `configs/fcc_upright`：CO/Pt(111)，fcc 位点，upright 取向
- `configs/fcc_tilted_x`：CO/Pt(111)，fcc 位点，tilted_x 取向
- `configs/fcc_tilted_y`：CO/Pt(111)，fcc 位点，tilted_y 取向
- `configs/ontop_upright`：CO/Pt(111)，ontop 位点，upright 取向
- `configs/ontop_tilted_x`：CO/Pt(111)，ontop 位点，tilted_x 取向
- `configs/ontop_tilted_y`：CO/Pt(111)，ontop 位点，tilted_y 取向

所有体系的 `OUTCAR` 均显示：

```text
reached required accuracy - stopping structural energy minimisation
```

## 能量结果

主表采用最终 `energy(sigma->0)` / `E0`，单位为 eV。吸附能定义为：

```text
E_ads = E(adsorbed) - E(surface) - E(CO)
```

参考能量：

- `E(CO) = -14.80019516 eV`
- `E(surface) = -92.80116004 eV`
- `E(CO) + E(surface) = -107.60135520 eV`

| 体系 | 说明 | E0 / eV | E_ads / eV |
|---|---|---:|---:|
| `CO` | 气相 CO | -14.80019516 | - |
| `surface` | clean Pt(111) slab | -92.80116004 | - |
| `configs/fcc_upright` | fcc, upright | -109.35721338 | **-1.75585818** |
| `configs/fcc_tilted_x` | fcc, tilted_x | -109.35368201 | -1.75232681 |
| `configs/fcc_tilted_y` | fcc, tilted_y | -109.35336539 | -1.75201019 |
| `configs/ontop_upright` | ontop, upright | -109.19196945 | -1.59061425 |
| `configs/ontop_tilted_x` | ontop, tilted_x | -109.18784567 | -1.58649047 |
| `configs/ontop_tilted_y` | ontop, tilted_y | -109.18860801 | -1.58725281 |

## TOTEN 核对

| 体系 | TOTEN / eV |
|---|---:|
| `CO` | -14.80019516 |
| `surface` | -92.80111913 |
| `configs/fcc_upright` | -109.35885708 |
| `configs/fcc_tilted_x` | -109.35537341 |
| `configs/fcc_tilted_y` | -109.35510391 |
| `configs/ontop_upright` | -109.19041445 |
| `configs/ontop_tilted_x` | -109.18630653 |
| `configs/ontop_tilted_y` | -109.18711612 |

## 结论

本批计算中最稳定构型为：

```text
configs/fcc_upright
E_ads = -1.75585818 eV
```

三个 fcc 构型能量非常接近，`fcc_upright`、`fcc_tilted_x`、`fcc_tilted_y` 的吸附能差异约为 0.004 eV 以内。fcc 构型整体比 ontop 构型稳定约 0.16-0.17 eV。
