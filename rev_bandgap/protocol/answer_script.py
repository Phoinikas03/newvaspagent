"""Pre-registered user-answer script for the agent arm.

The agent is driven interactively, but every reply it receives is produced by
the deterministic rules below -- regex matching only, no model in the loop --
so the whole session is reproducible and no calculation decision is handed to
the agent by its interlocutor.

Rules are evaluated top to bottom; the first match wins. A question that would
decide the physics ("should I run a convergence test?", "what ENCUT?") is
always answered with "you decide", even when it is phrased as a request for
approval -- otherwise a "yes" would silently transfer the protocol decision
from the agent to the operator.
"""
import re

HARDWARE = """\
本机是单节点工作站，没有 Slurm / PBS 调度器。
CPU 64 核；GPU 为 8 × NVIDIA RTX 3090（24 GB）。其中 GPU 2 存在降频问题，已从本任务的分配中排除。
VASP 6.4.2 为 GPU (OpenACC) 构建，vasp_gpu 与 vasp_std 都在 /mnt/data_x4/vasp/vasp.6.4.2/bin。
环境脚本：source ~/env_vasp（已包含 MKL、CUDA、NVIDIA HPC SDK 的 MPI 以及 VASP 的 PATH）。
本任务独占 7 块 GPU（CUDA_VISIBLE_DEVICES 已设好），同一时刻只有本材料在计算，可以按 1 rank ↔ 1 GPU
使用全部 7 块（例如 KPAR 与之对齐），也可以只用其中一部分，由你决定。"""

# Wording follows the archived sessions (see protocol/answering_policy.md).
GO_AHEAD = "进行收敛测试，执行完整的 ENCUT/KSPACING 收敛路径。"
CONSENT = "同意，请继续执行。"
# Used only when the agent asks for a parameter it has not itself proposed --
# the operator never originates a value.
FALLBACK = "请你自行判断并说明理由，然后继续执行。"

# A message quoting a concrete launch command is an execution-approval request,
# even though the command line itself is full of protocol words.
_COMMAND_TOKEN = re.compile(
    r"(vasp_runner\.py|quick_test\.py|mpirun|--dirs|--np\b|--gpu-per-task|"
    r"\.claude/skills/run-vasp)", re.I)
_CONFIRM_PHRASE = re.compile(
    r"(是否同意|是否确认|请确认|确认执行|是否执行|可以执行吗|是否开始|请批准|"
    r"shall\s+i\s+proceed|do\s+you\s+approve|please\s+confirm)", re.I)
# "shall I run a convergence test / which path do you want" -- a go-ahead
# question, answered affirmatively as in the archived sessions.
_CONVERGENCE_ASK = re.compile(
    r"(收敛测试|convergence\s*test|收敛扫描|完整收敛|收敛流程|选项\s*[ab]|"
    r"是否.{0,12}收敛|要不要.{0,12}收敛|需不需要.{0,12}收敛)", re.I)
_HARDWARE_ASK = re.compile(
    r"(硬件|机器配置|几块\s*gpu|几张卡|gpu\s*数|cpu\s*核|调度器|slurm|pbs|"
    r"env_script|环境脚本|可执行文件|vasp_gpu|vasp_std|module\s*load|环境变量)", re.I)

# (category, predicate, answer) -- first match wins.
RULES = [
    ("command_confirmation",
     lambda t: bool(_COMMAND_TOKEN.search(t) and _CONFIRM_PHRASE.search(t)), CONSENT),
    ("convergence_go_ahead", lambda t: bool(_CONVERGENCE_ASK.search(t)), GO_AHEAD),
    ("hardware_environment", lambda t: bool(_HARDWARE_ASK.search(t)), HARDWARE),
    ("command_confirmation", lambda t: bool(_CONFIRM_PHRASE.search(t)), CONSENT),
]


def classify(text: str):
    """Return (category, answer) for an agent message that awaits a reply.

    Anything unmatched -- notably a bare "what ENCUT should I use?" -- falls
    through to FALLBACK, because the operator never originates a parameter.
    """
    for category, predicate, answer in RULES:
        if predicate(text):
            return category, answer
    return "fallback", FALLBACK
