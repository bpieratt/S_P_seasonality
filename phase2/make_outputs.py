"""Write seasonality_oos_2023_present.csv, occurrences CSV and seasonality_validation_2023_present.json."""
import json
import os
import pickle

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
O = pickle.load(open(os.path.join(HERE, "outputs", "oos_results.pkl"), "rb"))
R = O["results"]
FROZEN = json.load(open(os.path.join(os.path.dirname(HERE), "seasonal_patterns_2003_2022.json")))
order = [w["id"] for w in FROZEN["windows"]] + [m["id"] for m in FROZEN["months"]]


def f(x, nd=6):
    if x is None:
        return None
    if isinstance(x, (float, np.floating)):
        return None if np.isnan(x) else round(float(x), nd)
    return x


rows, occ_rows = [], []
for rid in order:
    s = R[rid]
    i = s["is_stats"]
    rows.append(dict(
        rule_id=rid, window=s["window"], original_direction=s["designation"], is_classification=s["is_class"],
        primary_hypothesis=s["primary"], is_win_pct=i["win_rate"], is_avg_return=i["mean"], is_median_return=i["median"],
        is_mean_excess=i["mean_excess"], is_baseline_same_length=i["base"],
        oos_n=s["n"], oos_win_pct=f(s.get("win_raw")), oos_avg_return=f(s.get("mean")), oos_median_return=f(s.get("median")),
        oos_excess_vs_is_baseline=f(s.get("excess_vs_is_base")), oos_drift_same_length=f(s.get("oos_drift")),
        oos_excess_vs_oos_drift=f(s.get("excess_vs_oos_drift")), rho_share_of_is_edge=f(s.get("rho"), 4),
        hit_rate_excess_in_direction=f(s.get("hit_excess"), 4), placebo_percentile_expected_tail=f(s.get("placebo_pct_expected_tail"), 4),
        oos_avg_max_drawdown=f(s.get("avg_mdd")), oos_worst_max_drawdown=f(s.get("worst_mdd")),
        direction_match=(None if s["n"] == 0 else ((1 if s["designation"] == "bullish" else -1) * s["excess_vs_is_base"] > 0)),
        effect_direction=s.get("effect"), validation=s["classification"],
        incomplete_occurrences="; ".join(f'{o["year"]}: {o["status"]}' for o in s["occurrences"] if o["status"] != "complete") or ""))
    for o in s["occurrences"]:
        occ_rows.append(dict(rule_id=rid, year=o["year"], status=o["status"], entry_date=o.get("entry_date"),
                             entry_price=f(o.get("entry_px"), 2), exit_date=o.get("exit_date"), exit_price=f(o.get("exit_px"), 2),
                             return_pct=None if o["ret"] is None else round(o["ret"] * 100, 3),
                             max_drawdown_pct=None if o.get("mdd") is None else round(o["mdd"] * 100, 3),
                             expected_direction=s["designation"],
                             correct_raw=None if o["ret"] is None else ((o["ret"] > 0) if s["designation"] == "bullish" else (o["ret"] < 0)),
                             beat_is_baseline_in_direction=None if o["ret"] is None else
                             bool((1 if s["designation"] == "bullish" else -1) * (o["ret"] - s["is_stats"]["base"]) > 0)))
pd.DataFrame(rows).to_csv(os.path.join(HERE, "seasonality_oos_2023_present.csv"), index=False)
pd.DataFrame(occ_rows).to_csv(os.path.join(HERE, "seasonality_oos_occurrences_2023_present.csv"), index=False)

js = dict(
    title="S&P 500 seasonality — strict out-of-sample validation of the frozen 2003-2022 rules",
    frozen_rules_file="seasonal_patterns_2003_2022.json", frozen_rules_sha256=O["frozen_sha256"],
    criteria_file="oos_validation_criteria.yaml", criteria_sha256=O["criteria_sha256"],
    oos_data=dict(instrument="^GSPC", sha256=O["data_sha256"], **{k: v for k, v in O["data_quality"].items()}),
    hard_stop=O["hard_stop"], oos_drift_same_length=O["oos_drift"],
    aggregate=O["aggregate"],
    rules=[dict(
        rule_id=rid, original_window=R[rid]["window"], original_direction=R[rid]["designation"],
        primary_hypothesis=R[rid]["primary"], original_is_statistics=R[rid]["is_stats"],
        oos_observations=[{k: (f(v) if isinstance(v, float) else v) for k, v in o.items() if k not in ("entry_idx", "view_last_date")}
                          for o in R[rid]["occurrences"]],
        oos_returns=R[rid].get("returns", []), oos_n=R[rid]["n"], oos_win_rate=R[rid].get("win_raw"),
        oos_hit_rate_ci95=R[rid].get("hit_raw_ci"), oos_avg_return=R[rid].get("mean"), oos_ci95_mean=R[rid].get("ci95_mean"),
        oos_median_return=R[rid].get("median"),
        oos_drawdown=dict(avg=R[rid].get("avg_mdd"), median=R[rid].get("median_mdd"), worst=R[rid].get("worst_mdd"),
                          freq_ge2=R[rid].get("freq_dd2"), freq_ge3=R[rid].get("freq_dd3"), freq_ge5=R[rid].get("freq_dd5")),
        benchmark=dict(is_baseline=R[rid]["is_stats"]["base"], excess_vs_is_baseline=R[rid].get("excess_vs_is_base"),
                       oos_drift=R[rid].get("oos_drift"), excess_vs_oos_drift=R[rid].get("excess_vs_oos_drift"),
                       placebo_percentile_expected_tail=R[rid].get("placebo_pct_expected_tail"),
                       placebo_mean=R[rid].get("placebo_mean"), placebo_p05_p95=R[rid].get("placebo_p05_p95")),
        rho_share_of_is_edge=R[rid].get("rho"), hit_rate_excess=R[rid].get("hit_excess"),
        effect_direction=R[rid].get("effect"), validation_classification=R[rid]["classification"],
        scorecard=R[rid].get("scorecard")) for rid in order],
)
txt = json.dumps(js, indent=2, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else str(x))
open(os.path.join(HERE, "seasonality_validation_2023_present.json"), "w").write(txt)
print("rows", len(rows), "occurrences", len(occ_rows))
