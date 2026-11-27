# S&P 500 Calendar Seasonality

A two-phase study of whether the S&P 500 (^GSPC) shows recurring calendar seasonality.

| Phase | Data | What it does |
|---|---|---|
| 1. Discovery | 2003-01-02 … 2022-12-30 (5,035 days) | Tests 120 pre-declared calendar windows + 12 months against normal drift, with FDR and permutation corrections, then **freezes** all 132 rules |
| 2. Out-of-sample validation | 2023-01-03 … 2026-10-02 (941 days) | Applies the frozen rules unchanged, using criteria hash-locked **before** the new data was loaded |

## Results in brief

- **In-sample:** no window or month survived multiple-testing correction (best FDR q = 0.64). 8 windows showed nominal (Moderate) evidence and were frozen as the primary hypotheses.
- **Out-of-sample:** v�� 8 primaries scored 4 Supportive, 1 Partially Supportive, 3 Inconclusive, 0 Contradicted. As a group, though, the bullish windows did **not** beat randomly timed windows in the same period (placebo p = 0.36), and the drawdown windows did not flag unusual downside.
- **Best-supported:** Apr 16 → Apr 29 (10 trading days) and mid-November (Nov 16 + 15/30 td). With only 3–4 years each, this is evidence, not proof.

## Reports

Download and open in a browser:
- `docs/phase1_report.html`: discovery study, charts, heatmap, frozen rules
- `docs/phase2_oos_report.html`: out-of-sample scorecard, year-by-year results, integrity statement

Chart images are in `outputs/charts/` (Phase 1) and `phase2/outputs/charts/` (Phase 2).

## Dashboard (plain-English view)

Open **`dashboard/index.html`** in a browser. It is one self-contained file that needs no installation or internet. It explains the whole study for a non-specialist: the executive summary, heat maps for 2003–2022 and for 2023–2026 (incomplete months clearly marked), a then-vs-now comparison, the rule check, a statistical review and a glossary with in-place explanations. See `dashboard/README.md` for details and `sensitivity/SENSITIVITY.md` for the separate sensitivity review.

### Original research vs presentation-only files

| Original research (frozen; not modified by the dashboard work) | Presentation and review additions |
|---|---|
| `config.yaml`, `data_handler.py`, `test_data_handler.py`, `analysis.py`, `build_outputs.py`, `make_report.py`, `data/`, `outputs/`, `seasonal_patterns_2003_2022.json` (+ `.sha256`), `report.html`, `docs/`, everything in `phase2/` | `dashboard/` (presentation only) and `sensitivity/` (separate checks that read the research files and write only into their own folder) |

## Layout

```
config.yaml                       Phase-1 parameters (data hash pinned)
data_handler.py                   point-in-time data handler; raises on any post-cutoff bar
test_data_handler.py              11 look-ahead / cutoff tests
analysis.py, build_outputs.py,    Phase-1 statistics, charts, frozen JSON, report
  make_report.py
seasonal_patterns_2003_2022.json  FROZEN rules (sha256 in .sha256 file)
outputs/                          Phase-1 tables and chart PNGs
data/GSPC_2003_2022.csv           Phase-1 prices (Yahoo Finance, unadjusted)
phase2/                           out-of-sample validation: locked criteria, data, tests, outputs
docs/                             both HTML reports
dashboard/                        plain-English dashboard (presentation only)
sensitivity/                      separate sensitivity review (2026-10-13)
```

## Reproduce

```
python test_data_handler.py && python analysis.py && python build_outputs.py && python make_report.py
cd phase2 && python test_oos.py && python validate.py && python make_outputs.py && python make_report.py
```

Requires Python 3 with pandas, numpy, scipy, matplotlib and pyyaml.

Returns are price-only and exclude dividends, transaction costs, slippage and taxes. This is research, not investment advice.
