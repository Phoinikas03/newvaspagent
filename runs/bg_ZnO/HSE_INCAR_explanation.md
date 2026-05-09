# ZnO HSE06 能带计算参数说明

## 计算流程

采用两步法策略：
1. **PBE SCF 预计算**：生成 WAVECAR 和 CHGCAR
2. **HSE06 续算**：从 PBE 结果热启动，计算精确带隙

## 参数设置

### ENCUT 和 KSPACING
- 来源：收敛测试（见 `convergence_test/Convergence_Report.md`）
- ENCUT = 550 eV
- KSPACING = 0.20 Å⁻¹
- 两阶段完全一致，确保 WAVECAR 可读

### HSE06 参数
- HFSCREEN = 0.2 Å⁻¹（HSE06 标准屏蔽参数）
- AEXX = 0.25（精确交换混合比例）
- ALGO = All（氧化物宽带隙推荐，更稳定）
- PRECFOCK = Fast（加速 HF 积分，精度损失 < 0.05 eV）

### 参考来源
- HSE 参数参考：`.claude/skills/bandgap/references/hse_params.md`
- ZnO 属于氧化物宽带隙半导体，使用标准 HSE06 参数

## 计算资源配置
- PBE SCF：1 张 GPU
- HSE：8 张 GPU（用户指定）

## 文件清单
- `INCAR_pbe`：PBE SCF 输入
- `INCAR_hse`：HSE 输入
- `WAVECAR`：PBE 波函数（HSE 热启动）
- `CHGCAR`：PBE 电荷密度
