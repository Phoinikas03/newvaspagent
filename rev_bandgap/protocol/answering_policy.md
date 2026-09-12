# Operator answering policy (pre-registered)

VASP Agent is positioned as a tool for *partially specified, interactive* VASP
tasks, so the agent arm is run interactively and the operator answers its
questions. The rules below are derived from how the archived Sol27LC sessions
under `runs/lc_*` were actually answered (97 logged user turns), not invented for
this experiment. They are fixed before the first run and are not revised in
response to how any run is going. Every question and reply is recorded verbatim
in `run_meta.json` (`qa`) and `driver.log` and released as supplementary material.

## Historical answer categories, and what this experiment does with each

| Category | Representative logged answers | Replicated? |
|---|---|---|
| Hardware / environment | `使用gpu vasp，source ~/env_vasp后调用vasp_std` | Yes, adapted to the 1-GPU allocation |
| Go-ahead for convergence testing | `进行收敛测试`, `做收敛测试`, `选项A，执行完整收敛测试`, `是` | Yes |
| Generic advance / approval | `开始`, `启动`, `执行`, `继续`, `同意`, `同意执行`, `开始计算` | Yes |
| Confirming a value the agent itself proposed | `同意：ENCUT=250 就按你给出的单卡命令执行` | Yes |
| **Operator supplying the protocol outright** | `EOS 拟合用 7 个体积点、体积范围 ±5%` (lc_Si_dia); the lc_Ge_dia opening prompt, which specifies the convergence criterion and the 7-point ±5% grid | **No** |

## Rules

1. **Answer as the archived sessions did.** Go-aheads are granted, hardware
   questions are answered factually, and commands or values the agent has itself
   proposed are approved without edits.

2. **Never originate a calculation parameter.** The operator does not name an
   ENCUT, k-spacing, smearing scheme, pseudopotential variant, strain window,
   number of volume points, or EOS form that the agent has not already proposed.
   This is the one historical pattern deliberately not replicated: it occurs in
   2-3 of the 97 logged turns, and it hands over exactly the decisions this
   experiment measures.

3. **Open parameter questions** ("what ENCUT should I use?", asked without a
   proposal) are answered `请你自行判断并说明理由，然后继续执行`.

4. **Repeats.** A question already answered gets the same answer plus a note not
   to ask again. After three identical questions the run stops as `stuck_qa_loop`.

5. **Timeout.** If the operator does not reply within 15 minutes, the
   deterministic classifier in `answer_script.py` supplies the reply so an
   unattended run still terminates. Every question records `answered_by`, so
   operator replies and fallback replies can be told apart in the transcript.

## Note on the archived runs

The archived Sol27LC sessions are `T3`-specified (the opening prompt is
`我要计算FCC Ag的晶格常数`, with no POSCAR) and were answered ad hoc across three
different LLMs. This experiment is `T2`-specified (POSCAR supplied) and uses a
single model, so its transcripts are not directly comparable to the archived
ones; both are released.
