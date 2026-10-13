"""
S&P 500 seasonality discovery study — in-sample 2003-01-01 .. 2022-12-31 only.

Every historical trade (window occurrence) is evaluated through
MarketData.as_of(exit_date): the strategy sees only bars dated <= the exit
date, and the entry decision is purely calendar-based (no price input).

Run:  python analysis.py      -> writes outputs/results.pkl + CSV tables
"""
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from data_handler import load_market_data

ENGINE_VERSION = "1.0.0"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

cfg = yaml.safe_load(open("config.yaml"))
md = load_market_data(cfg)
CAL = md.trading_calendar
HARD_STOP = md.hard_stop
assert CAL[-1] <= HARD_STOP
RNG = np.random.default_rng(cfg["statistics"]["random_seed"])
Y0, Y1 = int(cfg["study"]["start_date"][:4]), int(cfg["study"]["end_date"][:4])
YEARS = list(range(Y0, Y1 + 1))
OUT = "outputs"
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------------------
# Point-in-time trade evaluation
# ---------------------------------------------------------------------------
def _entry_index(anchor: np.datetime64) -> int:
    """Last trading bar strictly before the anchor date (-1 => use first Open)."""
    return int(np.searchsorted(CAL, anchor, side="left")) - 1


def evaluate_trade(entry_idx: int, exit_idx: int):
    """Evaluate a hold from close[entry_idx] to close[exit_idx] using ONLY a
    point-in-time view as of the exit date. Returns None if exit is beyond data."""
    if exit_idx >= len(CAL) or exit_idx <= max(entry_idx, -1):
        return None
    view = md.as_of(CAL[exit_idx])           # nothing after the exit date exists here
    assert view.dates[-1] == CAL[exit_idx]
    if entry_idx >= 0:
        path = view.close[entry_idx: exit_idx + 1]
        entry_date = view.dates[entry_idx]
    else:                                    # Jan 2003: use first available open
        path = np.concatenate([[view.open[0]], view.close[: exit_idx + 1]])
        entry_date = view.dates[0]
    ret = path[-1] / path[0] - 1.0
    peak = np.maximum.accumulate(path)
    dd_series = path / peak - 1.0
    trough = int(np.argmin(dd_series))
    return dict(ret=float(ret), mdd=float(dd_series.min()), entry_date=entry_date,
                exit_date=view.dates[-1], trough_offset=trough,
                peak_level=float(peak[trough]), path_len=len(path))


def recovery_days(exit_idx: int, trough_offset: int, path_len: int, peak_level: float):
    """Trading days from trough until close regains prior peak (in-sample only)."""
    full = md.as_of(HARD_STOP).close
    t_idx = exit_idx - (path_len - 1) + trough_offset
    after = np.nonzero(full[t_idx:] >= peak_level)[0]
    return int(after[0]) if len(after) else np.nan


# ---------------------------------------------------------------------------
# Baselines (unconditional drift) — all from 2003-2022 data
# ---------------------------------------------------------------------------
FULL_CLOSE = md.as_of(HARD_STOP).close
LOGRET = np.diff(np.log(FULL_CLOSE))


def baseline(n: int):
    r = FULL_CLOSE[n:] / FULL_CLOSE[:-n] - 1
    return float(r.mean()), float((r > 0).mean())


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------
def streaks(signs):
    best_w = best_l = cur_w = cur_l = 0
    for s in signs:
        cur_w = cur_w + 1 if s > 0 else 0
        cur_l = cur_l + 1 if s <= 0 else 0
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
    return best_w, best_l


def boot_ci(x, draws, alpha=0.05):
    idx = RNG.integers(0, len(x), size=(draws, len(x)))
    m = x[idx].mean(axis=1)
    return float(np.quantile(m, alpha / 2)), float(np.quantile(m, 1 - alpha / 2))


def bh_qvalues(p):
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[i] * n / rank)
        q[i] = prev
    return q


def describe(rets, mdds, base_mean, base_win, draws):
    r = np.asarray(rets)
    d = np.asarray(mdds)
    x = r - base_mean
    n = len(r)
    sd = r.std(ddof=1)
    t_x, p_t = stats.ttest_1samp(x, 0.0)
    try:
        p_w = stats.wilcoxon(x).pvalue
    except ValueError:
        p_w = 1.0
    npos = int((r > 0).sum())
    p_sign = stats.binomtest(npos, n, base_win).pvalue
    se = sd / np.sqrt(n)
    tcrit = stats.t.ppf(0.975, n - 1)
    pos, neg = r[r > 0], r[r <= 0]
    favour = np.sort(x)[::-1] if x.mean() > 0 else np.sort(x)   # most favourable first
    excl2 = favour[2:].mean()
    top2_share = favour[:2].sum() / x.sum() if x.sum() != 0 else np.nan
    w, l = streaks(r)
    bci = boot_ci(r, draws)
    return dict(
        n=n, n_pos=npos, n_neg=n - npos, pct_pos=npos / n, pct_neg=1 - npos / n,
        mean=r.mean(), median=float(np.median(r)), std=sd,
        avg_pos=pos.mean() if len(pos) else np.nan, avg_neg=neg.mean() if len(neg) else np.nan,
        max_ret=r.max(), min_ret=r.min(),
        reward_risk=(r.mean() / sd) if sd > 0 else np.nan,
        ci_lo=r.mean() - tcrit * se, ci_hi=r.mean() + tcrit * se,
        boot_lo=bci[0], boot_hi=bci[1],
        base_mean=base_mean, base_win=base_win,
        mean_excess=x.mean(), median_excess=float(np.median(x)),
        t=float(t_x), p_t=float(p_t), p_wilcoxon=float(p_w), p_sign=float(p_sign),
        cohen_d=x.mean() / x.std(ddof=1),
        mean_excess_excl_top2=float(excl2), top2_share_of_excess=float(top2_share),
        streak_win=w, streak_loss=l,
        avg_mdd=d.mean(), median_mdd=float(np.median(d)), worst_mdd=d.min(),
        freq_dd2=float((d <= -0.02).mean()), freq_dd3=float((d <= -0.03).mean()),
        freq_dd5=float((d <= -0.05).mean()),
    )


def half_stats(df, base_mean):
    out = {}
    for name, (a, b) in cfg["study"]["subperiods"].items():
        s = df[(df.year >= int(a[:4])) & (df.year <= int(b[:4]))]
        r = s.ret.values
        out[name] = dict(n=len(r), pct_pos=float((r > 0).mean()), mean=float(r.mean()),
                         median=float(np.median(r)), std=float(r.std(ddof=1)),
                         worst_mdd=float(s.mdd.min()), avg_mdd=float(s.mdd.mean()),
                         mean_excess=float(r.mean() - base_mean))
    return out


# ---------------------------------------------------------------------------
# Analysis 1 — calendar months
# ---------------------------------------------------------------------------
def month_trades():
    rows = []
    for y in YEARS:
        for m in range(1, 13):
            start = np.datetime64(f"{y}-{m:02d}-01")
            end = np.datetime64(f"{y + (m == 12)}-{(m % 12) + 1:02d}-01")
            e = _entry_index(start)
            x = _entry_index(end)               # last bar of month
            t = evaluate_trade(e, x)
            if t:
                rows.append(dict(year=y, month=m, **t))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Analysis 2 — systematic calendar window grid
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Window:
    month: int
    day: int
    length: int

    @property
    def wid(self):
        return f"{MONTHS[self.month - 1]}{self.day:02d}+{self.length}td"


def window_grid():
    s = cfg["seasonality"]
    return [Window(m, d, n) for m in range(1, 13) for d in s["anchor_days_of_month"]
            for n in s["window_lengths"]]


def window_trades(w: Window):
    rows = []
    for y in YEARS:
        anchor = np.datetime64(f"{y}-{w.month:02d}-{w.day:02d}")
        e = _entry_index(anchor)
        t = evaluate_trade(e, e + w.length)
        if t:
            rows.append(dict(year=y, entry_idx=e, **t))
    return pd.DataFrame(rows)


def typical_dates(df):
    first = pd.to_datetime(df.exit_date)
    md_ = first.dt.strftime("%m-%d")
    end = sorted(md_)[len(md_) // 2]
    return end, sorted(md_)[0], sorted(md_)[-1]


# ---------------------------------------------------------------------------
# Multiple testing: calendar-scramble permutation (max-|t| family-wise)
# ---------------------------------------------------------------------------
def permutation_fwer(windows, trades, base, draws):
    """Null: each year's window start dates are shifted together by a random
    number of trading days (same shift for every window in that year), which
    preserves window lengths, overlap structure and the year's volatility
    regime while destroying any fixed calendar alignment."""
    cum = np.concatenate([[0.0], np.cumsum(LOGRET)])  # cum[i] = log(close[i]/close[0])
    T = len(FULL_CLOSE)
    maxlen = max(w.length for w in windows)
    obs_t = np.array([trades[w.wid]["t"] for w in windows])
    entry = [trades[w.wid]["df"].entry_idx.values for w in windows]
    years = [trades[w.wid]["df"].year.values for w in windows]
    yr_index = {y: i for i, y in enumerate(YEARS)}
    max_abs = np.empty(draws)
    per_win_ge = np.zeros(len(windows))
    for k in range(draws):
        shift = RNG.integers(0, T, size=len(YEARS))
        tk = np.empty(len(windows))
        for j, w in enumerate(windows):
            e = np.clip(entry[j], 0, None)
            s = (e + shift[[yr_index[y] for y in years[j]]]) % (T - maxlen - 1)
            r = np.exp(cum[s + w.length] - cum[s]) - 1 - base[w.length][0]
            sd = r.std(ddof=1)
            tk[j] = r.mean() / (sd / np.sqrt(len(r))) if sd > 0 else 0.0
        max_abs[k] = np.abs(tk).max()
        per_win_ge += np.abs(tk) >= np.abs(obs_t)
    fwer = np.array([(1 + (max_abs >= abs(t)).sum()) / (1 + draws) for t in obs_t])
    per = (1 + per_win_ge) / (1 + draws)
    return fwer, per, max_abs


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify(s, halves, q, perm_fwer=None):
    c = cfg["classification"]
    bull = s["mean_excess"] > 0
    sign = 1 if bull else -1
    same = all(np.sign(h["mean_excess"]) == sign for h in halves.values())
    robust = np.sign(s["mean_excess_excl_top2"]) == sign
    hit = s["pct_pos"] if bull else s["pct_neg"]
    raw_p = min(s["p_t"], s["p_wilcoxon"])
    if (q <= c["strong"]["fdr_q_max"] and s["p_wilcoxon"] <= c["strong"]["wilcoxon_p_max"]
            and same and robust and hit >= c["strong"]["min_hit_rate"]):
        cls = "Strong Historical Evidence"
    elif raw_p <= c["moderate"]["raw_p_max"] and same and robust:
        cls = "Moderate Historical Evidence"
    elif raw_p <= c["weak"]["raw_p_max"] or (same and robust and hit >= 0.6):
        cls = "Weak / Inconclusive"
    else:
        cls = "No Meaningful Seasonal Effect"
    flags = []
    if not robust:
        flags.append("result reverses sign without the 2 most favourable years")
    elif abs(s["top2_share_of_excess"]) > 0.6:
        flags.append(f"top 2 years = {s['top2_share_of_excess']:.0%} of total excess return")
    if not same:
        flags.append("sign differs between 2003-12 and 2013-22")
    return ("bullish" if bull else "bearish"), cls, same, bool(robust), hit, flags


CLASS_RANK = {"Strong Historical Evidence": 0, "Moderate Historical Evidence": 1,
              "Weak / Inconclusive": 2, "No Meaningful Seasonal Effect": 3}


def main():
    st = cfg["statistics"]
    draws_b = st["bootstrap_draws"]

    # ---------------- months
    mt = month_trades()
    allm = mt.ret.values
    base_m = (float(allm.mean()), float((allm > 0).mean()))
    month_rows = []
    for m in range(1, 13):
        df = mt[mt.month == m]
        s = describe(df.ret.values, df.mdd.values, *base_m, draws_b)
        s["month"] = MONTHS[m - 1]
        s["halves"] = half_stats(df, base_m[0])
        s["per_year"] = dict(zip(df.year.astype(int), df.ret.round(6)))
        month_rows.append(s)
    qm = bh_qvalues([r["p_t"] for r in month_rows])
    for r, q in zip(month_rows, qm):
        r["q_fdr"] = q
        r["direction"], r["classification"], r["halves_agree"], r["robust"], r["hit_rate"], r["flags"] = \
            classify(r, r["halves"], q)

    # ---------------- windows
    windows = window_grid()
    base = {n: baseline(n) for n in cfg["seasonality"]["window_lengths"]}
    trades = {}
    for w in windows:
        df = window_trades(w)
        assert len(df) >= cfg["seasonality"]["min_years"], w.wid
        s = describe(df.ret.values, df.mdd.values, *base[w.length], draws_b)
        rec = [recovery_days(int(r.entry_idx) + w.length, r.trough_offset, r.path_len, r.peak_level)
               for r in df.itertuples() if r.mdd <= -0.02]
        s["median_recovery_days_dd2"] = float(np.nanmedian(rec)) if len(rec) and not np.all(np.isnan(rec)) else np.nan
        s["unrecovered_dd2"] = int(np.isnan(rec).sum()) if len(rec) else 0
        s["halves"] = half_stats(df, base[w.length][0])
        end, end_lo, end_hi = typical_dates(df)
        s.update(id=w.wid, month=w.month, day=w.day, length=w.length,
                 start_md=f"{w.month:02d}-{w.day:02d}", typical_end_md=end,
                 end_range=(end_lo, end_hi),
                 label=f"{MONTHS[w.month-1]} {w.day} → ~{MONTHS[int(end[:2])-1]} {int(end[3:])} ({w.length} td)",
                 per_year=dict(zip(df.year.astype(int), df.ret.round(6))),
                 per_year_mdd=dict(zip(df.year.astype(int), df.mdd.round(6))),
                 df=df)
        trades[w.wid] = s

    q = bh_qvalues([trades[w.wid]["p_t"] for w in windows])
    fwer, perm_p, null_max = permutation_fwer(windows, trades, base, st["permutation_draws"])
    q_perm = bh_qvalues(perm_p)
    for w, qi, f, pp, qp in zip(windows, q, fwer, perm_p, q_perm):
        s = trades[w.wid]
        s["q_fdr"], s["perm_fwer_p"], s["perm_p"], s["perm_q_fdr"] = float(qi), float(f), float(pp), float(qp)
        s["direction"], s["classification"], s["halves_agree"], s["robust"], s["hit_rate"], s["flags"] = \
            classify(s, s["halves"], qi)

    res = dict(engine_version=ENGINE_VERSION, config=cfg, data=md.summary(), months=month_rows,
               month_baseline=base_m, windows=[trades[w.wid] for w in windows], baselines=base,
               null_max_t=null_max, n_windows=len(windows))

    # per-day series for charts (calendar paths)
    dates = pd.to_datetime(CAL.astype("datetime64[ns]"))
    res["daily"] = pd.DataFrame(dict(date=dates, close=FULL_CLOSE, open=md.as_of(HARD_STOP).open))
    pickle.dump(res, open(f"{OUT}/results.pkl", "wb"))

    # flat CSVs
    keep = [k for k in trades[windows[0].wid] if k not in ("df", "per_year", "per_year_mdd", "halves", "flags", "end_range")]
    pd.DataFrame([{k: trades[w.wid][k] for k in keep} for w in windows]).to_csv(f"{OUT}/all_windows.csv", index=False)
    mk = [k for k in month_rows[0] if k not in ("halves", "per_year", "flags")]
    pd.DataFrame([{k: r[k] for k in mk} for r in month_rows]).to_csv(f"{OUT}/months.csv", index=False)
    print("windows tested:", len(windows), "| classes:",
          pd.Series([trades[w.wid]["classification"] for w in windows]).value_counts().to_dict())


if __name__ == "__main__":
    main()
