#!/usr/bin/env python3
"""Compare each arm against the Sol27LC references."""
import json, os, sys
import pandas as pd

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(os.path.dirname(EXP), "lattice_constant.xlsx")

df = pd.read_excel(XLSX, sheet_name="晶格常数")
exp_row, expert_row = df.iloc[0], df.iloc[1]
exp, expert = {}, {}
for col in df.columns[1:]:
    if isinstance(col, str) and "(" in col:
        el = col.split(" ")[0]
        try:
            exp[el] = float(exp_row[col]); expert[el] = float(expert_row[col])
        except (TypeError, ValueError):
            pass

rows = json.load(open(os.path.join(EXP, "audit", "results.json")))
out = []
for r in rows:
    if not r.get("a_conv_A"):
        continue
    el = r["system"].split("_")[0]
    a = r["a_conv_A"]
    out.append({
        "system": r["system"], "arm": r["arm"], "a_calc": a,
        "a_expert": expert.get(el), "a_exp": exp.get(el),
        "err_expert_%": 100 * (a - expert[el]) / expert[el] if el in expert else None,
        "err_exp_%": 100 * (a - exp[el]) / exp[el] if el in exp else None,
        "R2": r.get("R2"), "pts": r.get("n_points"),
        "wall_s": r.get("wall_s"), "custodian": r.get("custodian_events"),
    })
d = pd.DataFrame(out).sort_values(["arm", "system"])
pd.set_option("display.width", 200, "display.max_rows", 100)
print(d.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print("\n=== per-arm summary ===")
for arm, g in d.groupby("arm"):
    print(f"{arm:<14} n={len(g):<3} MAE_vs_expert={g['err_expert_%'].abs().mean():.3f}%  "
          f"MAE_vs_exp={g['err_exp_%'].abs().mean():.3f}%  "
          f"median_wall={g['wall_s'].median():.0f}s  custodian={g['custodian'].sum() if g['custodian'].notna().any() else '-'}")
d.to_csv(os.path.join(EXP, "audit", "comparison.csv"), index=False)
