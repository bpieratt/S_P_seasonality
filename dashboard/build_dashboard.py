"""
Build the self-contained dashboard (dashboard/index.html).

    python sensitivity/run_sensitivity.py     # only if sensitivity results need refreshing
    python dashboard/build_dashboard.py

Presentation only: reads research files through build_data.py (which cross-checks every
monthly return against the frozen outputs) and writes nothing outside dashboard/.
"""
import datetime as dt
import json
import os
import re

import yaml

from build_data import ROOT, build

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")


def pct(v, nd=2):
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v) * 100:.{nd}f}%"


def info_button(term_id, terms):
    title = terms.get(term_id, term_id)
    return (f'<button type="button" class="info" data-term="{term_id}" '
            f'aria-label="Explain: {title}" aria-expanded="false">i</button>')


def main():
    cfg = yaml.safe_load(open(os.path.join(HERE, "config.yaml")))
    data = build()
    glossary = json.load(open(os.path.join(HERE, "content", "glossary.json")))
    terms = {t["id"]: t["term"] for t in glossary["terms"]} | {f["id"]: f["name"] for f in glossary["formulas"]}

    pm = {r["m"]: r for r in data["months"]["is_"]}
    prim = {p["id"]: p for p in data["primaries"]}
    agg = data["aggregate"]
    rules = data["rules"]
    c = data["compare"]
    oos_last = dt.date.fromisoformat(data["meta"]["oos_last"])
    build_today = dt.date.today()
    recent_through = data["meta"].get("oos_last_recent") or data["meta"]["oos_last"]
    recent_through_date = dt.date.fromisoformat(recent_through)
    tokens = dict(
        oos_years_word="almost four", oos_last_long=f"{oos_last:%B} {oos_last.day}, {oos_last.year}",
        build_date_long=f"{build_today:%B} {build_today.day}, {build_today.year}",
        recent_through_long=f"{recent_through_date:%B} {recent_through_date.day}, {recent_through_date.year}",
        oos_last_short=f"{oos_last:%b} {oos_last.day}, {oos_last.year}",
        is_months=str(c["is_"]["n_months"]), is_days=f'{data["meta"]["is_days"]:,}',
        oos_months=str(c["oos"]["n_months"]), oos_days=f'{data["meta"]["oos_days"]:,}',
        p1_raw=str(data["phase1"]["n_raw_p05"]), p1_expected=str(round(0.05 * data["phase1"]["n_windows"])),
        apr_avg=pct(pm["Apr"]["avg"]), jul_avg=pct(pm["Jul"]["avg"]), nov_avg=pct(pm["Nov"]["avg"]),
        sep_avg=pct(pm["Sep"]["avg"]), jan_avg=pct(pm["Jan"]["avg"]), jun_avg=pct(pm["Jun"]["avg"]),
        month_same_sign=str(c["consistency"]["oos_same_sign_as_history_vs_own_avg"]),
        apr_oos_n=str(prim["Apr16+10td"]["oos_n"]), apr_oos_mean=pct(prim["Apr16+10td"]["oos_mean"]),
        q1_pooled=pct(agg["Q1"]["pooled_mean_return"]),
        q1_vs_drift=pct(agg["Q1"]["pooled_excess_vs_oos_drift"]).replace("%", " pts"),
        q1_p=f'{agg["Q1"]["placebo_p_one_sided"]:.2f}',
        is_avg_month=pct(data["months"]["is_avg_all"]), oos_avg_month=pct(data["months"]["oos_avg_all"]),
        min_month_q=f'{min(r["q"] for r in data["months"]["is_"]):.2f}',
        oos_worst_single=pct(c["oos"]["worst_single"]["ret"], 1), oos_worst_single_ym=c["oos"]["worst_single"]["ym"],
        is_worst_single=pct(c["is_"]["worst_single"]["ret"], 1), is_worst_single_ym=c["is_"]["worst_single"]["ym"],
        n_contra=str(sum(r["verdict"] == "CONTRADICTED" for r in rules)),
        n_supp=str(sum(r["verdict"] == "SUPPORTIVE" for r in rules)),
        share_vs_drift=f'{agg["Q4"]["share_all_same_sign_vs_oos_drift"] * 100:.0f}%',
        review_date=cfg["review_date"],
        s3_p=f'{data["sensitivity"]["S3_cross_rule_tests"]["calendar_shift_p_spearman"]:.2f}',
        frozen_sha=data["meta"]["frozen_sha"], criteria_sha=data["meta"]["criteria_sha"],
        build_date=dt.date.today().isoformat(),
        base5=pct(data["calendar_heat"]["base5"]),
    )
    css = open(os.path.join(SRC, "styles.css")).read()
    for k, v in cfg["colors"].items():
        css = css.replace("{{color_" + k + "}}", v)
    html = open(os.path.join(SRC, "template.html")).read()
    html = re.sub(r"\[\[i:([a-z_0-9]+)\]\]", lambda m: info_button(m.group(1), terms), html)
    for k, v in tokens.items():
        html = html.replace("{{" + k + "}}", v)
    safe = lambda o: json.dumps(o, separators=(",", ":"), default=float).replace("</", "<\\/")
    html = (html.replace("{{CSS}}", css).replace("{{DATA_JSON}}", safe(data))
                .replace("{{GLOSSARY_JSON}}", safe(glossary)).replace("{{APP_JS}}", open(os.path.join(SRC, "app.js")).read()))
    left = re.findall(r"\{\{[A-Za-z_0-9]+\}\}", html)
    assert not left, f"unfilled template tokens: {left}"
    unknown = [t for t in re.findall(r'data-term="([a-z_0-9]+)"', html) if t not in terms]
    assert not unknown, f"tooltips without glossary entry: {unknown}"
    out = os.path.join(ROOT, cfg["output_file"])
    open(out, "w").write(html)
    json.dump(data, open(os.path.join(HERE, "dashboard_data.json"), "w"), indent=1, default=float)
    print(f"wrote {out} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
