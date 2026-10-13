"""
Phase 2 — strict out-of-sample validation of the 132 frozen rules on 2023-01-03 .. 2026-10-02.
Reads the frozen rules (never writes them), applies the pre-registered criteria
(oos_validation_criteria.yaml, hash-locked), evaluates every trade through a
point-in-time view as of its exit date. Run: python validate.py
"""
import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats

from oos_data import (FROZEN_PATH, load_criteria, load_oos, quality_report, sha256,
                      verify_frozen)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
os.makedirs(OUT, exist_ok=True)
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CRIT = load_criteria()                      # aborts if criteria changed after lock
FROZEN_SHA = verify_frozen(CRIT)            # aborts if frozen rules changed
FROZEN = json.load(open(FROZEN_PATH))
assert len(FROZEN["windows"]) == CRIT["frozen_rules"]["expected_windows"] == 120
assert len(FROZEN["months"]) == CRIT["frozen_rules"]["expected_months"] == 12
PRIMARY = CRIT["frozen_rules"]["primary_hypotheses"]
assert [c["id"] for c in FROZEN["candidate_rules"]] == PRIMARY

HARD = CRIT["data"]["hard_stop"]
MD, DF = load_oos(min_date=CRIT["data"]["min_date"], hard_stop=HARD)
CAL = MD.trading_calendar
T = len(CAL)
FULL = MD.as_of(HARD)                      # used ONLY for benchmarks/placebo (descriptive of the OOS period)
CLOSE = FULL.close
FIRST_OPEN = MD.first_open
YEARS = [2023, 2024, 2025, 2026]
RNG = np.random.default_rng(CRIT["benchmarks"]["seed"])
N_PLACEBO = 10_000

RULES = {r["id"]: dict(r, kind="window") for r in FROZEN["windows"]}
for i, r in enumerate(FROZEN["months"]):
    RULES[r["id"]] = dict(r, kind="month", month=i + 1)


# ---------------------------------------------------------------------------
# Point-in-time trade evaluation (identical rules to Phase 1)
# ---------------------------------------------------------------------------
def _entry_index(anchor):
    return int(np.searchsorted(CAL, np.datetime64(anchor), side="left")) - 1


def _evaluate(entry_idx, exit_idx):
    view = MD.as_of(CAL[exit_idx])             # bars dated > exit do not exist in this view
    if entry_idx >= 0:
        path = view.close[entry_idx: exit_idx + 1]
        entry_date, entry_px = str(view.dates[entry_idx]), float(view.close[entry_idx])
    else:                                      # Jan 2023: first-bar open, same rule as Phase 1 (Jan 2003)
        path = np.concatenate([[view.open[0]], view.close[: exit_idx + 1]])
        entry_date, entry_px = str(view.dates[0]) + " (open)", float(view.open[0])
    dd = path / np.maximum.accumulate(path) - 1
    return dict(entry_date=entry_date, entry_px=entry_px, exit_date=str(view.dates[-1]),
                exit_px=float(path[-1]), ret=float(path[-1] / path[0] - 1), mdd=float(dd.min()),
                view_last_date=str(view.dates[-1]), length=int(exit_idx - max(entry_idx, 0)) + (entry_idx < 0))


def window_occurrences(rule):
    m, d = map(int, rule["window_start_month_day"].split("-"))
    L = rule["window_length_trading_days"]
    out = []
    for y in YEARS:
        anchor = f"{y}-{m:02d}-{d:02d}"
        e = _entry_index(anchor)
        x = e + L
        if np.datetime64(anchor) > CAL[-1]:
            out.append(dict(year=y, status="not started", ret=None))
        elif x >= T:
            out.append(dict(year=y, status=f"in progress (exits after {HARD})", ret=None,
                            entry_date=str(CAL[e]) if e >= 0 else None))
        else:
            out.append(dict(year=y, status="complete", entry_idx=e, **_evaluate(e, x)))
    return out


def month_occurrences(rule):
    m = rule["month"]
    out = []
    for y in YEARS:
        start = np.datetime64(f"{y}-{m:02d}-01")
        nxt = np.datetime64(f"{y + (m == 12)}-{m % 12 + 1:02d}-01")
        last_day = nxt - np.timedelta64(1, "D")
        if start > CAL[-1]:
            out.append(dict(year=y, status="not started", ret=None))
        elif last_day > np.datetime64(HARD):
            out.append(dict(year=y, status=f"in progress (month ends after {HARD})", ret=None))
        else:
            e, x = _entry_index(start), _entry_index(nxt)
            out.append(dict(year=y, status="complete", entry_idx=e, **_evaluate(e, x)))
    return out


def occurrences(rule):
    return window_occurrences(rule) if rule["kind"] == "window" else month_occurrences(rule)


# ---------------------------------------------------------------------------
# OOS benchmarks (contemporaneous drift, DD frequency) and placebo
# ---------------------------------------------------------------------------
_drift, _ddfreq = {}, {}


def drift(L):
    if L not in _drift:
        _drift[L] = float(np.mean(CLOSE[L:] / CLOSE[:-L] - 1))
    return _drift[L]


def dd_unconditional(L):
    if L not in _ddfreq:
        dds = np.array([(CLOSE[i:i + L + 1] / np.maximum.accumulate(CLOSE[i:i + L + 1]) - 1).min()
                        for i in range(T - L)])
        _ddfreq[L] = dict(ge2=float((dds <= -0.02).mean()), ge3=float((dds <= -0.03).mean()),
                          ge5=float((dds <= -0.05).mean()), avg=float(dds.mean()))
    return _ddfreq[L]


def placebo_means(lengths):
    """Random OOS start for each occurrence (same lengths); returns N_PLACEBO means."""
    lengths = np.asarray(lengths)
    starts = RNG.integers(0, T - lengths[None, :] , size=(N_PLACEBO, len(lengths)))
    r = CLOSE[starts + lengths[None, :]] / CLOSE[starts] - 1
    return r.mean(axis=1)


# ---------------------------------------------------------------------------
# Pre-registered classification
# ---------------------------------------------------------------------------
def effect_direction(d, e, E_IS):
    if abs(E_IS) < 0.0025:
        de = d * e
        return "Same direction" if de >= 0.0025 else ("Opposite direction" if de <= -0.0025 else "Neutral")
    rho = e / E_IS
    if rho >= 0.75:
        return "Same direction"
    if rho >= 0.25:
        return "Weaker same direction"
    if rho > -0.25:
        return "Neutral"
    return "Opposite direction"


def classify(n, rho, hit):
    if n < 3:
        return "INCONCLUSIVE (N<3)"
    if rho >= 0.5 and hit >= 2 / 3 - 1e-9:
        return "SUPPORTIVE"
    if rho >= 0.25 and hit >= 0.5:
        return "PARTIALLY SUPPORTIVE"
    if rho <= -0.25 and hit <= 0.5:
        return "CONTRADICTED"
    return "INCONCLUSIVE"


def clopper(k, n):
    lo = stats.beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0
    hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return float(lo), float(hi)


def evaluate_rule(rid):
    rule = RULES[rid]
    occ = occurrences(rule)
    done = [o for o in occ if o["status"] == "complete"]
    d = 1 if rule["designation"] == "bullish" else -1
    base = rule["baseline_mean_return_same_length"]
    E_IS = rule["mean_excess_return"]
    r = np.array([o["ret"] for o in done])
    mdd = np.array([o["mdd"] for o in done])
    lens = [o["length"] for o in done]
    n = len(r)
    res = dict(id=rid, kind=rule["kind"], designation=rule["designation"], is_class=rule["classification"],
               primary=rid in PRIMARY, n=n, occurrences=occ,
               is_stats=dict(win_rate=rule["win_rate"], hit_rate=rule["hit_rate_in_designated_direction"],
                             mean=rule["mean_return"], median=rule["median_return"],
                             mean_excess=E_IS, base=base, avg_mdd=rule["avg_max_drawdown"],
                             worst_mdd=rule["worst_max_drawdown"], freq_dd2=rule["freq_drawdown_gt_2pct"],
                             freq_dd3=rule["freq_drawdown_gt_3pct"], freq_dd5=rule["freq_drawdown_gt_5pct"],
                             pct_neg=rule["loss_rate"], q=rule["q_value_bh_fdr"]))
    if rule["kind"] == "window":
        res["window"] = f'{MON[int(rule["window_start_month_day"][:2])-1]} {int(rule["window_start_month_day"][3:])} → ~' \
                        f'{MON[int(rule["typical_window_end_month_day"][:2])-1]} {int(rule["typical_window_end_month_day"][3:])} ' \
                        f'({rule["window_length_trading_days"]} td)'
    else:
        res["window"] = f"Calendar month: {MON[rule['month']-1]}"
    if n == 0:
        res.update(classification="INCONCLUSIVE (N<3)", effect="—")
        return res
    e = float(r.mean() - base)
    rho = e / E_IS if E_IS != 0 else np.nan
    hit = float(np.mean(d * (r - base) > 0))
    dr = float(np.mean([drift(L) for L in lens]))
    pm = placebo_means(lens)
    pct = float(np.mean(pm <= r.mean())) if d > 0 else float(np.mean(pm >= r.mean()))
    ci = (np.nan, np.nan)
    if n >= 2:
        se = r.std(ddof=1) / np.sqrt(n)
        tc = stats.t.ppf(0.975, n - 1)
        ci = (float(r.mean() - tc * se), float(r.mean() + tc * se))
    k_raw = int((r > 0).sum()) if d > 0 else int((r < 0).sum())
    ddu = {L: dd_unconditional(L) for L in set(lens)}
    res.update(
        returns=r.tolist(), win_raw=float((r > 0).mean()), pct_neg=float((r < 0).mean()),
        hits_raw=k_raw, hit_raw_ci=clopper(k_raw, n),
        mean=float(r.mean()), median=float(np.median(r)), ci95_mean=ci,
        avg_mdd=float(mdd.mean()), median_mdd=float(np.median(mdd)), worst_mdd=float(mdd.min()),
        freq_dd2=float((mdd <= -0.02).mean()), freq_dd3=float((mdd <= -0.03).mean()),
        freq_dd5=float((mdd <= -0.05).mean()),
        dd_uncond=dict(ge3=float(np.mean([ddu[L]["ge3"] for L in lens])),
                       ge5=float(np.mean([ddu[L]["ge5"] for L in lens])),
                       avg=float(np.mean([ddu[L]["avg"] for L in lens]))),
        excess_vs_is_base=e, rho=float(rho), hit_excess=hit,
        oos_drift=dr, excess_vs_oos_drift=float(r.mean() - dr), adv_vs_drift=float(d * (r.mean() - dr)),
        placebo_pct_expected_tail=pct,
        placebo_mean=float(pm.mean()), placebo_p05_p95=(float(np.quantile(pm, .05)), float(np.quantile(pm, .95))),
        effect=effect_direction(d, e, E_IS),
        classification=classify(n, rho, hit),
        diff_win_pp=float((r > 0).mean() - rule["win_rate"]),
        diff_mean_pp=float(r.mean() - rule["mean_return"]),
        diff_median_pp=float(np.median(r) - rule["median_return"]),
    )
    return res


def scorecard(s):
    d = 1 if s["designation"] == "bullish" else -1
    rho = s["rho"]
    dm = "Supportive" if rho >= .25 else "Partially Supportive" if rho > 0 else "Contradicted" if rho <= -.25 else "Inconclusive"
    diff = s["hit_excess"] - s["is_stats"]["hit_rate"]
    wr = "Supportive" if diff >= -.25 else "Partially Supportive" if diff >= -.5 else "Contradicted"
    rc = "Supportive" if rho >= .5 else "Partially Supportive" if rho >= .25 else "Contradicted" if rho <= -.25 else "Inconclusive"
    oa, ia = s["avg_mdd"], s["is_stats"]["avg_mdd"]
    if d > 0:
        dc = "Supportive" if oa >= ia - .01 else "Partially Supportive" if oa >= ia - .03 else "Contradicted"
    else:
        dc = "Supportive" if oa <= ia else "Partially Supportive" if oa <= ia + .01 else "Contradicted"
    adv, pct = s["adv_vs_drift"], s["placebo_pct_expected_tail"]
    ba = ("Supportive" if adv > 0 and pct >= .75 else "Partially Supportive" if adv > 0
          else "Contradicted" if pct <= .25 else "Inconclusive")
    return dict(direction_match=dm, win_rate=wr, return_consistency=rc, drawdown=dc, benchmark=ba,
                overall=s["classification"])


def main():
    qr = quality_report(DF, HARD)
    results = {rid: evaluate_rule(rid) for rid in RULES}
    for rid in PRIMARY:
        results[rid]["scorecard"] = scorecard(results[rid])

    # ------------------------------------------------------------- aggregates
    agg = {}
    bulls = [rid for rid in PRIMARY if RULES[rid]["designation"] == "bullish"]
    pooled = [(o, RULES[rid]) for rid in bulls for o in results[rid]["occurrences"] if o["status"] == "complete"]
    obs_ex = np.mean([o["ret"] - r["baseline_mean_return_same_length"] for o, r in pooled])
    obs_ex_drift = np.mean([o["ret"] - drift(o["length"]) for o, r in pooled])
    # placebo with a common random shift per year across rules (keeps overlap structure)
    ent = np.array([max(o["entry_idx"], 0) for o, _ in pooled])
    lens = np.array([o["length"] for o, _ in pooled])
    yrs = np.array([o["year"] for o, _ in pooled])
    bases = np.array([r["baseline_mean_return_same_length"] for _, r in pooled])
    yidx = {y: i for i, y in enumerate(YEARS)}
    sh = RNG.integers(0, T, size=(N_PLACEBO, len(YEARS)))
    st = (ent[None, :] + sh[:, [yidx[y] for y in yrs]]) % (T - lens.max() - 1)
    pr = CLOSE[st + lens[None, :]] / CLOSE[st] - 1
    plac = (pr - bases[None, :]).mean(axis=1)
    agg["Q1"] = dict(n_occurrences=len(pooled), rules=bulls, pooled_mean_return=float(np.mean([o["ret"] for o, _ in pooled])),
                     pooled_excess_vs_is_base=float(obs_ex), pooled_excess_vs_oos_drift=float(obs_ex_drift),
                     placebo_mean_excess=float(plac.mean()), placebo_p_one_sided=float((1 + (plac >= obs_ex).sum()) / (1 + N_PLACEBO)),
                     share_occurrences_beating_drift=float(np.mean([o["ret"] > drift(o["length"]) for o, _ in pooled])))
    # Q2 drawdown set (pre-registered)
    ddset = ["Jun16+10td", "Mar01+10td", "Jan16+10td", "May01+10td", "Oct01+10td", "Feb16+10td",
             "Sep16+20td", "Jun01+20td", "Jun16+20td", "Feb16+20td", "Mar01+20td", "Jan16+20td"]
    q2 = {}
    for L in (10, 20):
        ids = [i for i in ddset if i.endswith(f"+{L}td")]
        mdds = [o["mdd"] for i in ids for o in results[i]["occurrences"] if o["status"] == "complete"]
        k = int(sum(m <= -0.03 for m in mdds))
        u = dd_unconditional(L)
        q2[L] = dict(rules=ids, n=len(mdds), k_ge3=k, freq_ge3=k / len(mdds), uncond_ge3=u["ge3"],
                     freq_ge5=float(np.mean([m <= -0.05 for m in mdds])), uncond_ge5=u["ge5"],
                     avg_mdd=float(np.mean(mdds)), uncond_avg=u["avg"],
                     p_binom_greater=float(stats.binomtest(k, len(mdds), u["ge3"], alternative="greater").pvalue))
    agg["Q2"] = dict(drawdown_set=q2, sep16=dict((k, results["Sep16+10td"][k]) for k in
                                                ("returns", "mean", "excess_vs_is_base", "excess_vs_oos_drift", "placebo_pct_expected_tail", "classification")))
    # Q3 magnitude
    num = sum((1 if RULES[i]["designation"] == "bullish" else -1) * results[i]["excess_vs_is_base"] for i in PRIMARY)
    den = sum((1 if RULES[i]["designation"] == "bullish" else -1) * RULES[i]["mean_excess_return"] for i in PRIMARY)
    allr = [results[i] for i in RULES if results[i]["n"] >= 3]
    sp = stats.spearmanr([RULES[x["id"]]["mean_excess_return"] for x in allr], [x["excess_vs_is_base"] for x in allr])
    sp_drift = stats.spearmanr([RULES[x["id"]]["mean_excess_return"] for x in allr], [x["excess_vs_oos_drift"] for x in allr])
    agg["Q3"] = dict(pooled_rho_primary=float(num / den),
                     spearman_is_vs_oos_excess=float(sp.statistic),
                     spearman_p_one_sided=float(sp.pvalue / 2 if sp.statistic > 0 else 1 - sp.pvalue / 2),
                     spearman_vs_oos_drift=float(sp_drift.statistic), n_rules=len(allr))
    # Q4 directions
    cnt = lambda ids: pd.Series([results[i]["effect"] for i in ids]).value_counts().to_dict()
    sgn = [((1 if RULES[x["id"]]["designation"] == "bullish" else -1) * x["excess_vs_is_base"]) > 0 for x in allr]
    sgn_d = [((1 if RULES[x["id"]]["designation"] == "bullish" else -1) * x["excess_vs_oos_drift"]) > 0 for x in allr]
    agg["Q4"] = dict(primary=cnt(PRIMARY), all=cnt(list(RULES)),
                     share_all_same_sign_vs_is_base=float(np.mean(sgn)),
                     binom_p_vs_is_base=float(stats.binomtest(int(sum(sgn)), len(sgn), 0.5, alternative="greater").pvalue),
                     share_all_same_sign_vs_oos_drift=float(np.mean(sgn_d)),
                     binom_p_vs_oos_drift=float(stats.binomtest(int(sum(sgn_d)), len(sgn_d), 0.5, alternative="greater").pvalue),
                     classes_primary=pd.Series([results[i]["classification"] for i in PRIMARY]).value_counts().to_dict(),
                     classes_all=pd.Series([results[i]["classification"] for i in RULES]).value_counts().to_dict())
    agg["Q5"] = {i: results[i]["placebo_pct_expected_tail"] for i in PRIMARY}

    # ------------------------------------------------------------- seasonal paths
    paths = {}
    for y in YEARS:
        idx = np.nonzero((CAL >= np.datetime64(f"{y}-01-01")) & (CAL <= np.datetime64(f"{y}-12-31")))[0]
        base = FIRST_OPEN if idx[0] == 0 else CLOSE[idx[0] - 1]
        paths[y] = (CLOSE[idx] / base * 100).round(3).tolist()

    out = dict(frozen_sha256=FROZEN_SHA, criteria_sha256=sha256(os.path.join(HERE, "oos_validation_criteria.yaml")),
               data_sha256=sha256(os.path.join(HERE, "data", "GSPC_2023_2026-10-02.csv")),
               data_quality=qr, hard_stop=HARD, results=results, aggregate=agg, paths=paths,
               oos_drift={L: drift(L) for L in (5, 10, 15, 20, 30)})
    pickle.dump(out, open(os.path.join(OUT, "oos_results.pkl"), "wb"))
    print(json.dumps(agg, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
