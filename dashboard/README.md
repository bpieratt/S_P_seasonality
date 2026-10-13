# Seasonality dashboard

A single, self-contained page that explains the S&P 500 seasonality study in plain English. Its styling follows the `seasonal-screener` dashboard.

**This folder is presentation only.** It reads the research files and never changes them. Every monthly return it shows is recomputed from the price files and checked against the frozen research outputs; if anything disagrees, the build stops.

## How to open it

Double-click **`dashboard/index.html`**. It opens in any modern browser and needs no internet, server or installation. Everything (styles, scripts, data) is inside that one file.

## Sections

| Section | What you'll find |
|---|---|
| **Summary** | Five plain-English answers, each tagged as *historical observation*, *supported*, *inconclusive*, *no reliable advantage* or *reversed* |
| **2003–2022** | Monthly averages (switchable to 2023–26 or side by side), a sortable month scorecard, and the 8 strongest historical windows |
| **Heat map: history** | Every month 2003–2022, with year totals and monthly averages, plus "How to read this heat map" |
| **Heat map: 2023–26** | Same scale for the newer data. October 2026 is marked *In progress* and gets no monthly return. Includes "What changed?" |
| **Then vs now** | Side-by-side metrics, which monthly tendencies persisted, and typical-year path charts |
| **Rule check** | The 8 frozen hypotheses in their original order, each year's result, and a searchable table of all 132 rules |
| **Statistical review** | The new sensitivity checks (see `../sensitivity/`), shown next to the original results |
| **Glossary** | 32 terms (meaning, why it matters, example) and 9 formulas (symbols, worked example, limitations) |

The small **ⓘ** buttons explain a term in place: hover or click on a computer, tap on a phone, and press Esc to close. Click a table heading to sort, and click a row in the rule check to expand it.

## How the heat maps are calculated

`monthly return = close on the month's last trading day ÷ close on the previous month's last trading day − 1`

The first month of each price file (January 2003, January 2023) starts from that day's open, because the file contains no earlier close. This is the same rule the frozen research used.

A month counts as complete only if its last calendar day is on or before the last price date (2026-10-02). Incomplete months show *In progress* and are left out of every average and comparison. Year totals multiply the completed months together. For 2026 the total is labelled "Jan–Sep", not a full year.

Colors: teal means a gain and red a loss. Intensity grows with size up to ±8%, and anything between −0.5% and +0.5% is grey.

## Regenerating

```
python sensitivity/run_sensitivity.py      # optional: refresh the sensitivity results
python dashboard/build_dashboard.py        # rebuilds dashboard/index.html and dashboard_data.json
python dashboard/tests/ui_test.py          # optional browser test (needs Playwright)
```

You need Python 3 with pandas, numpy, scipy and pyyaml (already required by the research). Colors are set in `dashboard/config.yaml`, mirroring the screener's `dashboard.colors`.

## Files

| File | Role |
|---|---|
| `build_data.py` | Computes every dashboard number from the research files and cross-checks it (presentation only) |
| `build_dashboard.py` | Fills the template and writes `index.html` |
| `src/template.html`, `src/styles.css`, `src/app.js` | Page structure, styling and interactive charts and tables (no external libraries) |
| `content/glossary.json` | Glossary terms and formula explanations |
| `config.yaml` | Colors and output path |
| `index.html` | **The dashboard** (generated) |
| `dashboard_data.json` | The exact numbers embedded in the page, for inspection (generated) |
| `tests/ui_test.py` | Browser checks: page errors, tooltips, sorting, toggles, phone layout |
