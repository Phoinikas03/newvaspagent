# Changes made to the agent system for the revision experiment

Disclosed here because they alter agent behaviour relative to the runs archived
under `runs/`, which produced the numbers in the submitted manuscript.

## 2026-09-08 — `run-vasp`: honour an inherited GPU allocation

`vasp_runner.py` computed each task's GPU as `task_idx * gpu_per_task` counting
from physical index 0 and wrote that into `CUDA_VISIBLE_DEVICES`, overwriting any
allocation the caller had already made. Running N single-directory tasks in
parallel, one per GPU, therefore put all N on GPU 0.

Fix: `inherited_visible_devices()` / `allocate_gpu_tokens()` allocate from the
caller's `CUDA_VISIBLE_DEVICES` when it is set (indices or `GPU-<uuid>` alike),
and the flex scheduler — which picks by physical index from `nvidia-smi` — is
bypassed in that case. Behaviour is unchanged when the variable is not set.

Found by the agent itself during the Si pilot: it read the runner source, saw the
override, and worked around it with `--gpu-per-task 0`. Reproducibility should
not depend on the agent rediscovering this each run.

## 2026-09-08 — `workflow-convergence` / `workflow-eos-lattice-constant`: convergence testing is default-on

Both skills previously gated the ENCUT/KSPACING sweep behind explicit user
consent ("用户确认（总闸）… 未经用户明确同意，不得启动"), with skipping as the
documented fallback when no consent arrived. In the Si pilot the agent took that
branch and picked ENCUT=520 by judgement, quoting the task prompt's "参数由你自行决定".
The archived `runs/lc_*` sessions show the same mechanism from the other side:
convergence testing happened because the operator volunteered `进行收敛测试` in
essentially every session.

Change: the sweep now runs by default. The agent announces the cost rather than
asking permission, and may skip only on an explicit request or a valid existing
`Convergence_Report.md` — in which case it must write `CONVERGENCE_SKIPPED.md`
and say so next to the result. "The task says parameters are up to you" is
explicitly ruled out as a reason to skip.

**Effect on what can be claimed.** After this change, a per-system convergence
test is a guarantee of the workflow, not an autonomous decision by the model. The
comparison with atomate2 remains meaningful — atomate2's input set carries fixed
values and never converges anything — but the claim must be phrased as a property
of the workflow, and this modification (and its date) must be disclosed.

## 2026-09-08 — task prompt wording

The agent arm's prompt ended with "计算方案与所有计算参数由你自行决定", which the
agent read as licence to drop workflow steps. Replaced with wording that still
supplies no parameters but requires the workflow to be run in full.

## 2026-09-08 — driver and batch fixes during the rep1 run

* `run_agent_lc.py`: a patch slice had deleted `ESCALATION`, `_normalize`,
  `ask_operator` and the ask/timeout constants while leaving their call sites.
  Runs that reached the question path died with `NameError`. Two systems were
  affected (`C_dia`, `Au_fcc`); both were re-run from scratch, and the crashed
  workspaces are kept as `.C_dia.crashed` / `.Au_fcc.crashed`.
* `run_batch.sh`: GPUs were assigned as `index % parallel`, so when run times
  were uneven a later system landed on a GPU whose earlier occupant was still
  running. Ag_fcc/Ge_dia shared GPU 0 and Al_fcc/Ir_fcc shared GPU 1 for part of
  rep1 while two GPUs sat idle. Assignment now polls for a genuinely idle GPU.
  **Wall times for those four systems in rep1 are contended and must not be used
  in the cost comparison**; they are re-measured before the numbers are reported.

## 2026-09-08 — rep1 discarded: the agent arm was not running on the configured model

`run_agent_lc.py` loaded `.env` (which sets `LLM_API_BASE` / `LLM_API_KEY` /
`LLM_MODEL`) but never called `resolve_llm_endpoint()`. The Claude Agent SDK
speaks Anthropic protocol over `ANTHROPIC_BASE_URL`; with that unset it fell back
to the machine's own Claude credentials. `api.deepseek.com` does not implement
`/v1/messages` (probe returns 404), so the project's resolver normally starts an
in-process protocol bridge — that step was missing.

Consequences: the Si pilot and the six "completed" rep1 systems ran on Claude,
not on `deepseek-v4-flash-vision-exp`, while `run_meta.json` reported the latter
because it echoed `.env`. The Claude account then hit its session limit, and
twelve further systems burned the whole 300-round budget replaying
"You've hit your session limit" (~165 s each, no tool calls).

Actions: the whole attempt is quarantined as `runs_agent/rep1_invalid_wrong_model`
and re-run from scratch. `run_agent_lc.py` now resolves the endpoint before
creating the client, records the *resolved* model / mode / base URL rather than
the `.env` value, and aborts a run with status `upstream_failure` when the
upstream refuses, instead of spending the round budget on it.

## 2026-09-08 — `.env` upstream URL corrected; the protocol bridge was never needed

`LLM_API_BASE` was `https://api.deepseek.com`, but DeepSeek serves its
Anthropic-compatible API under `/anthropic`. `POST /v1/messages` on the root
returns 404, so `resolve_llm_endpoint()` concluded the upstream did not speak
Anthropic and started the in-process litellm bridge. The bridge worked for short
sessions and then began returning `API Error: 400 malformed JSON body` once a
conversation grew long; eleven systems spent their whole 300-round budget
replaying that message.

`LLM_API_BASE` is now `https://api.deepseek.com/anthropic` (verified: HTTP 200,
`mode=direct`, no bridge). Original file kept as
`.env.bak_20260908_before_anthropic_base`.

The bridged attempt is quarantined as `runs_agent/rep1_invalid_bridge`. Its ten
completed systems are *not* reused: mixing a translated and a direct transport
inside one arm is an inconsistency that would be hard to defend, and re-running
them costs about an hour.

Two driver changes came out of the same failure:

* `UPSTREAM_FAILURE` now also matches `API Error:`, `malformed JSON`,
  `connection error` and `overloaded`, so an upstream refusal ends the run
  instead of consuming the round budget.
* The driver used to answer every agent turn with "please continue" immediately.
  While the agent waits for VASP it replies with another status paragraph, so the
  loop burned rounds and grew the context until the upstream rejected the
  request. The workspace is now fingerprinted (OUTCAR count and total size); an
  unchanged fingerprint buys a wait (30/60/120/240/300 s) instead of a prompt.
