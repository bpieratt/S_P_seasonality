# S&P 500 Calendar Seasonality

A two-phase study of whether the S&P 500 (^GSPC) shows recurring calendar seasonality.

| Phase | Data | What it does |
|---|---|---|
| 1. Discovery | 2003-01-02 … 2022-12-30 (5,035 days) | Tests 120 pre-declared calendar windows + 12 months against normal drift, with FDR and permutation corrections, then **freezes** all 132 rules |
| 2. Out-of-sample validation | 2023-01-03 … 2026-10-02 (941 days) | Applies the frozen rules unchanged, using criteria hash-locked **before** the new data was loaded |

## Results in brief

- **In-sample:** no window or month survived multiple-testing correction (best FDR q = 0.64). 8 windows showed nominal (Moderate) evidence and were frozen as the primary hypotheses.
- **Out-of-sample:** the 8 primaries scored 4 Supportive, 1 Partially Supportive, 3 Inconclusive, 0 Contradicted. As a group, though, the bullish windows did **not** beat randomly timed windows in the same period (placebo p = 0.36), and the drawdown windows did not flag unusual downside.
- **Best-supported:** Apr 16 → Apr 29 (10 trading days) and mid-November (Nov 16 + 15/30 td). With only 3–4 years each, this is evidence, not proof.

## Reports

Download and open in a browser:
- `docs/phase1_report.html`: discovery study, charts, heatmap, frozen rules
- `docs/phase2_oos_report.html`: out-of-sample scorecard, year-by-year results, integrity statement

Chart images are in `outputs/charts/` (Phase 1) and `phase2/outputs/charts/` (Phase 2).

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
```

## Reproduce

```
python test_data_handler.py && python analysis.py && python build_outputs.py && python make_report.py
cd phase2 && python test_oos.py && python validate.py && python make_outputs.py && python make_report.py
```

Requires Python 3 with pandas, numpy, scipy, matplotlib and pyyaml.

Returns are price-only and exclude dividends, transaction costs, slippage and taxes. This is research, not investment advice.
