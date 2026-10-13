"""
Builds chart data, PNG charts and the FROZEN pattern file from outputs/results.pkl.
Run after analysis.py:  python build_outputs.py
"""
import datetime as dt
import hashlib
import json
import os
import pickle

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

R = pickle.load(open("outputs/results.pkl", "rb"))
CFG = R["config"]
daily = R["daily"]
HARD = pd.Timestamp(CFG["data_guardrails"]["hard_stop_date"])
assert daily.date.max() <= HARD, "post-cutoff data present"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
os.makedirs("outputs/charts", exist_ok=True)


def _f(x, nd=6):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, (np.floating, float)):
        return round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


# ---------------------------------------------------------------- seasonal paths
daily["year"] = daily.date.dt.year
paths = {}
start_idx = {}
for y, g in daily.groupby("year"):
    i0 = g.index[0]
    base = daily.open.iloc[0] if i0 == 0 else daily.close.iloc[i0 - 1]
    paths[y] = (g.close.values / base * 100.0)
    start_idx[y] = i0
L = 252
mat = np.vstack([np.pad(p[:L], (0, max(0, L - len(p))), mode="edge") for p in paths.values()])
avg_path, med_path = mat.mean(0), np.median(mat, 0)
prob_pos = (mat > 100).mean(0)
# typical calendar date for each trading-day index (median month-day across years)
lab = []
for k in range(L):
    mds = sorted(daily.date.iloc[start_idx[y] + min(k, len(paths[y]) - 1)].strftime("%m-%d") for y in paths)
    lab.append(mds[len(mds) // 2])


def tdoy(md_):
    """Trading-day-of-year index for a month-day (first index whose typical date >= md)."""
    for k, s in enumerate(lab):
        if s >= md_:
            return k
    return L - 1


# ---------------------------------------------------------------- heatmap: 5-td forward excess from each date
close = daily.close.values
dates = daily.date.values.astype("datetime64[D]")
b5 = np.mean(close[5:] / close[:-5] - 1)
heat = []
for m in range(1, 13):
    for d in range(1, 32):
        try:
            dt.date(2021, m, d)
        except ValueError:
            continue
        xs, pos = [], 0
        for y in range(2003, 2023):
            a = np.datetime64(f"{y}-{m:02d}-{d:02d}")
            e = int(np.searchsorted(dates, a)) - 1
            p0 = daily.open.iloc[0] if e < 0 else close[e]
            x = e + 5
            if x >= len(close):
                continue
            r = close[x] / p0 - 1
            xs.append(r - b5)
            pos += r > 0
        heat.append(dict(m=m, d=d, ex=float(np.mean(xs)), pp=pos / len(xs), n=len(xs)))

# ---------------------------------------------------------------- frozen pattern file
W = R["windows"]
order = {"Strong Historical Evidence": 0, "Moderate Historical Evidence": 1,
         "Weak / Inconclusive": 2, "No Meaningful Seasonal Effect": 3}


def pattern(s, kind="window"):
    rec = dict(
        id=s["id"] if kind == "window" else f"MONTH-{s['month']}",
        type=kind,
        designation=s["direction"],
        classification=s["classification"],
        entry_rule=("Buy at the close of the last trading day BEFORE " +
                    (f"{MONTHS[s['month']-1]} {s['day']}" if kind == "window" else f"the 1st of {s['month']}")),
        exit_rule=(f"Sell at the close of the {s['length']}th trading day counting the first trading day on/after the anchor date"
                   if kind == "window" else f"Sell at the close of the last trading day of {s['month']}"),
        window_start_month_day=s.get("start_md", None),
        window_length_trading_days=s.get("length", None),
        typical_window_end_month_day=s.get("typical_end_md", None),
        window_end_range_month_day=list(s["end_range"]) if "end_range" in s else None,
        historical_years=s["n"],
        win_rate=_f(s["pct_pos"]), loss_rate=_f(s["pct_neg"]),
        hit_rate_in_designated_direction=_f(s["hit_rate"]),
        mean_return=_f(s["mean"]), median_return=_f(s["median"]),
        std_return=_f(s["std"]), best_return=_f(s["max_ret"]), worst_return=_f(s["min_ret"]),
        baseline_mean_return_same_length=_f(s["base_mean"]),
        baseline_win_rate_same_length=_f(s["base_win"]),
        mean_excess_return=_f(s["mean_excess"]),
        avg_max_drawdown=_f(s["avg_mdd"]), median_max_drawdown=_f(s["median_mdd"]),
        worst_max_drawdown=_f(s["worst_mdd"]),
        freq_drawdown_gt_2pct=_f(s["freq_dd2"]), freq_drawdown_gt_3pct=_f(s["freq_dd3"]),
        freq_drawdown_gt_5pct=_f(s["freq_dd5"]),
        ci95_mean_t=[_f(s["ci_lo"]), _f(s["ci_hi"])],
        ci95_mean_bootstrap=[_f(s["boot_lo"]), _f(s["boot_hi"])],
        t_stat_excess=_f(s["t"], 4), p_value_t=_f(s["p_t"], 5), p_value_wilcoxon=_f(s["p_wilcoxon"], 5),
        p_value_sign_vs_baseline=_f(s["p_sign"], 5), cohen_d_excess=_f(s["cohen_d"], 4),
        q_value_bh_fdr=_f(s["q_fdr"], 5),
        permutation_p=_f(s.get("perm_p"), 5), permutation_fwer_p=_f(s.get("perm_fwer_p"), 5),
        survives_multiple_testing=bool(s["q_fdr"] <= CFG["statistics"]["fdr_q"]),
        subperiods={k: {kk: _f(vv) for kk, vv in v.items()} for k, v in s["halves"].items()},
        consistency=dict(longest_win_streak=s["streak_win"], longest_loss_streak=s["streak_loss"],
                         top2_share_of_excess=_f(s["top2_share_of_excess"]),
                         mean_excess_excluding_top2=_f(s["mean_excess_excl_top2"]),
                         flags=s["flags"]),
        in_sample_returns_by_year={str(k): _f(v) for k, v in s["per_year"].items()},
    )
    return rec


frozen = dict(
    title="S&P 500 seasonal patterns — discovered on 2003-01-01..2022-12-31 ONLY",
    frozen_at_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    status="FROZEN — do not modify after out-of-sample data (2023-01-01 onward) is seen",
    engine_version=R["engine_version"],
    data=dict(instrument=CFG["study"]["instrument"], source=CFG["study"]["data_source"],
              file_sha256=CFG["study"]["data_sha256"], first_bar=R["data"]["first"],
              last_bar=R["data"]["last"], observations=R["data"]["n_obs"],
              prices="Unadjusted index levels (price index; dividends excluded)"),
    parameters=dict(config=CFG),
    methodology=dict(
        returns="Simple price return, entry close -> exit close. Excludes dividends, transaction costs, slippage and taxes.",
        excess_return="Window return minus the mean return of ALL overlapping windows of the same length in 2003-2022 (unconditional drift).",
        tests=["one-sample t-test on excess return", "Wilcoxon signed-rank on excess return",
               "binomial sign test of win rate vs unconditional same-length win rate",
               "bootstrap CI (resampling years)", "Benjamini-Hochberg FDR across the 120 windows (and separately the 12 months)",
               "calendar-scramble permutation (within-year common shift), max-|t| family-wise p"],
        drawdown="Max peak-to-trough decline of daily closes inside the holding window, peak includes the entry close.",
        classification_rules=CFG["classification"],
        n_windows_tested=R["n_windows"], n_months_tested=12,
    ),
    oos_test_protocol=dict(
        evaluate="ALL 120 windows and 12 months exactly as defined here, not only the candidates, so the out-of-sample test cannot be cherry-picked.",
        primary_hypotheses=[p for p in []],
        notes="Apply the same entry/exit rules and the same in-sample baseline means (do not re-estimate baselines from OOS data when computing excess return).",
    ),
    candidate_rules=[],
    windows=[],
    months=[],
)
cands = sorted([s for s in W if s["classification"] != "No Meaningful Seasonal Effect"],
               key=lambda s: (order[s["classification"]], s["p_t"]))
frozen["candidate_rules"] = [pattern(s) for s in cands if order[s["classification"]] <= 1]
frozen["oos_test_protocol"]["primary_hypotheses"] = [
    dict(id=p["id"], designation=p["designation"], classification=p["classification"]) for p in frozen["candidate_rules"]]
frozen["windows"] = [pattern(s) for s in W]
frozen["months"] = [pattern(dict(s, month=i + 1), "month") for i, s in enumerate(R["months"])]
for i, mrec in enumerate(frozen["months"]):
    mrec["id"] = f"MONTH-{MONTHS[i]}"
    mrec["entry_rule"] = f"Buy at the close of the last trading day before {MONTHS[i]} 1"
    mrec["exit_rule"] = f"Sell at the close of the last trading day of {MONTHS[i]}"
txt = json.dumps(frozen, indent=2)
open("seasonal_patterns_2003_2022.json", "w").write(txt)
open("seasonal_patterns_2003_2022.sha256", "w").write(hashlib.sha256(txt.encode()).hexdigest() + "  seasonal_patterns_2003_2022.json\n")

# ---------------------------------------------------------------- report data blob
shade = []
for s in cands:
    if order[s["classification"]] <= 1:
        k0 = tdoy(s["start_md"])
        shade.append(dict(id=s["id"], dir=s["direction"], k0=k0, k1=min(L - 1, k0 + s["length"])))
report = dict(
    labels=lab, avg=np.round(avg_path, 3).tolist(), med=np.round(med_path, 3).tolist(),
    prob=np.round(prob_pos, 4).tolist(), heat=heat, shade=shade,
    year_end={str(y): round(float(p[-1]), 2) for y, p in paths.items()},
)
json.dump(report, open("outputs/report_data.json", "w"))

# ---------------------------------------------------------------- static PNG charts (reproducible copies)
x = np.arange(L)
ticks = [k for k in range(L) if k == 0 or lab[k][:2] != lab[k - 1][:2]]
for name, y, ttl, yl in [("chart1_average_path", avg_path, "Average seasonal path (prior year-end = 100), 2003–2022", "Index"),
                         ("chart2_median_path", med_path, "Median seasonal path (prior year-end = 100), 2003–2022", "Index"),
                         ("chart3_prob_positive", prob_pos * 100, "Share of years with a positive year-to-date return, 2003–2022", "% of years")]:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x, y, color="#2a78d6", lw=2)
    ax.axhline(100 if "path" in name else 50, color="#8a8984", lw=1, ls="--")
    ax.set_xticks(ticks, [MONTHS[int(lab[k][:2]) - 1] for k in ticks])
    ax.set_title(ttl, loc="left")
    ax.set_ylabel(yl)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e5e4e0")
    fig.tight_layout()
    fig.savefig(f"outputs/charts/{name}.png", dpi=150)
    plt.close(fig)
fig, ax = plt.subplots(figsize=(10, 4))
for sh in shade:
    ax.axvspan(sh["k0"], sh["k1"], color="#2a78d6" if sh["dir"] == "bullish" else "#e34948", alpha=0.15)
ax.plot(x, avg_path, color="#0b0b0b", lw=2)
ax.set_xticks(ticks, [MONTHS[int(lab[k][:2]) - 1] for k in ticks])
ax.set_title("Average path with nominal bullish (blue) / bearish (red) windows — none survive FDR", loc="left")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig("outputs/charts/chart4_windows_on_path.png", dpi=150)
plt.close(fig)
hm = np.full((12, 31), np.nan)
for h in heat:
    hm[h["m"] - 1, h["d"] - 1] = h["ex"] * 100
fig, ax = plt.subplots(figsize=(11, 4.5))
v = np.nanmax(np.abs(hm))
im = ax.imshow(hm, cmap="RdBu", vmin=-v, vmax=v, aspect="auto")
ax.set_yticks(range(12), MONTHS)
ax.set_xticks(range(0, 31, 5), range(1, 32, 5))
ax.set_title("Calendar heatmap: mean 5-trading-day forward EXCESS return from each date (%), 2003–2022", loc="left")
fig.colorbar(im, ax=ax, label="% vs unconditional 5-day drift")
fig.tight_layout()
fig.savefig("outputs/charts/calendar_heatmap.png", dpi=150)
plt.close(fig)
print("candidates frozen:", [p["id"] for p in frozen["candidate_rules"]])
