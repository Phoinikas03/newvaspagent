"""Pre-registered user-answer script for the SR (structure relaxation) agent arm.

Derived from rev_sol27lc/protocol/answer_script.py; the mechanism is the same
(regex rules, first match wins, no model in the loop) and so are the hardware,
consent and fallback wordings. What differs is taken from how the archived SR
sessions under runs/rx_* were actually answered (see answering_policy.md):

* the ENCUT/KSPACING convergence question is *declined* -- the archived SR
  operators said "否 / 不需要 / 跳过收敛测试" in every session that asked,
  whereas the Sol27LC operators said "进行收敛测试";
* "do you want any follow-up calculation?" is answered "no, finish";
* the workflow-relax skill's opening "how will you give me the structure
  (A name / B mp-id / C POSCAR)?" is answered with the POSCAR already supplied.

No reply ever names a calculation parameter value.
"""
import os as _os
import re

_VASP_BIN_DIR = _os.environ.get("VASP_BIN_DIR") or "/mnt/data_x4/vasp/vasp.6.4.2/bin"
_NCPU = _os.cpu_count() or 64
HARDWARE = f"""\
本机是单节点工作站，没有 Slurm / PBS 调度器。
CPU {_NCPU} 核；GPU 为 8 × NVIDIA RTX 3090（24 GB）。
VASP 6.4.2 为 GPU (OpenACC) 构建，vasp_gpu 与 vasp_std 都在 {_VASP_BIN_DIR}。
环境脚本：source ~/env_vasp（已包含 MKL、CUDA、NVIDIA HPC SDK 的 MPI 以及 VASP 的 PATH）。
使用 GPU 版 VASP，source ~/env_vasp 后调用 vasp_gpu。本任务已分配 1 块 GPU（CUDA_VISIBLE_DEVICES 已设好），请按 1 rank ↔ 1 GPU、--np 1 --gpu-per-task 1 使用。"""

# Archived SR wording: "否，直接进行结构优化" (rx_MgO), "不需要收敛测试" (rx_Ni,
# rx_Sr2RuO4, rx_TePb). The second sentence covers the combined questions the
# archive also shows (rx_LiCoO2: DFT+U? spin? convergence? in one message) --
# the agent's own proposals stand, the operator adds nothing.
NO_CONVERGENCE = "否，不需要收敛测试，直接进行结构优化。其余设置按你的判断执行。"
NO_FOLLOWUP = "不需要后续计算，结束当前任务。"
STRUCTURE_GIVEN = "C：已有 POSCAR，就是工作目录中的 POSCAR，请直接使用。"
CONSENT = "同意，请继续执行。"
FALLBACK = "请你自行判断并说明理由，然后继续执行。"

_COMMAND_TOKEN = re.compile(
    r"(vasp_runner\.py|quick_test\.py|mpirun|--dirs|--np\b|--gpu-per-task|"
    r"\.claude/skills/run-vasp)", re.I)
_CONFIRM_PHRASE = re.compile(
    r"(是否同意|是否确认|请确认|确认执行|是否执行|可以执行吗|是否开始|是否继续|是否提交|是否运行|请批准|"
    r"shall\s+i\s+proceed|do\s+you\s+approve|please\s+confirm)", re.I)
# "是否需要进行后续计算？" / "是否需要我继续进行其他计算？" (rx_Au, rx_MgB2, rx_Li4Ti5O12).
# Kept tight: a convergence question also says "需要多步静态计算…确保后续计算".
_FOLLOWUP_ASK = re.compile(
    r"((是否|需不需要|要不要|需要)(我)?(继续)?(进行|做)?.{0,4}(后续|进一步|其他|其它)的?(计算|分析)|"
    r"any\s+follow.?up|further\s+calculation)", re.I)
_CONVERGENCE_ASK = re.compile(
    r"(收敛测试|convergence\s*test|收敛扫描|完整收敛|收敛流程|"
    r"要不要.{0,12}收敛|需不需要.{0,12}收敛)", re.I)
# workflow-relax step 1: A 材料名称 / B mp-id / C 已有 POSCAR
_STRUCTURE_SOURCE_ASK = re.compile(
    r"(mp-?id|materials\s*project\s*id|已有\s*poscar|poscar.{0,10}路径|(属于|哪种).{0,10}情况)", re.I)
_HARDWARE_ASK = re.compile(
    r"(硬件|机器配置|几块\s*gpu|几张卡|gpu\s*数|多少.{0,4}gpu|空闲.{0,4}gpu|gpu.{0,6}空闲|"
    r"cpu\s*核|调度器|slurm|pbs|env_script|环境脚本|可执行文件|vasp_gpu|vasp_std|"
    r"module\s*load|环境变量)", re.I)

# A message quoting a concrete launch command is an execution-approval request
# even though the command line is full of protocol words; that rule always wins.
FIRST = ("command_confirmation",
         lambda t: bool(_COMMAND_TOKEN.search(t) and _CONFIRM_PHRASE.search(t)), CONSENT)
QUESTION_RULES = [
    ("followup_decline", _FOLLOWUP_ASK, NO_FOLLOWUP),
    ("convergence_decline", _CONVERGENCE_ASK, NO_CONVERGENCE),
    ("hardware_environment", _HARDWARE_ASK, HARDWARE),
    ("structure_source", _STRUCTURE_SOURCE_ASK, STRUCTURE_GIVEN),
    ("command_confirmation", _CONFIRM_PHRASE, CONSENT),
]


def classify(text: str):
    """Return (category, answer) for an agent message that awaits a reply.

    Only the tail is matched (the question is at the end; the body often has
    tables mentioning GPUs or the POSCAR path for other reasons). An archived
    message often asks several things at once ("which GPUs? and do you want a
    convergence test?", rx_Ni / rx_CoSb3); every question rule that matches
    contributes its reply, in the order the questions appear, as the archived
    operators answered them. The generic "please confirm" rule only answers
    when nothing more specific matched. Anything unmatched -- notably a bare
    "what ENCUT should I use?" -- gets FALLBACK, because the operator never
    originates a parameter.
    """
    tail = text[-900:]
    category, predicate, answer = FIRST
    if predicate(tail):
        return category, answer
    hits = []
    for category, pattern, answer in QUESTION_RULES:
        ends = [m.end() for m in pattern.finditer(tail)]
        if ends:
            hits.append((max(ends), category, answer))
    if len(hits) > 1:
        hits = [h for h in hits if h[1] != "command_confirmation"]
    # "Any follow-up calculation?" comes at the end of a final report, whose
    # body recaps convergence status; answering that part as well would read
    # as "go and relax again".
    followup = [h for h in hits if h[1] == "followup_decline"]
    if followup:
        hits = followup
    if not hits:
        return "fallback", FALLBACK
    hits.sort()
    return "+".join(h[1] for h in hits), "\n".join(h[2] for h in hits)
