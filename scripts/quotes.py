"""Quote + history fetcher for US equities/ETFs.

Providers (auto order): fixture -> yfinance (if installed) -> Yahoo public chart API
-> Finnhub (FINNHUB_API_KEY) -> Alpha Vantage (ALPHAVANTAGE_API_KEY).
Alpaca (ALPACA_API_KEY_ID/ALPACA_API_SECRET_KEY) supported for latest trade.

Normalized quote dict:
  symbol, price, prev_close, open, day_high, day_low, volume, avg_volume_20d,
  high_52w, low_52w, closes (list, oldest->newest, daily), earnings_date (ISO or None),
  source, as_of (ISO UTC)

CLI: python scripts/quotes.py AAPL MSFT [--fixture tests/fixtures/quotes.json] [--provider yahoo]
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (us-watchlist-alerts)"}


def _get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _finish(q):
    closes = q.get("closes") or []
    vols = q.pop("_volumes", None) or []
    if vols and not q.get("avg_volume_20d"):
        past = vols[-21:-1] if len(vols) > 20 else vols[:-1]
        q["avg_volume_20d"] = sum(past) / len(past) if past else None
    if closes:
        yr = closes[-252:]
        q.setdefault("high_52w", max(yr)); q.setdefault("low_52w", min(yr))
        if q.get("high_52w") is None: q["high_52w"] = max(yr)
        if q.get("low_52w") is None: q["low_52w"] = min(yr)
    q.setdefault("earnings_date", None)
    q.setdefault("as_of", _now())
    return q


def from_fixture(symbol, path):
    data = json.load(open(path))
    q = dict(data[symbol.upper()]); q["symbol"] = symbol.upper(); q.setdefault("source", "fixture")
    return _finish(q)


def from_yahoo(symbol):
    s = urllib.parse.quote(symbol.upper())
    d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=1y&interval=1d&includePrePost=false")
    r = d["chart"]["result"][0]; m = r["meta"]; ind = r["indicators"]["quote"][0]
    closes = [c for c in ind.get("close", []) if c is not None]
    vols = [v for v in ind.get("volume", []) if v is not None]
    opens = [o for o in ind.get("open", []) if o is not None]
    q = {"symbol": symbol.upper(), "price": m.get("regularMarketPrice"),
         "prev_close": closes[-2] if len(closes) > 1 else m.get("chartPreviousClose"),
         "open": opens[-1] if opens else None, "day_high": m.get("regularMarketDayHigh"),
         "day_low": m.get("regularMarketDayLow"), "volume": m.get("regularMarketVolume"),
         "high_52w": m.get("fiftyTwoWeekHigh"), "low_52w": m.get("fiftyTwoWeekLow"),
         "closes": closes, "_volumes": vols, "source": "yahoo-chart"}
    return _finish(q)


def from_yfinance(symbol):
    import yfinance as yf  # optional dependency
    t = yf.Ticker(symbol)
    h = t.history(period="1y", interval="1d")
    closes = [float(x) for x in h["Close"].tolist()]
    vols = [float(x) for x in h["Volume"].tolist()]
    fi = t.fast_info
    ed = None
    try:
        cal = t.calendar
        e = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if e: ed = str(e[0])
    except Exception:
        pass
    q = {"symbol": symbol.upper(), "price": float(fi["last_price"]),
         "prev_close": closes[-2] if len(closes) > 1 else None,
         "open": float(h["Open"].iloc[-1]), "day_high": float(h["High"].iloc[-1]),
         "day_low": float(h["Low"].iloc[-1]), "volume": vols[-1] if vols else None,
         "closes": closes, "_volumes": vols, "earnings_date": ed, "source": "yfinance"}
    return _finish(q)


def from_finnhub(symbol):
    k = os.environ["FINNHUB_API_KEY"]
    d = _get(f"https://finnhub.io/api/v1/quote?symbol={symbol.upper()}&token={k}")
    q = {"symbol": symbol.upper(), "price": d["c"], "prev_close": d["pc"], "open": d["o"],
         "day_high": d["h"], "day_low": d["l"], "closes": [], "source": "finnhub"}
    return _finish(q)


def from_alphavantage(symbol):
    k = os.environ["ALPHAVANTAGE_API_KEY"]
    d = _get(f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&outputsize=full&symbol={symbol.upper()}&apikey={k}")
    ts = d["Time Series (Daily)"]; days = sorted(ts)[-260:]
    closes = [float(ts[x]["4. close"]) for x in days]; vols = [float(ts[x]["5. volume"]) for x in days]
    last = ts[days[-1]]
    q = {"symbol": symbol.upper(), "price": closes[-1], "prev_close": closes[-2], "open": float(last["1. open"]),
         "day_high": float(last["2. high"]), "day_low": float(last["3. low"]), "volume": vols[-1],
         "closes": closes, "_volumes": vols, "source": "alphavantage"}
    return _finish(q)


def from_alpaca(symbol):
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY_ID"], "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET_KEY"]}
    d = _get(f"https://data.alpaca.markets/v2/stocks/{symbol.upper()}/snapshot", headers=h)
    q = {"symbol": symbol.upper(), "price": d["latestTrade"]["p"], "prev_close": d["prevDailyBar"]["c"],
         "open": d["dailyBar"]["o"], "day_high": d["dailyBar"]["h"], "day_low": d["dailyBar"]["l"],
         "volume": d["dailyBar"]["v"], "closes": [], "source": "alpaca"}
    return _finish(q)


PROVIDERS = {"yfinance": from_yfinance, "yahoo": from_yahoo, "finnhub": from_finnhub,
             "alphavantage": from_alphavantage, "alpaca": from_alpaca}


def auto_order():
    order = []
    try:
        import yfinance  # noqa: F401
        order.append("yfinance")
    except ImportError:
        pass
    order.append("yahoo")
    if os.environ.get("ALPACA_API_KEY_ID"): order.append("alpaca")
    if os.environ.get("FINNHUB_API_KEY"): order.append("finnhub")
    if os.environ.get("ALPHAVANTAGE_API_KEY"): order.append("alphavantage")
    return order


def get_quote(symbol, provider="auto", fixture=None):
    if fixture:
        return from_fixture(symbol, fixture)
    errors = []
    for p in ([provider] if provider != "auto" else auto_order()):
        try:
            return PROVIDERS[p](symbol)
        except Exception as e:  # try next provider
            errors.append(f"{p}: {e}")
    raise RuntimeError(f"all providers failed for {symbol}: " + "; ".join(errors))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--provider", default=os.environ.get("WATCHLIST_PROVIDER", "auto"))
    ap.add_argument("--fixture")
    ap.add_argument("--full", action="store_true", help="include closes history")
    a = ap.parse_args(argv)
    out = {}
    for s in a.symbols:
        try:
            q = get_quote(s, a.provider, a.fixture)
            if not a.full: q.pop("closes", None)
            out[s.upper()] = q
        except Exception as e:
            out[s.upper()] = {"error": str(e)}
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
