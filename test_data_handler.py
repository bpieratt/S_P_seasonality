"""Look-ahead / cutoff guardrail tests. Run: python test_data_handler.py  (or pytest)"""
import copy

import numpy as np
import pandas as pd
import contextlib
import inspect
import sys
import tempfile
from pathlib import Path

try:
    import pytest
    raises = pytest.raises
except ImportError:  # minimal fallback so the tests run without pytest
    @contextlib.contextmanager
    def raises(exc):
        try:
            yield
        except exc:
            return
        raise AssertionError(f"expected {exc.__name__}")
import yaml

from data_handler import (FutureDataError, LookAheadError, MarketData,
                          load_market_data)

CFG = yaml.safe_load(open("config.yaml"))


def _df(dates):
    n = len(dates)
    p = np.linspace(100, 110, n)
    return pd.DataFrame(dict(Date=pd.to_datetime(dates), Open=p, High=p + 1, Low=p - 1, Close=p))


def test_real_file_loads_and_ends_on_or_before_cutoff():
    md = load_market_data(CFG)
    s = md.summary()
    assert s["last"] <= "2022-12-31"
    assert s["first"] >= "2003-01-01"


def test_any_post_cutoff_row_raises():
    with raises(FutureDataError):
        MarketData(_df(["2022-12-29", "2022-12-30", "2023-01-03"]), "2022-12-31")


def test_loader_rejects_post_cutoff_file(tmp_path):
    f = tmp_path / "bad.csv"
    _df(["2022-12-30", "2023-01-03"]).to_csv(f, index=False)
    cfg = copy.deepcopy(CFG)
    cfg["study"]["data_file"] = str(f)
    cfg["study"]["data_sha256"] = None
    with raises(FutureDataError):
        load_market_data(cfg)


def test_allow_future_data_flag_cannot_be_enabled():
    cfg = copy.deepcopy(CFG)
    cfg["data_guardrails"]["allow_future_data"] = True
    with raises(FutureDataError):
        load_market_data(cfg)


def test_as_of_beyond_hard_stop_raises():
    md = load_market_data(CFG)
    with raises(FutureDataError):
        md.as_of("2023-01-03")


def test_view_contains_no_future_bars_for_every_date():
    md = load_market_data(CFG)
    cal = md.trading_calendar
    for t in cal[::97]:
        v = md.as_of(t)
        assert v.dates[-1] == t
        assert (v.dates <= t).all()
        assert len(v) == int((cal <= t).sum())


def test_view_on_non_trading_day_ends_at_previous_bar():
    md = load_market_data(CFG)
    v = md.as_of("2020-07-04")  # Saturday / holiday
    assert v.dates[-1] < np.datetime64("2020-07-04")


def test_future_bar_request_raises():
    md = load_market_data(CFG)
    v = md.as_of("2010-06-15")
    with raises(LookAheadError):
        v.bar("2010-06-16")


def test_view_arrays_are_read_only():
    v = load_market_data(CFG).as_of("2010-06-15")
    with raises(ValueError):
        v.close[-1] = 0.0


def test_view_holds_no_reference_to_future_memory():
    md = load_market_data(CFG)
    v = md.as_of("2010-06-15")
    # The view's arrays are standalone copies (no base buffer reaching later bars)
    for arr in (v.dates, v.close, v.open, v.high, v.low):
        assert arr.base is None or arr.base.size == arr.size
    assert not hasattr(v, "__dict__")  # __slots__: no attaching extra state


def test_view_cannot_be_built_with_future_bars():
    d = np.array(["2010-01-04", "2010-01-05"], dtype="datetime64[D]")
    with raises(LookAheadError):
        from data_handler import PointInTimeView
        PointInTimeView("2010-01-04", d, d.astype(float), d.astype(float), d.astype(float), d.astype(float))


if __name__ == "__main__":
    failed = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            if "tmp_path" in inspect.signature(fn).parameters:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print("PASS", name)
        except Exception as e:  # noqa
            failed += 1
            print("FAIL", name, repr(e))
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
