# SR repeated-run experiment — protocol and changes

Purpose: three independent runs (rep1–rep3) of the VASP Agent on the
manuscript's 40 SR (structure relaxation) systems with DeepSeek v4 + domain
skills, to quantify run-to-run variation (completion, RMSD vs expert, volume,
parameter choices), in the same way the Sol27LC replications did.

Every entry below is fixed before rep1 starts. Changes made while a rep is
running go at the end with a date and their effect, and affected runs are
quarantined as `runs_agent/repN_invalid_<reason>` and re-run from scratch.

## 2026-09-24 — protocol as registered

**Agent configuration: identical to Sol27LC rep1–rep3.** Model
`deepseek-v4-flash-vision-exp` via DeepSeek's Anthropic-compatible endpoint
(`mode=direct`, no bridge); all 21 project skills (`setting_sources=["project"]`);
same system-prompt rules (no AskUserQuestion, VASP only through
`vasp_runner.py`, POTCAR only through `setup_vasp_inputs`, one GPU, one rank);
same driver mechanics (upstream-failure abort, OUTCAR-fingerprint idle back-off,
repeated-question escalation, 15 min operator timeout). The driver
`scripts/run_agent_relax.py` is a copy of `rev_sol27lc/scripts/run_agent_lc.py`;
the differences are exactly the ones listed here.

**Inputs.** The 40 starting structures of the manuscript's SR task,
`data/relax/<MAT>` copied byte-for-byte (sha256 in `data/dataset.json`).
La2CuO4 is excluded, as in `relax_new.xlsx`: its expert relaxation never reached
ionic convergence. `Li10Ge(PS6)2` runs as `Li10GeP2S12` (same file; parentheses
in a directory name break unquoted shell commands).

**Reference (kept off the run machine).** `reference/<system>/CONTCAR` = final
structure of the expert relaxation in `vasp_benchmark_old/relax/<MAT>/relax` (Cr: the 2026-06-25
reference re-run), the same references as `relax_new.xlsx`. RMSD uses the same
matcher (`StructureMatcher(angle_tol=30).get_rms_dist()[0]`); replaying the
archived `rx_*`/`rxpv_*` runs through `scripts/collect_results.py` reproduces
the VASP Agent row of `relax_new.xlsx` RMSD_vs_expert for all 40 systems.
`reference/` is untracked and exists only on d01; RMSD, dV and dE are computed
there after the runs are copied back (see the pilot entry below for why).

**Task prompt (T2).** POSCAR + goal only: "结构优化（晶格与原子位置全松弛）",
PBE, run the relax workflow, report convergence / energy / max force / CONTCAR
path; no parameter named. The goal "全松弛" matches what the expert reference
computed (ISIF=3); a final run with ISIF≠3 is scored `done_with_deviation`.

**Operator answers.** `answering_policy.md` / `answer_script.py`, derived from
the archived SR sessions. Differs from Sol27LC in one decision: the
ENCUT/KSPACING convergence test is **declined** (every archived SR operator who
was asked declined; Sol27LC's archive accepted). `workflow-relax` asks before
running one, so under this policy no convergence sweep runs unless the agent
starts one without asking.

**Budget: 24 h wall clock per system (Sol27LC: 6 h), 300 rounds, 1 system : 1
GPU.** The SR systems are 15–95-atom vacancy supercells; the archived sessions
took up to 19 h (FeSe) on eight GPUs, five of them over 6 h. A 6 h cap on one
GPU would censor the same slow systems in every rep and measure the budget
rather than the agent. Chosen by the operator on 2026-09-24 before any run.

**Completion test** (`scripts/check_flow.py`, files on disk only): at least one
relaxation (NSW>0, IBRION 1/2/3) reached "reached required accuracy", ended
with VASP's timing block and left a CONTCAR, and no VASP process is running in
the workspace. The latest such relaxation is the result. Unlike an EOS fit, a
converged relaxation need not be the last step (the agent may re-relax from
CONTCAR), so a round that ends in a question is answered before completion is
declared; a final "any follow-up calculation?" gets `NO_FOLLOWUP` and the next
round ends the run. If the agent keeps asking after the run is finished on disk,
the repeat limit ends it as `completed` (with `completed_note`) rather than
`stuck_qa_loop`.

**Leftover VASP.** When the driver exits for any reason, VASP processes still
running inside that workspace are terminated (`killed_vasp_pids` in
`run_meta.json`). The scheduler hands the GPU to the next system the moment the
driver exits; without this a budget-exceeded run would keep the card busy and
spoil the next system's wall clock.

**Restarts.** The driver refuses a workspace that holds an earlier attempt
(`run_meta.json` or `driver.log` present); a crashed system is renamed to
`.<system>.crashed` and started from scratch, as in Sol27LC.

**Scheduling.** `run_batch.sh rep1 rep2 rep3` queues all 120 runs rep-major on
the GPUs left after `EXCLUDE_GPU_INDEX` (d03: GPU 5 excluded, 7 cards), longest
system first within a rep (`data/launch_order.tsv`, archived VASP minutes).
Reps overlap in time only at the boundaries. Nothing a run computes depends on
the card or the order.

**Cross-system and cross-rep reads: disclosed, not prevented**, as in Sol27LC
(operator decision 2026-09-24): the agent configuration stays identical to
Sol27LC. `scripts/crosstalk_audit.py` counts, per system, commands naming a
sibling system of the same rep and commands naming another rep (a same-system
read across reps would feed one rep's answer into another and is reported
separately).

## 2026-09-24 — pilot on d03 (TiC); expert references removed from the repository

Pilot `runs_agent/pilot/TiC` (not part of any rep): `completed` in 6.2 min,
3 rounds, no question asked, `mode=direct` on deepseek-v4-flash-vision-exp,
`check_flow.py` verdict `conformant`. The agent chose Ti_pv + C (as the expert
did), ENCUT 520, KSPACING 0.20, ISMEAR 1 / SIGMA 0.1, ISPIN 1, ISIF 3;
RMSD vs expert 0.00028, dV +0.04 %. It did not ask about a convergence test and
ran none, noting that in its report.

Found in the pilot: while exploring, the agent listed `rev_relax/protocol`,
`rev_relax/reference` and `reference/TiC/` (file names only; it did not open
the reference CONTCAR/INCAR). The first commit (776cdd5) had the expert
references in the repository, i.e. within reach of every run on d03. They are
now untracked (`.gitignore`) and absent from d03's working tree; the expert
energies moved from `data/dataset.json` to `reference/reference.json`.
`collect_results.py` leaves the comparison columns empty when `reference/` is
missing. The files remain in git history (776cdd5); `crosstalk_audit.py` now
also counts commands touching an answer source -- `reference`, the result
workbooks, the archived `rx_*` runs, `git log/show/...` -- per system.

The protocol files (`protocol/answer_script.py` etc.) stay readable to the
agent, as in Sol27LC; they carry no calculation parameter.

Also reported by the agent, not changed (the skills are frozen with the Sol27LC
configuration): `workflow-relax/scripts/analyze_result.py` does not parse the
max force from a VASP 6.4.2 OUTCAR and returns null; the agent extracted it from
the last TOTAL-FORCE block itself.
