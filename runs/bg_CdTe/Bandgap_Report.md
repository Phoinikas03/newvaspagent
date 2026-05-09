# CdTe HSE06 能带计算报告

## 计算体系
- **材料**: CdTe (闪锌矿结构)
- **原子数**: 2 (Cd: 1, Te: 1)
- **POSCAR来源**: `/mnt/data_x3/xiazeyu/newvaspagent/data/bandgap/CdTe`

## 收敛参数

通过ENCUT和KSPACING收敛测试确定（详见 `convergence_test/Convergence_Report.md`）：

| 参数 | 值 | 说明 |
|------|-----|------|
| ENCUT | 500 eV | 收敛判据: ≤1 meV/atom |
| KSPACING | 0.15 Å⁻¹ | 收敛判据: ≤1 meV/atom |
| KGAMMA | .TRUE. | Gamma中心K点网格 |

## 计算流程

### 1. PBE静态计算
- **目的**: 生成WAVECAR和CHGCAR供HSE热启动
- **GPU**: 2张
- **KPAR**: 2
- **状态**: ✅ 电子收敛成功

### 2. HSE06计算
- **目的**: 高精度带隙计算
- **GPU**: 8张
- **KPAR**: 8
- **HSE参数**:
  - HFSCREEN = 0.2 Å⁻¹
  - AEXX = 0.25
  - ALGO = All
  - PRECFOCK = Fast
- **状态**: ✅ 电子收敛成功
- **计算时间**: ~3909 秒

## 带隙结果

| 属性 | 值 |
|------|-----|
| **带隙** | **1.431 eV** |
| **带隙类型** | **直接带隙** |
| **跃迁路径** | Γ → Γ |

## 输出文件

| 文件 | 路径 |
|------|------|
| PBE INCAR | `INCAR_pbe` |
| HSE INCAR | `INCAR_hse` |
| HSE参数说明 | `HSE_INCAR_explanation.md` |
| 收敛报告 | `convergence_test/Convergence_Report.md` |
| vasprun.xml | `vasprun.xml` |
| OUTCAR | `OUTCAR` |
| PBE日志 | `vasp_pbe.log` |
| HSE日志 | `vasp_hse.log` |

## 备注

CdTe实验带隙约为 1.44-1.50 eV（室温），HSE06计算值 1.431 eV 与实验值符合良好。
