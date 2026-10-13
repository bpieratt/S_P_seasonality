# Sensitivity analysis (2026-10-13)

A separate review of five places where the original method could have overstated confidence. **It changes nothing in the original research.** It reads the frozen files, writes only into this folder, and its results are reported next to the originals, not in place of them.

Run it from the repository root: `python sensitivity/run_sensitivity.py`. Results are saved to `sensitivity_results.json`.

| # | Concern | Original result | Sensitivity result | Effect |
|---|---|---|---|---|
| 1 | **Overlapping windows** (2003–2022). Windows such as Jul 1 + 15 days and Jul 1 + 20 days share most of their days, so the 120 tests aren't independent. | Best FDR q = 0.64; permutation family-wise p = 0.40 | The 120 windows behave like about **26 independent tests** (Li–Ji method; the Nyholt method gives 108). The best p (0.0053) × 26.5 = **0.14**, still not significant. FDR on the Wilcoxon test gives a best q of 0.64. | Confirms the original |
| 2 | **Placebo environment** (2023–2026). Comparing a 2024 trade with random dates from other years mixes market conditions. | Bullish windows vs random timing, p = 0.36 | Placebo kept in the **same calendar year**: p = **0.29**. Fully independent random dates: p = 0.30. | Confirms: no better than random timing |
| 3 | **Spearman and binomial tests across 132 rules.** These assumed the rules were independent, but they overlap heavily. | "In-sample winners stayed ahead" Spearman 0.15, p = **0.041** (nominal). 55% kept direction, p = 0.17 | Shifting all rules' dates together (which keeps their overlaps) 2,000 times: Spearman p = **0.23**, share p = **0.27**. | **Qualifies the original:** the 0.041 was overstated. The faint persistence is within normal luck. |
| 4 | **Entry and exit timing** | Entry at the close before the start date; exit at the close of the Nth trading day | All 30 newer-period trades of the 8 main rules match the definition. Labels show the *typical* exit date; the actual date varies by 1–3 days. January 2023 rules start from the Jan 3 open, which gives January 2023 = +5.80%. Using the Dec 30, 2022 close would give +6.18%. This affects 6 January rules, none of them main hypotheses. | Confirms; one minor convention noted |
| 5 | **Partial 2026 data** | Occurrences ending after 2026-10-02 marked incomplete | 37 incomplete occurrences, none carrying a return. October 2026 is excluded. 37 rules (October–December windows, plus late-September ones) have 3 newer years instead of 4. | Correctly handled |

**Overall:** the conclusion that the calendar shows no statistically reliable edge stands, and if anything it is strengthened. The only original figure that needs a caveat is the Phase 2 Spearman p = 0.041, which should be read as about 0.23 once overlap is accounted for.

The placebo p-values in rows 2 and 3 come from random draws (seed 20261013), so a different seed would shift them slightly. The original Phase 2 placebo used a different scheme (a common random shift per year), so its 0.36 isn't expected to match these exactly.
