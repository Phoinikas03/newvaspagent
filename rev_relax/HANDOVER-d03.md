# SR 结构优化重复实验（rep1 / rep2 / rep3）交接 — d03

写给在 d03 上开的监管 Claude Code 会话。2026-09-24 由 d01 上的会话准备，
做法照搬 `rev_sol27lc/HANDOVER-d03.md`（Sol27LC 的 rep2/rep3 已在 d03 跑完）。

## 1. 目标

用 **DeepSeek v4 + 领域 skill** 的 VASP Agent，把论文 SR（结构优化）任务的 **40 个体系**
在同一配置下独立跑 **3 遍**（`rep1`、`rep2`、`rep3`），量化 run-to-run 变异：
完成数、对专家结构的 RMSD、体积偏差、agent 选的参数（POTCAR、DFT+U、ISPIN、ENCUT、K 点）在 rep 间是否一致。

固定配置（开跑后不得改动；详见 `protocol/CHANGELOG.md`）：

| 项 | 值 |
|---|---|
| 模型 | `deepseek-v4-flash-vision-exp`，DeepSeek Anthropic 兼容端点直连（`mode=direct`，无协议桥）— 与 Sol27LC 相同 |
| 领域 skill | 启用（`.claude/skills/` 全部 21 个）；走 `workflow-relax` |
| 任务规格 | T2：只给 POSCAR + 目标（晶格与原子位置全松弛、PBE），不给任何参数（`scripts/run_agent_relax.py` 的 `TASK_PROMPT`） |
| 操作员回答 | `protocol/answer_script.py` 预注册规则；人工只按 `protocol/answering_policy.md` 回答。**收敛测试一律答“否”**（照 SR 历史会话；这点与 Sol27LC 相反） |
| 预算 | 每体系 **24 h** 墙钟（Sol27LC 是 6 h）、300 轮；1 体系 ↔ 1 GPU |
| GPU | 排除 GPU 5（`EXCLUDE_GPU_INDEX=5`），7 卡并发 |
| 体系 | `data/` 下 40 个（`data/relax` 去掉 La2CuO4；`Li10Ge(PS6)2` 目录名改为 `Li10GeP2S12`），`data/dataset.json` 为清单 |
| 专家参考 | **不在 d03 上**。只留在 d01 的 `rev_relax/reference/`（git 忽略；与 `relax_new.xlsx` 同一套，Cr 用 06-25 重算的参考）。RMSD 等结果拿回 d01 后再算 |
| 完成判定 | `scripts/check_flow.py`：存在离子收敛且正常结束、有 CONTCAR 的松弛，且工作目录里没有 VASP 在跑 |

论文里的 SR 数字（VASP Agent 行，旧 rx_* 运行，glm-5.1/Claude 驱动、人工回答）：40/40 完成，
RMSD vs expert 中位数 0.0051、均值 0.0218（`relax_new.xlsx`）。那是另一种模型和回答方式，只作量级参考，不是本实验的对照组。

## 2. d03 上已经就绪的东西

与 Sol27LC 共用同一仓库与环境（见 `rev_sol27lc/HANDOVER-d03.md` §2），本实验只新增 `rev_relax/`：

| 项 | 位置 / 状态 |
|---|---|
| 仓库 | `/home/xiazeyu/vasp_agent/newvaspagent`，已拉到含 `rev_relax/` 的最新提交（`776cdd5` 之后那个把 `reference/` 移出了仓库；d03 工作区里应该**没有** `rev_relax/reference/`，有就删掉）。d03 上 `rev_sol27lc/scripts/run_batch.sh` 与 `rev_sol27lc/protocol/CHANGELOG.md` 有 Sol27LC 会话留下的未提交改动，**不要动、不要 `git checkout`** |
| 拉代码 | 非交互 shell 不带代理：`git -c http.proxy=http://127.0.0.1:7890 pull --ff-only` |
| Python 环境 | `/home/xiazeyu/conda-envs/vaspagent`（Sol27LC 同一个） |
| agent 实际用的 CLI | claude-agent-sdk 0.2.110 自带的 `_bundled/claude` 2.1.191，d01/d03 相同（`~/.local/bin/claude` 自动升级不影响 agent） |
| `.env` / `site.env` / POTCAR / VASP | 与 Sol27LC 相同，已就绪 |
| 磁盘 | `/home` 剩 53 GB。每个体系大约 50–300 MB（WAVECAR/CHG 看 agent 设置），3 个 rep 估 10–30 GB。跑的过程中盯 `df -h /home`，低于 15 GB 就先删已完成体系的 `WAVECAR`/`CHG`/`CHGCAR` |

## 3. 开跑前的检查

d01 会话 2026-09-24 已在 d03 上跑过：包导入正常；端点 `直连上游 https://api.deepseek.com/anthropic model=deepseek-v4-flash-vision-exp [HTTP 200]`；
`vasp_std`/`vasp_gpu`/`mpirun` 都在 `~/software/vasp/...`；8 张卡全空。
**试跑**：TiC（15 原子）在 GPU 7 上跑了一遍 `runs_agent/pilot/TiC`，通过，见第 9 节。pilot 不计入 rep。

开跑前再过一遍（环境可能被别的会话动过）：

```bash
cd /home/xiazeyu/vasp_agent/newvaspagent
source ~/env_vasp && which vasp_std vasp_gpu mpirun
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader      # 除 5 以外应全空
export PATH=/home/xiazeyu/conda-envs/vaspagent/bin:$PATH
python -c "from dotenv import load_dotenv; load_dotenv('.env'); from src.litellm_proxy import resolve_llm_endpoint as r; print(r().describe())"
#   期望：直连上游 .../anthropic  model=deepseek-v4-flash-vision-exp。出现 bridge / litellm 字样就停
```

DeepSeek 余额：3 个 rep × 40 体系的 token 量比 Sol27LC 两个 rep 大得多，开跑前请主人确认余额；
中途出现 `upstream_failure` 先查余额/限流，不要盲目重启。

## 4. 正式跑法

三个 rep 排进同一个队列（按 rep 顺序：rep1 的 40 个排完再排 rep2……；同一 rep 内按历史耗时从长到短），
7 张卡始终有活干，rep 之间只在交界处重叠：

```bash
cd /home/xiazeyu/vasp_agent/newvaspagent/rev_relax
mkdir -p runs_agent audit
EXCLUDE_GPU_INDEX=5 nohup scripts/run_batch.sh rep1 rep2 rep3 > runs_agent/_batch.log 2>&1 < /dev/null &
nohup scripts/watch_loop.sh > audit/watch.log 2>&1 < /dev/null &        # 每 2 min 记一行
scripts/wait_until_done.sh "rep1 rep2 rep3" 86400                        # 阻塞等；有待答问题先返回
```

日常查看：`scripts/monitor.sh`（每个运行的状态/轮数/问答数/小时数）、`scripts/pending.sh`（待答问题）、`tail runs_agent/_batch.log`。

**只能起一个 `run_batch.sh`**，两个会抢卡。它会跳过已有 `run_meta.json`（不论状态）的体系，所以中断后重跑同一条命令即可续上。
**被中断的体系要从头来**：驱动拒绝在有旧尝试（`run_meta.json` 或 `driver.log`）的目录里开跑，
把它改名为 `runs_agent/<rep>/.<system>.crashed` 再重启批次。
停实验用 `scripts/stop_agent_arm.sh`（按 /proc 校验，别用 `pkill -f`）。

耗时：**unknown，只有粗估**。历史 rx 运行在 8 卡上合计 118 h VASP 墙钟（FeSe 19 h、Li4Ti5O12 16 h、SnSe 9 h……）；
单卡会慢，但本协议拒绝了收敛测试、agent 的参数也可能不同。按单卡比 8 卡慢 2–4 倍粗算，一个 rep 250–450 GPU·h，7 卡约 1.5–3 天，
三个 rep 约 5–9 天；24 h 上限封顶。rep1 跑完后用实际数字重估并告诉主人。

## 5. 作为"操作员"回答问题

问题出现在 `runs_agent/<rep>/<system>/PENDING_QUESTION.md`（`pending.sh` 会列出，文件头有规则建议的类别）。
回答：`echo '<答复>' > runs_agent/<rep>/<system>/OPERATOR_ANSWER.txt`。15 min 没人答由 `answer_script.py` 兜底。

只能用 `protocol/answering_policy.md` 里的原话：

| 问题 | 回答原话 |
|---|---|
| 要不要做 ENCUT/KSPACING 收敛测试（含“选 A/B”“是/否”） | `否，不需要收敛测试，直接进行结构优化。其余设置按你的判断执行。` |
| 放行 / 确认它自己提出的命令或数值 | `同意，请继续执行。` |
| 硬件 / 环境 / 用几块 GPU | `answer_script.py` 里 `HARDWARE` 的全文（1 卡、vasp_gpu、`--np 1 --gpu-per-task 1`） |
| 是否需要后续计算（电子结构、HSE……） | `不需要后续计算，结束当前任务。` |
| 结构从哪来（A 名称 / B mp-id / C POSCAR） | `C：已有 POSCAR，就是工作目录中的 POSCAR，请直接使用。` |
| 它没给方案就问参数（“ENCUT 用多少？”“要不要 DFT+U？”） | `请你自行判断并说明理由，然后继续执行。` |

**绝不主动给参数**（ENCUT、K 点、smearing、赝势变体、U 值、磁矩、IVDW、ISIF）。历史 SR 会话里操作员给过
`ENCUT=520、KSPACING=0.20`、`IVDW=12`、`不需要DFT+U` 这类话，本实验刻意不复现。
同一问题重复问：同样的答复（规则会自动加“别再问”）；三次后驱动停止（若磁盘上已完成则记 `completed`）。

## 6. 已知的坑

- **核对模型**：每个 `runs_agent/<rep>/<system>.log` 首行应是 `[llm] 直连上游 https://api.deepseek.com/anthropic model=deepseek-v4-flash-vision-exp`。不是就整批停。
- **上游拒绝**：`upstream_failure` 状态 = 余额/限流/网络。先查原因；恢复后按第 4 节把这些体系改名 `.crashed` 重跑。若一个 rep 里大量体系被上游打断，整 rep 隔离为 `repN_invalid_upstream` 重跑，并写进 CHANGELOG。
- **收敛测试被拒后 agent 用模板参数**：这是预期行为（历史 SR 会话同样如此）。`workflow-relax` 会把“未做系统收敛”写进 `INCAR_explanation.md`。
- **agent 自己不问就开跑收敛测试**：照录不改，事后 `collect_results.py` 的 `n_static_runs` / `convergence_report` 列会显示。
- **大体系超时**：Li7La3Zr2O12（95 原子）、FeSe、Li4Ti5O12、SnSe 最可能撞 24 h。**不要中途改预算**；状态记 `budget_exceeded`，驱动会停掉该目录里残留的 VASP；若之前已有收敛的松弛，`collect_results.py` 照样取结果并注明状态。
- **显存**：95 原子单卡 3090（24 GB）一般够；若出现 CUDA OOM，是 agent 的事（它会看到报错并调整），照录。
- **串扰**：同一 rep 的 40 个目录同在 `runs_agent/<rep>/` 下，前一个 rep 的目录也在旁边。按主人决定**只审计不阻止**（与 Sol27LC 一致）；跑完用 `scripts/crosstalk_audit.py` 统计。
- **找答案**：试跑里 agent 自己 `ls` 过 `rev_relax/reference`，所以专家参考已移出 d03。**不要把 `reference/`、`relax_new.xlsx` 的内容或 d01 的任何结果拷到 d03 上**。
  试跑里它还翻了 `rev_sol27lc/runs_agent/rep*/…/env_local.sh` 找 VASP 环境写法（审计里记为 `rev_sol27lc/repN`，与本实验的 rep 区分）。
  仓库根目录的 `relax.xlsx`/`relax_new.xlsx`（论文的能量/RMSD 表）和 git 历史仍在，`crosstalk_audit.py` 会统计 agent 碰这些的命令（`answer_source_reads`）。
- **skill 小 bug 不修**：`workflow-relax/scripts/analyze_result.py` 在 VASP 6.4.2 的 OUTCAR 上取不到最大力（返回 null），agent 会自己从 OUTCAR 读。skill 与 Sol27LC 一起冻结，不改。
- 其余（`pkill -f` 会杀到自己、一张卡别放两个体系、agent 单轮可长时间不回话）同 Sol27LC 交接文档 §6。

**原则**：rep 进行中不改 `protocol/`、`scripts/`、`.claude/skills/`。真被 bug 逼着改：在 `protocol/CHANGELOG.md` 末尾写明日期与影响，
受影响的运行整体隔离为 `runs_agent/repN_invalid_<原因>` 并从头重跑，不混用。

## 7. 跑完之后

```bash
cd /home/xiazeyu/vasp_agent/newvaspagent/rev_relax
export PATH=/home/xiazeyu/conda-envs/vaspagent/bin:$PATH
for r in rep1 rep2 rep3; do python scripts/check_flow.py runs_agent/$r/* > audit/check_flow_$r.txt; done
python scripts/collect_results.py --reps rep1,rep2,rep3 > audit/results.json   # 同时写 audit/results_rep1_rep2_rep3.csv
#   d03 上没有专家参考，rmsd_vs_expert / dV_pct / dE_meV_atom 为空（reference_missing=true），其余齐全
python scripts/rep_spread.py > audit/rep_spread.txt; python scripts/rep_spread.py --json > audit/rep_spread.json
#   rep 间 agent↔agent 的 RMSD 与体积散布不需要参考，d03 上就能出
for r in rep1 rep2 rep3; do python scripts/crosstalk_audit.py runs_agent/$r > audit/crosstalk_$r.txt; python scripts/crosstalk_audit.py runs_agent/$r --json > audit/crosstalk_$r.json; done
```

`rep_spread.py` 只把三个 rep 都 `completed` 的体系放进逐体系散布；**任何 rep 还在跑时出的汇总都作废**（Sol27LC 踩过：在跑的 Fe_bcc 看起来差 1.54%，跑完只差 0.078%）。

交回 d01：`runs_agent/rep1..3`（剔除 `WAVECAR`、`CHG`、`CHGCAR`，其余包括 `vasprun.xml` 照留）和 `audit/`，
放到 d01 `/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_relax/` 的对应位置（`rev_*/runs_agent`、`rev_*/audit` 已被 .gitignore 忽略）。
示例：`rsync -a --exclude WAVECAR --exclude 'CHG*' runs_agent audit <d01>:/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_relax/`。

d01 上补专家对比（在 d01 的会话里做）：`python scripts/collect_results.py --reps rep1,rep2,rep3 > audit/results.json && python scripts/rep_spread.py`。

汇报格式：先结果（每个 rep 的完成数、RMSD 中位数/均值、逐体系 rep 间最大 RMSD 与体积散布、参数选择在 rep 间是否一致），再方法，再细节；
没测到的写 unknown，不用先验补。

## 8. 文件索引

- `protocol/CHANGELOG.md` — 本实验与 Sol27LC 的全部差异及理由（论文里要披露）
- `protocol/answering_policy.md`、`protocol/answer_script.py` — 操作员规则（预注册）
- `scripts/run_agent_relax.py` — 单体系驱动；`scripts/launch_agent.sh` — 环境包装
- `scripts/run_batch.sh` — 多 rep 排队调度；`monitor.sh` / `pending.sh` / `wait_until_done.sh` / `watch_loop.sh` / `stop_agent_arm.sh`
- `scripts/check_flow.py`、`collect_results.py`、`rep_spread.py`、`crosstalk_audit.py` — 判定、汇总、散布、串扰
- `scripts/build_dataset.py` — 从 d01 的 `data/relax` 与 `vasp_benchmark_old/relax` 生成 `data/`（已提交）和 `reference/`（只在 d01，不提交）
- `data/launch_order.tsv` — 启动顺序（历史 8 卡耗时，长的先跑）

## 9. 试跑记录（pilot，2026-09-24，d01 会话在 d03 上跑）

`runs_agent/pilot/TiC`，GPU 7：`completed`，6.2 min，3 轮，0 个问题，首行 `[llm] 直连上游 https://api.deepseek.com/anthropic model=deepseek-v4-flash-vision-exp`。
agent 调了 `workflow-relax` → `run-vasp` → `potcar-policy`，选 Ti_pv + C（与专家相同）、ENCUT 520、KSPACING 0.20、ISMEAR 1/SIGMA 0.1、ISPIN 1、ISIF 3，
4 个离子步收敛；`check_flow.py` 判 `conformant`。在 d01 上对专家：RMSD 0.00028，体积 +0.04%（论文旧运行 TiC 为 0.0013）。
它没问收敛测试、也没做，报告里写明了“未做系统性收敛测试”。

试跑暴露的问题：agent 探索时 `ls` 了 `rev_relax/protocol` 与 `rev_relax/reference`（只看到文件名，没打开参考文件）→ 专家参考已移出 d03（见 CHANGELOG）。
pilot 目录保留作记录，不进任何统计（`collect_results.py` 用 `--reps rep1,rep2,rep3`）。
