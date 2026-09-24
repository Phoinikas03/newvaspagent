# Operator answering policy — SR repeated runs (pre-registered 2026-09-24)

Same mechanism as `rev_sol27lc/protocol/answering_policy.md`: the agent is run
interactively, every question is answered by the operator under the rules below
or, after 15 minutes, by the deterministic classifier in `answer_script.py`.
Every question and reply is recorded verbatim in `run_meta.json` (`qa`, with
`answered_by`) and `driver.log`. The rules are fixed before rep1 and not revised
while any rep is running.

The rules are derived from how the archived SR sessions (`runs/rx_*`, 41
materials, the runs behind the manuscript's SR numbers) were actually answered.
`answer_script.py` was checked by replaying the archived agent message before
each of the 209 archived operator replies: every convergence and follow-up
question lands in the category the archived operator answered it with. The 99
turns it leaves to `FALLBACK` are mostly the archived operator prodding status
messages (`继续`, `勿长阻塞 TaskOutput…`); the driver does not treat a status
message without a question in it as one (it waits with back-off instead), so
those do not reach the classifier.

## Historical answer categories, and what this experiment does with each

| Category | Representative archived answers | Replicated? |
|---|---|---|
| Hardware / environment | `使用8GPU并行计算`, `使用gpu vasp，source ~/env_vasp后调用vasp_std` | Yes, with the 1-GPU allocation (`HARDWARE`, same text as Sol27LC) |
| Convergence test? | `否`, `不需要`, `否，直接进行结构优化`, `跳过收敛测试，使用默认参数`, `B`（= 拒绝） | Yes: **declined** (`NO_CONVERGENCE`) |
| Generic advance / approval | `同意`, `执行命令`, `继续` | Yes (`CONSENT`) |
| Follow-up calculation? | `不需要后续计算，结束当前任务` | Yes (`NO_FOLLOWUP`) |
| Structure source (skill step 1) | not asked in the archive (the path was in the prompt) | Answered with the POSCAR already supplied |
| **Operator supplying parameters** | `…使用模板默认参数ENCUT=520、KSPACING=0.20…`; `建议添加vdW修正（IVDW=12）`; `不需要DFT+U修正` | **No** |

The convergence answer is the one place this policy differs from Sol27LC, where
the archived operators said `进行收敛测试`. Each policy follows its own archive.

## Rules

1. **Answer as the archived SR sessions did.** Go-aheads are granted, hardware
   questions are answered factually, the convergence test is declined, a
   follow-up calculation is declined, and commands or values the agent has itself
   proposed are approved without edits.
2. **Never originate a calculation parameter.** No ENCUT, k-spacing, smearing,
   POTCAR variant, DFT+U value, magnetic moment, vdW correction or ISIF that the
   agent has not proposed itself. Declining the convergence test names no value:
   the skill then tells the agent to use its template and to record that no
   convergence test was run.
3. **Open parameter questions** are answered `请你自行判断并说明理由，然后继续执行。`
4. **Several questions in one message** (the archive has "which GPUs? and a
   convergence test?") get each applicable reply, in the order asked.
5. **Repeats**: same reply plus a note not to ask again; after three identical
   questions the run stops as `stuck_qa_loop` (or `completed`, if the relaxation
   is already finished on disk).
6. **Timeout**: no operator reply within 15 minutes → the classifier answers.

A human operator answering by hand types the rule's reply text, nothing else.
