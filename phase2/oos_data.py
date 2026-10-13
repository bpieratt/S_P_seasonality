"""
Phase-2 guarded loader. Reuses the Phase-1 MarketData / PointInTimeView classes
unchanged, and adds out-of-sample isolation:
  * any row dated BEFORE 2023-01-01 -> DataIsolationError (no mixing with 2003-2022 prices)
  * any row dated AFTER the hard stop (last completed trading day) -> FutureDataError
"""
import hashlib
import os
import sys

import numpy as np
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from data_handler import FutureDataError, LookAheadError, MarketData, PointInTimeView  # noqa: E402,F401

CRITERIA_PATH = os.path.join(HERE, "oos_validation_criteria.yaml")
LOCK_PATH = os.path.join(HERE, "preregistration.lock")
FROZEN_PATH = os.path.join(os.path.dirname(HERE), "seasonal_patterns_2003_2022.json")
DATA_PATH = os.path.join(HERE, "data", "GSPC_2023_2026-10-02.csv")
DATA_SHA256 = "aec02f4f2efc98a13e14a02918e0c0aef45f388d57ef31e67d10c43cf937ab00"


class DataIsolationError(RuntimeError):
    """Raised when in-sample (pre-2023) prices appear in the OOS dataset."""


class PreregistrationError(RuntimeError):
    pass


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_criteria():
    lock = open(LOCK_PATH).read().split()[0]
    if sha256(CRITERIA_PATH) != lock:
        raise PreregistrationError("validation criteria changed after pre-registration")
    return yaml.safe_load(open(CRITERIA_PATH))


def verify_frozen(crit):
    fr = crit["frozen_rules"]
    h = sha256(FROZEN_PATH)
    if h != fr["sha256"]:
        raise PreregistrationError(f"frozen rule file hash {h} != {fr['sha256']}")
    return h


def load_oos(path=DATA_PATH, min_date="2023-01-01", hard_stop="2026-10-02", expected_sha=DATA_SHA256):
    if expected_sha and sha256(path) != expected_sha:
        raise ValueError("OOS data checksum mismatch")
    df = pd.read_csv(path, parse_dates=["Date"])
    if (df.Date < pd.Timestamp(min_date)).any():
        raise DataIsolationError(f"{(df.Date < pd.Timestamp(min_date)).sum()} rows before {min_date}")
    if (df.Date > pd.Timestamp(hard_stop)).any():
        raise FutureDataError(f"rows after hard stop {hard_stop}")
    if not df.Date.is_monotonic_increasing or df.Date.duplicated().any():
        raise ValueError("dates must be strictly increasing, no duplicates")
    px = df[["Open", "High", "Low", "Close"]]
    if px.isna().any().any() or (px <= 0).any().any():
        raise ValueError("missing or non-positive prices")
    return MarketData(df.reset_index(drop=True), hard_stop), df


# NYSE full-day closures 2023-01-01 .. 2026-10-02 (published exchange calendar)
NYSE_HOLIDAYS = [
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29", "2023-06-19", "2023-07-04",
    "2023-09-04", "2023-11-23", "2023-12-25",
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04",
    "2024-09-02", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
    "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07",
]


def quality_report(df, hard_stop="2026-10-02"):
    exp = pd.bdate_range("2023-01-01", hard_stop)
    exp = exp[~exp.isin(pd.to_datetime(NYSE_HOLIDAYS))]
    have = pd.DatetimeIndex(df.Date)
    r = df.Close.pct_change()
    sus = []
    for i, row in df.iterrows():
        why = []
        if row.High < row.Low:
            why.append("high<low")
        if not (row.Low - 0.01 <= row.Close <= row.High + 0.01):
            why.append("close outside high/low")
        if not (row.Low - 0.01 <= row.Open <= row.High + 0.01):
            why.append("open outside high/low")
        if i > 0 and abs(r.iloc[i]) >= 0.04:
            why.append(f"daily move {r.iloc[i]:+.2%}")
        if why:
            sus.append(dict(date=str(row.Date.date()), close=row.Close, flags=why))
    return dict(first=str(have[0].date()), last=str(have[-1].date()), trading_days=len(have),
                missing_vs_nyse_calendar=[str(d.date()) for d in exp.difference(have)],
                unexpected_dates=[str(d.date()) for d in have.difference(exp)],
                duplicate_dates=int(df.Date.duplicated().sum()), flagged_observations=sus)
