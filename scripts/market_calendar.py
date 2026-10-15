"""NYSE trading calendar and session helpers (US/Eastern). Stdlib only."""
from __future__ import annotations
import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _nth_weekday(year, month, weekday, n):
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year):
    a = year % 19; b = year // 100; c = year % 100
    d = b // 4; e = b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30; i = c // 4; k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31; day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def _observed(d):
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def nyse_holidays(year):
    """Full-day NYSE closures for a year (rule-based; excludes ad-hoc closures)."""
    h = {
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        _easter(year) - dt.timedelta(days=2): "Good Friday",
        _last_weekday(year, 5, 0): "Memorial Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
    }
    ny = dt.date(year, 1, 1)
    if ny.weekday() != 5:  # NYSE does not observe Sat New Year's on the prior Friday
        h[_observed(ny)] = "New Year's Day"
    if year >= 2022:
        h[_observed(dt.date(year, 6, 19))] = "Juneteenth"
    h[_observed(dt.date(year, 7, 4))] = "Independence Day"
    h[_observed(dt.date(year, 12, 25))] = "Christmas Day"
    return h


def early_closes(year):
    """Days the market closes at 1:00 PM ET."""
    out = set()
    tg = _nth_weekday(year, 11, 3, 4)
    out.add(tg + dt.timedelta(days=1))
    ce = dt.date(year, 12, 24)
    if ce.weekday() < 5:
        out.add(ce)
    j3 = dt.date(year, 7, 3)
    if j3.weekday() < 4:
        out.add(j3)
    hol = nyse_holidays(year)
    return {d for d in out if d.weekday() < 5 and d not in hol}


def is_trading_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def session(now: dt.datetime | None = None) -> str:
    """Return one of: closed, pre, regular, after."""
    now = (now or dt.datetime.now(ET)).astimezone(ET)
    if not is_trading_day(now.date()):
        return "closed"
    t = now.time()
    close = dt.time(13, 0) if now.date() in early_closes(now.year) else dt.time(16, 0)
    after_end = dt.time(17, 0) if close == dt.time(13, 0) else dt.time(20, 0)
    if dt.time(4, 0) <= t < dt.time(9, 30):
        return "pre"
    if dt.time(9, 30) <= t < close:
        return "regular"
    if close <= t < after_end:
        return "after"
    return "closed"


def next_trading_day(d: dt.date) -> dt.date:
    d += dt.timedelta(days=1)
    while not is_trading_day(d):
        d += dt.timedelta(days=1)
    return d


if __name__ == "__main__":
    n = dt.datetime.now(ET)
    print(f"{n:%Y-%m-%d %H:%M %Z} session={session(n)} trading_day={is_trading_day(n.date())}")
