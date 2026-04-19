---
name: run-vasp
description: "环境与硬件感知下编排 VASP：探针 mpirun/vasp_std/vasp_gpu、STRICT HARDWARE ALIGNMENT（GPU 与 CPU 共存 / Slurm 分叉）、GPU 映射（通常 1 rank↔1 GPU）、ITERATIVE 分批调用 vasp_runner、执行前向用户展示完整命令并取得同意。凡在本工作区使用 mpirun、vasp_std、vasp_gpu、Slurm/PBS 提交或 vasp_runner.py 时必须加载本 skill；lattice_constant、relax、bandgap、adsorption_energy、literature、supercell 等材料类 skill 在真正启动 VASP 前也必须先加载本 skill。"
version: "1.0.3"
---

# Skill: Run VASP (Intelligent Orchestrator)

## 核心目标
作为高级计算科学助理，你的职责是安全、高效地编排 VASP 任务。在执行任何计算前，你必须感知所处环境，绝不能在未确认资源、**可执行依赖**与算力映射的情况下盲目执行耗时计算或 `mpirun`。

## 核心执行准则 (CRITICAL EXECUTION RULES)

### 1. 硬件对齐与 MPI 映射 (Hardware Alignment & MPI Mapping)

准备启动 VASP（无论经 `vasp_runner.py` 还是 Slurm/PBS 脚本内的命令）时，须遵循下列映射，**严禁**在未对齐硬件的前提下凭习惯使用过大 `-np`（例如不经询问默认 `-np 16` / `-np 64`）。

- **GPU 加速（OpenACC 等 GPU 构建）**
  - **缺省心智模型（务必牢记）**：在典型 GPU 环境下，**一块物理 GPU 对应一个（并发）VASP 任务**；每个任务独占一组可见设备，且 **`mpirun` 对该任务使用 `-n 1` 或 `-np 1`**，与「一卡一进程」对齐。**手写启动范式**：`CUDA_VISIBLE_DEVICES=i mpirun -n 1 <gpu_exe>`（或 `mpirun -np 1`；`i` 为设备索引，`0`、`1`、…）。多任务并发时依次为不同 `i` 各起一条上述命令（或由 `vasp_runner.py --gpu-per-task 1` 等价生成），**禁止**在单任务内对单卡使用 `-np`>1 除非用户明确要求多卡并行同一计算。
  - **映射规则**：通常 **1 个 MPI rank ↔ 1 块物理 GPU**（与 `vasp_runner.py` 的 `--gpu-per-task` 为各任务设置 `CUDA_VISIBLE_DEVICES` 一致；细节见 `references/orchestration.md` §3）。
  - **可执行文件名**：不少站点提供独立名 **`vasp_gpu`**；也有许多环境把 **GPU 版仍叫做 `vasp_std`**，或通过路径/模块区分（例如安装布局里的 **`vasp_std/gpu`**、`bin/gpu/vasp_std` 等）。**以用户模块与 `command -v` 为准**；`vasp_runner.py` 的 `--exe` 应填**实际会出现在 `mpirun … <exe>` 中的名字或 PATH 可解析名**。
  - **单任务单卡**：只跑一个任务且占用 1 卡 → **`mpirun -np 1`**，`<exe>` 为上述 **GPU 构建**入口；`np` 必须与该任务实际占用的 GPU 数一致。
  - **单任务多卡**：同一计算使用多块 GPU（例如 4 卡）→ **`mpirun -np 4`**（或与用户/站点约定的 GPU 绑定方式一致），`<exe>` 仍为 GPU 构建入口。
  - **多任务并发**：多个独立任务并行时，每任务宜 **每卡 `np=1`**，并用 **互斥的 `CUDA_VISIBLE_DEVICES`** 隔离（或由 `vasp_runner.py --gpu-per-task 1` 自动生成）。例如任务 A：`CUDA_VISIBLE_DEVICES=0 mpirun -np 1 <gpu_exe>`；任务 B：`CUDA_VISIBLE_DEVICES=1 mpirun -np 1 <gpu_exe>`（`<gpu_exe>` 可为 `vasp_gpu` 或站点上的 `vasp_std` 等）。禁止多任务无约束地争用同一 GPU。
- **纯 CPU（CPU-only 构建）**
  - 使用 **仅 CPU** 的 VASP 可执行文件时，为本任务预留的 **`-np`** 可与为该任务分配的 **物理核心数** 一致（或按站点策略略小于核心数以防过载）；仍须在 Step 2–3 中与用户确认，禁止默认定大核数。**勿**把「名为 `vasp_std`」自动当成纯 CPU——若该二进制实为 GPU 构建，仍按上文 GPU 映射与 `--gpu-per-task` 处理。

**可执行名与工具链**：`probe_env.py` 中的 `vasp_std_found` / `vasp_gpu_found` 只反映默认名是否在默认 PATH 下命中；**最终合法性以 `source env_script` 后** `vasp_runner.py` / `verify_local_dependencies` 能否找到 **`--exe` 所指可执行文件**为准。向用户确认命令时，应写出**真实**的 `<exe>`（无论是 `vasp_gpu` 还是 GPU 版 `vasp_std`）。

### 2. 强制命令确认审查 (Exact Command Confirmation)

在调用 `Bash` 或 `TaskOutput` **真正启动**计算前，**必须**停下并向用户展示：（1）Step 2 得到的**硬件与调度摘要**（CPU/GPU 数、是否登录节点、调度器类型等）；（2）你**最终采用的完整命令**（含 `source env_script`、`CUDA_VISIBLE_DEVICES` 若手写、`vasp_runner.py` 的完整参数行，或作业脚本中的 `mpirun` 行）。**仅当用户明确同意**（如「是 / 同意 / 确认」）后，方可执行。

*示例*：「探针显示共 8 块 GPU。当前收敛测试第一步采用单卡单任务。拟执行：`source ./template/env_local.sh && python .claude/skills/run_vasp/scripts/vasp_runner.py --dirs <dir> --mode local --np 1 --exe vasp_gpu --gpu-per-task 1 --env-script ./template/env_local.sh`（若站点 GPU 入口为 `vasp_std`，则将 `--exe vasp_std`）。是否同意？」

**与迭代工作流的关系**：命令确认针对**当前拟执行的这一步或这一批**；若上游 skill 要求逐点/逐目录核查，仍须遵守下文 Step 4 的 **ITERATIVE EXECUTION RULE**，**禁止**用「一次确认」覆盖随后无核查的多点排队。多任务本地并发优先用 `vasp_runner.py` 内置的 GPU 分配与日志，**不要**自写 monolithic `for`+`mpirun` 绕过 runner 与迭代规则。

---

## 工作流 (Workflow)

### Step 1: 意图识别 (Intent Recognition)
- 询问用户或分析 Prompt：这是正式的生产计算（Production），还是只是为了测试输入文件是否合法的快速验证（Pre-flight / Quick Test）？
- **如果属于快速试错**：先完成 Step 2 探针；若依赖满足，调用 `python .claude/skills/run_vasp/scripts/quick_test.py`（可配合 `--env-script`、`--exe`）。
- **如果是生产计算**：进入 Step 2。

### Step 2: 环境侦察 (Environment Probing)
- 运行探针：`python .claude/skills/run_vasp/scripts/probe_env.py`
- **与项目 system_prompt 对齐的补充探测**（探针未覆盖或需人工核对时）：
  - **优先**已跑 `probe_env.py`：调度器由 **`sbatch` / `qsub` 是否在 PATH** 判定（与脚本一致），**不依赖** `sinfo`/`qstat`。
  - 若再用 Bash 补充 `lscpu`、`nvidia-smi -L`、`hostname`：**禁止**把 `sinfo`/`qstat` 与上述命令用 **`&&`** 串成一条——裸机工作站上常无 `sinfo`，会导致整条命令失败（如 exit 127），并可能拖累同轮**并行**的其它工具（「Sibling tool call errored」）。
  - 若需 Slurm/PBS 详情：仅当 `command -v sinfo` / `command -v qstat` 成功后再执行（如 `sinfo -N`）；否则跳过。稳妥的一行示例：`lscpu; nvidia-smi -L 2>/dev/null || true; hostname; command -v sinfo >/dev/null && sinfo -N || true`
- 分析 JSON 输出，至少关注：
  - **资源与调度**：`cpu_cores_total`、`gpu_info`、`scheduler`（`slurm` / `pbs` / `none`）、`is_login_node`
  - **可执行依赖（主动排雷）**：`dependencies` 对象
    - `mpirun_found`
    - `vasp_std_found`
    - `vasp_gpu_found`

**依赖红线（必须在策略阶段处理，禁止盲目执行）：**
- 若计划 **仅 CPU**、且 `--exe` 为 **`vasp_std`（或默认 `vasp_std`）** 并**未**启用 GPU 映射（无 `--gpu-per-task`，且用户确认该二进制为 CPU-only 构建），而 `mpirun_found` 或 `vasp_std_found` 为 `false`：**不得**直接执行 `vasp_runner.py --mode local` 或 `quick_test.py`。必须在 Step 3 中向用户说明缺失项，询问应使用的 `module load`、`export PATH` 或其它初始化方式，将约定写入 **`template/env_local.sh`**（或工作区内的专用 `env_script`），经用户确认后再执行，并在命令行传入 `--env-script`。
- 若计划 **GPU 加速**：在 `source env_script` 之后必须能解析 **`--exe` 所选的 GPU 构建可执行文件**（常见为 `vasp_gpu`，或为站点提供的 GPU 版 `vasp_std` / `vasp_std/gpu` 等）。若探针仅显示 `vasp_std_found` 而 `vasp_gpu_found` 为 `false`，**不要**据此断定无 GPU 版——以用户模块说明与 `command -v` 为准；若仍无法解析，在 Step 3 中补齐 `env_script` 后再跑。
- **Slurm 特例**：登录节点上 `dependencies` 可能全为 `false`，但计算节点上已有模块——允许生成作业脚本并在脚本内 `source` 用户提供的 env；策略中必须写清「依赖在计算节点加载」，并避免在登录节点执行本地 `mpirun`。

**STRICT HARDWARE ALIGNMENT（硬性分叉询问，与 system_prompt 一致）：**
- 若 **同时探测到 GPU 与 CPU**（例如 `gpu_info.has_gpu` 且 CPU 核心数明显可用）：**禁止**在未询问的情况下默认走纯 CPU 多核 `mpirun`。**必须**停下并向用户明确提问：希望 **GPU 加速**（可执行名可能是 `vasp_gpu` 或站点上的 GPU 版 `vasp_std` 等）还是 **仅用 CPU**？若用 GPU，需要几张/如何绑定？
- 若探测到 **Slurm 或 PBS**：**禁止**用本地 `mpirun` 代替集群提交。**必须**向用户索要：目标 partition/queue、节点数、作业时限等，再写入 `sbatch`/PBS 脚本。

### Step 3: 策略制定 (Strategy formulation)
根据探针结果和待计算的目录数量，向用户推荐策略，并**显式核对依赖、硬性分叉结论与登录节点规则**（参见 `references/orchestration.md`）。策略中须写明 **MPI 进程数与 CPU/GPU 的对应关系**（见上文「核心执行准则 §1」），并准备好将在 Step 4 经 **§2 强制命令确认** 展示给用户的完整命令草稿。
- **场景 1 (胖节点裸机多任务)**：无 Slurm，资源充足，且 Step 2 中（或在 `source env_script` 后）依赖已满足，且用户已确认 **CPU-only 或 GPU** 方案。推荐使用 `vasp_runner.py` 的 `--mode local`，为每个目录分配合适的 `--np`，GPU 方案下设置 **`--gpu-per-task`** 且 **`--exe`** 为站点实际的 GPU 入口（`vasp_gpu` 或 GPU 版 `vasp_std` 等），并通过 `--env-script` 传入已确认的 env 文件。
- **场景 2 (HPC 集群)**：存在 Slurm，且处于登录节点。**严禁**在登录节点执行本地 `mpirun`。推荐使用 `--mode slurm` 生成并提交作业；脚本内包含 `source env_script` 与用户约定的 `mpirun` 命令；partition/时限等须来自用户明确回复。
- **场景 3 (GPU 工作站)**：存在 GPU。多任务时可用 `--gpu-per-task` 与用户确认的 **`--exe`（`vasp_gpu` 或 GPU 版 `vasp_std` 等）**；须与用户确认的 GPU 偏好及 Step 2 依赖红线一致。

**若 `dependencies` 显示所需可执行文件不可用（且不属于「仅计算节点有模块」的已说明情形）**：必须在推荐策略中主动询问用户需要加载的 module 或环境变量，并写入执行策略的 **env_script**；**绝不能**在未解决前直接执行本地 VASP。

### Step 4: 执行与追踪 (Execution & Tracking)
- 与用户确认策略与 **env_script** 后，先完成 **「核心执行准则 §2」**：展示硬件摘要与**完整拟执行命令**（或作业脚本内 `mpirun` 片段），**取得用户明确同意**，再通过 Bash 调用 `python .claude/skills/run_vasp/scripts/vasp_runner.py`（传入 `--dirs`、`--mode`、`--np`、`--exe`、`--env-script`、`--gpu-per-task` 等）或提交 Slurm/PBS。
- **`vasp_runner` 已启动后的等待方式（与仓库 system_prompt 一致）：** Bash 必须使用 **`run_in_background: true`**。**禁止**用 **`TaskOutput` + `block: true` + 超长 `timeout`** 单次阻塞到 VASP 结束（会冻结 Web/IDE）。须在仍由你亲自轮询直至完成的前提下，使用 **`TaskOutput` + `block: false`** 反复查询同一 `task_id`，或多次**短时** Bash（各 `--dirs` 目录 `OUTCAR` 终态、`pgrep` 等）；完成后再读日志与做下游检查。
- 告知用户日志路径；Slurm 场景用 `squeue -u $USER` 等帮助追踪队列状态。
- **与项目 ITERATIVE EXECUTION RULE 对齐**：若上游 skill 要求**逐点**收敛（多 ENCUT/K 点）或**逐目录**核查（如多个 `scale_*`），**禁止**单次 `vasp_runner.py --dirs` 把全部点或全部目录一次性排队跑完而不在中间读 OUTCAR/日志；应分多次调用（或每批少量目录），每步确认后再继续。

### 输出疑为截断/损坏时（与 bandgap 等上游 skill 对齐，强制）

在读取 `vasprun.xml`、`OUTCAR` 做后处理或决定重跑前：

1. **先**用 Bash 确认**无**仍在运行的 VASP / `mpirun … vasp` 进程（见上文 Step 4 轮询方式）；若有进程，**不得**认定文件为最终态，**不得**删文件或重跑。
2. 仅在确认无进程后，再判断是否需修正输入并重跑。
3. **默认**对将废弃或覆盖的文件使用 **`mv` 重命名/迁入备份目录**，**禁止**默认 `rm`。
4. 再次启动 `vasp_runner` 前，须**用户明确同意**，或用户已声明的**自动重试策略**；**禁止**无确认自动重跑。

上游若已载入 **`bandgap`**，详细条文以 **`bandgap/SKILL.md` 中「输出完整性：疑为截断/损坏时」** 为准；本段为编排层最低要求。

---

## 依赖缺失时的安全防线（与项目 system_prompt 对齐）

当环境中缺少 `mpirun` 或所选 VASP 可执行文件时，按下列链路处理，避免死循环或胡乱重试：

1. **执行阶段**  
   Agent 通过 Bash 运行 `scripts/vasp_runner.py` 或 `quick_test.py` 时，底层会执行类似 `mpirun -np … vasp_std` 的命令。若可执行文件不在 PATH，shell 会报 `bash: mpirun: command not found` 或 `bash: vasp_std: command not found`。

2. **脚本捕获**  
   `vasp_runner.py` / `quick_test.py` 在本地流程中会先校验依赖（若提供 `--env-script` 则在 `source` 之后校验）；失败时向 **stderr** 打印以 **`ERROR:`** 开头的说明，并以**非零退出码**退出。该输出随 Bash 工具结果完整返回给 Agent。

3. **system_prompt 强制规则**  
   一旦从工具输出中看到 **`command not found`** 或 **`ModuleNotFoundError`**，必须遵守全局规则：**不要**用通用 `Read` 工具去碰二进制文件（如 PDF）来逃避问题；**应**向用户报告缺失的依赖并请求指示。

4. **挂起并向用户说明**  
   本回合用纯文本收尾（符合 CRITICAL INTERACTION RULE / END OF TURN），**停止**继续自动重试 VASP 链，直至用户给出环境信息。示例：  
   *「在尝试执行 VASP 时失败：系统提示 `mpirun`（或 `vasp_std`）command not found，通常表示尚未加载并行环境或 VASP 未在 PATH 中。是否需要我根据您的环境修改 `template/env_local.sh`（或工作区 env 脚本），加入 `module load` 或 `export PATH`？」*

---

## 进阶：从被动报错到主动排雷
优先在 **Step 2** 根据 `probe_env.py` 的 `dependencies` 拦截问题，再进入 Step 3–4，可显著减少失败次数。细节见 `references/orchestration.md`。

## 参考文件
- `references/orchestration.md`：登录节点禁忌、内存、GPU 与依赖探测
- `template/env_local.sh`：本地/交互环境初始化模板（取消注释并填写 `module load` 等）
- `template/job_slurm.sh`：Slurm 模板占位符说明
