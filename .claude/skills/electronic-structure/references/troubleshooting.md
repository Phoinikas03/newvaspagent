# Electronic Structure Troubleshooting

## 可安全忽略的报错

### ZBRENT: fatal error in bracketing

若 `vasprun.xml` 已完整生成，且 `OUTCAR` 中已有最终能量或能带信息，通常可视为接近收敛时的数值问题，不必立刻整轮重算。

## 电子步不收敛

### 现象
- `EDDDAV`
- `Sub-Space-Matrix is not hermitian`
- 达到 `NELM` 上限但未见 `reached required accuracy`

### 建议
1. 增大 `NELM`
2. 调 `ALGO = All`
3. 调整 `AMIX` / `BMIX`
4. 检查 `ISMEAR` / `SIGMA`
5. 检查结构质量

## HSE 内存不足

### 现象
- `LAPACK: Routine ZPOTRF failed`
- OOM / `Killed`

### 建议
1. 降低 K 点密度
2. 重新评估 `KPAR`、`NCORE`
3. 视情况去掉 `PRECFOCK = Fast` 做对照
4. 降低并发任务数或增加节点/显存

## WAVECAR 读取失败

### 现象
```text
WAVECAR: reading failed
```

### 建议
1. 确保续算前后 `ENCUT` 完全一致
2. 确保 `KSPACING` / `KPOINTS` 完全一致
3. 若参数已改变，删除旧 `WAVECAR`，并把 `ISTART` 改为 `0`

## 带隙为 0，但材料应为半导体

### 建议
1. 检查 `ISMEAR` 是否误设为金属展宽
2. 检查 `SIGMA` 是否过大
3. 检查 K 点是否足够密
4. 确认 HSE / 杂化泛函设置是否真正生效

## HSE 极慢或无进展

### 建议
1. 重新评估 K 点密度
2. 大体系尝试 `ALGO = Damped` + `TIME = 0.4`
3. 若用户要求按硬件优化，先走 `performance`
4. 若日志长期不更新，先判断是否 stalled，再决定是否终止当前 run

## DOS / 能带后处理异常

### 现象
- `vasprun.xml` 不完整
- `PROCAR` 缺失
- 路径模式 KPOINTS 写错

### 建议
1. 确认非自洽阶段使用了正确的 `ICHARG`
2. 做投影时确认 `LORBIT` 已开启
3. 线模式能带检查 `KPOINTS` 高对称路径格式
4. 若电子步已完成但 `vasprun.xml` 不完整，优先判断是否只需补后处理，而不是整轮重算
