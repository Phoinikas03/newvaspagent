# Sr2RuO4 结构优化 INCAR 参数说明

## 材料特性
- **化学式**：Sr2RuO4（Ruddlesden-Popper 结构）
- **原子数**：27（7 Sr + 4 Ru + 16 O）
- **电子性质**：金属（非常规超导体母体材料）
- **磁性**：含 Ru 4d 电子，开启自旋极化

## 关键参数选择依据

| 参数 | 设置值 | 选择理由 |
|------|--------|----------|
| ISMEAR | 1 | 金属体系，使用 Methfessel-Paxton 展宽 |
| SIGMA | 0.2 | 金属用较大展宽改善 K 点收敛 |
| ISPIN | 2 | 含 Ru 过渡金属，开启自旋极化 |
| MAGMOM | 7*0 4*1 16*0 | Sr 无磁矩，Ru 初始磁矩 1 μB，O 无磁矩 |
| ISIF | 3 | 全结构优化：原子位置 + 晶胞形状 + 体积 |
| IBRION | 2 | 共轭梯度法，稳健可靠 |
| ENCUT | 520 | PBE 推荐值，覆盖 Ru 的 ENMAX |
| KSPACING | 0.20 | 默认值，金属可适当收紧 |
| KPAR | 8 | 8 GPU 并行，K 点并行数等于 GPU 数 |
| NCORE | 4 | 每个 MPI rank 处理的核数 |

## 未执行的操作
- **ENCUT/KSPACING 收敛测试**：用户确认不需要，使用模板默认值
- **DFT+U 修正**：Ru 4d 电子关联性中等，PBE 通常足够

## 赝势选择
- **Sr_sv**：Sr 的半芯态版本（更精确）
- **Ru**：标准 Ru 赝势
- **O**：标准 O 赝势

## 参考文献
- VASP Wiki: K 点数量与 Smearing 展宽方法指导
- VASP Wiki: 体积松弛与 Pulay 应力消除
