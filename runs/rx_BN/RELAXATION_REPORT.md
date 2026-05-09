# BN 结构松弛计算报告

## 计算概览
- **材料**：硼氮化物 (BN)
- **计算类型**：全结构松弛（ISIF=3）
- **计算日期**：2026-04-18
- **计算资源**：GPU (NVIDIA RTX 3090, GPU 0)
- **总耗时**：736.43秒 (约12分钟)

---

## 收敛状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 离子步收敛 | ✅ 是 | 原子受力已收敛 |
| 电子步收敛 | ✅ 是 | 电子能量已收敛 |
| NSW达到 | ❌ 否 | 在NSW=200之前收敛 |
| 完成离子步数 | 7 | 共进行7步离子优化 |

---

## 计算参数

### INCAR关键参数
```
SYSTEM = Full Structural Relaxation (atoms + cell shape + volume)
ISMEAR = 0          # Gaussian展宽（半导体）
SIGMA  = 0.05       # 小展宽
ENCUT  = 520 eV     # 截断能
EDIFF  = 1E-6       # 电子步收敛标准
EDIFFG = -0.02 eV/Å # 力收敛标准
IBRION = 2          # 共轭梯度法
ISIF   = 3          # 全松弛
NSW    = 200        # 最大离子步数
KSPACING = 0.20 Å⁻¹ # K点间距
```

### 计算资源
- **MPI进程数**：1
- **GPU分配**：1个GPU（CUDA_VISIBLE_DEVICES=0）
- **CPU时间**：226.064秒
- **最大内存**：1625852 KB (~1.6 GB)

---

## 最终结果

### 能量
- **总能量**：-125.614 eV
- **原子平均能量**：-8.374 eV/atom
- **原子总数**：15 (7个B + 8个N)

### 结构参数
- **晶胞体积**：95.79 Ų
- **最终压力**：0.3 kbar（接近零，表示结构已优化）

### 晶胞参数变化
| 参数 | 初始值 | 最终值 | 变化 |
|------|--------|--------|------|
| 晶胞常数 (Å) | 3.6260 | 3.6316 | +0.0056 (+0.15%) |
| 体积 (Ų) | 95.62 | 95.79 | +0.17 (+0.18%) |

---

## 原子位置变化

### B原子位移
初始结构中B原子位于高对称位置，松弛后发生微小位移：
- 原子1-6：位移约0.0014 Å（沿对角线方向）
- 原子7：保持在(0.5, 0.5, 0.5)位置

### N原子位移
N原子位移更显著，反映了B-N键长的优化：
- 原子1-3, 5：位移约0.009 Å
- 原子4, 6-8：位移约0.006 Å

---

## 输出文件

| 文件 | 位置 | 说明 |
|------|------|------|
| CONTCAR | `/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BN/CONTCAR` | 松弛后的最终结构（后续计算的输入） |
| OUTCAR | `/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BN/OUTCAR` | 完整计算日志 |
| INCAR | `/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BN/INCAR` | 计算参数文件 |
| POSCAR | `/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BN/POSCAR` | 初始结构 |
| POTCAR | `/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BN/POTCAR` | 赝势文件 |
| INCAR_explanation.md | `/mnt/data_x3/xiazeyu/newvaspagent/runs/rx_BN/INCAR_explanation.md` | 参数选择说明 |

---

## 物理意义

BN的结构松弛结果表明：
1. **晶胞膨胀**：晶胞常数从3.6260 Å增加到3.6316 Å，增幅0.15%
2. **压力释放**：最终压力接近零（0.3 kbar），表示结构已达到力学平衡
3. **原子重排**：B和N原子均发生微小位移，优化了B-N键长和键角
4. **收敛性**：仅需7步离子优化即达到收敛，说明初始结构质量良好

---

## 后续建议

该松弛结构可用于：
1. **能带结构计算**：使用 `Skill: bandgap` 计算带隙和能带
2. **晶格常数精细化**：使用 `Skill: lattice_constant` 进行EOS拟合
3. **表面/吸附计算**：基于该结构构建表面模型
4. **动力学模拟**：作为分子动力学的初始结构

---

**报告生成时间**：2026-04-18
**工作流**：relax skill + run_vasp skill
