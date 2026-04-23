# VASP Error Recovery Guide

通用 VASP 排障知识库，优先覆盖 `run_vasp`、`relax`、`electronic-structure` 等工作流里最常见的问题。

## 电子步不收敛

### 现象
- `EDDDAV: ... eigenvalues not converged`
- `WARNING: Sub-Space-Matrix is not hermitian`
- 达到 `NELM` 上限后仍未见 `reached required accuracy`

### 建议
1. 增大 `NELM`，如从 `60` 调到 `100` 或 `200`
2. 改 `ALGO = All` 或其它更稳的算法
3. 调整混合参数，例如 `AMIX = 0.2`、`BMIX = 0.0001`
4. 对金属检查 `ISMEAR` / `SIGMA` 是否合理
5. 对半导体/绝缘体避免过大的 `SIGMA`
6. 检查初始结构是否存在原子过近、错误对称性或坏几何

## 离子步不收敛

### 现象
- 到达 `NSW` 上限，力仍然较大
- 结构持续震荡，难以稳定

### 建议
1. 增大 `NSW`
2. 续算时把 `CONTCAR` 复制为 `POSCAR`
3. 尝试更稳的离子优化器，例如 `IBRION = 1` 或 `IBRION = 3`
4. 减小 `POTIM`，例如改成 `0.2` 或 `0.1`
5. 必要时先做固定晶格松弛，再放开晶胞

## ZBRENT: fatal error in bracketing

### 现象
```text
ZBRENT: fatal error in bracketing
```

### 建议
1. 先确认 `vasprun.xml`、`OUTCAR` 是否已经完整写出
2. 若后处理文件已完整，这类报错经常是接近收敛时的可恢复问题，可视情况忽略
3. 若需要重跑，减小 `POTIM`
4. 改用 `IBRION = 3` 的阻尼动力学
5. 检查初始结构是否过于激进

## 内存不足 / LAPACK 错误

### 现象
- `LAPACK: Routine ZPOTRF failed`
- `allocation failed`
- `Killed`
- `segmentation fault`

### 建议
1. 降低并发数，避免多个重任务挤在同一节点
2. 减小 K 点密度、`NBANDS`，或降低过于激进的并行设置
3. HSE/GW 等高阶方法优先减少 GPU/CPU 资源争抢
4. 必要时增加节点或换到更大内存机器

## WAVECAR 读取失败

### 现象
```text
WAVECAR: reading failed
```

### 建议
1. 确保前后阶段 `ENCUT` 一致
2. 确保 `KSPACING` / `KPOINTS` 一致
3. 若已改变参数，删除旧 `WAVECAR` 并把 `ISTART` 改回 `0`

## POTCAR 与 POSCAR 元素顺序不匹配

### 现象
- 结构异常
- 原子“爆炸”
- 结果明显不合理

### 建议
1. 检查 `POTCAR` 中 `VRHFIN` 顺序
2. 确保它与 `POSCAR` 第 6 行元素顺序完全一致
3. 不一致时重新生成 `POTCAR`

## 晶胞异常膨胀 / 坍缩

### 现象
- `ISIF = 3` 后晶胞形状明显失真
- 体积不合理地快速变化

### 建议
1. 先用 `ISIF = 2` 只松弛原子，再转 `ISIF = 3`
2. 检查初始结构和实验晶格参数
3. 检查是否误设置 `PSTRESS`
4. 必要时关闭错误对称性，或重新检查结构来源

## HSE 计算极慢 / 看似无进展

### 现象
- 长时间无新输出
- GPU 占用低但任务一直不结束

### 建议
1. 检查是否 K 点过密
2. 根据硬件重新评估 `KPAR`、`NCORE`
3. 大体系可尝试 `ALGO = Damped` 配合 `TIME = 0.4`
4. 若日志和 `OUTCAR` 长时间不更新，先判断是否已卡住，再决定是否终止

## 带隙为 0，但材料应为半导体

### 建议
1. 检查 `ISMEAR` 和 `SIGMA`
2. 检查 K 点是否足够密
3. 确认 HSE / 杂化泛函参数是否真正生效
4. 核查结构是否仍未松弛好

## 卡住 / 长时间无新输出

### 判断思路
1. 看主日志、`OUTCAR`、`OSZICAR` 的最后修改时间
2. 看 runner state 是否仍标记为 `running`
3. 看当前目录是否仍有属于本次 run 的进程或作业

### 建议
1. 若输出仍持续更新，优先继续等待
2. 若长时间无更新且能证明是当前 run，先询问用户是否停止
3. 停止后再修改参数并通过 `vasp_runner.py` 重跑
