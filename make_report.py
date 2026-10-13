"""Render report.html from outputs/results.pkl + outputs/report_data.json. Run after build_outputs.py."""
import json
import pickle

import numpy as np

R = pickle.load(open("outputs/results.pkl", "rb"))
D = json.load(open("outputs/report_data.json"))
FROZEN = json.load(open("seasonal_patterns_2003_2022.json"))
W, M = R["windows"], R["months"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ORDER = {"Strong Historical Evidence": 0, "Moderate Historical Evidence": 1,
         "Weak / Inconclusive": 2, "No Meaningful Seasonal Effect": 3}
SHORT = {0: ("Strong", "s"), 1: ("Moderate*", "m"), 2: ("Weak", "w"), 3: ("None", "n")}
daily = R["daily"]
close = daily.close.values


def pct(x, nd=2, sign=True):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x*100:+.{nd}f}%" if sign else f"{x*100:.{nd}f}%"


def p(x):
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def badge(cls):
    t, c = SHORT[ORDER[cls]]
    return f'<span class="b b-{c}">{t}</span>'


def wlabel(s):
    e = s["typical_end_md"]
    return f'{MON[s["month"]-1]} {s["day"]} → {MON[int(e[:2])-1]} {int(e[3:])}<span class="td">{s["length"]} td</span>'


def table(head, rows, cls=""):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


rank_key = lambda s: (ORDER[s["classification"]], s["p_t"])
bull = sorted([s for s in W if s["direction"] == "bullish"], key=rank_key)[:12]
bear = sorted([s for s in W if s["direction"] == "bearish"], key=rank_key)[:12]


def evidence(s):
    return f'{badge(s["classification"])} <span class="ev">t={s["t"]:+.2f} · p={p(s["p_t"])} · q={s["q_fdr"]:.2f}</span>'


bull_rows = [[i + 1, wlabel(s), s["n"], s["n_pos"], pct(s["pct_pos"], 0, False), pct(s["mean"]), pct(s["median"]),
              pct(s["max_ret"]), pct(s["min_ret"]), pct(s["avg_mdd"]), evidence(s)] for i, s in enumerate(bull)]
bear_rows = [[i + 1, wlabel(s), s["n"], s["n_neg"], pct(s["pct_neg"], 0, False), pct(s["mean"]), pct(s["median"]),
              pct(s["avg_mdd"]), pct(s["worst_mdd"]), evidence(s)] for i, s in enumerate(bear)]


def character(s):
    t = SHORT[ORDER[s["classification"]]][0]
    if t == "None":
        return "No reliable tilt"
    return f'{"Bullish" if s["direction"]=="bullish" else "Bearish"} tilt ({t.lower().rstrip("*")}, not significant)' if t != "Strong" else "Strong"


month_rows = [[s["month"], pct(s["pct_pos"], 0, False), pct(s["pct_neg"], 0, False), pct(s["mean"]), pct(s["median"]),
               pct(s["avg_mdd"]), pct(s["worst_mdd"]), character(s)] for s in M]
month_detail = [[s["month"], s["n"], s["n_pos"], s["n_neg"], pct(s["mean"]), pct(s["median"]), pct(s["max_ret"]),
                 pct(s["min_ret"]), pct(s["std"], 2, False), f'{s["reward_risk"]:.2f}', pct(s["mean_excess"]),
                 f'{s["t"]:+.2f}', p(s["p_t"]), p(s["p_wilcoxon"]), f'{s["q_fdr"]:.2f}'] for s in M]

cands = sorted([s for s in W if ORDER[s["classification"]] <= 1], key=rank_key)
cons_rows = []
for s in cands:
    a, b = s["halves"]["A"], s["halves"]["B"]
    fl = "; ".join(s["flags"]) or "—"
    cons_rows.append([wlabel(s), pct(s["pct_pos"], 0, False), pct(s["mean"]), pct(s["median"]), pct(s["std"], 2, False),
                      f'{s["streak_win"]} / {s["streak_loss"]}',
                      pct(s["top2_share_of_excess"], 0, False), pct(s["mean_excess_excl_top2"]),
                      f'{pct(a["pct_pos"],0,False)} · {pct(a["mean"])} · {pct(a["median"])} · σ {pct(a["std"],1,False)} · DD {pct(a["worst_mdd"],1)}',
                      f'{pct(b["pct_pos"],0,False)} · {pct(b["mean"])} · {pct(b["median"])} · σ {pct(b["std"],1,False)} · DD {pct(b["worst_mdd"],1)}',
                      fl])
sig_rows = [[wlabel(s), pct(s["mean_excess"]), f'{pct(s["ci_lo"])} to {pct(s["ci_hi"])}',
             f'{pct(s["boot_lo"])} to {pct(s["boot_hi"])}', f'{s["t"]:+.2f}', p(s["p_t"]), p(s["p_wilcoxon"]),
             p(s["p_sign"]), f'{s["cohen_d"]:+.2f}', f'{s["q_fdr"]:.2f}', f'{s["perm_fwer_p"]:.2f}', badge(s["classification"])]
            for s in cands]

# drawdown analysis: 20-td windows vs unconditional frequency
from scipy import stats  # noqa: E402


def uncond_dd(n):
    out = []
    for i in range(len(close) - n):
        pth = close[i:i + n + 1]
        out.append((pth / np.maximum.accumulate(pth) - 1).min())
    out = np.array(out)
    return dict(dd3=(out <= -0.03).mean(), dd5=(out <= -0.05).mean(), avg=out.mean())


dd_sections = []
for n in (10, 20):
    u = uncond_dd(n)
    ws = sorted([s for s in W if s["length"] == n], key=lambda s: (-s["freq_dd3"], s["avg_mdd"]))[:6]
    rows = []
    for s in ws:
        k = int(round(s["freq_dd3"] * s["n"]))
        pb = stats.binomtest(k, s["n"], u["dd3"], alternative="greater").pvalue
        neg = [v for v in s["per_year"].values() if v <= 0]
        rows.append([wlabel(s), pct(s["pct_neg"], 0, False), pct(np.mean(neg)) if neg else "—",
                     pct(np.median(neg)) if neg else "—", pct(s["min_ret"]),
                     pct(s["avg_mdd"]), pct(s["median_mdd"]), pct(s["worst_mdd"]),
                     f'{pct(s["freq_dd2"],0,False)} / {pct(s["freq_dd3"],0,False)} / {pct(s["freq_dd5"],0,False)}',
                     "—" if np.isnan(s["median_recovery_days_dd2"]) else f'{s["median_recovery_days_dd2"]:.0f} td' + (f' ({s["unrecovered_dd2"]} open)' if s["unrecovered_dd2"] else ""),
                     p(pb)])
    dd_sections.append((n, u, rows))

n_raw = sum(s["p_t"] < 0.05 for s in W)
n_either = sum(min(s["p_t"], s["p_wilcoxon"]) < 0.05 for s in W)
best = min(W, key=lambda s: s["p_t"])
null_med = float(np.median(R["null_max_t"]))
null95 = float(np.percentile(R["null_max_t"], 95))
c = {k: sum(s["classification"] == k for s in W) for k in ORDER}
S = {s["id"]: s for s in W}


def ln(i):
    s = S[i]
    return f'<b>{wlabel(s)}</b>'


data_js = json.dumps(D)

html = f"""<title>S&amp;P 500 Seasonality 2003–2022</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Serif:wght@500;600&display=swap">
<style>
/* Layout: single reading column (~72ch) with full-width figure/table bands; research-note register */
:root {{
  --bg:#f5f7f8; --panel:#ffffff; --fg:#14181c; --fg2:#4a535c; --muted:#7b858e; --rule:#dde2e6;
  --accent:#1c5cab; --bull:#2a78d6; --bear:#e34948; --mid:#e9ebec; --grid:#e6e9eb;
  --s-bg:#dbe9fb; --s-fg:#184f95; --m-bg:#e7eef8; --m-fg:#256abf; --w-bg:#f0efec; --w-fg:#52514e; --n-bg:transparent; --n-fg:#8a8984;
  --warn-bg:#fdf3e1; --warn-fg:#7a4b00;
  --f-display:"IBM Plex Serif", Georgia, serif;
  --f-body:"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-data:"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#121416; --panel:#1a1d20; --fg:#eef1f3; --fg2:#b9c0c6; --muted:#8a939b; --rule:#2c3136;
  --accent:#6da7ec; --bull:#3987e5; --bear:#e66767; --mid:#383835; --grid:#262a2e;
  --s-bg:#184f95; --s-fg:#e3efff; --m-bg:#1f3352; --m-fg:#9ec5f4; --w-bg:#2b2b29; --w-fg:#c3c2b7; --n-fg:#8a8984;
  --warn-bg:#3a2c12; --warn-fg:#f5cf8a; color-scheme:dark; }} }}
:root[data-theme="dark"] {{
  --bg:#121416; --panel:#1a1d20; --fg:#eef1f3; --fg2:#b9c0c6; --muted:#8a939b; --rule:#2c3136;
  --accent:#6da7ec; --bull:#3987e5; --bear:#e66767; --mid:#383835; --grid:#262a2e;
  --s-bg:#184f95; --s-fg:#e3efff; --m-bg:#1f3352; --m-fg:#9ec5f4; --w-bg:#2b2b29; --w-fg:#c3c2b7; --n-fg:#8a8984;
  --warn-bg:#3a2c12; --warn-fg:#f5cf8a; color-scheme:dark; }}
* {{ box-sizing:border-box }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.6 var(--f-body); padding-inline:16px; padding-block:32px 64px }}
.wrap {{ max-width:1080px; margin:0 auto; display:flex; flex-direction:column; gap:40px }}
.col {{ max-width:72ch }}
h1,h2,h3 {{ font-family:var(--f-display); font-weight:600; text-wrap:balance; margin:0; line-height:1.2 }}
h1 {{ font-size:clamp(28px,4.4vw,40px) }}
h2 {{ font-size:24px; padding-top:8px; border-top:1px solid var(--rule) }}
h3 {{ font-size:17px; font-family:var(--f-body) }}
p {{ margin:0 }}
section {{ display:flex; flex-direction:column; gap:16px; min-width:0 }}
.eyebrow {{ font:500 12px/1 var(--f-data); letter-spacing:.08em; text-transform:uppercase; color:var(--muted) }}
.lede {{ font-size:17px; color:var(--fg2) }}
.meta {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1px; background:var(--rule); border:1px solid var(--rule); border-radius:6px; overflow:hidden }}
.meta div {{ background:var(--panel); padding:10px 14px; display:flex; flex-direction:column; gap:2px; min-width:0 }}
.meta span {{ font:500 11px var(--f-data); letter-spacing:.06em; text-transform:uppercase; color:var(--muted) }}
.meta b {{ font:500 14px var(--f-data); overflow-wrap:anywhere }}
.verdict {{ background:var(--panel); border:1px solid var(--rule); border-radius:8px; padding:20px 22px; display:flex; flex-direction:column; gap:10px }}
.verdict .big {{ font-family:var(--f-display); font-size:21px; line-height:1.35 }}
ol.qa {{ margin:0; padding-left:22px; display:flex; flex-direction:column; gap:12px }}
ol.qa li::marker {{ font-family:var(--f-data); color:var(--muted) }}
ol.qa .q {{ font-weight:600 }}
.tw {{ overflow-x:auto; border:1px solid var(--rule); border-radius:6px; background:var(--panel) }}
table {{ border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums }}
th {{ text-align:left; font:500 11px/1.3 var(--f-data); letter-spacing:.04em; text-transform:uppercase; color:var(--muted); padding:10px 10px; border-bottom:1px solid var(--rule); white-space:nowrap; vertical-align:bottom }}
td {{ padding:8px 10px; border-bottom:1px solid var(--grid); white-space:nowrap; font-family:var(--f-data); font-size:12.5px }}
tr:last-child td {{ border-bottom:0 }}
td:first-child {{ font-family:var(--f-body); }}
.td {{ display:inline-block; margin-left:6px; font:11px var(--f-data); color:var(--muted) }}
.wrapcells td {{ white-space:normal; min-width:90px }}
.b {{ display:inline-block; padding:1px 7px; border-radius:3px; font:500 11px/1.6 var(--f-data); }}
.b-s {{ background:var(--s-bg); color:var(--s-fg) }} .b-m {{ background:var(--m-bg); color:var(--m-fg) }}
.b-w {{ background:var(--w-bg); color:var(--w-fg) }} .b-n {{ color:var(--n-fg); border:1px solid var(--rule) }}
.ev {{ color:var(--muted); margin-left:6px }}
.note {{ font-size:13px; color:var(--fg2) }}
.callout {{ background:var(--warn-bg); color:var(--warn-fg); border-radius:6px; padding:12px 16px; font-size:14px }}
.fig {{ background:var(--panel); border:1px solid var(--rule); border-radius:6px; padding:16px 16px 10px; position:relative; min-width:0 }}
.fig h3 {{ margin-bottom:2px }}
.fig .sub {{ font-size:13px; color:var(--muted); margin-bottom:8px }}
.fig svg {{ display:block; width:100%; height:auto; overflow:visible }}
.figs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr)); gap:16px }}
.tip {{ position:absolute; pointer-events:none; background:var(--fg); color:var(--bg); font:12px/1.4 var(--f-data); padding:6px 9px; border-radius:4px; white-space:nowrap; z-index:2 }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; font-size:12px; color:var(--fg2); margin-top:6px }}
.legend i {{ display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-2px; margin-right:5px }}
.hm {{ overflow-x:auto }}
.hm-grid {{ display:grid; grid-template-columns:40px repeat(31,minmax(16px,1fr)); gap:2px; min-width:620px; font:11px var(--f-data); color:var(--muted) }}
.hm-grid .c {{ aspect-ratio:1; border-radius:2px; }}
.hm-grid .c:hover {{ outline:2px solid var(--fg) }}
.hm-grid .lab {{ display:flex; align-items:center }}
.hm-grid .dl {{ text-align:center }}
.scale {{ display:flex; align-items:center; gap:8px; font:11px var(--f-data); color:var(--muted); margin-top:10px; flex-wrap:wrap }}
.scale .bar {{ height:10px; width:220px; max-width:60vw; border-radius:2px }}
dl.rules {{ display:grid; grid-template-columns:minmax(120px,max-content) 1fr; gap:8px 18px; margin:0 }}
dl.rules dt {{ font-weight:600 }} dl.rules dd {{ margin:0; color:var(--fg2) }}
code {{ font-family:var(--f-data); font-size:.9em; background:var(--mid); padding:1px 5px; border-radius:3px }}
ul.plain {{ margin:0; padding-left:20px; display:flex; flex-direction:column; gap:6px }}
@media (max-width:720px) {{ .meta {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} }}
@media (max-width:560px) {{ dl.rules {{ grid-template-columns:1fr }} body {{ font-size:14.5px }} }}
</style>

<div class="wrap">
<header class="col" style="display:flex;flex-direction:column;gap:14px">
  <div class="eyebrow">^GSPC · in-sample study · data cut off 2022-12-31</div>
  <h1>S&amp;P 500 Seasonality, 2003–2022</h1>
  <p class="lede">I tested a pre-declared grid of calendar windows, plus the 12 calendar months, against 20 years of daily S&amp;P 500 closes. Each was compared against the index's normal drift and corrected for the number of tests run. No market data from 2023 or later was loaded at any step.</p>
</header>

<div class="meta">
  <div><span>Instrument</span><b>^GSPC price index</b></div>
  <div><span>Source</span><b>Yahoo Finance, daily</b></div>
  <div><span>First bar</span><b>{R["data"]["first"]}</b></div>
  <div><span>Last bar</span><b>{R["data"]["last"]}</b></div>
  <div><span>Observations</span><b>{R["data"]["n_obs"]:,} days · 0 missing</b></div>
  <div><span>Prices</span><b>Unadjusted closes, no dividends</b></div>
  <div><span>Windows tested</span><b>{len(W)} + 12 months</b></div>
  <div><span>Hard stop</span><b>2022-12-31 · enforced</b></div>
</div>

<section class="verdict">
  <div class="eyebrow">Bottom line</div>
  <p class="big">The 2003–2022 data does not provide statistically reliable evidence of calendar seasonality in the S&amp;P 500. Of {len(W)} windows, {n_raw} cleared p&nbsp;&lt;&nbsp;0.05 on a t-test, about the {len(W)*0.05:.0f} that chance alone would produce. None survive false-discovery-rate correction (best q&nbsp;=&nbsp;{min(s["q_fdr"] for s in W):.2f}).</p>
  <p class="note">In a calendar-scramble simulation that destroys any real seasonality, the best of 120 windows still reached a median |t| of {null_med:.2f}. The strongest real window, {wlabel(best)}, reached t&nbsp;=&nbsp;{best["t"]:.2f}. That result is what the best of 120 random windows typically looks like (family-wise p&nbsp;=&nbsp;{best["perm_fwer_p"]:.2f}).</p>
</section>

<section class="col">
  <h2>Executive summary</h2>
  <ol class="qa">
    <li><span class="q">Is there meaningful evidence of seasonality?</span> Not statistically. There are recurring tendencies that look interesting, but their number and size match what random noise produces when 120 windows are tested. Classification: <b>0 Strong</b>, <b>{c["Moderate Historical Evidence"]} Moderate</b> (nominal only), {c["Weak / Inconclusive"]} Weak, {c["No Meaningful Seasonal Effect"]} None.</li>
    <li><span class="q">Strongest bullish tendencies.</span> {ln("Jul01+15td")}: 80% of years up, mean {pct(S["Jul01+15td"]["mean"])}, median {pct(S["Jul01+15td"]["median"])}. {ln("Mar16+30td")}: 85% up, mean {pct(S["Mar16+30td"]["mean"])}. {ln("Nov16+15td")}: 85% up, mean {pct(S["Nov16+15td"]["mean"])}. {ln("Apr16+10td")}: 80% up, mean {pct(S["Apr16+10td"]["mean"])}.</li>
    <li><span class="q">Strongest bearish tendency and drawdown risk.</span> {ln("Sep16+10td")} is the only window with nominal bearish support: 60% of years down, mean {pct(S["Sep16+10td"]["mean"])}, median {pct(S["Sep16+10td"]["median"])}. Early June and late January lean weak but are inconclusive. Drawdowns of 3% or more were most frequent in mid-to-late June, late September to mid-October, late February through March, and late January. The deepest of them come from 2008, 2009 and 2020. The drawdown section below separates drawdowns from negative returns.</li>
    <li><span class="q">How often did each occur?</span> The bullish candidates were up in 80–90% of years, against an unconditional base rate of 58–66% for windows of the same length. Late September was down in 60% of years, against a base rate of about 38%.</li>
    <li><span class="q">Average and median moves.</span> These are listed in the tables below. The candidates beat normal drift by roughly 0.6–2.4 percentage points per window. The medians agree in sign with the means, so a single outlier year is not driving any of them.</li>
    <li><span class="q">Consistent across both halves?</span> All 8 Moderate windows have the same sign in 2003–2012 and 2013–2022. The early-July effect is mostly a 2013–2022 phenomenon (100% up, mean {pct(S["Jul01+15td"]["halves"]["B"]["mean"])}, vs 60% and {pct(S["Jul01+15td"]["halves"]["A"]["mean"])} before). Mid-March–April and mid-November were stronger in 2003–2012.</li>
    <li><span class="q">Which survived statistical testing?</span> None. No window or month survives Benjamini–Hochberg FDR at q&nbsp;≤&nbsp;0.10, and none survives the permutation family-wise test.</li>
    <li><span class="q">Too weak or unstable to rely on.</span> Every calendar month: none has p&nbsp;&lt;&nbsp;0.05, including the well-known “Sell in May” and “September effect”. Also early June, late January, early October and the Santa-Claus period. The Nov16+30td candidate qualifies only on its Wilcoxon test (t-test p&nbsp;=&nbsp;{S["Nov16+30td"]["p_t"]:.2f}).</li>
    <li><span class="q">Economically meaningful?</span> Marginally at best. An excess of +0.6–2.4% over 1–6 weeks is real money if it persists. But the 95% confidence intervals are wide and several nearly touch zero, and the figures exclude costs, slippage, taxes and dividends. Worst-year drawdowns inside the "bullish" windows reached −5% to −17%.</li>
    <li><span class="q">What gets frozen?</span> All 120 windows and 12 months, with exact entry and exit rules and in-sample statistics, go into <code>seasonal_patterns_2003_2022.json</code>. The 8 Moderate windows are flagged as the primary out-of-sample hypotheses. Testing all 132 later prevents cherry-picking after the fact.</li>
  </ol>
</section>

<section>
  <h2>Seasonal paths</h2>
  <p class="note col">Each year is indexed to the prior year's last close = 100 and aligned by trading day of the year. The x-axis shows the typical calendar date for that trading day.</p>
  <div class="figs">
    <div class="fig"><h3>Chart 1 · Average path</h3><div class="sub">Mean of 20 yearly paths</div><div id="c1"></div></div>
    <div class="fig"><h3>Chart 2 · Median path</h3><div class="sub">Median of 20 yearly paths</div><div id="c2"></div></div>
    <div class="fig"><h3>Chart 3 · Probability of a positive year-to-date</h3><div class="sub">Share of years above the prior year-end close</div><div id="c3"></div></div>
    <div class="fig"><h3>Chart 4 · Candidate windows on the average path</h3><div class="sub">Moderate windows only. None survive FDR correction.</div><div id="c4"></div>
      <div class="legend"><span><i style="background:var(--bull);opacity:.35"></i>Bullish candidate</span><span><i style="background:var(--bear);opacity:.35"></i>Bearish candidate</span></div></div>
  </div>
</section>

<section>
  <h2>Calendar heatmap</h2>
  <p class="note col">Each cell is the mean 5-trading-day forward return from that calendar date, minus the normal 5-day drift ({pct(R["baselines"][5][0])}), averaged over 2003–2022. Adjacent cells overlap, so neighbouring days are not independent. Hover a cell for its value and win rate.</p>
  <div class="fig hm"><div class="hm-grid" id="hm"></div>
    <div class="scale"><span>Weaker than drift</span><span class="bar" id="hmbar"></span><span>Stronger than drift</span><span id="hmrange"></span></div></div>
</section>

<section>
  <h2>Monthly summary</h2>
  {table(["Month","Positive %","Negative %","Avg return","Median return","Avg drawdown","Max drawdown","Seasonal character"], month_rows)}
  <h3>Monthly detail</h3>
  {table(["Month","Years","Up","Down","Mean","Median","Best","Worst","Std dev","Mean/σ","Excess vs avg month","t","p (t)","p (Wilcoxon)","q (FDR)"], month_detail)}
  <p class="note col">Month return is measured from the prior month's last close to the month's last close (January 2003 uses the 2003-01-02 open). Excess is measured against the average month across all 240 months ({pct(R["month_baseline"][0])}). Drawdown is the deepest close-to-close decline from the running peak within the month, with the entry close included in the peak.</p>
</section>

<section>
  <h2>Primary bullish seasonality table</h2>
  <p class="note col">Ranked by strength of evidence (classification, then p-value), not by return. <span class="b b-m">Moderate*</span> means nominal significance with stable halves; it does not survive multiple-testing correction.</p>
  {table(["Rank","Seasonal period","Years","Positive years","Positive %","Avg return","Median return","Max gain","Worst loss","Avg drawdown","Statistical evidence"], bull_rows)}
</section>

<section>
  <h2>Primary bearish seasonality table</h2>
  {table(["Rank","Seasonal period","Years","Negative years","Negative %","Avg return","Median return","Avg drawdown","Max drawdown","Statistical evidence"], bear_rows)}
  <p class="note col">Few windows have a negative average return. In a market rising about 9% a year, "bearish" in practice means weaker than drift. Only one window clears even nominal significance.</p>
</section>

<section>
  <h2>Consistency and subperiod stability</h2>
  <p class="note col">Moderate candidates only. Each half shows win rate · mean · median · volatility · worst drawdown. "Top-2 share" is the portion of total excess return contributed by the two most favourable years. A window is flagged if dropping those two years flips its sign.</p>
  {table(["Window","Win %","Mean","Median","Std dev","Longest win / loss streak (yrs)","Top-2 share","Mean excess ex top-2","2003–2012","2013–2022","Flags"], cons_rows, "wrapcells")}
</section>

<section>
  <h2>Statistical significance</h2>
  {table(["Window","Mean excess","95% CI mean (t)","95% CI mean (bootstrap)","t","p (t)","p (Wilcoxon)","p (sign vs base rate)","Cohen d","q (BH-FDR)","Perm. FWER p","Class"], sig_rows)}
  <div class="callout col">With {len(W)} windows tested at α&nbsp;=&nbsp;0.05, about {len(W)*0.05:.0f} false positives are expected. The study found {n_raw} on the t-test and {n_either} on either test. The 95th percentile of the permutation max-|t| is {null95:.2f}, and no real window comes close.</div>
</section>

<section>
  <h2>Drawdown analysis</h2>
  <p class="note col">A <b>negative return</b> means the window closed below its entry. An <b>intra-period drawdown</b> is the deepest close-to-close fall from a running peak inside the window, and it can be large even when the window ends positive. Windows are ranked by how often they saw a drawdown of 3% or more. The last column tests that frequency against the rate for any window of the same length (uncorrected, 24 windows per length). Recovery counts trading days from the trough back to the prior peak.</p>
  {"".join(f'<h3>{n}-trading-day windows · unconditional: ≥3% DD in {pct(u["dd3"],0,False)}, ≥5% DD in {pct(u["dd5"],0,False)}, avg DD {pct(u["avg"])}</h3>' + table(["Window","Negative %","Avg decline (neg yrs)","Median decline","Largest decline","Avg max DD","Median max DD","Worst max DD","DD ≥2 / 3 / 5%","Median recovery","p (DD≥3% vs base)"], rows) for n,u,rows in dd_sections)}
  <p class="note col">The worst drawdowns in these windows come from a few crisis episodes: Sep–Oct 2008, Feb–Mar 2020 and early 2009. June is the exception, where 3%+ drawdowns are frequent but spread across many years (2008, 2010, 2016, 2020, 2022). The best drawdown-frequency result (Jun 16, p = 0.046) is not significant once you account for 24 comparisons per length.</p>
</section>

<section class="col">
  <h2>Classification rules</h2>
  <p class="note">The rules were fixed in <code>config.yaml</code> before the results were seen. A window's direction comes from the sign of its mean excess return. "Halves agree" means the mean excess has the same sign in 2003–2012 and 2013–2022. "Robust" means the sign holds after removing the two most favourable years.</p>
  <dl class="rules">
    <dt>{badge("Strong Historical Evidence")}</dt><dd>BH-FDR q ≤ 0.10, Wilcoxon p ≤ 0.05, halves agree, robust, and a hit rate of at least 65% in the stated direction. <b>No window qualified.</b></dd>
    <dt>{badge("Moderate Historical Evidence")}</dt><dd>Raw p ≤ 0.05 on the t-test or Wilcoxon, halves agree, robust. Nominal evidence that does not survive multiplicity correction. 8 windows.</dd>
    <dt>{badge("Weak / Inconclusive")}</dt><dd>Raw p ≤ 0.20, or halves agree and robust with a hit rate of at least 60%. {c["Weak / Inconclusive"]} windows.</dd>
    <dt>{badge("No Meaningful Seasonal Effect")}</dt><dd>Everything else. {c["No Meaningful Seasonal Effect"]} windows.</dd>
  </dl>
</section>

<section class="col">
  <h2>Method and assumptions</h2>
  <ul class="plain">
    <li><b>Search grid (not optimised).</b> Windows start on the 1st and the 16th of every month and run for 5, 10, 15, 20 or 30 trading days: 24 anchors × 5 lengths = 120 windows. Start and end dates were never moved to improve results.</li>
    <li><b>Entry and exit.</b> Buy at the close of the last trading day before the anchor date. Sell at the close of the Nth trading day. Dec-16 windows of 15 days or more have 19 occurrences, because their 2022 instance would have ended in 2023 and was excluded.</li>
    <li><b>Excess return.</b> Each window is tested against the mean return of all overlapping windows of the same length in 2003–2022. This keeps the index's general upward drift from being counted as seasonality.</li>
    <li><b>Tests.</b> One-sample t-test and Wilcoxon signed-rank on excess return; a binomial sign test against the unconditional win rate; a 95% bootstrap CI (10,000 resamples of years); Cohen's d; Benjamini–Hochberg FDR across the 120 windows (and separately the 12 months); and a 2,000-draw calendar-scramble permutation. The permutation shifts every window in a year by the same random number of days, which preserves window overlap and volatility regimes, and yields max-|t| family-wise p-values.</li>
    <li><b>Point-in-time engine.</b> Every trade is evaluated through <code>MarketData.as_of(exit_date)</code>. That returns a read-only copy holding only bars on or before that date, so later bars are not in memory. Requesting a later bar raises <code>LookAheadError</code>. The loader raises <code>FutureDataError</code> if any row is dated after 2022-12-31. All 11 guardrail tests pass.</li>
    <li><b>Not a trading system.</b> Returns exclude transaction costs, slippage, taxes and dividends (^GSPC is a price index). Window selection is in-sample by construction, so the out-of-sample test is the real evidence.</li>
    <li><b>Sample length.</b> Only 2003–2022 was loaded, so there is no longer-history comparison. Twenty observations per window give low statistical power. Effects smaller than about 1.5–2% per window can't be distinguished from noise.</li>
  </ul>
</section>

<section class="col">
  <h2>Frozen for out-of-sample testing</h2>
  <p class="note">These are the primary hypotheses for 2023 onward. Use the exact rules and the in-sample baselines without re-estimating them. The SHA-256 of the frozen JSON is saved alongside it.</p>
  {table(["Window","Direction","Entry (close before)","Hold","In-sample win %","Mean","Median"],
         [[wlabel(s), s["direction"], f'{MON[s["month"]-1]} {s["day"]}', f'{s["length"]} td', pct(s["pct_pos"],0,False), pct(s["mean"]), pct(s["median"])] for s in cands])}
</section>
</div>

<script>
const D = {data_js};
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmtDate = md => MON[+md.slice(0,2)-1] + " " + (+md.slice(3));
function lineChart(el, ys, opt) {{
  const W = 560, H = 250, m = {{l:44, r:12, t:10, b:26}};
  const n = ys.length, lo = opt.min ?? Math.min(...ys), hi = opt.max ?? Math.max(...ys);
  const pad = (hi-lo)*0.08, y0 = opt.min ?? lo-pad, y1 = opt.max ?? hi+pad;
  const X = i => m.l + i*(W-m.l-m.r)/(n-1), Y = v => m.t + (1-(v-y0)/(y1-y0))*(H-m.t-m.b);
  const ticks = []; const step = opt.step;
  for (let v = Math.ceil(y0/step)*step; v <= y1+1e-9; v += step) ticks.push(+v.toFixed(6));
  let s = `<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="${{opt.aria}}">`;
  (opt.bands||[]).forEach(b => s += `<rect x="${{X(b.k0)}}" y="${{m.t}}" width="${{X(b.k1)-X(b.k0)}}" height="${{H-m.t-m.b}}" fill="${{b.dir==='bullish'?'var(--bull)':'var(--bear)'}}" opacity=".18"><title>${{b.id}}</title></rect>`);
  ticks.forEach(v => s += `<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{Y(v)}}" y2="${{Y(v)}}" stroke="var(--grid)" stroke-width="1"/><text x="${{m.l-6}}" y="${{Y(v)+4}}" text-anchor="end" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{opt.fmt(v)}}</text>`);
  if (opt.ref != null) s += `<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{Y(opt.ref)}}" y2="${{Y(opt.ref)}}" stroke="var(--muted)" stroke-dasharray="3 3" stroke-width="1"/>`;
  let prev = "";
  D.labels.forEach((l,i) => {{ const mo = l.slice(0,2); if (mo !== prev) {{ s += `<text x="${{X(i)}}" y="${{H-8}}" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{MON[+mo-1]}}</text>`; prev = mo; }} }});
  s += `<path d="${{ys.map((v,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1)).join('')}}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>`;
  s += `<line class="xh" y1="${{m.t}}" y2="${{H-m.b}}" stroke="var(--fg2)" stroke-width="1" opacity="0"/><circle class="dot" r="4" fill="var(--accent)" stroke="var(--panel)" stroke-width="2" opacity="0"/>`;
  s += `<rect x="${{m.l}}" y="0" width="${{W-m.l-m.r}}" height="${{H}}" fill="transparent" class="hit"/></svg>`;
  el.innerHTML = s;
  const svg = el.querySelector("svg"), xh = svg.querySelector(".xh"), dot = svg.querySelector(".dot");
  const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; el.parentElement.appendChild(tip);
  svg.querySelector(".hit").addEventListener("pointermove", e => {{
    const r = svg.getBoundingClientRect(), sx = (e.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(n-1, Math.round((sx-m.l)/((W-m.l-m.r)/(n-1)))));
    xh.setAttribute("x1", X(i)); xh.setAttribute("x2", X(i)); xh.setAttribute("opacity", 1);
    dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(ys[i])); dot.setAttribute("opacity", 1);
    const band = (opt.bands||[]).filter(b => i>=b.k0 && i<=b.k1).map(b=>b.id).join(", ");
    tip.innerHTML = `Day ${{i+1}} · ~${{fmtDate(D.labels[i])}}<br>${{opt.tipLabel}}: ${{opt.fmt2(ys[i])}}${{band? '<br>'+band:''}}`;
    tip.hidden = false;
    const pr = el.parentElement.getBoundingClientRect();
    let left = e.clientX - pr.left + 12; if (left > pr.width - 170) left -= 190;
    tip.style.left = left + "px"; tip.style.top = (e.clientY - pr.top - 10) + "px";
  }});
  svg.querySelector(".hit").addEventListener("pointerleave", () => {{ tip.hidden = true; xh.setAttribute("opacity",0); dot.setAttribute("opacity",0); }});
}}
const f1 = v => v.toFixed(0), f2 = v => v.toFixed(2);
lineChart(document.getElementById("c1"), D.avg, {{step:2, ref:100, fmt:f1, fmt2:f2, tipLabel:"Avg index", aria:"Average seasonal path"}});
lineChart(document.getElementById("c2"), D.med, {{step:2, ref:100, fmt:f1, fmt2:f2, tipLabel:"Median index", aria:"Median seasonal path"}});
lineChart(document.getElementById("c3"), D.prob.map(v=>v*100), {{min:0, max:100, step:25, ref:50, fmt:v=>v+"%", fmt2:v=>v.toFixed(0)+"% of years", tipLabel:"Positive YTD", aria:"Probability of positive year to date"}});
lineChart(document.getElementById("c4"), D.avg, {{step:2, ref:100, fmt:f1, fmt2:f2, tipLabel:"Avg index", bands:D.shade, aria:"Average path with candidate windows"}});

// heatmap
(function() {{
  const g = document.getElementById("hm");
  const vmax = Math.max(...D.heat.map(h=>Math.abs(h.ex)));
  const mix = (a,b,t) => `color-mix(in oklab, ${{b}} ${{(t*100).toFixed(0)}}%, ${{a}})`;
  const col = v => v >= 0 ? mix("var(--mid)","var(--bull)", Math.min(1, v/vmax)) : mix("var(--mid)","var(--bear)", Math.min(1, -v/vmax));
  let h = `<div></div>`; for (let d=1; d<=31; d++) h += `<div class="dl">${{d%5===1||d===31? d : ""}}</div>`;
  for (let m=1; m<=12; m++) {{
    h += `<div class="lab">${{MON[m-1]}}</div>`;
    for (let d=1; d<=31; d++) {{
      const c = D.heat.find(x=>x.m===m && x.d===d);
      h += c ? `<div class="c" style="background:${{col(c.ex)}}" data-t="${{MON[m-1]}} ${{d}} · next 5 td excess ${{(c.ex*100>=0?'+':'')+(c.ex*100).toFixed(2)}}% · up ${{(c.pp*100).toFixed(0)}}% of years (n=${{c.n}})"></div>` : `<div></div>`;
    }}
  }}
  g.innerHTML = h;
  document.getElementById("hmbar").style.background = `linear-gradient(90deg, var(--bear), var(--mid), var(--bull))`;
  document.getElementById("hmrange").textContent = `±${{(vmax*100).toFixed(1)}}%`;
  const fig = g.parentElement, tip = document.createElement("div"); tip.className="tip"; tip.hidden=true; fig.appendChild(tip);
  g.addEventListener("pointermove", e => {{
    const t = e.target.dataset && e.target.dataset.t; if (!t) {{ tip.hidden = true; return; }}
    tip.textContent = t; tip.hidden = false;
    const pr = fig.getBoundingClientRect(); let left = e.clientX - pr.left + 12; if (left > pr.width - 330) left -= 350;
    tip.style.left = Math.max(4,left) + "px"; tip.style.top = (e.clientY - pr.top + 14) + "px";
  }});
  g.addEventListener("pointerleave", () => tip.hidden = true);
}})();
</script>
"""
open("report.html", "w").write(html)
print("report.html", len(html) // 1024, "KB")
