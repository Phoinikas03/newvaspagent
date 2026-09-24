#!/usr/bin/env python3
"""Quantify cross-system information flow inside one rep.

Copied from rev_sol27lc/audit/crosstalk_audit.py. The 40 systems of a rep run
concurrently under a shared parent directory, so an agent can read a sibling's
working directory. Because rev_relax queues its reps back to back, an agent can
also read *another rep's* run of the same or another system; those reads are
counted separately (cross_rep_reads) -- a same-system read across reps would
directly contaminate the repeatability measurement.

It also counts commands that go looking for an answer outside the run:
the expert references (kept off the run machine, but present in git history),
the manuscript's result workbooks, the archived rx_* runs, or git history
(answer_source_reads). This script records, per system,
every tool call whose command names another system of the same rep, and flags
the ones that touch a file carrying a calculation parameter (INCAR/OUTCAR/EOS
fit/convergence report). It reads logs only; it changes nothing.

Usage: crosstalk_audit.py <runs_agent/repN> [--json]
"""
from __future__ import annotations
import json, os, re, sys

ANSWER_SOURCE = re.compile(r"rev_relax/reference|(?<![\w-])reference(?=[/\s\"']|$)|vasp_benchmark|relax_new\.xlsx|"
                           r"relax\.xlsx|benchmark_summary|(?<![\w-])runs/rxp?v?_|(?<![\w-])rx_[A-Z]|"
                           r"git\s+(log|show|cat-file|rev-list|checkout|grep)|rev_relax/audit", re.I)
PHYS = re.compile(r"INCAR|ENCUT|KSPACING|SIGMA|ISMEAR|OUTCAR|OSZICAR|CONTCAR|"
                  r"LDAU|MAGMOM|POTCAR|Convergence_Report|INCAR_explanation", re.I)

def tool_inputs(obj):
    if isinstance(obj, dict):
        if (obj.get("__type__") or obj.get("type")) in ("ToolUseBlock", "tool_use"):
            yield obj.get("id"), json.dumps(obj.get("input", {}), ensure_ascii=False)
        for v in obj.values():
            yield from tool_inputs(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from tool_inputs(v)

def tool_results(obj):
    if isinstance(obj, dict):
        if (obj.get("__type__") or obj.get("type")) in ("ToolResultBlock", "tool_result"):
            yield obj.get("tool_use_id"), json.dumps(obj.get("content"), ensure_ascii=False)
        for v in obj.values():
            yield from tool_results(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from tool_results(v)

def audit(rep_dir: str) -> list[dict]:
    systems = sorted(d for d in os.listdir(rep_dir)
                     if os.path.isdir(os.path.join(rep_dir, d)))
    rows = []
    for s in systems:
        log = os.path.join(rep_dir, s, "log.jsonl")
        if not os.path.exists(log):
            continue
        sib = [d for d in systems if d != s]
        if not sib:
            continue
        # a sibling name used as a path component, absolute or relative to the rep dir
        pat = re.compile(r"(?<![A-Za-z_])(" + "|".join(map(re.escape, sib)) + r")/")
        own_rep = os.path.basename(os.path.normpath(rep_dir))
        xrep = re.compile(r"runs_agent/(?!" + re.escape(own_rep) + r"/)([^/\s\"']+)/|"
                          r"(?<![A-Za-z0-9_])(rep\d+)/")
        row = {"system": s, "reads": 0, "param_reads": 0, "siblings": set(), "events": [],
               "cross_rep_reads": 0, "cross_rep_same_system": 0, "cross_rep_events": [],
               "answer_source_reads": 0, "answer_source_events": []}
        results = {}
        pending = []
        for line in open(log, encoding="utf-8", errors="replace"):
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            payload = msg.get("payload", {})
            for tid, cmd in tool_inputs(payload):
                try:  # the free-text "description" field is not an access
                    probe = json.loads(cmd)
                    probe.pop("description", None)
                    probe = json.dumps(probe, ensure_ascii=False)
                except (ValueError, AttributeError):
                    probe = cmd
                if ANSWER_SOURCE.search(probe):
                    row["answer_source_reads"] += 1
                    row["answer_source_events"].append(cmd[:400])
                other = {a or b for a, b in xrep.findall(cmd)} - {own_rep}
                if other:
                    row["cross_rep_reads"] += 1
                    same = bool(re.search(r"(" + "|".join(map(re.escape, sorted(other))) + r")/"
                                          + re.escape(s) + r"(/|\b)", cmd))
                    row["cross_rep_same_system"] += int(same)
                    row["cross_rep_events"].append({"reps": sorted(other), "same_system": same,
                                                    "command": cmd[:400]})
                hit = pat.findall(cmd)
                if hit:
                    pending.append((tid, cmd, sorted(set(hit))))
            for tid, out in tool_results(payload):
                results[tid] = out
        for tid, cmd, hit in pending:
            row["reads"] += 1
            row["siblings"] |= set(hit)
            is_param = bool(PHYS.search(cmd))
            if is_param:
                row["param_reads"] += 1
            row["events"].append({
                "siblings": hit, "touches_parameter_file": is_param,
                "command": json.loads(cmd).get("command", cmd)[:400],
                "result_excerpt": re.sub(r"\\n", " ", results.get(tid, ""))[:400],
            })
        row["siblings"] = sorted(row["siblings"])
        rows.append(row)
    return rows

def main() -> None:
    rep = sys.argv[1]
    rows = audit(rep)
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    print(f"{'system':<10} {'sibling_reads':>13} {'param_reads':>12}  siblings_seen")
    print("-" * 64)
    for r in rows:
        if r["reads"]:
            print(f"{r['system']:<14} {r['reads']:>13} {r['param_reads']:>12}  "
                  f"{' '.join(r['siblings'])}")
    tot = sum(r["reads"] for r in rows)
    par = sum(r["param_reads"] for r in rows)
    n = sum(1 for r in rows if r["reads"])
    print("-" * 64)
    print(f"{n}/{len(rows)} systems read a sibling; {tot} reads, {par} touching a parameter file")
    xr = [r for r in rows if r["cross_rep_reads"]]
    print(f"{len(xr)}/{len(rows)} systems named another rep; "
          f"{sum(r['cross_rep_reads'] for r in rows)} commands, "
          f"{sum(r['cross_rep_same_system'] for r in rows)} on the same system")
    for r in xr:
        print(f"    {r['system']}: " + "; ".join(e["command"][:120] for e in r["cross_rep_events"][:3]))
    ar = [r for r in rows if r["answer_source_reads"]]
    print(f"{len(ar)}/{len(rows)} systems touched an answer source (reference/, workbooks, rx_* runs, git history); "
          f"{sum(r['answer_source_reads'] for r in rows)} commands")
    for r in ar:
        print(f"    {r['system']}: " + "; ".join(c[:140] for c in r["answer_source_events"][:3]))

if __name__ == "__main__":
    main()
