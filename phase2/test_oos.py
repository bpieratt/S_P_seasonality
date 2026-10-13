"""Phase-2 isolation / point-in-time tests. Run: python test_oos.py"""
import inspect
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oos_data import (FROZEN_PATH, DataIsolationError, FutureDataError, LookAheadError,  # noqa: E402
                      load_criteria, load_oos, sha256, verify_frozen)


class raises:
    def __init__(self, exc):
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        if t is None:
            raise AssertionError(f"expected {self.exc.__name__}")
        return issubclass(t, self.exc)


def _write(tmp, dates):
    p = np.linspace(4000, 4100, len(dates))
    f = tmp / "x.csv"
    pd.DataFrame(dict(Date=dates, Open=p, High=p + 5, Low=p - 5, Close=p)).to_csv(f, index=False)
    return f


def test_frozen_rules_unchanged():
    assert verify_frozen(load_criteria()) == "6d8fbfbf56ee66cafd2d8938d93f4ec374d08d8dad67a1c5760b0413b749beac"


def test_frozen_file_is_read_only():
    assert not os.access(FROZEN_PATH, os.W_OK) or os.geteuid() == 0  # root ignores mode bits
    assert oct(os.stat(FROZEN_PATH).st_mode)[-3:] == "444"


def test_criteria_match_preregistration_lock():
    load_criteria()


def test_real_oos_file_bounds():
    md, df = load_oos()
    assert df.Date.min() >= pd.Timestamp("2023-01-01")
    assert df.Date.max() <= pd.Timestamp("2026-10-02")


def test_pre_2023_row_rejected(tmp_path):
    f = _write(tmp_path, ["2022-12-30", "2023-01-03"])
    with raises(DataIsolationError):
        load_oos(f, expected_sha=None)


def test_post_hard_stop_row_rejected(tmp_path):
    f = _write(tmp_path, ["2026-10-01", "2026-10-02", "2026-10-05"])
    with raises(FutureDataError):
        load_oos(f, expected_sha=None)


def test_as_of_beyond_hard_stop_raises():
    md, _ = load_oos()
    with raises(FutureDataError):
        md.as_of("2026-10-05")


def test_views_never_contain_future_bars():
    md, _ = load_oos()
    cal = md.trading_calendar
    for t in cal[::23]:
        v = md.as_of(t)
        assert v.dates[-1] == t and (v.dates <= t).all()


def test_future_bar_request_raises():
    md, _ = load_oos()
    v = md.as_of("2024-07-01")
    with raises(LookAheadError):
        v.bar("2024-07-02")


def test_incomplete_occurrences_are_excluded():
    import validate  # noqa
    occ = validate.window_occurrences(validate.RULES["Sep16+30td"])
    o26 = [o for o in occ if o["year"] == 2026][0]
    assert o26["status"] != "complete" and o26["ret"] is None
    m = validate.month_occurrences(validate.RULES["MONTH-Oct"])
    assert all(o["status"] != "complete" for o in m if o["year"] == 2026)


def test_trade_evaluation_view_ends_at_exit():
    import validate  # noqa
    for o in validate.window_occurrences(validate.RULES["Jul01+15td"]):
        if o["status"] == "complete":
            assert o["view_last_date"] == o["exit_date"]


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
