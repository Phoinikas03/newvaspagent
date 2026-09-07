"""入口 / 出口钩子：让 skill 库的「查得到」和「存得下」不依赖模型自觉。

自演化闭环实测断在两头，两处都不是措辞问题，是结构问题：

- **入口**：会话初始化只把 skill 的**名字**交给模型（`skills: ['run-vasp', ...]`），
  没有 description。模型无从判断哪个 skill 覆盖当前任务；更糟的是「凡使用
  mpirun / vasp_gpu / vasp_runner.py 必须先加载 run-vasp」这条规则写在
  **run-vasp 自己的 description 里**——要求你加载它的规则藏在它内部，循环依赖。
  实测一次跑通完整声子工作流的会话，`Skill` 调用数为 0。
- **出口**：沉淀的触发条件是「任务完全结束」这一由模型自判的模糊状态，措辞又是
  `consider whether`。同一份 system prompt 里措辞为 `STRICTLY FORBIDDEN` 且挂在
  无条件时机上的 ANTI-SILENCE 规则被遵守 17/17，而沉淀规则 0/1。

所以入口把描述表拼进 system prompt 并要求落一份覆盖度判定，出口无条件压缩轨迹、
再据那份判定决定走路径 B（改进）还是路径 C（新建）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SKILL_COVERAGE_FILENAME = ".skill_coverage.json"
DIGEST_DIRNAME = ".distill_candidates"

# system prompt 里每条 description 的截断长度。整表约 20 条，控制在几 KB 量级。
_DESC_LIMIT = 240


# ---------------------------------------------------------------------------
# 入口：skill 目录扫描
# ---------------------------------------------------------------------------

def _parse_frontmatter(path: Path) -> dict[str, Any]:
    """读 SKILL.md 的 YAML frontmatter。解析不了就返回空 dict，不让单个坏文件中断启动。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        import yaml

        data = yaml.safe_load(text[3:end])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_skill_catalog(repo_root: Path | str) -> list[tuple[str, str]]:
    """扫 `.claude/skills/*/SKILL.md`，返回 [(name, description), ...]，按名字排序。

    name 取 frontmatter 的 `name`（缺失时回退到目录名）——两者可能不一致，而
    模型在 `Skill` 工具里必须用 frontmatter 的 name。
    """
    skills_dir = Path(repo_root) / ".claude" / "skills"
    catalog: list[tuple[str, str]] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        meta = _parse_frontmatter(skill_md)
        name = str(meta.get("name") or skill_md.parent.name).strip()
        desc = " ".join(str(meta.get("description") or "").split())
        if name:
            catalog.append((name, desc))
    return catalog


def format_skill_catalog(catalog: list[tuple[str, str]], limit: int = _DESC_LIMIT) -> str:
    """渲染成 system prompt 里的紧凑清单。"""
    if not catalog:
        return "(no project skills found)"
    lines = []
    for name, desc in catalog:
        if len(desc) > limit:
            desc = desc[:limit].rstrip() + "…"
        lines.append(f"- `{name}`: {desc}" if desc else f"- `{name}`")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 出口：覆盖度判定
# ---------------------------------------------------------------------------

def read_coverage(workspace: Path | str) -> dict[str, Any] | None:
    """读入口写下的覆盖度判定。没有或损坏都返回 None，交给调用方回退。"""
    path = Path(workspace) / SKILL_COVERAGE_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def skills_loaded_from_log(workspace: Path | str) -> list[str]:
    """从 log.jsonl 里数实际加载过的 skill。

    这是 `read_coverage` 的兜底：入口那条「写 .skill_coverage.json」的指令同样
    要靠模型执行，可能落空；而 `Skill` 工具调用是硬事实，一定在日志里。
    """
    from src.event_log import resolve_log_path

    try:
        log_path = resolve_log_path(Path(workspace))
    except Exception:
        return []
    names: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if obj.get("__type__") == "ToolUseBlock" and obj.get("name") == "Skill":
                skill = (obj.get("input") or {}).get("skill")
                if skill and skill not in names:
                    names.append(str(skill))
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    try:
        with log_path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("type") == "AssistantMessage":
                    walk(record.get("payload", {}))
    except OSError:
        return []
    return names


# ---------------------------------------------------------------------------
# 出口：现场扫描（客观事实，而非 agent 当时看过什么）
# ---------------------------------------------------------------------------
#
# digest 原本只由 log.jsonl 派生，也就是只装「agent 当时 grep 过什么」。计算跑完后
# 磁盘上还躺着大量它从没看过的证据：OUTCAR 里的原子数、实际 MPI 布局、生效的 NCORE、
# GPU 是否初始化、墙钟时间。缺了这些，「任务成功完成但用错了资源」这类静默低效在
# 蒸馏时完全不可见——失败清单只收 is_error，而这种情况根本没报错。
#
# 实测例子：同一次会话里 8 原子的 LEPSILON 跑了 1282 s，64 原子的力计算只用 425 s。
# 小体系比大体系慢 3 倍是个刺眼的异常，但两个数字都没进 digest。

#: 要在 OUTCAR 头部找的字段。不能用固定行窗口——同样是 MgO，力计算的 NIONS 在第
#: 544 行，而 LEPSILON 的在第 3960 行（DFPT 前面多打了大量 k 点信息）。所以扫到
#: 找齐为止，并用一个宽松上限兜底。
_HEADER_KEYS = ("NIONS", "mpi-ranks", "one band on NCORE", "GPUs detected")
_OUTCAR_SCAN_LINE_CAP = 30000
_OUTCAR_WARNING_LINES = 600  # 警告块在最前面，不必全程收集
_OUTCAR_TAIL_BYTES = 8192    # 墙钟时间在尾部


def _scan_outcar(path: Path) -> tuple[dict[str, str], list[str], list[str]]:
    """返回 (头部字段首次匹配, 警告行, 尾部行)。整份 OUTCAR 可能上百 MB，只扫必要部分。"""
    found: dict[str, str] = {}
    warnings: list[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for i, raw_line in enumerate(handle):
                if i >= _OUTCAR_SCAN_LINE_CAP:
                    break
                line = raw_line.rstrip("\n")
                for key in _HEADER_KEYS:
                    if key not in found and key in line:
                        found[key] = line.strip()
                if i < _OUTCAR_WARNING_LINES and ("fallback" in line.lower() or "WARNING" in line):
                    cleaned = line.strip(" |").strip()
                    if cleaned:
                        warnings.append(cleaned)
                if len(found) == len(_HEADER_KEYS) and i >= _OUTCAR_WARNING_LINES:
                    break
        size = path.stat().st_size
        with path.open("rb") as raw:
            raw.seek(max(0, size - _OUTCAR_TAIL_BYTES))
            tail = raw.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return found, warnings, []
    return found, warnings, tail


def _first_match(lines: list[str], needle: str) -> str | None:
    for line in lines:
        if needle in line:
            return line.strip()
    return None


def scan_vasp_runs(workspace: Path | str, limit: int = 40) -> list[dict[str, Any]]:
    """扫工作区里的 VASP 运行目录，收集资源使用的客观事实。"""
    workspace = Path(workspace)
    rows: list[dict[str, Any]] = []
    for outcar in sorted(workspace.rglob("OUTCAR"))[:limit]:
        found, warnings, tail = _scan_outcar(outcar)
        if not found and not tail:
            continue
        run_dir = outcar.parent
        row: dict[str, Any] = {"dir": str(run_dir.relative_to(workspace))}

        nions = found.get("NIONS")
        if nions:
            parts = nions.split()
            if parts and parts[-1].isdigit():
                row["atoms"] = int(parts[-1])

        ranks = found.get("mpi-ranks")
        if ranks:
            nums = [int(t) for t in ranks.replace(",", " ").split() if t.isdigit()]
            if len(nums) >= 2:
                row["ranks"], row["threads"] = nums[0], nums[1]

        ncore = found.get("one band on NCORE")
        if ncore:
            nums = [int(t) for t in ncore.replace("=", " ").split() if t.isdigit()]
            if nums:
                row["ncore_effective"] = nums[0]

        row["gpu_initialised"] = "GPUs detected" in found

        elapsed = _first_match(tail, "Elapsed time")
        if elapsed:
            try:
                row["elapsed_s"] = float(elapsed.split(":")[-1])
            except ValueError:
                pass

        # VASP 自己打的警告块——agent 从不看，但 VASP 已经把话说了。
        row["warnings"] = sorted(set(warnings))

        incar = run_dir / "INCAR"
        if incar.exists():
            try:
                text = incar.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            for tag in ("NCORE", "NPAR", "KPAR"):
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.upper().startswith(tag) and "=" in stripped:
                        value = stripped.split("=", 1)[1].split("#")[0].strip()
                        if value.isdigit():
                            row[f"{tag.lower()}_declared"] = int(value)
                        break

        state = run_dir / ".vasp_run_state.json"
        if state.exists():
            try:
                data = json.loads(state.read_text(encoding="utf-8"))
                for key in ("exe", "np", "gpu_per_task", "mode"):
                    if key in data:
                        row[key] = data[key]
            except (OSError, ValueError):
                pass

        rows.append(row)
    return rows


def resource_anomalies(rows: list[dict[str, Any]]) -> list[str]:
    """机械的一致性检查。

    只报「声明值 vs 实际值」和「内部不自洽」——不编码任何领域结论。目的是把线索
    摆到蒸馏的视野里，让模型自己去问「为什么」，而不是替它回答。
    """
    flags: list[str] = []

    # 1. 小体系比大体系还慢：与规模明显反向，通常意味着某一步没吃上该吃的资源。
    sized = [r for r in rows if r.get("atoms") and r.get("elapsed_s")]
    for small in sized:
        for big in sized:
            if small is big:
                continue
            if small["atoms"] < big["atoms"] and small["elapsed_s"] > big["elapsed_s"] * 1.5:
                flags.append(
                    f"`{small['dir']}`（{small['atoms']} 原子，{small['elapsed_s']:.0f} s）"
                    f"比 `{big['dir']}`（{big['atoms']} 原子，{big['elapsed_s']:.0f} s）慢，"
                    "体系更小却更耗时——查这一步是否用错了执行档或并行方式"
                )
                break

    # 2. INCAR 写了并行参数但没生效（单 rank 下 NCORE 分不出 core group 是典型情形）。
    for row in rows:
        declared = row.get("ncore_declared")
        effective = row.get("ncore_effective")
        if declared and effective and declared != effective:
            flags.append(
                f"`{row['dir']}`：INCAR 声明 NCORE={declared}，OUTCAR 实际生效 NCORE={effective}"
                f"（ranks={row.get('ranks', '?')}）——声明的并行参数没起作用"
            )

    # 3. 要了 GPU 却没有 GPU 初始化记录。
    for row in rows:
        exe = str(row.get("exe") or "")
        if "gpu" in exe.lower() and not row.get("gpu_initialised"):
            flags.append(f"`{row['dir']}`：以 `{exe}` 提交，但 OUTCAR 里没有 GPU 初始化记录")

    return flags


def format_resource_section(rows: list[dict[str, Any]]) -> str:
    """渲染「资源使用与异常」一节，插进 digest 供蒸馏参考。"""
    if not rows:
        return ""
    lines = ["## 资源使用（磁盘现场，非 agent 视野）", ""]
    lines.append("| 目录 | 原子数 | ranks×threads | NCORE 实际/声明 | exe | GPU 初始化 | 墙钟 |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in rows:
        ncore = f"{row.get('ncore_effective', '?')}/{row.get('ncore_declared', '—')}"
        ranks = f"{row.get('ranks', '?')}×{row.get('threads', '?')}"
        elapsed = f"{row['elapsed_s']:.0f} s" if row.get("elapsed_s") else "—"
        lines.append(
            f"| `{row['dir']}` | {row.get('atoms', '?')} | {ranks} | {ncore} | "
            f"{row.get('exe', '—')} | {'是' if row.get('gpu_initialised') else '否'} | {elapsed} |"
        )

    flags = resource_anomalies(rows)
    if flags:
        lines += ["", "### ⚠ 资源异常（值得在 skill 里写成预防性指令）", ""]
        lines += [f"{i}. {flag}" for i, flag in enumerate(flags, 1)]

    warnings = sorted({w for row in rows for w in row.get("warnings", [])})
    if warnings:
        lines += ["", "### VASP 自身警告（去重）", ""]
        lines += [f"- {w}" for w in warnings[:15]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 出口：轨迹捕获
# ---------------------------------------------------------------------------

def write_trajectory_digest(workspace: Path | str, repo_root: Path | str) -> tuple[Path, str, int]:
    """把本次会话压成 digest 落到候选池，返回 (路径, 一行摘要)。

    这一步**必须**在任何依赖模型的动作之前完成：沉淀可以推迟，轨迹丢了就没了。
    与 batch_runner 用同一个 extract_trajectory，产物进同一个候选池。
    """
    repo_root = Path(repo_root)
    workspace = Path(workspace)
    scripts_dir = repo_root / ".claude" / "skills" / "simple-skill-creator" / "scripts"
    for path in (repo_root, scripts_dir):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from extract_trajectory import extract, to_markdown  # type: ignore

    from src.event_log import resolve_log_path

    data = extract(resolve_log_path(workspace))
    digest_dir = repo_root / "runs" / DIGEST_DIRNAME
    digest_dir.mkdir(parents=True, exist_ok=True)

    # 现场扫描的结果插在「失败清单」之前：两者是互补的证据——失败清单是报了错的，
    # 资源表是没报错但可能做错的。
    try:
        resource_section = format_resource_section(scan_vasp_runs(workspace))
    except Exception:  # 扫描失败不应拖垮存档
        resource_section = ""

    def _with_resources(text: str) -> str:
        if not resource_section:
            return text
        marker = "## 失败清单"
        if marker in text:
            return text.replace(marker, resource_section + "\n" + marker, 1)
        return text + "\n" + resource_section

    out = digest_dir / f"{workspace.name}.md"
    out.write_text(_with_resources(to_markdown(data)), encoding="utf-8")
    # 同时落一份 --errors-only 精简版。完整 digest 对一次长会话可达 200 KB / 4 万
    # token，远超单次 Read 的上限，整份塞给模型会被截断甚至把上游请求撑坏；而
    # 「概览 + 失败清单」才是沉淀真正要用的部分，通常只有几 KB。
    errors_out = digest_dir / f"{workspace.name}.errors.md"
    errors_out.write_text(_with_resources(to_markdown(data, errors_only=True)), encoding="utf-8")

    totals = data.get("totals") if isinstance(data, dict) else None
    totals = totals if isinstance(totals, dict) else {}
    turns = int(totals.get("turns") or 0)
    summary = f"{out.stat().st_size // 1024} KB，{turns} 轮，{totals.get('errors', 0)} 处工具失败"
    return out, summary, turns


# ---------------------------------------------------------------------------
# 出口：沉淀指令
# ---------------------------------------------------------------------------

def build_consolidation_prompt(
    *,
    digest_path: Path,
    covered_by: list[str],
    coverage: dict[str, Any] | None,
    repo_root: Path | str,
) -> str:
    """拼出退出时投给 agent 的沉淀指令。

    有覆盖走路径 B（改进那些 skill），没覆盖走路径 C（新建）。两条路都要求
    **读 digest 而不是靠会话记忆**——长会话末端模型的回忆并不可靠，而 digest
    已经把失败清单挑出来了，正是沉淀最需要的输入。
    """
    task_type = str((coverage or {}).get("task_type") or "").strip()
    task_label = f"（{task_type}）" if task_type else ""
    errors_path = digest_path.with_suffix(".errors.md")
    head = (
        "本次任务已结束，现在执行 skill 沉淀。加载 `Skill: simple-skill-creator` 并遵循它的流程。\n\n"
        "**先读这个（几 KB，概览 + 失败清单）**："
        f"`{errors_path}`\n"
        "失败清单是所有 `is_error` 的工具返回，是沉淀的主要依据；每一条失败都应转化为"
        "一条预防性指令，并写清为什么。\n\n"
        f"**完整轨迹在**：`{digest_path}`。它可能有上百 KB、几万 token，"
        "**不要整份 Read**——那会被截断甚至撑坏请求。需要细节时用 `Grep` 按关键词定位，"
        "或用 `Read` 的 `offset`/`limit` 分页取你要的那一段。\n\n"
        "无论如何都要基于这两份文件写，不要凭会话记忆——长会话末端的回忆并不可靠。\n\n"
    )
    if covered_by:
        body = (
            f"**走路径 B（改进已有 skill）**：本次任务由 {', '.join('`%s`' % s for s in covered_by)} 覆盖。\n"
            "逐个判断它们在本次执行中哪里不够用——步骤缺失、边界情况没写、"
            "或者你不得不自行恢复的错误——把这些补进去。改完按路径 B 启动 diff_skill.py 交用户逐条审阅。\n"
        )
    else:
        body = (
            f"**走路径 C（从轨迹沉淀新 skill）**：本次任务{task_label}没有任何现成 skill 覆盖，"
            "你是靠组合脚本、查文献或自行摸索完成的。\n"
            "先判断这类任务是否会重复出现——只有会重复才值得沉淀，一次性请求造 skill 只会污染 skill 库。"
            "值得就起草新 skill，按路径 C 启动 diff_skill.py（省略 `--old`）交用户逐条审阅。\n"
        )
    tail = (
        f"\n无论哪条路，写入前都必须跑 `python {Path(repo_root)}/.claude/skills/"
        "simple-skill-creator/scripts/quick_validate.py <skill目录>` 验证格式，"
        "并且**不得**在用户审阅通过前直接改动 `.claude/skills/`。\n"
    )
    return head + body + tail


def describe_coverage(workspace: Path | str) -> tuple[list[str], dict[str, Any] | None, str]:
    """汇总覆盖度判定，返回 (走路径 B 时要改进的 skill, 原始判定, 给用户看的一行说明)。

    路径 B/C 只由 ``workflow_skill`` 决定——即「有没有一个 skill 描述了这**类**
    任务的整体流程」。这与 ``component_skills`` 是两件事：声子任务的每一个零件
    （弛豫、扩胞、INCAR、跑 VASP、查文献）都有 skill 覆盖，但整体流程没有，
    此时正确答案是新建而非改进。早期把两者混为一谈会把路径 C 误判成路径 B。
    """
    coverage = read_coverage(workspace)
    if isinstance(coverage, dict):
        workflow = coverage.get("workflow_skill")
        if isinstance(workflow, str) and workflow.strip() and workflow.strip().lower() != "null":
            name = workflow.strip()
            return [name], coverage, f"入口判定：本类任务由 `{name}` 整体覆盖 → 建议改进（路径 B）"
        if "workflow_skill" in coverage:
            components = coverage.get("component_skills")
            extra = ""
            if isinstance(components, list) and components:
                extra = f"（零件由 {', '.join(str(s) for s in components)} 覆盖，但整体流程没有）"
            return [], coverage, f"入口判定：无 skill 覆盖本类任务{extra} → 建议新建（路径 C）"

    # 入口没写判定或用的是旧格式——退回日志里的硬事实：实际加载过 skill 就当作
    # 有覆盖。这只是兜底，宁可保守地提议改进，也好过完全不提。
    actual = skills_loaded_from_log(workspace)
    if actual:
        return actual, coverage, f"无有效入口判定；日志显示加载过 {', '.join(actual)} → 建议改进（路径 B）"
    return [], coverage, "无入口判定，且日志中未加载过任何 skill → 建议新建（路径 C）"
