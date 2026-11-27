"""
Fetch fresh ^GSPC daily OHLC data for the dashboard's UNLOCKED "recent" extension.

This is deliberately separate from everything under phase2/: it never writes to
phase2/data/, never touches oos_validation_criteria.yaml, preregistration.lock or
seasonal_patterns_2003_2022.json, and has no sha256 check against anything. Its only
output is phase2/data/extended/GSPC_2023_present.csv, which dashboard/build_data.py
reads ONLY to add descriptive, clearly-labeled months AFTER the locked hard_stop
(2026-10-02) to the heat map. It can be deleted at any time with zero effect on the
locked research or its validation.

Source: Yahoo Finance chart API v8, interval=1d — the same source and instrument
(^GSPC, unadjusted) documented in phase2/oos_validation_criteria.yaml, so the new
months are directly comparable to the locked ones.

Usage:
    python scripts/fetch_recent_prices.py

Run this before dashboard/build_dashboard.py. Safe to run as often as you like
(e.g. monthly from a scheduled job); each run simply refetches the full
2023-01-01..today series and overwrites the extended file.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "phase2", "data", "extended")
OUT_PATH = os.path.join(OUT_DIR, "GSPC_2023_present.csv")

SYMBOL = "%5EGSPC"  # ^GSPC, URL-encoded
START = dt.date(2023, 1, 1)
UA = "Mozilla/5.0 (compatible; S_P_seasonality-dashboard-refresh/1.0)"


def fetch_chart(period1, period2):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}"
           f"?period1={period1}&period2={period2}&interval=1d&events=history")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    period1 = int(dt.datetime(START.year, START.month, START.day, tzinfo=dt.timezone.utc).timestamp())
    period2 = int(dt.datetime.now(dt.timezone.utc).timestamp())

    payload = fetch_chart(period1, period2)
    result = payload.get("chart", {}).get("result")
    if not result:
        err = payload.get("chart", {}).get("error")
        print(f"Yahoo chart API returned no result: {err}", file=sys.stderr)
        sys.exit(1)

    r = result[0]
    timestamps = r.get("timestamp") or []
    quote = r["indicators"]["quote"][0]
    opens, highs, lows, closes = quote["open"], quote["high"], quote["low"], quote["close"]

    rows = []
    for ts, o, h, l, c in zip(timestamps, opens, highs, lows, closes):
        if None in (o, h, l, c):
            continue  # Yahoo sometimes returns a null bar for a half/no-trade day; skip it
        d = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).date()
        if d < START:
            continue
        rows.append((d, o, h, l, c))

    if not rows:
        print("No usable rows returned - refusing to write an empty/near-empty file.", file=sys.stderr)
        sys.exit(1)

    rows.sort(key=lambda row: row[0])
    # De-duplicate same-day bars, keep the last (Yahoo occasionally repeats the final bar).
    dedup = {row[0]: row for row in rows}
    rows = [dedup[d] for d in sorted(dedup)]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("Date,Open,High,Low,Close\n")
        for d, o, h, l, c in rows:
            f.write(f"{d.isoformat()},{o:.6f},{h:.6f},{l:.6f},{c:.6f}\n")

    print(f"wrote {OUT_PATH}: {len(rows)} rows, {rows[0][0]} .. {rows[-1][0]}")


if __name__ == "__main__":
    main()
