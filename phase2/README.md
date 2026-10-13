# Phase 2: strict out-of-sample validation (2023-01-03 … 2026-10-02)

Reproduce from this folder:

    python test_oos.py        # 11 isolation / point-in-time tests  (also run ../test_data_handler.py from the parent)
    python validate.py        # applies the 132 frozen rules -> outputs/oos_results.pkl
    python make_outputs.py    # seasonality_oos_2023_present.csv, occurrences CSV, seasonality_validation_2023_present.json
    python make_report.py     # report_oos.html

Locked inputs:
- ../seasonal_patterns_2003_2022.json  sha256 6d8fbfbf56ee66cafd2d8938d93f4ec374d08d8dad67a1c5760b0413b749beac (read-only, unchanged)
- oos_validation_criteria.yaml         sha256 recorded in preregistration.lock, locked 2026-10-03T23:35:57Z before any 2023+ price was loaded
- data/GSPC_2023_2026-10-02.csv        sha256 aec02f4f2efc98a13e14a02918e0c0aef45f388d57ef31e67d10c43cf937ab00 (^GSPC, Yahoo daily, 941 bars)
