#!/usr/bin/env python
"""VASP Agent arm of the Sol27LC end-to-end baseline.

Deliberately separate from batch_runner.py: that script produced the numbers
already in the manuscript and its prompts hand the agent its INCAR parameters,
which is exactly what this experiment must not do.

Task specification here is "T2": the agent is given a POSCAR and the goal, and
nothing else -- no ENCUT, no k-spacing, no smearing, no strain window. It may
ask questions; every reply comes from the pre-registered deterministic script
in protocol/answer_script.py, never from a model.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path("/mnt/data_x3/xiazeyu/vasp_agent/newvaspagent")
EXP = REPO / "rev_sol27lc"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(EXP / "protocol"))

DEFAULT_BUDGET_SEC = 6 * 3600
# The flash model yields in short turns; rounds are not the budget, wall time is.
MAX_ROUNDS = 300

# NOTE: an earlier version ended with "计算方案与所有计算参数由你自行决定", and the
# agent quoted exactly that line as its reason to skip the convergence sweep and
# pick ENCUT by eye. The wording below keeps the T2 specification -- the operator
# supplies no parameters -- without licensing the workflow's steps to be dropped.
TASK_PROMPT = """\
请计算工作目录中 POSCAR 所描述结构的平衡晶格常数。

工作目录: {workspace}
结构文件: {workspace}/POSCAR

要求：
- 使用 PBE 泛函。
- 按 lattice_constant 工作流**完整**执行，不要省略其中的步骤。
- 最终请明确报告平衡晶格常数（单位 Å）。

我不会为你指定任何计算参数（ENCUT、K 点、smearing、赝势变体、体积采样窗口等）。
这些参数应当由工作流本身确定，而不是凭经验直接取一个稳妥值。
"""


def build_system_prompt(workspace: str) -> str:
    return "\n".join(
        [
            f"Your workspace directory is: {workspace}",
            "All VASP input/output files should be read from and written to this directory.",
            "",
            f"Repository root (skills and everything under `.claude/`): {REPO}",
            "The shell cwd for Bash is the workspace above, which is **not** the repository "
            "root. Any Bash that runs a skill script MUST either be prefixed with "
            f'`cd "{REPO}" && ...` or use an absolute path starting with `{REPO}/`.',
            "",
            "CRITICAL RULES:",
            "1. Do NOT use the AskUserQuestion tool. If you need a decision or information "
            "from the user, print the question as plain text and stop generating; the "
            "user will reply in the terminal. This matches the skill instructions for "
            "non-GUI environments.",
            "2. Launch VASP through `python .claude/skills/run-vasp/scripts/vasp_runner.py` "
            "(with the cd/absolute-path rule above). Do NOT hand-write raw `mpirun`.",
            "3. Generate POTCAR only through `setup_vasp_inputs`; for per-volume "
            "subdirectories pass its `work_dir` argument rather than building POTCAR by hand.",
            "4. This task has been allocated exactly one GPU; CUDA_VISIBLE_DEVICES is "
            "already set for you. Use 1 MPI rank bound to that one GPU.",
            "",
            "任务类型: 平衡晶格常数计算。所有计算参数由你自行决定。",
        ]
    )


def looks_finished(workspace: Path) -> bool:
    """Completion is decided by files on disk, never by what the agent says.

    An earlier version accepted a text match, and a round in which the agent was
    merely *describing its plan* ("Report a_eq (A), B0, fit quality...") ended the
    run after four minutes with nothing computed.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_flow import check

    res = check(str(workspace))
    return res["verdict"] in ("conformant", "done_with_deviation")


def block_is_tool_use(block) -> bool:
    """The SDK yields ToolUseBlock instances; they carry no ``.type`` attribute."""
    return type(block).__name__ in ("ToolUseBlock", "ToolResultBlock") or (
        getattr(block, "type", None) == "tool_use"
    )


ESCALATION = [
    "",
    "\n\n（提示：这类问题已经回答过一次，请不要重复询问，直接按你的判断继续执行。）",
    "\n\n（提示：请立即继续执行计算，不要再提出同类问题。）",
]
STUCK_LIMIT = len(ESCALATION)

ASK_POLL_SEC = 20
ASK_TIMEOUT_SEC = 900  # after this the rule-based fallback answers, so a run
                       # never deadlocks waiting for the operator


UPSTREAM_FAILURE = re.compile(
    r"(hit your session limit|usage limit|rate.?limit|quota exceeded|"
    r"insufficient balance|invalid api key|authentication.?error|"
    r"upstream (error|timeout)|502 bad gateway|503 service unavailable|"
    r"api error:|malformed json|connection error|overloaded)", re.I)


def progress_fingerprint(workspace: Path) -> tuple:
    """Cheap signature of how much output exists, to tell work from waiting."""
    total = 0
    count = 0
    for path in workspace.rglob("OUTCAR"):
        try:
            total += path.stat().st_size
        except OSError:
            continue
        count += 1
    return count, total


# When the agent is waiting for VASP it answers every "please continue" with
# another status paragraph. Prodding it on a tight loop burned the round budget
# and grew the context until the upstream rejected the request, so an unchanged
# workspace now buys a wait instead of another prompt.
IDLE_BACKOFF_SEC = [30, 60, 120, 240, 300]


def awaits_reply(text: str) -> bool:
    """Whether a tool-free round is actually a question for the operator.

    The agent also emits pure status lines ("Waiting for e_400 to complete")
    with no tool call. Treating those as questions parks the run for the full
    operator timeout, so only text that actually asks something is escalated.
    """
    tail = text[-600:]
    if "?" in tail or "？" in tail:
        return True
    return bool(re.search(
        r"(是否同意|是否确认|请确认|确认执行|是否执行|请批准|请选择|选项\s*[ABab]|"
        r"请回复|等待.{0,6}回复|shall\s+i|do\s+you\s+approve|please\s+confirm|"
        r"let\s+me\s+know)", tail, re.I))


def _normalize(text: str) -> str:
    """Collapse a question to a shape that ignores volatile detail."""
    return re.sub(r"[\s\d.,;:!?()\[\]{}\-_/\\]+", "", text)[-400:]


def ask_operator(outdir: Path, round_idx: int, question: str, fallback: str,
                 fallback_category: str, transcript) -> tuple[str, str]:
    """Surface a question to the operator and wait for a written reply.

    The operator answers under the policy in protocol/answering_policy.md.
    If nobody answers within ASK_TIMEOUT_SEC the deterministic reply from
    answer_script.py is used instead, so an unattended run still finishes.
    """
    pending = outdir / "PENDING_QUESTION.md"
    answer_file = outdir / "OPERATOR_ANSWER.txt"
    if answer_file.exists():
        answer_file.unlink()
    pending.write_text(
        f"# round {round_idx}\n"
        f"# suggested category: {fallback_category}\n"
        f"# write the reply into OPERATOR_ANSWER.txt in this directory\n\n"
        f"{question}\n"
    )
    transcript.write(f"\n=== round {round_idx} WAITING FOR OPERATOR ===\n")
    transcript.flush()

    waited = 0
    while waited < ASK_TIMEOUT_SEC:
        if answer_file.exists():
            text = answer_file.read_text().strip()
            if text:
                pending.unlink(missing_ok=True)
                return "operator", text
        time.sleep(ASK_POLL_SEC)
        waited += ASK_POLL_SEC
    pending.unlink(missing_ok=True)
    return f"fallback_timeout:{fallback_category}", fallback


async def run_one(system: str, gpu_uuid: str, outdir: Path, budget_sec: int) -> dict:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    # The Claude Agent SDK talks Anthropic protocol over ANTHROPIC_BASE_URL.
    # Loading .env only sets LLM_*, so without this call the SDK silently falls
    # back to the machine's own Claude credentials -- which is what happened on
    # the first rep1 attempt: every run was labelled deepseek and actually ran on
    # Claude until the account hit its session limit. The bridge this starts
    # lives in this process, so it must outlive the client below.
    from src.litellm_proxy import resolve_llm_endpoint

    endpoint = resolve_llm_endpoint()
    print(f"[llm] {endpoint.describe()}", flush=True)
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_uuid
    os.environ["OMP_NUM_THREADS"] = "1"

    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        create_sdk_mcp_server,
    )
    from src.tool_wrapper import (
        arxiv_search_tool,
        duckduckgo_search_tool,
        google_search_tool,
        setup_vasp_inputs_tool,
        visit_webpage_tool,
    )
    from src.event_log import EventLogWriter
    from answer_script import classify

    outdir.mkdir(parents=True, exist_ok=True)
    workspace = str(outdir)
    mcp_name = "vasp_agent"
    server = create_sdk_mcp_server(
        name=mcp_name,
        tools=[
            setup_vasp_inputs_tool(workspace),
            duckduckgo_search_tool(),
            google_search_tool(),
            visit_webpage_tool(),
            arxiv_search_tool(),
        ],
    )
    options = ClaudeAgentOptions(
        cwd=workspace,
        model=os.environ.get("CLAUDE_CODE_MODEL") or None,
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt=build_system_prompt(workspace),
        mcp_servers={mcp_name: server},
        allowed_tools=[
            "Skill",
            f"mcp__{mcp_name}__setup_vasp_inputs",
            f"mcp__{mcp_name}__duckduckgo_search",
            f"mcp__{mcp_name}__google_search",
            f"mcp__{mcp_name}__visit_webpage",
            f"mcp__{mcp_name}__arxiv_search",
        ],
    )

    info = {
        "system": system,
        "gpu_uuid": gpu_uuid,
        "model": getattr(endpoint, "model", None),
        "llm_mode": getattr(endpoint, "mode", None),
        "llm_base_url": os.environ.get("ANTHROPIC_BASE_URL"),
        "llm_upstream": os.environ.get("LLM_API_BASE"),
        "workspace": workspace,
        "budget_sec": budget_sec,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rounds": 0,
        "total_turns": 0,
        "status": "unknown",
        "qa": [],
    }
    started = time.time()
    event_log = EventLogWriter.open_for_workspace(outdir)
    transcript = open(outdir / "driver.log", "w", encoding="utf-8")

    try:
        async with ClaudeSDKClient(options=options) as client:
            prompt = TASK_PROMPT.format(workspace=workspace)
            asked_shapes: list[tuple[str, str]] = []
            last_fingerprint = progress_fingerprint(outdir)
            idle_rounds = 0
            for rnd in range(MAX_ROUNDS):
                info["rounds"] = rnd + 1
                if time.time() - started > budget_sec:
                    info["status"] = "budget_exceeded"
                    break

                transcript.write(f"\n{'='*70}\n=== round {rnd} USER ===\n{prompt}\n")
                transcript.flush()
                event_log.append_user_turn(prompt)
                await client.query(prompt)

                texts, had_tool_use = [], False
                async for msg in client.receive_response():
                    event_log.append_sdk_message(msg)
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                texts.append(block.text)
                            elif block_is_tool_use(block):
                                had_tool_use = True
                    elif isinstance(msg, ResultMessage):
                        info["total_turns"] += msg.num_turns

                last_text = "\n".join(texts)
                if not had_tool_use and UPSTREAM_FAILURE.search(last_text):
                    # No amount of "please continue" fixes an upstream refusal;
                    # stop now so the failure is visible and the run is re-runnable.
                    info["status"] = "upstream_failure"
                    info["upstream_message"] = last_text.strip()[:300]
                    transcript.write(f"\n=== round {rnd} ABORT: upstream failure ===\n{last_text[:300]}\n")
                    break
                transcript.write(f"\n=== round {rnd} AGENT (tool_use={had_tool_use}) ===\n{last_text}\n")
                transcript.flush()

                if looks_finished(outdir):
                    info["status"] = "completed"
                    break

                # No tool call this round means the agent stopped to ask something.
                if not had_tool_use and awaits_reply(last_text):
                    category, answer = classify(last_text)
                    shape = (category, _normalize(last_text))
                    repeats = sum(1 for s_ in asked_shapes if s_ == shape)
                    asked_shapes.append(shape)
                    if repeats >= STUCK_LIMIT:
                        # The agent is asking the same thing in a loop; a scripted
                        # reply is not going to break it, so stop and say so
                        # rather than burn the remaining budget.
                        info["status"] = "stuck_qa_loop"
                        info["stuck_category"] = category
                        transcript.write(
                            f"\n=== round {rnd} ABORT: same question asked "
                            f"{repeats + 1}x [{category}] ===\n"
                        )
                        break
                    rule_answer = answer + ESCALATION[repeats]
                    source, answer = ask_operator(
                        outdir, rnd, last_text, rule_answer, category, transcript
                    )
                    info["qa"].append(
                        {"round": rnd, "category": category, "repeats": repeats,
                         "answered_by": source,
                         "question": last_text[-1200:], "answer": answer}
                    )
                    transcript.write(
                        f"\n=== round {rnd} REPLY [{category}] by={source} "
                        f"repeat={repeats} ===\n{answer}\n"
                    )
                    prompt = answer
                else:
                    fingerprint = progress_fingerprint(outdir)
                    if fingerprint == last_fingerprint:
                        idle_rounds += 1
                        wait = IDLE_BACKOFF_SEC[min(idle_rounds - 1, len(IDLE_BACKOFF_SEC) - 1)]
                        transcript.write(
                            f"\n=== round {rnd} NO PROGRESS (idle {idle_rounds}), "
                            f"waiting {wait}s before prompting again ===\n"
                        )
                        transcript.flush()
                        time.sleep(wait)
                    else:
                        idle_rounds = 0
                        last_fingerprint = fingerprint
                    prompt = "继续执行上述计算任务。请直接调用工具完成操作，不要重复描述计划。"
            else:
                info["status"] = "max_rounds"
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed silently
        info["status"] = f"exception: {type(exc).__name__}: {exc}"
        transcript.write(f"\nEXCEPTION: {exc}\n")
    finally:
        transcript.close()
        event_log.close()

    info["wall_seconds"] = round(time.time() - started, 1)
    info["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (outdir / "run_meta.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    return info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--rep", default="rep1")
    parser.add_argument("--budget-sec", type=int, default=DEFAULT_BUDGET_SEC)
    args = parser.parse_args()

    outdir = EXP / "runs_agent" / args.rep / args.system
    outdir.mkdir(parents=True, exist_ok=True)
    src = EXP / "data" / args.system / "POSCAR"
    (outdir / "POSCAR").write_text(src.read_text())

    info = asyncio.run(run_one(args.system, args.gpu_uuid, outdir, args.budget_sec))
    print(json.dumps(info, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
