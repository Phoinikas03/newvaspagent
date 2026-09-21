# Sol27LC 重复实验（rep2 / rep3）交接 — d03

写给在 d03 上开的监管 Claude Code 会话。写于 2026-09-22，由 d01 上的会话准备环境后交接。

## 1. 目标

在 **完全相同的配置** 下把 Sol27LC 的 agent 臂再跑两遍（`rep2`、`rep3`），
用于回复审稿意见 "Repeated-run reliability"（response_letter Reviewer Comment 1）：
量化同一配置下的 run-to-run 变异——完成数、MAE、逐体系晶格常数散布。

固定配置（与 d01 上 2026-09-08 的 `rep1` 相同，不得改动）：

| 项 | 值 |
|---|---|
| 模型 | `deepseek-v4-flash-vision-exp`，DeepSeek Anthropic 兼容端点直连（`mode=direct`，无协议桥） |
| 领域 skill | **启用**（`.claude/skills/` 全部 21 个，`setting_sources=["project"]`） |
| 任务规格 | T2：只给 POSCAR + 目标，不给任何参数（`run_agent_lc.py` 的 `TASK_PROMPT`） |
| 操作员回答 | `protocol/answer_script.py` 的预注册规则；人只按 `protocol/answering_policy.md` 回答 |
| 预算 | 每体系 6 h 墙钟、300 轮；1 体系 ↔ 1 GPU |
| 体系 | `data/` 下 27 个，`dataset.json` 为清单 |
| 完成判定 | `check_flow.py`：按磁盘产物判 `conformant` / `done_with_deviation` |

rep1 的结果基线（d01）：27/27 有晶格常数（其中 Au_fcc 状态 `budget_exceeded`，数据齐但撞了 6 h 上限），
MAE vs expert PBE 0.281%，最大偏差 W_bcc −0.98%。逐体系数字在 `audit/comparison.csv`（d01 上）。

## 2. d03 上已经就绪的东西

| 项 | 位置 / 状态 |
|---|---|
| 仓库 | `/home/xiazeyu/vasp_agent/newvaspagent`，`origin/main` @ `462e9d9`（2026-09-22 已把 rev_sol27lc 脚本改成按脚本位置定位路径） |
| Python 环境 | `/home/xiazeyu/conda-envs/vaspagent`（Python 3.12.14；包版本按 d01 `claude` 环境锁定，见 `rev_sol27lc/protocol/d01-claude-env-freeze.txt`） |
| 机器相关配置 | `<repo>/site.env`（未跟踪）：`VASPAGENT_CONDA_PREFIX`、`VASP_ENV_SCRIPT` |
| LLM / 工具密钥 | `<repo>/.env`（未跟踪，从 d01 拷贝，`PMG_VASP_PSP_DIR` 已改成 d03 路径） |
| POTCAR | `<repo>/POTCAR_dir/POT_GGA_PAW_PBE` → 软链到 `/home/xiazeyu/software/vasp/potentials/PBE`（与 d01 同一套 347 元素） |
| VASP | `~/software/vasp`（6.4.2 GPU 构建，从 d01 整体搬来，未重编译；`source ~/env_vasp`；主人 09-22 用 Si 单卡/双卡冒烟验证过，见 `~/software/vasp/validation/results.txt`） |
| GPU | 8 × RTX 3090，全部可用（d01 的 GPU 2/4 有掉卡史，d03 无此问题） |
| 磁盘 | 写 `/home`（58 GB 可用；每个 rep 约 2.5 GB）。**`/data` 已满，不要往那写** |
| 网络 | `~/.bashrc` 全局设了 `http(s)_proxy=http://127.0.0.1:7890`；DeepSeek 端点直连和走代理都通 |
| Claude Code CLI | `~/.local/bin/claude` 2.1.278（与 d01 相同） |

d03 与 d01 的差异只有：VASP 运行时通过 `~/software/vasp/env.sh` 重定位（HPC-X 的 Open MPI，MPI 环境变量 `OPAL_PREFIX` 由它设置）、机器名。
`answer_script.py` 的硬件回答措辞不变，只有 VASP bin 目录和 CPU 核数在运行时填入（d03 也是 64 核 / 8 × 3090）。

## 3. 开跑前的检查（每项都要真的跑一下）

d01 会话在 2026-09-22 00:50 前后已经在 d03 上跑过一遍下面的检查，结果：
包导入正常；端点探测 `直连上游 https://api.deepseek.com/anthropic model=deepseek-v4-flash-vision-exp [HTTP 200]`；
pymatgen 能从软链的库解析 `Ag` / `Fe_pv`；用 `vasp_runner.py --np 1 --exe vasp_gpu --gpu-per-task 1 --env-script ~/env_vasp`
在 GPU 7 上跑 `~/software/vasp/validation/si-1gpu` 的输入 19.5 s 完成，TOTEN = −9.20866026 eV，与主人的验证结果逐位一致。
pip 曾顺带装进 `pymatgen-core 2026.5.17`（d01 没有），已卸掉并把 `pymatgen 2025.10.7`、`pymatgen-io-validation 0.1.2` 按 d01 版本重装，`pip check` 干净。
开跑前仍建议再过一遍，环境可能被别的会话动过。

```bash
cd /home/xiazeyu/vasp_agent/newvaspagent
source ~/env_vasp && which vasp_std vasp_gpu mpirun     # 应在 ~/software/vasp/... 下
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader   # 8 张卡应全空
export PATH=/home/xiazeyu/conda-envs/vaspagent/bin:$PATH
python -c "import claude_agent_sdk, pymatgen, litellm, dotenv; print('imports ok')"
python -c "from dotenv import load_dotenv; load_dotenv('.env'); from src.litellm_proxy import resolve_llm_endpoint as r; print(r().describe())"
#   期望：mode=direct、model=deepseek-v4-flash-vision-exp。若出现 bridge / litellm 字样，停，见第 6 节
python -c "from src.tool import *" 2>&1 | tail -1     # 无 ImportError
```

然后做一次 **Si 试跑**（rep1 在 d01 上也先做了 Si pilot），验证 VASP 能通过 `vasp_runner.py` 在单卡上起来：

```bash
UUID=$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -1)
mkdir -p rev_sol27lc/runs_agent/pilot
nohup rev_sol27lc/scripts/launch_agent.sh --system Si_dia --gpu-uuid "$UUID" --rep pilot \
  > rev_sol27lc/runs_agent/pilot/Si_dia.log 2>&1 &
```

看 `runs_agent/pilot/Si_dia.log` 第一行 `[llm] ...` 确认 direct + deepseek；
看 `runs_agent/pilot/Si_dia/driver.log` 前几轮确认 agent 调用了 `Skill`（`workflow-eos-lattice-constant` / `workflow-convergence`），
并且第一次 VASP 在该卡上跑起来（`nvidia-smi` 有显存占用，工作目录里出现 `OUTCAR`）。
Si 在 rep1 用时约 24 min。试跑完成即可，**pilot 不计入 rep**。

## 4. 正式跑法

一次只跑一个 rep（`run_batch.sh` 自己按 GPU 空闲分配，两个批次同时跑会互相抢卡）：

```bash
cd /home/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc
mkdir -p runs_agent/rep2
nohup scripts/run_batch.sh agent rep2 > runs_agent/rep2/_batch_rep2.log 2>&1 &
nohup scripts/watch_loop.sh > audit/watch_rep2.log 2>&1 &      # 每 2 min 记一行进度
scripts/wait_until_done.sh rep2 27 43200                          # 阻塞等待；有待答问题会先返回
```

日常查看：`scripts/monitor.sh`（两臂状态）、`scripts/pending.sh`（待答问题）。
rep2 完成后同样起 rep3。估算：rep1 在 d01 上 27 体系合计 49.5 h GPU 时；8 卡并行，一个 rep 约 8–10 h 墙钟
（尾巴是 Au_fcc ≈ 6 h、Fe_bcc ≈ 6.9 h、Ni_fcc ≈ 4.5 h），两个 rep 合计约一天。

`run_batch.sh` 会跳过 `run_meta.json` 里已 `completed` 的体系，所以中断后重新执行同一条命令即可续跑；
但**被中断的那个体系会从头开始**（工作目录残留会让判定器混乱），续跑前把未完成体系的目录改名为 `.<system>.crashed` 再启动。

## 5. 作为"操作员"回答问题

agent 的问题会以 `runs_agent/<rep>/<system>/PENDING_QUESTION.md` 出现，`pending.sh` 会列出来。
回答方式：`echo '<答复>' > runs_agent/<rep>/<system>/OPERATOR_ANSWER.txt`。
15 min 没人答，`answer_script.py` 的规则会自动兜底（`answered_by` 会记录是谁答的）。

回答必须遵守 `protocol/answering_policy.md`，要点：

1. 放行类（要不要做收敛测试、要不要开始算、确认它自己提出的命令/数值）：同意，按 `answer_script.py` 里 `GO_AHEAD` / `CONSENT` 的原话。
2. 硬件类：如实答（`HARDWARE` 原话）。
3. **绝不主动给出任何计算参数**（ENCUT、K 点、smearing、赝势变体、体积窗口、点数、EOS 形式）。它没提方案就问"用多少"，一律答 `请你自行判断并说明理由，然后继续执行。`
4. 同一问题重复问：同样的答复加一句别再问；三次后驱动自动判 `stuck_qa_loop` 停止。

大多数体系在 rep1 里 0 个问题（`qa=0`），少数 1–2 个。

## 6. 已知的坑（都在 rep1 及无 skill 实验里踩过，详见 `protocol/CHANGELOG.md`）

- **跑在错误的模型上**：`.env` 只设 `LLM_*`；驱动已改为先 `resolve_llm_endpoint()` 再建客户端，并把解析到的模型写进 `run_meta.json`。仍要在每个 `<system>.log` 首行核对 `[llm] mode=direct ... deepseek-v4-flash-vision-exp`。若变成 bridge（litellm 协议桥），是 `LLM_API_BASE` 少了 `/anthropic` 后缀；桥在长对话下会 `400 malformed JSON`，整批作废。
- **上游拒绝不能耗预算**：驱动匹配到 `API Error:` / `usage limit` / `insufficient balance` 等即以 `upstream_failure` 结束。出现后先查 DeepSeek 余额/限流，不要盲目重启。
- **Au_fcc 撞 6 h 预算**：rep1 里数据全齐（5 ENCUT + 4 KSPACING + 12 EOS 点），只是没写出拟合 JSON。**不要中途改预算**（协议固定）；记录状态，事后用 `collect_results.py` 照样能提取晶格常数，报告时注明。
- **墙钟争用**：一张卡两个体系会让墙钟不可用。`run_batch.sh` 现在按驱动 PID 判空闲；不要手工往已占的卡上加体系。
- **别用 `pkill -f`**：会杀到自己。停实验用 `scripts/stop_agent_arm.sh`（按 /proc 校验）。
- **判定器依赖 skill 的目录约定**（`convergence_test/encut_test/e_*`、`scale_*`）。有 skill 时没问题；如果某体系产物命名怪异导致长期不判完成，看 `check_flow.py` 的分项输出再决定，不要改判定规则。
- 一次 agent 单轮可能做几十次 VASP、持续数小时不回话，这是正常的（驱动按 OUTCAR 指纹退避等待）。
- rep1 里 Cu_fcc 的 agent 把正常 SCF 过冲误诊为"逃逸"并用 `EDIFF=2e-3` 截断，结果碰巧没坏。这类行为**照录不改**，它就是被测对象。

**原则**：rep 进行中不改 `protocol/`、`scripts/`、`.claude/skills/`。真被 bug 逼着改，参照 rep1 的做法：
在 `CHANGELOG.md` 写明日期与影响，受影响的运行整体隔离为 `runs_agent/repN_invalid_<原因>` 并从头重跑，不混用。

## 7. 跑完之后

```bash
cd /home/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc
export PATH=/home/xiazeyu/conda-envs/vaspagent/bin:$PATH
for s in $(ls data | grep -v json); do python scripts/check_flow.py runs_agent/rep2/$s; done   # 逐体系流程符合性
python scripts/collect_results.py > audit/results_d03.json     # 两 rep 的 a、B0、R²、墙钟、参数
python scripts/compare.py                                        # 对 expert PBE / 实验值的误差表
```

（`collect_results.py` / `compare.py` 会扫描 `runs_agent/*`，d03 上只有 rep2/rep3 和 pilot；pilot 行要剔除。）

要交回 d01 的东西：`runs_agent/rep2`、`runs_agent/rep3`（可以剔除 `CHG*`、`WAVECAR`）、`audit/` 下新生成的文件，
放到 d01 的 `/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent/rev_sol27lc/` 对应位置（d01 上这些目录已被 .gitignore 忽略，不会进仓库）。
汇报格式：先结果（三个 rep 的完成数、MAE、逐体系最大 rep 间差），再方法，再细节；未测到的东西写 unknown，不用先验补。

## 8. 相关文件索引

- `protocol/answering_policy.md` — 操作员规则（预注册）
- `protocol/answer_script.py` — 兜底回答的确定性规则 + 硬件回答原文
- `protocol/CHANGELOG.md` — 对 agent 系统/驱动的所有改动及日期（要在论文里披露）
- `scripts/run_agent_lc.py` — 单体系驱动（提示词、预算、问答循环、状态判定）
- `scripts/run_batch.sh` — 27 体系按卡调度；`monitor.sh` / `pending.sh` / `wait_until_done.sh` / `watch_loop.sh` / `stop_agent_arm.sh`
- `scripts/check_flow.py`、`collect_results.py`、`compare.py` — 完成判定与汇总
- `../site.env.example` — 机器相关变量说明
