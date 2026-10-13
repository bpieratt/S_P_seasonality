"""
SENSITIVITY ANALYSIS — separate from, and never overwriting, the original research.

Reads only committed research outputs:
  ../seasonal_patterns_2003_2022.json                       (frozen Phase-1 rules + per-year IS returns)
  ../phase2/data/GSPC_2023_2026-10-02.csv                    (OOS prices)
  ../phase2/seasonality_oos_occurrences_2023_present.csv     (frozen Phase-2 occurrences)
  ../data/GSPC_2003_2022.csv                                 (one price only, for check S4b, clearly labelled)
Writes only into this folder: sensitivity_results.json

Run from the repository root:  python sensitivity/run_sensitivity.py
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "sensitivity", "sensitivity_results.json")
RNG = np.random.default_rng(20261013)
N_DRAWS = 10_000

FROZEN = json.load(open(os.path.join(ROOT, "seasonal_patterns_2003_2022.json")))
RULES = {r["id"]: r for r in FROZEN["windows"] + FROZEN["months"]}
PRIMARY = [c["id"] for c in FROZEN["candidate_rules"]]
OOS = pd.read_csv(os.path.join(ROOT, "phase2", "data", "GSPC_2023_2026-10-02.csv"), parse_dates=["Date"])
assert OOS.Date.min() >= pd.Timestamp("2023-01-01") and OOS.Date.max() <= pd.Timestamp("2026-10-02")
CLOSE = OOS.Close.values
DATES = OOS.Date.dt.strftime("%Y-%m-%d").values
IDX = {d: i for i, d in enumerate(DATES)}
T = len(CLOSE)
OCC = pd.read_csv(os.path.join(ROOT, "phase2", "seasonality_oos_occurrences_2023_present.csv"))
DONE = OCC[OCC.status == "complete"].copy()
# entry index: '(open)' entries (Jan 2023 only) start at bar 0's open; for re-sampling we use bar 0's close
DONE["e"] = DONE.entry_date.str.slice(0, 10).map(IDX)
DONE["x"] = DONE.exit_date.map(IDX)
DONE["L"] = DONE.x - DONE.e + DONE.entry_date.str.contains("open").astype(int)
DONE["d"] = np.where(DONE.expected_direction == "bullish", 1, -1)
DONE["base"] = DONE.rule_id.map(lambda r: RULES[r]["baseline_mean_return_same_length"])
DONE["E_IS"] = DONE.rule_id.map(lambda r: RULES[r]["mean_excess_return"])
DONE["r"] = DONE.return_pct / 100.0
res = {}

# ---------------------------------------------------------------------------
# S1. Overlapping windows: how many independent tests were really run in Phase 1?
# ---------------------------------------------------------------------------
yr = pd.DataFrame({w["id"]: pd.Series(w["in_sample_returns_by_year"]) for w in FROZEN["windows"]})
C = yr.corr(min_periods=15).values
eig = np.clip(np.linalg.eigvalsh(np.nan_to_num(C)), 0, None)
m_eff_liji = float(np.sum((eig >= 1).astype(float) + (eig - np.floor(eig))))       # Li & Ji (2005)
m_eff_nyholt = float(1 + (len(eig) - 1) * (1 - np.var(eig, ddof=1) / len(eig)))    # Nyholt (2004)
pmin = min(w["p_value_t"] for w in FROZEN["windows"])
pw = sorted(w["p_value_wilcoxon"] for w in FROZEN["windows"])
n = len(pw)
bh_w = min(min(1, p * n / (i + 1)) for i, p in enumerate(pw))
offdiag = C[np.triu_indices_from(C, 1)]
res["S1_overlap_dependence"] = dict(
    question="Overlapping windows (e.g. Jul01+15td and Jul01+20td) share most of their days, so their results are correlated. Did Phase 1 overstate how many independent chances it had?",
    n_windows=120, mean_abs_pairwise_corr=float(np.nanmean(np.abs(offdiag))),
    share_pairs_corr_gt_0_5=float(np.nanmean(offdiag > 0.5)),
    effective_independent_tests_li_ji=round(m_eff_liji, 1),
    effective_independent_tests_nyholt=round(m_eff_nyholt, 1),
    best_raw_p=pmin, best_p_bonferroni_at_m_eff=float(min(1, pmin * m_eff_liji)),
    min_bh_q_using_wilcoxon_instead_of_t=float(bh_w),
    original_min_bh_q=min(w["q_value_bh_fdr"] for w in FROZEN["windows"]),
    original_min_perm_fwer_p=min(w["permutation_fwer_p"] for w in FROZEN["windows"]),
    note="With only 20 years of data the 120 windows cannot carry more than ~20 independent pieces of information. Even crediting that, the best window does not reach significance. The original permutation test already accounted for overlap.")

# ---------------------------------------------------------------------------
# S2. Placebo that preserves each occurrence's own calendar year
# ---------------------------------------------------------------------------
year_bounds = {y: (int(np.argmax(DATES >= f"{y}-01-01")), int(np.nonzero(DATES <= f"{y}-12-31")[0][-1])) for y in range(2023, 2027)}


def same_year_starts(year, L, size):
    lo, hi = year_bounds[year]
    hi = min(hi, T - 1 - L)          # placebo trade must also finish inside the data
    lo = max(lo - 1, 0)              # entry may be the prior year's last close, like the real rule
    return RNG.integers(lo, hi + 1, size=size)


def placebo(sub, same_year, size=N_DRAWS):
    cols = []
    for _, o in sub.iterrows():
        s = same_year_starts(o.year, o.L, size) if same_year else RNG.integers(0, T - o.L, size=size)
        cols.append(CLOSE[s + o.L] / CLOSE[s] - 1 - o.base)
    return np.vstack(cols).T          # draws x occurrences (excess vs IS baseline)


bull = DONE[DONE.rule_id.isin(PRIMARY) & (DONE.d == 1)]
obs = float((bull.r - bull.base).mean())
s2 = {}
for label, same in (("anywhere_in_2023_2026", False), ("same_calendar_year", True)):
    pl = placebo(bull, same).mean(axis=1)
    s2[label] = dict(placebo_mean_excess=float(pl.mean()), p_one_sided=float((1 + (pl >= obs).sum()) / (1 + N_DRAWS)))
per = {}
for rid in PRIMARY:
    sub = DONE[DONE.rule_id == rid]
    d = int(sub.d.iloc[0])
    o = float((sub.r - sub.base).mean())
    row = {}
    for label, same in (("anywhere", False), ("same_year", True)):
        pm = placebo(sub, same).mean(axis=1)
        row[label + "_percentile"] = float(np.mean(pm <= o) if d > 0 else np.mean(pm >= o))
    per[rid] = row
res["S2_same_year_placebo"] = dict(
    question="The Phase-2 placebo drew random windows from anywhere in 2023-2026. Should it instead stay inside each occurrence's own year, so a 2023 trade is compared only with other 2023 trades?",
    pooled_bullish_observed_mean_excess=obs, original_reported_p=0.3588, variants=s2, per_primary=per,
    note="Placebo p-values here are re-computed with a different random seed, so the 'anywhere' variant will differ slightly from the original 0.36.")

# ---------------------------------------------------------------------------
# S3. Spearman and binomial tests across 132 overlapping rules: calendar-shift null
# ---------------------------------------------------------------------------
agg = DONE.groupby("rule_id").agg(mean_r=("r", "mean"), base=("base", "first"), E_IS=("E_IS", "first"), d=("d", "first"))
agg["e"] = agg.mean_r - agg.base
obs_rho = stats.spearmanr(agg.E_IS, agg.e).statistic
obs_share = float(np.mean(agg.d * agg.e > 0))
e_arr, L_arr, rid_arr = DONE.e.values, DONE.L.values, DONE.rule_id.values
codes, uniq = pd.factorize(rid_arr)
base_u = agg.loc[uniq, "base"].values
EIS_u = agg.loc[uniq, "E_IS"].values
d_u = agg.loc[uniq, "d"].values
rhos, shares = np.empty(2000), np.empty(2000)
span = T - L_arr.max() - 1
for k in range(2000):
    off = RNG.integers(21, span - 21)                      # shift every rule by the same number of days
    s = (e_arr + off) % span
    r = CLOSE[s + L_arr] / CLOSE[s] - 1
    m = np.bincount(codes, weights=r) / np.bincount(codes)
    ee = m - base_u
    rhos[k] = stats.spearmanr(EIS_u, ee).statistic
    shares[k] = np.mean(d_u * ee > 0)
res["S3_cross_rule_tests"] = dict(
    question="Phase 2 treated the 132 rules as independent when testing whether in-sample winners stayed winners (Spearman) and whether more than half kept their direction (binomial). The rules overlap heavily, so those p-values may be too small.",
    observed_spearman=float(obs_rho), original_reported_p_spearman=0.041,
    calendar_shift_p_spearman=float((1 + (rhos >= obs_rho).sum()) / 2001),
    observed_share_same_direction_vs_is_base=obs_share, original_reported_p_binomial=0.169,
    calendar_shift_p_share=float((1 + (shares >= obs_share).sum()) / 2001),
    null_spearman_p05_p95=[float(np.quantile(rhos, .05)), float(np.quantile(rhos, .95))],
    null_share_p05_p95=[float(np.quantile(shares, .05)), float(np.quantile(shares, .95))],
    method="Shift every rule's OOS entry by the same random number of trading days (wrapping inside 2023-2026), keeping all overlaps between rules intact, and recompute both statistics 2,000 times.")

# ---------------------------------------------------------------------------
# S4. Entry / exit assumptions
# ---------------------------------------------------------------------------
checks = []
for _, o in DONE[DONE.rule_id.isin(PRIMARY)].iterrows():
    r = RULES[o.rule_id]
    anchor = f"{o.year}-{r['window_start_month_day']}"
    first_held = int(np.argmax(DATES >= anchor))
    ok = (DATES[o.e] < anchor) and (o.x - first_held + 1 == r["window_length_trading_days"]) and (o.e == first_held - 1)
    checks.append(dict(rule=o.rule_id, year=int(o.year), entry=DATES[o.e], first_day_held=DATES[first_held],
                       exit=DATES[o.x], trading_days_held=int(o.x - o.e), as_defined=bool(ok)))
is_px = pd.read_csv(os.path.join(ROOT, "data", "GSPC_2003_2022.csv"), parse_dates=["Date"])
dec30 = float(is_px.Close.iloc[-1])
jan23 = OCC[(OCC.rule_id == "MONTH-Jan") & (OCC.year == 2023)].iloc[0]
res["S4_entry_exit"] = dict(
    question="Do entries and exits match the frozen definitions, and does any convention change results?",
    primary_occurrences_checked=len(checks), all_match_definition=all(c["as_defined"] for c in checks), checks=checks,
    label_note="Window names such as 'Jul 1 -> Jul 22' show the TYPICAL exit date. The rule is defined in trading days, so the actual exit moves by 1-3 calendar days from year to year (the frozen file records the range).",
    jan_2023_entry=dict(
        rule_used="Jan 2023 occurrences enter at the 2023-01-03 OPEN because the OOS file has no earlier bar (same rule Phase 1 used for Jan 2003).",
        open_price=float(jan23.entry_price), prior_close_2022_12_30=dec30,
        jan_2023_month_return_as_reported=float(jan23.return_pct) / 100,
        jan_2023_month_return_from_prior_close=float(jan23.exit_price / dec30 - 1),
        affects=sorted(OCC[(OCC.year == 2023) & OCC.entry_date.astype(str).str.contains("open")].rule_id.unique().tolist()),
        affects_primary=False))

# ---------------------------------------------------------------------------
# S5. Partial 2026 data
# ---------------------------------------------------------------------------
inc = OCC[OCC.status != "complete"]
res["S5_partial_2026"] = dict(
    question="Were unfinished 2026 periods kept out of every statistic?",
    incomplete_occurrences=int(len(inc)), any_incomplete_has_return=bool(inc.return_pct.notna().any()),
    by_status=inc.status.value_counts().to_dict(),
    rules_with_N_3=sorted(OCC[OCC.status == "complete"].groupby("rule_id").size().loc[lambda s: s == 3].index.tolist()),
    note="Rules whose 2026 occurrence had not finished by 2026-10-02 have N = 3 instead of 4. That is correct (no partial result is used) but means late-year rules carry a little less evidence.")

json.dump(res, open(OUT, "w"), indent=2, default=float)
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in ("checks", "per_primary", "question", "note", "method")} for k, v in res.items()}, indent=1, default=float))
