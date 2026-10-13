"""Render phase2/report_oos.html from outputs/oos_results.pkl."""
import json
import os
import pickle

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
O = pickle.load(open(os.path.join(HERE, "outputs", "oos_results.pkl"), "rb"))
R, A = O["results"], O["aggregate"]
IS_RD = json.load(open(os.path.join(os.path.dirname(HERE), "outputs", "report_data.json")))  # Phase-1 frozen output
CRIT_TXT = open(os.path.join(HERE, "oos_validation_criteria.yaml")).read()
LOCK = open(os.path.join(HERE, "preregistration.lock")).read().split("\n")
PRIMARY = ["Jul01+15td", "Sep16+10td", "Mar16+30td", "Jul01+20td", "Nov16+15td", "Apr16+10td", "Apr16+5td", "Nov16+30td"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DDSET = ["Jun16+10td", "Mar01+10td", "Jan16+10td", "May01+10td", "Oct01+10td", "Feb16+10td",
         "Sep16+20td", "Jun01+20td", "Jun16+20td", "Feb16+20td", "Mar01+20td", "Jan16+20td"]
FROZEN = json.load(open(os.path.join(os.path.dirname(HERE), "seasonal_patterns_2003_2022.json")))
ORDER = [w["id"] for w in FROZEN["windows"]] + [m["id"] for m in FROZEN["months"]]


def pct(x, nd=2, sign=True):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x*100:+.{nd}f}%" if sign else f"{x*100:.{nd}f}%"


def pp(x):
    return "—" if x is None else f"{x*100:+.2f} pp"


def nm(rid):
    w = R[rid]["window"]
    return w.replace(" (", '<span class="td">').replace(" td)", " td</span>").replace("~", "")


CLS = {"SUPPORTIVE": "s", "PARTIALLY SUPPORTIVE": "p", "INCONCLUSIVE": "i", "INCONCLUSIVE (N<3)": "i", "CONTRADICTED": "c",
       "Supportive": "s", "Partially Supportive": "p", "Inconclusive": "i", "Contradicted": "c"}


def badge(t):
    return f'<span class="b b-{CLS.get(t, "i")}">{t.title() if t.isupper() else t}</span>'


def dirb(d):
    return f'<span class="dir {d}">{"▲ bullish" if d == "bullish" else "▼ bearish"}</span>'


def table(head, rows, cls=""):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


# ---------------- primary table
prim_rows = []
for rid in PRIMARY:
    s = R[rid]
    i = s["is_stats"]
    prim_rows.append([nm(rid), dirb(s["designation"]), pct(i["win_rate"], 0, False), pct(i["mean"]), s["n"],
                      sum(1 for x in s["returns"] if (x > 0 if s["designation"] == "bullish" else x < 0)),
                      pct(s["win_raw"], 0, False), pct(s["mean"]), pct(s["median"]), pct(s["worst_mdd"]),
                      s["effect"], badge(s["classification"])])

# ---------------- every occurrence
occ_rows = []
for rid in PRIMARY:
    s = R[rid]
    for o in s["occurrences"]:
        if o["status"] == "complete":
            ok = (o["ret"] > 0) if s["designation"] == "bullish" else (o["ret"] < 0)
            beat = ((1 if s["designation"] == "bullish" else -1) * (o["ret"] - s["is_stats"]["base"])) > 0
            occ_rows.append([rid, o["year"], o["entry_date"], f'{o["entry_px"]:,.2f}', o["exit_date"], f'{o["exit_px"]:,.2f}',
                             pct(o["ret"]), pct(o["mdd"]), s["designation"],
                             ("✓ yes" if ok else "✗ no"), ("✓" if beat else "✗")])
        else:
            occ_rows.append([rid, o["year"], "—", "—", "—", "—", "—", "—", s["designation"], f'<span class="muted">{o["status"]} — excluded</span>', "—"])

# ---------------- expected vs observed
cmp_rows = []
for rid in PRIMARY:
    s = R[rid]
    i = s["is_stats"]
    cmp_rows.append([nm(rid), f'{pct(i["win_rate"],0,False)} → {pct(s["win_raw"],0,False)}', pp(s["diff_win_pp"]),
                     f'{pct(i["mean"])} → {pct(s["mean"])}', pp(s["diff_mean_pp"]),
                     f'{pct(i["median"])} → {pct(s["median"])}', pp(s["diff_median_pp"]),
                     f'{pct(i["avg_mdd"])} → {pct(s["avg_mdd"])}', f'{pct(i["worst_mdd"])} → {pct(s["worst_mdd"])}'])

# ---------------- benchmark
bm_rows = []
for rid in PRIMARY:
    s = R[rid]
    lo, hi = s["hit_raw_ci"]
    bm_rows.append([nm(rid), s["n"], pct(s["mean"]), f'{pct(s["ci95_mean"][0])} to {pct(s["ci95_mean"][1])}',
                    pct(s["is_stats"]["base"]), pct(s["excess_vs_is_base"]), pct(s["oos_drift"]), pct(s["excess_vs_oos_drift"]),
                    f'{s["placebo_pct_expected_tail"]*100:.0f}th', f'{s["hits_raw"]}/{s["n"]} ({pct(lo,0,False)}–{pct(hi,0,False)})',
                    f'{s["rho"]:+.2f}'])

# ---------------- scorecard
sc_rows = [[nm(rid), badge(R[rid]["scorecard"]["direction_match"]), badge(R[rid]["scorecard"]["win_rate"]),
            badge(R[rid]["scorecard"]["return_consistency"]), badge(R[rid]["scorecard"]["drawdown"]),
            badge(R[rid]["scorecard"]["benchmark"]), badge(R[rid]["scorecard"]["overall"])] for rid in PRIMARY]

# ---------------- bullish comparison (original rank order)
bulls = [r for r in PRIMARY if R[r]["designation"] == "bullish"]
bull_rows = []
for k, rid in enumerate(bulls, 1):
    s = R[rid]
    strength = {"Same direction": "Persisted", "Weaker same direction": "Weakened", "Neutral": "Faded to neutral",
                "Opposite direction": "Reversed"}[s["effect"]]
    bull_rows.append([k, nm(rid), pct(s["is_stats"]["win_rate"], 0, False), pct(s["is_stats"]["mean"]),
                      pct(s["win_raw"], 0, False), pct(s["mean"]),
                      "Yes" if s["excess_vs_is_base"] > 0 else "No", f'{strength} (ρ {s["rho"]:+.2f})'])

# ---------------- bearish / drawdown comparison
bear_rows = []
for rid in ["Sep16+10td"] + DDSET:
    s = R[rid]
    i = s["is_stats"]
    bear_rows.append([nm(rid), "primary (bearish)" if rid == "Sep16+10td" else "drawdown set", s["n"],
                      f'{pct(i["pct_neg"],0,False)} → {pct(s["pct_neg"],0,False)}', f'{pct(i["mean"])} → {pct(s["mean"])}',
                      f'{pct(i["median"])} → {pct(s["median"])}',
                      f'{pct(i["freq_dd3"],0,False)} → {pct(s["freq_dd3"],0,False)}',
                      f'{pct(i["avg_mdd"])} → {pct(s["avg_mdd"])}'])

dd_rows = []
for rid in DDSET:
    s = R[rid]
    dd_rows.append([nm(rid), s["n"], pct(s["avg_mdd"]), pct(s["median_mdd"]), pct(s["worst_mdd"]),
                    pct(s["freq_dd2"], 0, False), pct(s["freq_dd3"], 0, False), pct(s["freq_dd5"], 0, False),
                    pct(s["dd_uncond"]["ge3"], 0, False), pct(s["is_stats"]["freq_dd3"], 0, False),
                    "; ".join(f'{o["year"]} excluded' for o in s["occurrences"] if o["status"] != "complete") or "—"])

# ---------------- monthly
mon_rows = []
for k, m in enumerate(MON):
    s = R[f"MONTH-{m}"]
    by = {o["year"]: o for o in s["occurrences"]}
    cell = lambda y: pct(by[y]["ret"]) if by[y]["status"] == "complete" else '<span class="muted">incomplete</span>'
    mon_rows.append([m, pct(s["is_stats"]["win_rate"], 0, False), pct(s["is_stats"]["mean"]), cell(2023), cell(2024), cell(2025),
                     cell(2026), pct(s["mean"]), pct(s["median"]), s["designation"], s["effect"], badge(s["classification"])])

# ---------------- full table
full_rows = []
for rid in ORDER:
    s = R[rid]
    full_rows.append([rid, s["window"], s["designation"], pct(s["is_stats"]["win_rate"], 0, False), pct(s["is_stats"]["mean"]),
                      s["n"], pct(s.get("win_raw"), 0, False), pct(s.get("mean")), pct(s.get("excess_vs_is_base")),
                      pct(s.get("excess_vs_oos_drift")),
                      "Yes" if (1 if s["designation"] == "bullish" else -1) * s["excess_vs_is_base"] > 0 else "No",
                      badge(s["classification"])])

dq = O["data_quality"]
q1, q2, q3, q4 = A["Q1"], A["Q2"]["drawdown_set"], A["Q3"], A["Q4"]
cls_all = q4["classes_all"]
mon_cls = {}
for m in MON:
    c = R[f"MONTH-{m}"]["classification"]
    mon_cls[c] = mon_cls.get(c, 0) + 1

# chart data
charts = dict(
    primary=[dict(id=rid, label=R[rid]["window"].split(" (")[0].replace("~", ""), dir=R[rid]["designation"],
                  is_mean=R[rid]["is_stats"]["mean"], oos_mean=R[rid]["mean"], drift=R[rid]["oos_drift"],
                  years={str(o["year"]): o["ret"] for o in R[rid]["occurrences"] if o["status"] == "complete"}) for rid in PRIMARY],
    months=[dict(m=m, is_mean=R[f"MONTH-{m}"]["is_stats"]["mean"], oos_mean=R[f"MONTH-{m}"]["mean"],
                 n=R[f"MONTH-{m}"]["n"]) for m in MON],
    is_avg=IS_RD["avg"], labels=IS_RD["labels"],
    oos_avg=np.mean(np.vstack([np.pad(np.array(O["paths"][y][:252]), (0, max(0, 252 - len(O["paths"][y]))), mode="edge")
                               for y in (2023, 2024, 2025)]), axis=0).round(3).tolist(),
    ytd2026=O["paths"][2026],
    years={str(y): O["paths"][y] for y in (2023, 2024, 2025)},
)
DATA = json.dumps(charts)
S = {r: R[r] for r in R}

html = f"""<title>S&amp;P 500 Seasonality Out-of-Sample Test</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Serif:wght@500;600&display=swap">
<style>
/* Layout: one reading column (~72ch) with full-width figure/table bands — companion to the Phase-1 report */
:root {{
  --bg:#f5f7f8; --panel:#ffffff; --fg:#14181c; --fg2:#4a535c; --muted:#7b858e; --rule:#dde2e6; --grid:#e6e9eb; --mid:#e9ebec;
  --accent:#1c5cab; --is:#2a78d6; --oos:#eb6834; --drift:#52514e; --y23:#2a78d6; --y24:#eb6834; --y25:#1baf7a; --y26:#4a3aa7;
  --s-bg:#dcefe2; --s-fg:#0b5d1e; --p-bg:#e7eef8; --p-fg:#256abf; --i-bg:#f0efec; --i-fg:#52514e; --c-bg:#fbe3e2; --c-fg:#a42726;
  --bull:#1c5cab; --bear:#b8332f; --warn-bg:#fdf3e1; --warn-fg:#7a4b00;
  --f-display:"IBM Plex Serif", Georgia, serif; --f-body:"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-data:"IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#121416; --panel:#1a1d20; --fg:#eef1f3; --fg2:#b9c0c6; --muted:#8a939b; --rule:#2c3136; --grid:#262a2e; --mid:#383835;
  --accent:#6da7ec; --is:#3987e5; --oos:#d95926; --drift:#c3c2b7; --y23:#3987e5; --y24:#d95926; --y25:#199e70; --y26:#9085e9;
  --s-bg:#16391f; --s-fg:#9fe0ae; --p-bg:#1f3352; --p-fg:#9ec5f4; --i-bg:#2b2b29; --i-fg:#c3c2b7; --c-bg:#45201f; --c-fg:#f3a5a3;
  --bull:#6da7ec; --bear:#e66767; --warn-bg:#3a2c12; --warn-fg:#f5cf8a; color-scheme:dark; }} }}
:root[data-theme="dark"] {{
  --bg:#121416; --panel:#1a1d20; --fg:#eef1f3; --fg2:#b9c0c6; --muted:#8a939b; --rule:#2c3136; --grid:#262a2e; --mid:#383835;
  --accent:#6da7ec; --is:#3987e5; --oos:#d95926; --drift:#c3c2b7; --y23:#3987e5; --y24:#d95926; --y25:#199e70; --y26:#9085e9;
  --s-bg:#16391f; --s-fg:#9fe0ae; --p-bg:#1f3352; --p-fg:#9ec5f4; --i-bg:#2b2b29; --i-fg:#c3c2b7; --c-bg:#45201f; --c-fg:#f3a5a3;
  --bull:#6da7ec; --bear:#e66767; --warn-bg:#3a2c12; --warn-fg:#f5cf8a; color-scheme:dark; }}
* {{ box-sizing:border-box }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.6 var(--f-body); padding-inline:16px; padding-block:32px 64px }}
.wrap {{ max-width:1100px; margin:0 auto; display:flex; flex-direction:column; gap:40px }}
.col {{ max-width:74ch }}
h1,h2,h3 {{ font-family:var(--f-display); font-weight:600; text-wrap:balance; margin:0; line-height:1.2 }}
h1 {{ font-size:clamp(28px,4.4vw,40px) }} h2 {{ font-size:24px; padding-top:8px; border-top:1px solid var(--rule) }}
h3 {{ font-size:17px; font-family:var(--f-body) }}
p {{ margin:0 }}
section {{ display:flex; flex-direction:column; gap:16px; min-width:0 }}
.eyebrow {{ font:500 12px/1 var(--f-data); letter-spacing:.08em; text-transform:uppercase; color:var(--muted) }}
.lede {{ font-size:17px; color:var(--fg2) }}
.meta {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1px; background:var(--rule); border:1px solid var(--rule); border-radius:6px; overflow:hidden }}
.meta div {{ background:var(--panel); padding:10px 14px; display:flex; flex-direction:column; gap:2px; min-width:0 }}
.meta span {{ font:500 11px var(--f-data); letter-spacing:.06em; text-transform:uppercase; color:var(--muted) }}
.meta b {{ font:500 13.5px var(--f-data); overflow-wrap:anywhere }}
.verdict {{ background:var(--panel); border:1px solid var(--rule); border-radius:8px; padding:20px 22px; display:flex; flex-direction:column; gap:10px }}
.verdict .big {{ font-family:var(--f-display); font-size:21px; line-height:1.35 }}
ol.qa {{ margin:0; padding-left:24px; display:flex; flex-direction:column; gap:12px }}
ol.qa li::marker {{ font-family:var(--f-data); color:var(--muted) }}
.q {{ font-weight:600 }}
.tw {{ overflow-x:auto; border:1px solid var(--rule); border-radius:6px; background:var(--panel) }}
table {{ border-collapse:collapse; width:100%; font-size:13px; font-variant-numeric:tabular-nums }}
th {{ text-align:left; font:500 11px/1.3 var(--f-data); letter-spacing:.04em; text-transform:uppercase; color:var(--muted); padding:10px; border-bottom:1px solid var(--rule); white-space:nowrap; vertical-align:bottom }}
td {{ padding:7px 10px; border-bottom:1px solid var(--grid); white-space:nowrap; font-family:var(--f-data); font-size:12.5px }}
tr:last-child td {{ border-bottom:0 }}
td:first-child {{ font-family:var(--f-body) }}
.td {{ display:inline-block; margin-left:6px; font:11px var(--f-data); color:var(--muted) }}
.muted {{ color:var(--muted) }}
.b {{ display:inline-block; padding:1px 7px; border-radius:3px; font:500 11px/1.6 var(--f-data); white-space:nowrap }}
.b-s {{ background:var(--s-bg); color:var(--s-fg) }} .b-p {{ background:var(--p-bg); color:var(--p-fg) }}
.b-i {{ background:var(--i-bg); color:var(--i-fg) }} .b-c {{ background:var(--c-bg); color:var(--c-fg) }}
.dir {{ font:500 12px var(--f-data) }} .dir.bullish {{ color:var(--bull) }} .dir.bearish {{ color:var(--bear) }}
.note {{ font-size:13px; color:var(--fg2) }}
.callout {{ background:var(--warn-bg); color:var(--warn-fg); border-radius:6px; padding:12px 16px; font-size:14px }}
.fig {{ background:var(--panel); border:1px solid var(--rule); border-radius:6px; padding:16px 16px 12px; position:relative; min-width:0 }}
.fig .sub {{ font-size:13px; color:var(--muted); margin:2px 0 8px }}
.fig svg {{ display:block; width:100%; height:auto; overflow:visible }}
.figs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,500px),1fr)); gap:16px }}
.tip {{ position:absolute; pointer-events:none; background:var(--fg); color:var(--bg); font:12px/1.45 var(--f-data); padding:6px 9px; border-radius:4px; white-space:nowrap; z-index:2 }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; font-size:12px; color:var(--fg2); margin-top:8px }}
.legend svg {{ display:inline-block; width:14px; height:12px; vertical-align:-1px; margin-right:5px }}
pre.crit {{ background:var(--panel); border:1px solid var(--rule); border-radius:6px; padding:14px 16px; font:12px/1.55 var(--f-data); overflow-x:auto; margin:0; color:var(--fg2) }}
details {{ background:var(--panel); border:1px solid var(--rule); border-radius:6px; padding:10px 14px }}
details > summary {{ cursor:pointer; font-weight:600 }}
details[open] > summary {{ margin-bottom:10px }}
details .tw {{ border:0 }}
code {{ font-family:var(--f-data); font-size:.9em; background:var(--mid); padding:1px 5px; border-radius:3px; overflow-wrap:anywhere }}
ul.plain {{ margin:0; padding-left:20px; display:flex; flex-direction:column; gap:6px }}
ul.check {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px }}
ul.check li::before {{ content:"✓"; color:var(--s-fg); font-weight:700; margin-right:8px }}
@media (max-width:720px) {{ .meta {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} }}
</style>

<div class="wrap">
<header class="col" style="display:flex;flex-direction:column;gap:14px">
  <div class="eyebrow">Phase 2 · out-of-sample validation · 2023-01-03 → {O["hard_stop"]}</div>
  <h1>S&amp;P 500 Seasonality: Out-of-Sample Test</h1>
  <p class="lede">The 132 seasonal rules frozen from 2003–2022 data were applied, unchanged, to the 941 trading days since January 2023. The validation criteria were written and hash-locked before any 2023+ price was loaded. No window was moved, added or dropped.</p>
</header>

<div class="meta">
  <div><span>Frozen rules</span><b>120 windows + 12 months</b></div>
  <div><span>Primary hypotheses</span><b>8 (7 bullish, 1 bearish)</b></div>
  <div><span>OOS data</span><b>{dq["first"]} → {dq["last"]}</b></div>
  <div><span>Trading days</span><b>{dq["trading_days"]} · 0 missing · 0 dupes</b></div>
  <div><span>Frozen JSON SHA-256</span><b>{O["frozen_sha256"][:16]}…</b></div>
  <div><span>Criteria SHA-256</span><b>{O["criteria_sha256"][:16]}…</b></div>
  <div><span>Look-ahead tests</span><b>22 / 22 pass</b></div>
  <div><span>OOS years per window</span><b>3–4</b></div>
</div>

<section class="verdict">
  <div class="eyebrow">Bottom line</div>
  <p class="big">The frozen bullish windows rose in the unseen period, but no more than randomly timed windows of the same length did in the same bull market (placebo p&nbsp;=&nbsp;{q1["placebo_p_one_sided"]:.2f}). The bearish and drawdown hypotheses did not identify unusually weak periods. With only 3–4 observations per window, none of this is statistical proof either way.</p>
  <p class="note">Mid-April (Apr 16 → Apr 29) and mid-November held up best: they went the right way in every OOS year and beat both baselines. They are the hypotheses worth tracking further. Only 5 of 12 monthly rules were Supportive or Partially Supportive. The mid-year weakness lean (May, June, August) reversed, and January was up in all four years.</p>
</section>

<section class="col">
  <h2>Executive summary</h2>
  <ol class="qa">
    <li><span class="q">Did the 2003–2022 tendencies persist after Jan 1, 2023?</span> Only weakly. Of the 8 primary hypotheses, 4 are Supportive, 1 Partially Supportive, 3 Inconclusive and 0 Contradicted. Across all 132 rules, though, only {q4["share_all_same_sign_vs_oos_drift"]*100:.0f}% beat the OOS drift in their original direction, close to the 50% a coin flip gives (p&nbsp;=&nbsp;{q4["binom_p_vs_oos_drift"]:.2f}). The classification counts were {cls_all.get("SUPPORTIVE",0)} Supportive, {cls_all.get("PARTIALLY SUPPORTIVE",0)} Partial, {cls_all.get("INCONCLUSIVE",0)} Inconclusive and {cls_all.get("CONTRADICTED",0)} Contradicted. The in-sample ranking had only a faint relationship with OOS results (Spearman {q3["spearman_is_vs_oos_excess"]:+.2f}, nominal one-sided p&nbsp;=&nbsp;{q3["spearman_p_one_sided"]:.3f}). That p-value is overstated because overlapping windows are not independent.</li>
    <li><span class="q">Strongest support.</span> <b>Apr 16 → Apr 29</b> was up 4 of 4 years, averaging {pct(S["Apr16+10td"]["mean"])} against {pct(S["Apr16+10td"]["is_stats"]["mean"])} in-sample. It beat the OOS drift by {pp(S["Apr16+10td"]["adv_vs_drift"])} and is the only hypothesis Supportive on every scorecard line. <b>Nov 16 → Dec 7</b> was up 3 of 3 ({pct(S["Nov16+15td"]["mean"])}), and <b>Nov 16 → Dec 29</b> 3 of 3 ({pct(S["Nov16+30td"]["mean"])}); these overlap and are effectively one mid-November effect. <b>Jul 1 → Jul 22</b> was up 3 of 4, averaging {pct(S["Jul01+15td"]["mean"])}.</li>
    <li><span class="q">Which weakened?</span> Jul 1 → Jul 22 kept {S["Jul01+15td"]["rho"]*100:.0f}% of its historical edge, and 2026 was flat. Jul 1 → Jul 29 faded to neutral (ρ&nbsp;{S["Jul01+20td"]["rho"]:+.2f}) and lagged the OOS drift. Mar 16 → Apr 27 kept its average ({pct(S["Mar16+30td"]["mean"])}) only because of two big years; 2024 was flat and 2025 lost {pct(S["Mar16+30td"]["returns"][2])}.</li>
    <li><span class="q">Which failed or reversed?</span> No primary hypothesis met the pre-registered Contradicted definition. <b>Apr 16 → Apr 22</b> (5 td) effectively vanished: mean {pct(S["Apr16+5td"]["mean"])}, and only 1 of 4 years beat its baseline. <b>Sep 16 → Sep 29</b> (bearish) fell in only 1 of 4 years, averaging {pct(S["Sep16+10td"]["mean"])}. It did lag the OOS drift, but it was not a weak period in absolute terms. Among monthly rules, January (bearish lean in-sample) rose every year, and the May, June and August weakness leans reversed.</li>
    <li><span class="q">Did bullish windows beat random holding periods?</span> Not convincingly. The 26 bullish occurrences averaged {pct(q1["pooled_mean_return"])}, which is {pp(q1["pooled_excess_vs_oos_drift"])} above same-length random windows in the OOS period, and {q1["share_occurrences_beating_drift"]*100:.0f}% beat drift. The calendar-scramble placebo gives p&nbsp;=&nbsp;{q1["placebo_p_one_sided"]:.2f}, so a result this good is common by chance.</li>
    <li><span class="q">Did bearish windows identify weak or high-drawdown periods?</span> No, not as a group. In the 12 pre-identified drawdown windows, OOS 3%+ drawdowns occurred in {pct(q2[10]["freq_ge3"],0,False)} of 10-day and {pct(q2[20]["freq_ge3"],0,False)} of 20-day occurrences, against unconditional rates of {pct(q2[10]["uncond_ge3"],0,False)} and {pct(q2[20]["uncond_ge3"],0,False)} (p&nbsp;=&nbsp;{q2[10]["p_binom_greater"]:.2f} and {q2[20]["p_binom_greater"]:.2f}). The exception is late February through March, where 3 of 4 years again had 3%+ drawdowns. The June, January and May windows were calm.</li>
    <li><span class="q">Were OOS magnitudes consistent with the originals?</span> Against the frozen in-sample baselines, the primaries kept {q3["pooled_rho_primary"]*100:.0f}% of their historical edge overall. But 2023–2026 was a strong market: random 20-day windows averaged {pct(O["oos_drift"][20])}, against {pct(0.006906)} in 2003–2022. That flatters every bullish rule. Measured against the OOS drift, the remaining edge is small.</li>
    <li><span class="q">How much confidence?</span> Little. Each window has N&nbsp;=&nbsp;3–4. A 4-of-4 record has a 95% exact confidence interval of 40%–100% for the true hit rate. The 95% CI for the mean OOS return includes zero for 7 of the 8 primaries; Nov 16 → Dec 7 is the exception. These results can be consistent with a hypothesis; they cannot prove it.</li>
    <li><span class="q">Proceed to a formal walk-forward trading-strategy study?</span> Not yet. Nothing has survived a multiple-testing correction in-sample, and the OOS set as a whole did not beat random timing. A strategy built on this evidence would mostly be trading noise. A better next step is a second, independent holdout: run the same frozen rules on pre-2003 S&amp;P 500 data (for example 1950–2002), which these rules have also never seen. Then keep scoring them each year going forward.</li>
    <li><span class="q">Which deserve additional testing?</span> Apr16+10td and the mid-November pair (Nov16+15td / Nov16+30td), as already frozen. Jul01+15td is a lower priority. These are the same rule IDs as before; nothing was re-tuned.</li>
  </ol>
</section>

<section class="col">
  <h2>Frozen-rule verification</h2>
  <ul class="plain">
    <li>File: <code>seasonal_patterns_2003_2022.json</code>, read-only (mode 444), never rewritten.</li>
    <li>SHA-256: <code>{O["frozen_sha256"]}</code>. This matches the hash recorded when the file was frozen in Phase 1, and it was re-checked after every Phase-2 step.</li>
    <li>Counts: 120 calendar windows and 12 monthly rules, 132 in total, as expected.</li>
    <li>Primary hypotheses, in original order: {", ".join(PRIMARY)}.</li>
  </ul>
</section>

<section>
  <h2>Out-of-sample validation criteria</h2>
  <p class="note col">These criteria were written and locked at <code>{LOCK[1].split()[-1]}</code>, before the 2023+ data was downloaded. The lock file shows the data folder held only the 2003–2022 file at that moment. The validation script refuses to run if this file's hash ({O["criteria_sha256"][:16]}…) changes. Nothing below was edited after results were seen.</p>
  <pre class="crit">{CRIT_TXT.replace("&","&amp;").replace("<","&lt;")}</pre>
</section>

<section class="col">
  <h2>Data and point-in-time checks</h2>
  <ul class="plain">
    <li><b>Instrument:</b> ^GSPC from the Yahoo Finance daily chart API, the same source and unadjusted closes as Phase 1. The request was bounded to start 2023-01-01, and the loader rejects any earlier row (<code>DataIsolationError</code>). The 2003–2022 prices are never loaded in Phase 2.</li>
    <li><b>Coverage:</b> first bar {dq["first"]}, last bar {dq["last"]} (the last completed session before this run on Sat 2026-10-03), {dq["trading_days"]} trading days. The data matches the NYSE holiday calendar exactly: missing dates {len(dq["missing_vs_nyse_calendar"])}, unexpected dates {len(dq["unexpected_dates"])}, duplicates {dq["duplicate_dates"]}. File SHA-256 <code>{O["data_sha256"]}</code> matches the checksum computed in the browser at download.</li>
    <li><b>Flagged prices:</b> {", ".join(f'{x["date"]} ({x["flags"][0]})' for x in dq["flagged_observations"])}. These are the real April-2025 tariff-shock moves, kept as-is. No bar had high&nbsp;&lt;&nbsp;low or a close outside its range.</li>
    <li><b>First entry:</b> January 2023 windows and the January 2023 month have no prior bar in the OOS file. They enter at the 2023-01-03 open, the same rule Phase 1 applied to January 2003. Prices carry 2 decimals, the precision the index is published at.</li>
    <li><b>Point-in-time:</b> every trade is evaluated through <code>MarketData.as_of(exit_date)</code>, the unchanged Phase-1 class. Requesting a later bar raises <code>LookAheadError</code>. The 11 Phase-1 tests and 11 new Phase-2 tests all pass (22/22). The new tests cover pre-2023 rejection, post-hard-stop rejection, the frozen-file hash, the criteria lock, and the exclusion of incomplete occurrences.</li>
    <li><b>Completeness:</b> an occurrence counts only if its exit close is on or before {O["hard_stop"]}. Windows still open on that date (for example Sep16+20td and Oct01+10td in 2026) and October 2026 are listed as incomplete and excluded from all statistics. Windows that had not started yet (mid-November and December 2026) are listed as not started.</li>
  </ul>
</section>

<section>
  <h2>Primary test: the 8 frozen candidates</h2>
  {table(["Seasonal window","Direction","IS win %","IS avg return","OOS N","OOS wins","OOS win %","OOS avg return","OOS median","OOS max drawdown","Effect direction","Validation"], prim_rows)}
  <p class="note col">"Wins" are raw: up for bullish, down for bearish. Classification instead uses performance relative to the frozen in-sample baseline, so a rising market alone doesn't earn credit.</p>
  <div class="figs">
    <div class="fig"><h3>Chart 1 · In-sample vs out-of-sample average return</h3><div class="sub">▲ bullish rules should sit right of zero, ▼ bearish left. The grey tick is a random window of the same length in 2023–26.</div><div id="ch1"></div>
      <div class="legend"><span><svg viewBox="0 0 14 12"><rect width="14" height="12" rx="2" fill="var(--is)"/></svg>2003–2022 avg</span><span><svg viewBox="0 0 14 12"><rect width="14" height="12" rx="2" fill="var(--oos)"/></svg>2023+ avg</span><span><svg viewBox="0 0 14 12"><rect x="6" width="2" height="12" fill="var(--drift)"/></svg>OOS random-window drift</span></div></div>
    <div class="fig"><h3>Chart 2 · Every out-of-sample year</h3><div class="sub">One mark per completed occurrence, losing years included. Incomplete 2026 windows are absent.</div><div id="ch2"></div>
      <div class="legend" id="lg2"></div></div>
  </div>
</section>

<section>
  <h2>Every out-of-sample occurrence</h2>
  {table(["Rule","Year","Entry date","Entry price","Exit date","Exit price","Return","Max drawdown","Expected","Correct (raw)?","Beat IS baseline?"], occ_rows)}
</section>

<section>
  <h2>Expected vs observed</h2>
  {table(["Window","Win % (IS → OOS)","Δ win","Avg (IS → OOS)","Δ avg","Median (IS → OOS)","Δ median","Avg max DD (IS → OOS)","Worst DD (IS → OOS)"], cmp_rows)}
</section>

<section>
  <h2>Benchmark against normal drift</h2>
  {table(["Window","N","OOS mean","95% CI mean","IS baseline","Excess vs IS baseline","OOS drift (same length)","Excess vs OOS drift","Placebo percentile","Hits (95% CI)","ρ (share of IS edge)"], bm_rows)}
  <p class="note col">The placebo percentile is the rule's share of 10,000 calendar-scrambled OOS draws that it beat in its expected direction (each draw uses random start days and the same lengths). 50th means no better than random timing. ρ&nbsp;=&nbsp;OOS excess over the frozen baseline ÷ in-sample excess.</p>
  <div class="callout col">Small-sample warning: with N&nbsp;=&nbsp;3 or 4, one year moves a mean by 25–33% of the total. 3/3 or 4/4 hits are consistent with a true hit rate anywhere from about 30–40% to 100%. These results are evidence, not proof.</div>
</section>

<section>
  <h2>Scorecard</h2>
  {table(["Pattern","OOS direction match","Win-rate consistency","Return consistency","Drawdown consistency","Benchmark advantage","Overall"], sc_rows)}
</section>

<section>
  <h2>Bullish candidate comparison</h2>
  <p class="note col">Kept in the original study's rank order; not re-sorted by OOS results.</p>
  {table(["Original rank","Window","IS win %","IS avg","OOS win %","OOS avg","Same direction?","Strength"], bull_rows)}
</section>

<section>
  <h2>Bearish and drawdown candidate comparison</h2>
  {table(["Window","Role","OOS N","% negative (IS → OOS)","Avg return (IS → OOS)","Median (IS → OOS)","DD ≥3% freq (IS → OOS)","Avg max DD (IS → OOS)"], bear_rows)}
</section>

<section>
  <h2>Drawdown validation</h2>
  <p class="note col">These are the 12 windows from the Phase-1 drawdown tables, as frozen. A <b>negative return</b> means the window closed below entry. An <b>intra-period drawdown</b> is the deepest fall from a running peak inside the window.</p>
  {table(["Window","N","Avg max DD","Median max DD","Largest DD","≥2%","≥3%","≥5%","OOS unconditional ≥3%","IS ≥3%","Incomplete"], dd_rows)}
  <p class="note col">Pooled 10-day windows: {q2[10]["k_ge3"]} of {q2[10]["n"]} had a 3%+ drawdown ({pct(q2[10]["freq_ge3"],0,False)}) vs {pct(q2[10]["uncond_ge3"],0,False)} for any 10-day OOS window (p&nbsp;=&nbsp;{q2[10]["p_binom_greater"]:.2f}). Pooled 20-day: {q2[20]["k_ge3"]} of {q2[20]["n"]} ({pct(q2[20]["freq_ge3"],0,False)}) vs {pct(q2[20]["uncond_ge3"],0,False)} (p&nbsp;=&nbsp;{q2[20]["p_binom_greater"]:.2f}). The Feb16 and Mar01 windows repeated their elevated drawdowns in 2023, 2025 and 2026, while 2024 was calm. The June, January and May windows did not repeat them.</p>
</section>

<section>
  <h2>Monthly rule validation</h2>
  {table(["Month","IS positive %","IS avg","2023","2024","2025","2026","OOS avg","OOS median","Frozen direction","Effect","Validation"], mon_rows)}
  <p class="note col">Only completed months count; October 2026 is excluded. Months: {", ".join(f"{v} {k.title()}" for k,v in mon_cls.items())}. December is classified Contradicted although its effect is Neutral. Its in-sample edge was tiny (+0.20%), so the ratio ρ swings widely. The pre-registered rule is applied as written, but this verdict carries little information.</p>
  <div class="fig"><h3>Chart 4 · Monthly average return, 2003–2022 vs 2023+</h3><div class="sub">OOS bars average 3–4 years each.</div><div id="ch4"></div>
    <div class="legend"><span><svg viewBox="0 0 14 12"><rect width="14" height="12" rx="2" fill="var(--is)"/></svg>2003–2022 avg</span><span><svg viewBox="0 0 14 12"><rect width="14" height="12" rx="2" fill="var(--oos)"/></svg>2023+ avg</span></div></div>
</section>

<section>
  <h2>Seasonal path</h2>
  <div class="fig"><h3>Chart 3 · Frozen 2003–2022 average path vs 2023+ realized</h3><div class="sub">Prior year-end = 100. The in-sample line averages 20 years; the OOS line averages only 3 (2023–2025). 2026 is year-to-date through {O["hard_stop"]}.</div><div id="ch3"></div>
    <div class="legend"><span><svg viewBox="0 0 14 12"><rect y="5" width="14" height="2" fill="var(--is)"/></svg>2003–2022 average (20 yrs)</span><span><svg viewBox="0 0 14 12"><rect y="5" width="14" height="2" fill="var(--oos)"/></svg>2023–2025 average (3 yrs)</span><span><svg viewBox="0 0 14 12"><line x1="0" x2="14" y1="6" y2="6" stroke="var(--y26)" stroke-width="2" stroke-dasharray="3 2"/></svg>2026 YTD (partial)</span></div></div>
</section>

<section class="col">
  <h2>Aggregate results</h2>
  <ol class="qa">
    <li><span class="q">Did the bullish hypotheses collectively beat chance?</span> No. Pooled excess over the frozen baseline was {pp(q1["pooled_excess_vs_is_base"])} per occurrence, but over the OOS drift only {pp(q1["pooled_excess_vs_oos_drift"])}. The calendar-scramble placebo with common yearly shifts gives p&nbsp;=&nbsp;{q1["placebo_p_one_sided"]:.2f}.</li>
    <li><span class="q">Did bearish and drawdown hypotheses flag elevated downside?</span> No, as a group (p&nbsp;=&nbsp;{q2[10]["p_binom_greater"]:.2f} and {q2[20]["p_binom_greater"]:.2f}). Sep 16 → Sep 29 averaged {pct(S["Sep16+10td"]["mean"])} with 1 of 4 years down. Only the late-February and March windows repeated.</li>
    <li><span class="q">Similar magnitude?</span> Against the frozen baselines, pooled ρ&nbsp;=&nbsp;{q3["pooled_rho_primary"]:.2f}. Against contemporaneous drift the effects shrink to near zero, and the 2023–26 bull market accounts for most of the difference.</li>
    <li><span class="q">Weaken, persist, strengthen or reverse?</span> Primaries: {", ".join(f"{v} {k.lower()}" for k,v in q4["primary"].items())}. All 132 rules: {", ".join(f"{v} {k.lower()}" for k,v in q4["all"].items())}.</li>
    <li><span class="q">Better than randomly timed windows?</span> Placebo percentiles for the 8 primaries ranged from {min(A["Q5"].values())*100:.0f}th to {max(A["Q5"].values())*100:.0f}th. None reached the 95th, and the pooled test was not significant.</li>
  </ol>
</section>

<section>
  <h2>Full rule validation table</h2>
  <details><summary>All 132 frozen rules, in their original order</summary>
  {table(["Rule ID","Window","Original direction","IS win %","IS avg","OOS N","OOS win %","OOS avg","Excess vs IS base","Excess vs OOS drift","Direction match?","Validation"], full_rows)}
  </details>
  <p class="note col">Also saved as <code>seasonality_oos_2023_present.csv</code>. Every occurrence, including incomplete ones, is in <code>seasonality_oos_occurrences_2023_present.csv</code>, and the full record is in <code>seasonality_validation_2023_present.json</code>.</p>
</section>

<section class="col">
  <h2>Integrity statement</h2>
  <ul class="check">
    <li>The 2003–2022 discovery rules were not changed. The frozen JSON hash is <code>{O["frozen_sha256"]}</code>, identical before and after this analysis.</li>
    <li>No 2023+ data was used to alter, move, add or remove any rule, designation or classification.</li>
    <li>All 132 frozen rules were evaluated and reported in their original order.</li>
    <li>Losing and flat results were retained and shown year by year.</li>
    <li>No seasonal window was shifted, shortened or extended to improve OOS performance.</li>
    <li>Point-in-time restrictions were enforced by the guarded data handler. All 22 look-ahead and isolation tests pass.</li>
    <li>Partial or incomplete periods (2026 windows open on {O["hard_stop"]}, October 2026) were not treated as completed observations.</li>
    <li>The validation criteria were pre-registered and hash-locked (<code>{O["criteria_sha256"]}</code>) before any 2023+ price was loaded.</li>
    <li>This analysis is validation, not re-optimization. Returns exclude dividends, costs, slippage and taxes.</li>
  </ul>
</section>
</div>

<script>
const D = {DATA};
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const P = v => (v>=0?"+":"") + (v*100).toFixed(2) + "%";
function tipFor(fig) {{ const t=document.createElement("div"); t.className="tip"; t.hidden=true; fig.appendChild(t);
  return {{ show(e, html) {{ t.innerHTML=html; t.hidden=false; const r=fig.getBoundingClientRect(); let l=e.clientX-r.left+12; if (l>r.width-200) l-=220; t.style.left=Math.max(4,l)+"px"; t.style.top=(e.clientY-r.top+12)+"px"; }}, hide() {{ t.hidden=true; }} }}; }}
function hover(el, tip) {{ el.addEventListener("pointermove", e => {{ const h=e.target.closest("[data-t]"); if(!h) return tip.hide(); tip.show(e, h.dataset.t); }}); el.addEventListener("pointerleave", ()=>tip.hide()); }}
function ticksFor(lo, hi, n) {{ const raw=(hi-lo)/n, mag=Math.pow(10,Math.floor(Math.log10(raw))); const step=[1,2,2.5,5,10].map(m=>m*mag).find(s=>s>=raw); const out=[]; for(let v=Math.ceil(lo/step)*step; v<=hi+1e-12; v+=step) out.push(+v.toFixed(10)); return out; }}

// Chart 1: grouped horizontal bars
(function(){{
  const el=document.getElementById("ch1"), rows=D.primary, W=560, rowH=40, m={{l:150,r:16,t:8,b:28}}, H=m.t+m.b+rows.length*rowH;
  const vals=rows.flatMap(r=>[r.is_mean,r.oos_mean,r.drift,0]); const lo=Math.min(...vals)*1.15, hi=Math.max(...vals)*1.1;
  const X=v=>m.l+(v-lo)/(hi-lo)*(W-m.l-m.r);
  let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="In-sample vs out-of-sample average return for 8 primary hypotheses">`;
  ticksFor(lo,hi,5).forEach(v=>{{ s+=`<line x1="${{X(v)}}" x2="${{X(v)}}" y1="${{m.t}}" y2="${{H-m.b}}" stroke="var(--grid)"/><text x="${{X(v)}}" y="${{H-10}}" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{(v*100).toFixed(1)}}%</text>`; }});
  s+=`<line x1="${{X(0)}}" x2="${{X(0)}}" y1="${{m.t}}" y2="${{H-m.b}}" stroke="var(--fg2)" stroke-width="1"/>`;
  rows.forEach((r,i)=>{{ const y=m.t+i*rowH; const bh=12;
    s+=`<text x="0" y="${{y+rowH/2-2}}" font-size="12" fill="var(--fg)" font-family="var(--f-body)">${{r.label}}</text><text x="0" y="${{y+rowH/2+12}}" font-size="10.5" fill="${{r.dir==='bullish'?'var(--bull)':'var(--bear)'}}" font-family="var(--f-data)">${{r.dir==='bullish'?'▲ bullish':'▼ bearish'}} · ${{r.id.split('+')[1]}}</text>`;
    [["is_mean","var(--is)","2003–22 avg",y+6],["oos_mean","var(--oos)","2023+ avg",y+6+bh+2]].forEach(([k,c,lab,yy])=>{{ const v=r[k]; const x0=Math.min(X(0),X(v)), w=Math.max(1,Math.abs(X(v)-X(0)));
      s+=`<rect x="${{x0}}" y="${{yy}}" width="${{w}}" height="${{bh}}" rx="2" fill="${{c}}" data-t="${{r.id}}<br>${{lab}}: ${{P(v)}}"/>`; }});
    s+=`<rect x="${{X(r.drift)-1}}" y="${{y+4}}" width="2" height="${{2*bh+6}}" fill="var(--drift)" data-t="${{r.id}}<br>OOS random ${{r.id.split('+')[1]}} window: ${{P(r.drift)}}"/>`;
  }});
  el.innerHTML=s+"</svg>"; hover(el, tipFor(el.parentElement));
}})();

// Chart 2: per-year dot strip
(function(){{
  const el=document.getElementById("ch2"), rows=D.primary, W=560, rowH=40, m={{l:150,r:16,t:8,b:28}}, H=m.t+m.b+rows.length*rowH;
  const yrs=[["2023","var(--y23)","circle"],["2024","var(--y24)","square"],["2025","var(--y25)","triangle"],["2026","var(--y26)","diamond"]];
  const vals=rows.flatMap(r=>Object.values(r.years)).concat([0]); const lo=Math.min(...vals)*1.15, hi=Math.max(...vals)*1.1;
  const X=v=>m.l+(v-lo)/(hi-lo)*(W-m.l-m.r);
  const mark=(sh,x,y,c,t)=>{{ const a=`fill="${{c}}" stroke="var(--panel)" stroke-width="1.5" data-t="${{t}}"`;
    if(sh==="circle") return `<circle cx="${{x}}" cy="${{y}}" r="6" ${{a}}/>`; if(sh==="square") return `<rect x="${{x-5.5}}" y="${{y-5.5}}" width="11" height="11" ${{a}}/>`;
    if(sh==="triangle") return `<path d="M${{x}} ${{y-7}}L${{x+6.5}} ${{y+5}}L${{x-6.5}} ${{y+5}}Z" ${{a}}/>`; return `<path d="M${{x}} ${{y-7}}L${{x+7}} ${{y}}L${{x}} ${{y+7}}L${{x-7}} ${{y}}Z" ${{a}}/>`; }};
  let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="Out-of-sample return by year for each primary hypothesis">`;
  ticksFor(lo,hi,5).forEach(v=>{{ s+=`<line x1="${{X(v)}}" x2="${{X(v)}}" y1="${{m.t}}" y2="${{H-m.b}}" stroke="var(--grid)"/><text x="${{X(v)}}" y="${{H-10}}" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{(v*100).toFixed(0)}}%</text>`; }});
  s+=`<line x1="${{X(0)}}" x2="${{X(0)}}" y1="${{m.t}}" y2="${{H-m.b}}" stroke="var(--fg2)"/>`;
  rows.forEach((r,i)=>{{ const y=m.t+i*rowH+rowH/2;
    s+=`<text x="0" y="${{y-2}}" font-size="12" fill="var(--fg)" font-family="var(--f-body)">${{r.label}}</text><text x="0" y="${{y+12}}" font-size="10.5" fill="${{r.dir==='bullish'?'var(--bull)':'var(--bear)'}}" font-family="var(--f-data)">${{r.dir==='bullish'?'▲ bullish':'▼ bearish'}} · ${{r.id.split('+')[1]}}</text>`;
    s+=`<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{y}}" y2="${{y}}" stroke="var(--grid)" stroke-dasharray="2 3"/>`;
    yrs.forEach(([yr,c,sh],k)=>{{ if(r.years[yr]==null) return; s+=mark(sh, X(r.years[yr]), y+(k-1.5)*3, c, `${{r.id}} · ${{yr}}<br>${{P(r.years[yr])}}`); }});
  }});
  el.innerHTML=s+"</svg>"; hover(el, tipFor(el.parentElement));
  document.getElementById("lg2").innerHTML = yrs.map(([y,c,sh])=>`<span><svg viewBox="-8 -8 16 16">${{mark(sh,0,0,c,'').replace(/data-t="[^"]*"/,'')}}</svg>${{y}}${{y==='2026'?' (completed windows only)':''}}</span>`).join("");
}})();

// Chart 3: seasonal paths
(function(){{
  const el=document.getElementById("ch3"), W=900, H=300, m={{l:44,r:16,t:10,b:26}}, n=252;
  const all=D.is_avg.concat(D.oos_avg, D.ytd2026); const lo=Math.min(...all)-1, hi=Math.max(...all)+1;
  const X=i=>m.l+i*(W-m.l-m.r)/(n-1), Y=v=>m.t+(1-(v-lo)/(hi-lo))*(H-m.t-m.b);
  let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="Seasonal path, in-sample average vs out-of-sample">`;
  ticksFor(lo,hi,6).forEach(v=>{{ s+=`<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{Y(v)}}" y2="${{Y(v)}}" stroke="var(--grid)"/><text x="${{m.l-6}}" y="${{Y(v)+4}}" text-anchor="end" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{v}}</text>`; }});
  s+=`<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{Y(100)}}" y2="${{Y(100)}}" stroke="var(--muted)" stroke-dasharray="3 3"/>`;
  let prev=""; D.labels.forEach((l,i)=>{{ const mo=l.slice(0,2); if(mo!==prev){{ s+=`<text x="${{X(i)}}" y="${{H-8}}" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{MON[+mo-1]}}</text>`; prev=mo; }} }});
  const path=(a,c,dash)=>`<path d="${{a.map((v,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1)).join('')}}" fill="none" stroke="${{c}}" stroke-width="2" ${{dash?'stroke-dasharray="4 3"':''}}/>`;
  s+=path(D.is_avg,"var(--is)")+path(D.oos_avg,"var(--oos)")+path(D.ytd2026,"var(--y26)",true);
  s+=`<line class="xh" y1="${{m.t}}" y2="${{H-m.b}}" stroke="var(--fg2)" opacity="0"/><rect x="${{m.l}}" y="0" width="${{W-m.l-m.r}}" height="${{H}}" fill="transparent" class="hit"/></svg>`;
  el.innerHTML=s; const svg=el.querySelector("svg"), xh=svg.querySelector(".xh"), tip=tipFor(el.parentElement);
  svg.querySelector(".hit").addEventListener("pointermove", e=>{{ const r=svg.getBoundingClientRect(); const i=Math.max(0,Math.min(n-1,Math.round(((e.clientX-r.left)*W/r.width-m.l)/((W-m.l-m.r)/(n-1)))));
    xh.setAttribute("x1",X(i)); xh.setAttribute("x2",X(i)); xh.setAttribute("opacity",1);
    tip.show(e, `Day ${{i+1}} · ~${{MON[+D.labels[i].slice(0,2)-1]}} ${{+D.labels[i].slice(3)}}<br>2003–22 avg: ${{D.is_avg[i].toFixed(2)}}<br>2023–25 avg: ${{D.oos_avg[i].toFixed(2)}}${{D.ytd2026[i]!=null?'<br>2026 YTD: '+D.ytd2026[i].toFixed(2):''}}`); }});
  svg.querySelector(".hit").addEventListener("pointerleave", ()=>{{ tip.hide(); xh.setAttribute("opacity",0); }});
}})();

// Chart 4: monthly grouped bars
(function(){{
  const el=document.getElementById("ch4"), W=900, H=280, m={{l:44,r:16,t:10,b:28}}, rows=D.months;
  const vals=rows.flatMap(r=>[r.is_mean,r.oos_mean,0]); const lo=Math.min(...vals)*1.15, hi=Math.max(...vals)*1.1;
  const Y=v=>m.t+(1-(v-lo)/(hi-lo))*(H-m.t-m.b), gw=(W-m.l-m.r)/12, bw=Math.min(22,gw/2-6);
  let s=`<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="Monthly average return in-sample vs out-of-sample">`;
  ticksFor(lo,hi,5).forEach(v=>{{ s+=`<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{Y(v)}}" y2="${{Y(v)}}" stroke="var(--grid)"/><text x="${{m.l-6}}" y="${{Y(v)+4}}" text-anchor="end" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{(v*100).toFixed(1)}}%</text>`; }});
  s+=`<line x1="${{m.l}}" x2="${{W-m.r}}" y1="${{Y(0)}}" y2="${{Y(0)}}" stroke="var(--fg2)"/>`;
  rows.forEach((r,i)=>{{ const cx=m.l+gw*i+gw/2;
    [["is_mean","var(--is)","2003–22 avg (20 yrs)",cx-bw-1],["oos_mean","var(--oos)",`2023+ avg (${{r.n}} yrs)`,cx+1]].forEach(([k,c,lab,x])=>{{ const v=r[k]; const y0=Math.min(Y(0),Y(v)), h=Math.max(1,Math.abs(Y(v)-Y(0)));
      s+=`<rect x="${{x}}" y="${{y0}}" width="${{bw}}" height="${{h}}" rx="2" fill="${{c}}" data-t="${{r.m}}<br>${{lab}}: ${{P(v)}}"/>`; }});
    s+=`<text x="${{cx}}" y="${{H-8}}" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="var(--f-data)">${{r.m}}</text>`; }});
  el.innerHTML=s+"</svg>"; hover(el, tipFor(el.parentElement));
}})();
</script>
"""
open(os.path.join(HERE, "report_oos.html"), "w").write(html)
print("report_oos.html", len(html) // 1024, "KB")
