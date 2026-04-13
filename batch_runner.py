#!/usr/bin/env python3
"""批量 VASP Agent 运行器

用多进程池驱动 ClaudeSDKClient，对 data/relax 和 data/bandgap 下的材料
做结构优化和能带计算。每个 worker 绑定一块 GPU（CUDA_VISIBLE_DEVICES）。

用法示例：
    python batch_runner.py --gpus 0,1,2,3 --tasks relax bandgap
    python batch_runner.py --api-base http://127.0.0.1:43336   # LiteLLM 若随机端口须显式指定
    python batch_runner.py --gpus 0,1 --tasks relax --materials Al AlN
    python batch_runner.py --dry-run          # 只列出任务不执行

环境：启动前请 export ANTHROPIC_BASE_URL 与 litellm 监听一致；worker 内用 setdefault，不再强行覆盖为 4000。
"""

from __future__ import annotations

import os
import sys
import json
import time
import asyncio
import argparse
import multiprocessing as mp
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

DATA_ROOT = SCRIPT_DIR / "data"
LOG_DIR = SCRIPT_DIR / "logs" / "batch"
MAX_CONTINUATIONS = 15
TASK_TIMEOUT_SEC = 3600  # 1 hour per task

# ───────────────────────── prompt templates ──────────────────────────

RELAX_PROMPT = """\
请对材料 {material} 执行结构优化（structure relaxation）计算。

数据目录: {data_dir}
该目录中已有以下文件: POSCAR, KPOINTS, POTCAR, run_vasp.sh
你需要将该目录复制到/mnt/data_x3/xiazeyu/newvaspagent/runs/relax/{material}目录下

操作步骤：
1. 查看数据目录中的文件，确认 POSCAR、KPOINTS、POTCAR 存在
2. 该目录中没有 INCAR，请根据结构优化需求创建 INCAR 文件（推荐参数：IBRION=2, ISIF=3, NSW>=30, EDIFFG=-0.02, ENCUT 根据 POTCAR 选取合适值）
3. 在数据目录中执行 bash run_vasp.sh 来运行 VASP
4. VASP 完成后检查 OSZICAR 确认收敛
5. 运行 python get_energy.py 获取最终优化能量并报告

关键要求：
- 你必须一次性完成所有步骤，最终输出优化后的总能量数值
- 直接执行，不要向用户提问或等待确认
- 如果遇到错误，尝试诊断修复后重试
"""

BANDGAP_PROMPT = """\
请对材料 {material} 执行能带带隙（band gap）计算。

数据目录: {data_dir}
该目录中已有以下文件: POSCAR, KPOINTS, POTCAR, run_vasp.sh
你需要将该目录复制到/mnt/data_x3/xiazeyu/newvaspagent/runs/bandgap/{material}目录下

操作步骤：
1. 查看数据目录中的文件，确认 POSCAR、KPOINTS、POTCAR 存在
2. 该目录中没有 INCAR，请根据能带带隙计算需求创建 INCAR 文件（需使用HSE06杂化泛函，请合理调整HFSCREEN、AEXX、ALGO等参数）
3. 在数据目录中执行 bash run_vasp.sh 来运行 VASP
4. VASP 完成后检查 OSZICAR/OUTCAR 确认计算正常完成
5. 运行 python gap.py 获取带隙值并报告（包括带隙数值和类型）

关键要求：
- 你必须一次性完成所有步骤，最终输出带隙数值
- 直接执行，不要向用户提问或等待确认
- 如果遇到错误，尝试诊断修复后重试
"""

CONTINUE_PROMPT = "继续执行上述计算任务。请直接调用工具完成操作，不要重复描述计划。"


def _build_system_prompt(workspace: str, task_type: str) -> str:
    lines = [
        f"Your workspace directory is: {workspace}",
        f"All VASP input/output files should be read from and written to this directory.",
        "",
        "CRITICAL RULES:",
        "1. You MUST NOT use the AskUserQuestion tool. Never ask for confirmation.",
        "2. You MUST complete the entire computation in one session — create INCAR, "
        "run VASP, extract results. Do NOT stop after merely describing your plan.",
        "3. Prefer running `bash run_vasp.sh` in the data directory via Shell to launch VASP.",
        "",
    ]
    if task_type == "relax":
        lines.append("任务类型: 结构优化，目标是获得优化后总能量。")
    else:
        lines.append("任务类型: 能带带隙计算，目标是获得准确带隙值。")
    return "\n".join(lines)


# ───────────────────────── single task (async) ───────────────────────

async def run_single_task(
    task_type: str,
    material: str,
    data_dir: Path,
    log_path: Path,
    gpu_id: str,
    max_continuations: int,
) -> dict[str, Any]:
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR / ".env")

    from claude_agent_sdk import (
        create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient,
        AssistantMessage, ResultMessage, TextBlock,
    )
    from src.tool_wrapper import (
        poscar_tool, setup_vasp_inputs_tool,
        duckduckgo_search_tool, google_search_tool,
        visit_webpage_tool, arxiv_search_tool,
    )
    from src.result_message import result_message_indicates_failure

    workspace = str(data_dir)
    mcp_name = "vasp_agent"
    mcp_server = create_sdk_mcp_server(
        name=mcp_name,
        tools=[
            poscar_tool(workspace),
            setup_vasp_inputs_tool(workspace),
            duckduckgo_search_tool(),
            google_search_tool(),
            visit_webpage_tool(),
            arxiv_search_tool(),
        ],
    )
    options = ClaudeAgentOptions(
        cwd=workspace,
        setting_sources=["project"],
        permission_mode="bypassPermissions",
        system_prompt=_build_system_prompt(workspace, task_type),
        mcp_servers={mcp_name: mcp_server},
        allowed_tools=[
            "Skill",
            f"mcp__{mcp_name}__get_poscar_from_md",
            f"mcp__{mcp_name}__setup_vasp_inputs",
            f"mcp__{mcp_name}__duckduckgo_search",
            f"mcp__{mcp_name}__google_search",
            f"mcp__{mcp_name}__visit_webpage",
            f"mcp__{mcp_name}__arxiv_search",
        ],
    )

    template = RELAX_PROMPT if task_type == "relax" else BANDGAP_PROMPT
    initial_prompt = template.format(material=material, data_dir=data_dir)

    info: dict[str, Any] = {
        "task_type": task_type,
        "material": material,
        "data_dir": str(data_dir),
        "gpu": gpu_id,
        "status": "unknown",
        "total_turns": 0,
        "rounds": 0,
        "agent_text_tail": "",
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", encoding="utf-8")

    try:
        async with ClaudeSDKClient(options=options) as client:
            prompt = initial_prompt
            ever_had_tool_use = False

            for rnd in range(max_continuations + 1):
                info["rounds"] = rnd + 1
                log_file.write(f"\n{'='*60}\n=== Round {rnd}  prompt={'(initial)' if rnd == 0 else '(continue)'}\n{'='*60}\n")
                if rnd == 0:
                    log_file.write(prompt + "\n\n")
                log_file.write(
                    "\n--- 等待 LLM 响应（若长时间无下文，请检查 ANTHROPIC_BASE_URL 是否与 LiteLLM 端口一致）---\n"
                )
                log_file.flush()

                await client.query(prompt)

                round_tool_use = False
                round_texts: list[str] = []

                async for msg in client.receive_response():
                    log_file.write(repr(msg) + "\n")
                    log_file.flush()

                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                round_texts.append(block.text)
                            elif getattr(block, "type", None) == "tool_use":
                                round_tool_use = True

                    elif isinstance(msg, ResultMessage):
                        info["total_turns"] += msg.num_turns
                        if result_message_indicates_failure(msg):
                            info["status"] = "error"

                if round_tool_use:
                    ever_had_tool_use = True

                last_text = "\n".join(round_texts)
                info["agent_text_tail"] = last_text[-2000:]
                lt = last_text.lower()

                relax_kw = ["total energy", "总能量", "final energy",
                            "optimized total energy", "e0=", "ev"]
                bandgap_kw = ["band gap", "带隙", "bandgap", "band_gap", "ev"]

                has_result_kw = any(
                    k in lt for k in (relax_kw if task_type == "relax" else bandgap_kw)
                )

                # Round 0 一定要有 tool_use 才算完成；后续轮次只要关键词命中
                # 且本轮没有 tool_use（纯文本复读）就说明真的做完了
                done = False
                if has_result_kw and ever_had_tool_use:
                    done = True
                if has_result_kw and rnd > 0 and not round_tool_use:
                    done = True

                if done:
                    info["status"] = "completed"
                    break
                if info["status"] == "error":
                    break
                if rnd >= max_continuations:
                    info["status"] = "max_rounds"
                    break

                prompt = CONTINUE_PROMPT

    except Exception as exc:
        info["status"] = f"exception: {exc}"
        log_file.write(f"\nEXCEPTION: {exc}\n")
    finally:
        log_file.close()

    if info["status"] == "unknown":
        info["status"] = "completed"
    return info


# ───────────────────────── worker process ────────────────────────────

def _worker_entry(
    gpu_id: str,
    task_queue: mp.Queue,
    result_queue: mp.Queue,
    log_root: Path,
    max_continuations: int,
):
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_id
    # 须与 LiteLLM / 代理实际监听端口一致；启动 batch 前可 export ANTHROPIC_BASE_URL
    os.environ.setdefault("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-dummy-key")
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,0.0.0.0")

    tag = f"GPU-{gpu_id}"
    print(f"[{tag}] worker 启动", flush=True)

    while True:
        task = task_queue.get()
        if task is None:
            break

        task_type, material, data_dir = task
        label = f"{task_type}/{material}"
        log_path = log_root / f"gpu{gpu_id}" / f"{task_type}_{material}.txt"

        print(f"[{tag}] ▶ {label}", flush=True)
        t0 = time.monotonic()

        info = asyncio.run(
            run_single_task(task_type, material, data_dir, log_path, gpu_id, max_continuations)
        )
        elapsed = time.monotonic() - t0
        info["elapsed_sec"] = round(elapsed, 1)
        result_queue.put(info)

        sym = "✓" if info["status"] == "completed" else "✗"
        print(
            f"[{tag}] {sym} {label}  status={info['status']}  "
            f"turns={info['total_turns']}  rounds={info['rounds']}  "
            f"time={info['elapsed_sec']}s",
            flush=True,
        )

    print(f"[{tag}] worker 退出", flush=True)


# ───────────────────────── task discovery ────────────────────────────

def discover_tasks(
    data_root: Path,
    task_types: list[str],
    materials_filter: list[str] | None,
) -> list[tuple[str, str, Path]]:
    tasks = []
    for tt in task_types:
        task_dir = data_root / tt
        if not task_dir.is_dir():
            print(f"警告: 目录不存在 {task_dir}", file=sys.stderr)
            continue
        for d in sorted(task_dir.iterdir()):
            if not d.is_dir():
                continue
            if not (d / "POSCAR").exists():
                continue
            if materials_filter and d.name not in materials_filter:
                continue
            tasks.append((tt, d.name, d))
    return tasks


# ───────────────────────── main ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="批量 VASP Agent 运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python batch_runner.py --gpus 0,1,2,3\n"
               "  python batch_runner.py --api-base http://127.0.0.1:43336   # 与 LiteLLM 实际端口一致\n"
               "  python batch_runner.py --gpus 0 --tasks relax --materials Al AlN\n"
               "  python batch_runner.py --dry-run\n",
    )
    parser.add_argument(
        "--gpus",
        default=os.environ.get("CUDA_VISIBLE_DEVICES", "0"),
        help="GPU 编号列表，逗号分隔（默认读 CUDA_VISIBLE_DEVICES 或 '0'）",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=["relax", "bandgap"],
        default=["relax", "bandgap"],
        help="任务类型（默认两者都跑）",
    )
    parser.add_argument(
        "--materials",
        nargs="*",
        default=None,
        help="仅运行指定材料名（默认全部）",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DATA_ROOT,
        help=f"数据根目录（默认 {DATA_ROOT}）",
    )
    parser.add_argument(
        "--max-continuations",
        type=int,
        default=MAX_CONTINUATIONS,
        help=f"每个任务最大自动续接轮次（默认 {MAX_CONTINUATIONS}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出任务，不执行",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="覆盖 ANTHROPIC_BASE_URL（须与 litellm 监听地址一致，默认 env 或 http://127.0.0.1:4000）",
    )
    args = parser.parse_args()

    if args.api_base:
        os.environ["ANTHROPIC_BASE_URL"] = args.api_base.rstrip("/")

    gpu_list = [g.strip() for g in args.gpus.split(",") if g.strip()]
    if not gpu_list:
        print("错误：未指定任何 GPU", file=sys.stderr)
        sys.exit(1)

    all_tasks = discover_tasks(args.data_root, args.tasks, args.materials)
    if not all_tasks:
        print("未发现任何符合条件的任务", file=sys.stderr)
        sys.exit(1)

    print(f"共 {len(all_tasks)} 个任务，GPU: [{', '.join(gpu_list)}]  ({len(gpu_list)} workers)")
    for tt, mat, ddir in all_tasks:
        print(f"  {tt:>7s} / {mat:<20s}  {ddir}")

    if args.dry_run:
        print("\n(dry-run 模式，不执行)")
        return

    api_base = os.environ.get("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    print(f"ANTHROPIC_BASE_URL={api_base}  （须与 LiteLLM 终端里 Uvicorn 端口一致）")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_root = LOG_DIR / timestamp
    log_root.mkdir(parents=True, exist_ok=True)

    task_queue: mp.Queue = mp.Queue()
    result_queue: mp.Queue = mp.Queue()

    for t in all_tasks:
        task_queue.put(t)
    for _ in gpu_list:
        task_queue.put(None)

    workers: list[mp.Process] = []
    for gid in gpu_list:
        p = mp.Process(
            target=_worker_entry,
            args=(gid, task_queue, result_queue, log_root, args.max_continuations),
        )
        p.start()
        workers.append(p)

    for p in workers:
        p.join()

    results: list[dict] = []
    while not result_queue.empty():
        results.append(result_queue.get_nowait())

    summary_path = log_root / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    ok = sum(1 for r in results if r["status"] == "completed")
    err = len(results) - ok
    print(f"\n{'='*60}")
    print(f"全部完成  成功: {ok}  失败/未完成: {err}  共: {len(results)}")
    print(f"日志目录: {log_root}")
    print(f"汇总文件: {summary_path}")

    if err:
        print("\n失败任务：")
        for r in results:
            if r["status"] != "completed":
                print(f"  {r['task_type']}/{r['material']}  status={r['status']}")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
