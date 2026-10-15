"""Render a markdown watchlist brief (morning or close).

python scripts/brief.py --watchlist watchlist.json --kind morning|close [--fixture f.json]
"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import indicators as ind, market_calendar as mc, quotes as qt, watchlist as wlm


def row(t, q):
    p, pc = q["price"], q.get("prev_close")
    chg = (p - pc) / pc * 100 if pc else 0
    closes = (q.get("closes") or [])[:-1] + [p]
    r = ind.rsi(closes); s50 = ind.sma(closes, 50); s200 = ind.sma(closes, 200)
    trend = "n/a" if not (s50 and s200) else ("up (50>200)" if s50 > s200 else "down (50<200)")
    stop = t.get("stop"); dist = f"{(p - stop) / p * 100:+.1f}%" if stop else "-"
    tg = (t.get("targets") or [None])[0]; to_t = f"{(tg - p) / p * 100:+.1f}%" if tg else "-"
    return f"| {t['symbol']} | ${p:,.2f} | {chg:+.2f}% | {'-' if r is None else f'{r:.0f}'} | {trend} | {dist} | {to_t} |", chg


def render(wl, quotes, kind, now):
    et = now.astimezone(mc.ET)
    lines = [f"# Watchlist {kind} brief - {et:%a %b %d, %Y %I:%M %p} ET", ""]
    if not mc.is_trading_day(et.date()):
        lines += [f"_Market closed today. Next session: {mc.next_trading_day(et.date()):%a %b %d}._", ""]
    lines += ["| Ticker | Price | Chg | RSI14 | Trend | To stop | To target 1 |", "|---|---|---|---|---|---|---|"]
    movers, errs = [], []
    for t in wl["tickers"]:
        q = quotes.get(t["symbol"])
        if not q or "error" in q: errs.append(t["symbol"]); continue
        line, chg = row(t, q); lines.append(line); movers.append((abs(chg), t["symbol"], chg))
    movers.sort(reverse=True)
    if movers:
        lines += ["", "**Biggest movers:** " + ", ".join(f"{s} {c:+.1f}%" for _, s, c in movers[:3])]
    earn = [f"{s} ({str(q['earnings_date'])[:10]})" for s, q in quotes.items() if q.get("earnings_date")]
    if earn: lines.append("**Earnings dates:** " + ", ".join(earn))
    if errs: lines.append("**Data unavailable:** " + ", ".join(errs))
    lines += ["", "_Informational only - not financial advice._"]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--watchlist", default=wlm.DEFAULT_PATH)
    ap.add_argument("--kind", default="morning", choices=["morning", "close"]); ap.add_argument("--fixture")
    ap.add_argument("--provider", default="auto"); ap.add_argument("--now")
    a = ap.parse_args(argv)
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(mc.ET)
    wl = wlm.load(a.watchlist); quotes = {}
    for t in wl["tickers"]:
        try: quotes[t["symbol"]] = qt.get_quote(t["symbol"], a.provider, a.fixture)
        except Exception as e: quotes[t["symbol"]] = {"error": str(e)}
    print(render(wl, quotes, a.kind, now))


if __name__ == "__main__":
    sys.exit(main())
