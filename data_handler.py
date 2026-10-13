"""
Point-in-time market data handler with a hard data cutoff.

Design (look-ahead is prevented structurally, not by discipline):
  * load_market_data() refuses to construct a dataset if ANY row is dated after
    the configured hard_stop_date (raises FutureDataError), if the date index is
    not strictly increasing, or if prices are missing/non-positive.
  * MarketData keeps its arrays private and read-only. Strategies never receive
    a MarketData object; they receive a PointInTimeView built by as_of(T).
  * PointInTimeView is constructed from *slices* of the arrays that end at T.
    It holds no reference to the parent arrays or to any bar dated > T, so there
    is nothing in memory for strategy code to reach. Any request for a bar dated
    after T raises LookAheadError. All exposed arrays are read-only.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd


class FutureDataError(RuntimeError):
    """Raised when data dated after the hard stop date is loaded."""


class LookAheadError(RuntimeError):
    """Raised when a strategy requests information dated after its as-of date."""


def _ro(a: np.ndarray) -> np.ndarray:
    a = np.array(a, copy=True)
    a.setflags(write=False)
    return a


class PointInTimeView:
    """Everything a strategy may see at date T: bars with date <= T, nothing else."""

    __slots__ = ("_as_of", "_dates", "_open", "_high", "_low", "_close")

    def __init__(self, as_of, dates, open_, high, low, close):
        as_of = np.datetime64(as_of, "D")
        if len(dates) and dates[-1] > as_of:
            raise LookAheadError("view constructed with bars after its as-of date")
        self._as_of = as_of
        self._dates, self._open, self._high, self._low, self._close = (
            _ro(dates), _ro(open_), _ro(high), _ro(low), _ro(close))

    # read-only accessors -------------------------------------------------
    @property
    def as_of(self):
        return self._as_of

    @property
    def dates(self):
        return self._dates

    @property
    def close(self):
        return self._close

    @property
    def open(self):
        return self._open

    @property
    def high(self):
        return self._high

    @property
    def low(self):
        return self._low

    def __len__(self):
        return len(self._dates)

    def bar(self, date):
        d = np.datetime64(date, "D")
        if d > self._as_of:
            raise LookAheadError(f"requested {d} but view is as of {self._as_of}")
        i = np.searchsorted(self._dates, d)
        if i >= len(self._dates) or self._dates[i] != d:
            raise KeyError(f"no bar on {d}")
        return dict(date=d, open=self._open[i], high=self._high[i],
                    low=self._low[i], close=self._close[i])

    def last_close(self):
        return float(self._close[-1])


@dataclass(frozen=True)
class _Cfg:
    hard_stop: np.datetime64
    start: np.datetime64


class MarketData:
    """Full in-sample dataset. Only hands out PointInTimeViews."""

    def __init__(self, df: pd.DataFrame, hard_stop: str):
        self.__hard_stop = np.datetime64(hard_stop, "D")
        d = df["Date"].values.astype("datetime64[D]")
        if (d > self.__hard_stop).any():
            raise FutureDataError(
                f"{int((d > self.__hard_stop).sum())} rows dated after {self.__hard_stop}")
        self.__dates = _ro(d)
        self.__open = _ro(df["Open"].values.astype(float))
        self.__high = _ro(df["High"].values.astype(float))
        self.__low = _ro(df["Low"].values.astype(float))
        self.__close = _ro(df["Close"].values.astype(float))

    @property
    def hard_stop(self):
        return self.__hard_stop

    @property
    def trading_calendar(self):
        """Exchange trading dates (a published, known-in-advance calendar)."""
        return self.__dates

    @property
    def first_open(self):
        return float(self.__open[0])

    def as_of(self, date) -> PointInTimeView:
        t = np.datetime64(date, "D")
        if t > self.__hard_stop:
            raise FutureDataError(f"as_of {t} is beyond hard stop {self.__hard_stop}")
        n = int(np.searchsorted(self.__dates, t, side="right"))
        return PointInTimeView(t, self.__dates[:n], self.__open[:n], self.__high[:n],
                               self.__low[:n], self.__close[:n])

    def summary(self):
        return dict(first=str(self.__dates[0]), last=str(self.__dates[-1]),
                    n_obs=int(len(self.__dates)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_market_data(cfg: dict) -> MarketData:
    g = cfg["data_guardrails"]
    if g.get("allow_future_data", False):
        raise FutureDataError("allow_future_data must be false for this study")
    path = cfg["study"]["data_file"]
    expected = cfg["study"].get("data_sha256")
    if expected and sha256(path) != expected:
        raise ValueError("data file checksum does not match config (file changed)")
    df = pd.read_csv(path, parse_dates=["Date"])
    hard_stop = pd.Timestamp(g["hard_stop_date"])
    if (df["Date"] > hard_stop).any():
        raise FutureDataError(
            f"Data contains {(df['Date'] > hard_stop).sum()} rows after {hard_stop.date()} — refusing to load")
    df = df[df["Date"] >= pd.Timestamp(cfg["study"]["start_date"])]
    if not df["Date"].is_monotonic_increasing or df["Date"].duplicated().any():
        raise ValueError("dates must be strictly increasing with no duplicates")
    px = df[["Open", "High", "Low", "Close"]]
    if px.isna().any().any() or (px <= 0).any().any():
        raise ValueError("missing or non-positive prices")
    return MarketData(df.reset_index(drop=True), g["hard_stop_date"])
