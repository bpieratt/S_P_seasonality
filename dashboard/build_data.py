"""
Dashboard data layer (PRESENTATION ONLY — reads the research files, never writes them).

Every number shown on the dashboard comes from this module. Monthly returns are
recomputed from the two price files with the study's own monthly rule and then
CROSS-CHECKED against the frozen research outputs; the build stops if they differ.

  Monthly rule (same as the study): close of the month's last trading day divided by
  the close of the previous month's last trading day, minus 1. The first month of each
  price file (Jan 2003, Jan 2023) has no prior close inside that file, so it starts from
  the first day's OPEN — exactly as the frozen research did.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
OOS_LAST = "2026-10-02"


def _load(path, lo, hi):
    df = pd.read_csv(path, parse_dates=["Date"])
    assert df.Date.min() >= pd.Timestamp(lo) and df.Date.max() <= pd.Timestamp(hi), f"{path} outside {lo}..{hi}"
    return df


def monthly_table(df):
    """One row per calendar month present in the file: return, intra-month max drawdown, completeness."""
    df = df.copy()
    df["ym"] = df.Date.dt.to_period("M")
    rows, prev_close = [], None
    for ym, g in df.groupby("ym", sort=True):
        start = float(df.Open.iloc[0]) if prev_close is None else prev_close
        path = np.concatenate([[start], g.Close.values])
        dd = float((path / np.maximum.accumulate(path) - 1).min())
        rows.append(dict(year=ym.year, month=ym.month, ret=float(path[-1] / start - 1), mdd=dd,
                         last_date=str(g.Date.iloc[-1].date()), days=len(g)))
        prev_close = float(g.Close.values[-1])
    return pd.DataFrame(rows)


def build():
    frozen = json.load(open(P("seasonal_patterns_2003_2022.json")))
    is_px = _load(P("data", "GSPC_2003_2022.csv"), "2003-01-01", "2022-12-31")
    oos_px = _load(P("phase2", "data", "GSPC_2023_2026-10-02.csv"), "2023-01-01", OOS_LAST)
    is_m, oos_m = monthly_table(is_px), monthly_table(oos_px)

    # A month is complete only if its last calendar day is on/before the last bar (2026-10-02)
    oos_m["complete"] = oos_m.apply(lambda r: (pd.Period(f"{r.year}-{r.month:02d}").end_time.normalize()
                                               <= pd.Timestamp(OOS_LAST)), axis=1)
    is_m["complete"] = True

    # ---- cross-checks against frozen research outputs (build fails on any mismatch)
    fm = {m["id"]: m for m in frozen["months"]}
    for r in is_m.itertuples():
        ref = fm[f"MONTH-{MON[r.month-1]}"]["in_sample_returns_by_year"][str(r.year)]
        assert abs(round(r.ret, 6) - ref) < 1.5e-6, ("IS month mismatch", r.year, r.month, r.ret, ref)
    occ = pd.read_csv(P("phase2", "seasonality_oos_occurrences_2023_present.csv"))
    om = occ[occ.rule_id.str.startswith("MONTH-")]
    checked = 0
    for r in oos_m.itertuples():
        ref = om[(om.rule_id == f"MONTH-{MON[r.month-1]}") & (om.year == r.year)].iloc[0]
        if r.complete:
            assert ref.status == "complete" and abs(r.ret * 100 - ref.return_pct) < 1.5e-3, ("OOS mismatch", r.year, r.month)
            checked += 1
        else:
            assert ref.status != "complete" and pd.isna(ref.return_pct), "partial month treated as complete in research"
    assert checked == 45

    # ---- heat-map grids
    def grid(mt, years):
        out = []
        for y in years:
            cells = []
            for m in range(1, 13):
                hit = mt[(mt.year == y) & (mt.month == m)]
                if hit.empty:
                    cells.append(dict(state="future"))
                elif not bool(hit.complete.iloc[0]):
                    cells.append(dict(state="partial", through=hit.last_date.iloc[0]))
                else:
                    cells.append(dict(state="complete", ret=round(float(hit.ret.iloc[0]), 6), mdd=round(float(hit.mdd.iloc[0]), 6)))
            done = mt[(mt.year == y) & mt.complete]
            yr = float(np.prod(1 + done.ret.values) - 1) if len(done) else None
            out.append(dict(year=y, cells=cells, year_ret=yr, months_in_year=int(len(done)), full_year=len(done) == 12))
        return out

    is_grid = grid(is_m, range(2003, 2023))
    oos_grid = grid(oos_m, range(2023, 2027))
    is_c, oos_c = is_m, oos_m[oos_m.complete]

    def per_month(mt):
        res = []
        for m in range(1, 13):
            s = mt[mt.month == m]
            res.append(dict(m=MON[m - 1], n=int(len(s)), avg=float(s.ret.mean()), median=float(s.ret.median()),
                            pos=int((s.ret > 0).sum()), neg=int((s.ret <= 0).sum()), pct_pos=float((s.ret > 0).mean()),
                            best=float(s.ret.max()), worst=float(s.ret.min()), avg_mdd=float(s.mdd.mean()),
                            worst_mdd=float(s.mdd.min())))
        return res

    is_pm, oos_pm = per_month(is_c), per_month(oos_c)
    all_is_avg = float(is_c.ret.mean())
    for r, fz in zip(is_pm, frozen["months"]):
        r["excess"] = r["avg"] - all_is_avg
        r["frozen_class"] = fz["classification"]
        r["frozen_dir"] = fz["designation"]
        r["p_t"] = fz["p_value_t"]
        r["q"] = fz["q_value_bh_fdr"]
        r["std"] = fz["std_return"]
        r["t"] = fz["t_stat_excess"]
        r["p_w"] = fz["p_value_wilcoxon"]
        assert abs(r["avg"] - fz["mean_return"]) < 1e-5

    def summary(mt, pm):
        best_m = max(pm, key=lambda r: r["avg"])
        worst_m = min(pm, key=lambda r: r["avg"])
        bi, wi = mt.ret.idxmax(), mt.ret.idxmin()
        return dict(n_months=int(len(mt)), avg=float(mt.ret.mean()), median=float(mt.ret.median()),
                    pct_pos=float((mt.ret > 0).mean()), avg_mdd=float(mt.mdd.mean()), worst_mdd=float(mt.mdd.min()),
                    best_cal_month=dict(m=best_m["m"], avg=best_m["avg"], n=best_m["n"]),
                    worst_cal_month=dict(m=worst_m["m"], avg=worst_m["avg"], n=worst_m["n"]),
                    best_single=dict(ym=f'{MON[int(mt.month[bi])-1]} {int(mt.year[bi])}', ret=float(mt.ret[bi])),
                    worst_single=dict(ym=f'{MON[int(mt.month[wi])-1]} {int(mt.year[wi])}', ret=float(mt.ret[wi])),
                    std=float(mt.ret.std(ddof=1)))

    # Seasonal consistency (two different questions — explained on the page)
    a = is_c[is_c.year <= 2012].groupby("month").ret.mean()
    b = is_c[is_c.year >= 2013].groupby("month").ret.mean()
    split_agree = int(sum(np.sign(a - all_is_avg) == np.sign(b - all_is_avg)))
    oos_avg_all = float(oos_c.ret.mean())
    is_ex = is_c.groupby("month").ret.mean() - all_is_avg
    oos_ex_vs_is = oos_c.groupby("month").ret.mean() - all_is_avg       # vs the frozen 'average month'
    oos_ex_vs_own = oos_c.groupby("month").ret.mean() - oos_avg_all     # vs 2023-26's own average month
    keep_rank = float(pd.Series(is_ex).corr(pd.Series(oos_ex_vs_own), method="spearman"))
    consistency = dict(
        is_split_half_same_sign=split_agree,
        oos_same_sign_as_history_vs_own_avg=int(sum(np.sign(is_ex) == np.sign(oos_ex_vs_own))),
        oos_same_sign_as_history_vs_is_avg=int(sum(np.sign(is_ex) == np.sign(oos_ex_vs_is))),
        rank_corr_month_pattern=keep_rank)

    # ---- frozen windows + OOS validation (8 primaries and all 132 rules)
    val = json.load(open(P("phase2", "seasonality_validation_2023_present.json")))
    vrules = {r["rule_id"]: r for r in val["rules"]}
    oos_tab = pd.read_csv(P("phase2", "seasonality_oos_2023_present.csv")).set_index("rule_id")
    primaries = []
    for k, c in enumerate(frozen["candidate_rules"], 1):
        v = vrules[c["id"]]
        primaries.append(dict(
            rank=k, id=c["id"], dir=c["designation"], start=c["window_start_month_day"], days=c["window_length_trading_days"],
            end=c["typical_window_end_month_day"], end_range=c["window_end_range_month_day"],
            is_years=c["historical_years"], is_win=c["win_rate"], is_hit=c["hit_rate_in_designated_direction"],
            is_mean=c["mean_return"], is_median=c["median_return"], is_excess=c["mean_excess_return"], base=c["baseline_mean_return_same_length"],
            is_avg_mdd=c["avg_max_drawdown"], is_worst_mdd=c["worst_max_drawdown"], is_p=c["p_value_t"], is_q=c["q_value_bh_fdr"],
            is_fwer=c["permutation_fwer_p"], is_ci=c["ci95_mean_t"], is_class=c["classification"],
            is_halves=c["subperiods"], is_years_ret=c["in_sample_returns_by_year"],
            oos_n=v["oos_n"], oos_win=v["oos_win_rate"], oos_mean=v["oos_avg_return"], oos_median=v["oos_median_return"],
            oos_ci=v["oos_ci95_mean"], oos_hit_ci=v["oos_hit_rate_ci95"], oos_dd=v["oos_drawdown"],
            oos_drift=v["benchmark"]["oos_drift"], oos_ex_is=v["benchmark"]["excess_vs_is_baseline"],
            oos_ex_drift=v["benchmark"]["excess_vs_oos_drift"], placebo_pct=v["benchmark"]["placebo_percentile_expected_tail"],
            rho=v["rho_share_of_is_edge"], hit_excess=v["hit_rate_excess"], effect=v["effect_direction"],
            verdict=v["validation_classification"], scorecard=v["scorecard"],
            occurrences=[dict(year=o["year"], status=o["status"], entry=o.get("entry_date"), exit=o.get("exit_date"),
                              entry_px=o.get("entry_px"), exit_px=o.get("exit_px"), ret=o.get("ret"), mdd=o.get("mdd"))
                         for o in v["oos_observations"]]))

    allrules = []
    for r in frozen["windows"] + frozen["months"]:
        t = oos_tab.loc[r["id"]]
        allrules.append(dict(id=r["id"], window=t.window, dir=r["designation"], is_class=r["classification"],
                             is_win=r["win_rate"], is_mean=r["mean_return"], is_excess=r["mean_excess_return"],
                             is_p=r["p_value_t"], is_q=r["q_value_bh_fdr"], oos_n=int(t.oos_n),
                             oos_win=None if pd.isna(t.oos_win_pct) else float(t.oos_win_pct),
                             oos_mean=None if pd.isna(t.oos_avg_return) else float(t.oos_avg_return),
                             oos_ex_is=None if pd.isna(t.oos_excess_vs_is_baseline) else float(t.oos_excess_vs_is_baseline),
                             oos_ex_drift=None if pd.isna(t.oos_excess_vs_oos_drift) else float(t.oos_excess_vs_oos_drift),
                             match=bool(t.direction_match), effect=t.effect_direction, verdict=t.validation,
                             primary=bool(t.primary_hypothesis)))

    # ---- seasonal paths (prior year-end = 100)
    rd = json.load(open(P("outputs", "report_data.json")))
    oos_paths = {}
    for y in (2023, 2024, 2025, 2026):
        g = oos_px[oos_px.Date.dt.year == y]
        base = float(oos_px.Open.iloc[0]) if g.index[0] == 0 else float(oos_px.Close.iloc[g.index[0] - 1])
        oos_paths[y] = (g.Close.values / base * 100).round(3).tolist()
    L = 252
    oos_avg = np.mean([np.pad(np.array(oos_paths[y][:L]), (0, max(0, L - len(oos_paths[y]))), mode="edge")
                       for y in (2023, 2024, 2025)], axis=0).round(3).tolist()

    sens = json.load(open(P("sensitivity", "sensitivity_results.json")))
    data = dict(
        meta=dict(is_first=str(is_px.Date.min().date()), is_last=str(is_px.Date.max().date()), is_days=len(is_px),
                  oos_first=str(oos_px.Date.min().date()), oos_last=str(oos_px.Date.max().date()), oos_days=len(oos_px),
                  frozen_sha=val["frozen_rules_sha256"], criteria_sha=val["criteria_sha256"],
                  oos_months_complete=int(len(oos_c)), oos_months_partial=int((~oos_m.complete).sum())),
        heat=dict(is_=is_grid, oos=oos_grid,
                  is_month_avg=[r["avg"] for r in is_pm], oos_month_avg=[r["avg"] for r in oos_pm],
                  oos_month_n=[r["n"] for r in oos_pm]),
        months=dict(is_=is_pm, oos=oos_pm, is_avg_all=all_is_avg, oos_avg_all=oos_avg_all,
                    oos_valid={m: vrules[f"MONTH-{m}"]["validation_classification"] for m in MON},
                    oos_effect={m: vrules[f"MONTH-{m}"]["effect_direction"] for m in MON}),
        compare=dict(is_=summary(is_c, is_pm), oos=summary(oos_c, oos_pm), consistency=consistency),
        primaries=primaries, rules=allrules, aggregate=val["aggregate"], oos_drift=val["oos_drift_same_length"],
        calendar_heat=dict(cells=rd["heat"], base5=frozen["windows"][0]["baseline_mean_return_same_length"]),
        paths=dict(labels=rd["labels"], is_avg=rd["avg"], is_med=rd["med"], is_prob=rd["prob"], oos_avg=oos_avg,
                   oos_years={str(y): oos_paths[y] for y in oos_paths}),
        phase1=dict(n_windows=120, n_raw_p05=sum(w["p_value_t"] < 0.05 for w in frozen["windows"]),
                    min_q=min(w["q_value_bh_fdr"] for w in frozen["windows"]),
                    min_fwer=min(w["permutation_fwer_p"] for w in frozen["windows"]),
                    classes=pd.Series([w["classification"] for w in frozen["windows"]]).value_counts().to_dict()),
        sensitivity=sens,
    )
    return data


if __name__ == "__main__":
    d = build()
    c = d["compare"]
    print(json.dumps({k: c[k] for k in c}, indent=1, default=float))
    print([ (r["m"], round(r["avg"]*100,2), r["n"]) for r in d["months"]["oos"]])
    print(d["phase1"])
