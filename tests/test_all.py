import copy, datetime as dt, json, os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import alerts, brief, indicators as ind, market_calendar as mc, quotes as qt, watchlist as wlm

FX = os.path.join(ROOT, "tests", "fixtures", "quotes.json")
WL = os.path.join(ROOT, "tests", "fixtures", "watchlist.json")
ET = mc.ET
def T(s): return dt.datetime.fromisoformat(s).replace(tzinfo=ET)
def quotes(): return {s: qt.get_quote(s, fixture=FX) for s in ("AAPL", "TSLA", "NVDA")}


class Calendar(unittest.TestCase):
    def test_holidays_2026(self):
        h = mc.nyse_holidays(2026)
        for d in ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
                  "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"]:
            self.assertIn(dt.date.fromisoformat(d), h, d)
    def test_saturday_new_year_not_observed(self):
        self.assertNotIn(dt.date(2021, 12, 31), mc.nyse_holidays(2022))
    def test_good_friday_2027(self):
        self.assertIn(dt.date(2027, 3, 26), mc.nyse_holidays(2027))
    def test_sessions(self):
        self.assertEqual(mc.session(T("2026-10-15T08:00")), "pre")
        self.assertEqual(mc.session(T("2026-10-15T09:30")), "regular")
        self.assertEqual(mc.session(T("2026-10-15T16:30")), "after")
        self.assertEqual(mc.session(T("2026-10-15T21:00")), "closed")
        self.assertEqual(mc.session(T("2026-10-17T12:00")), "closed")  # Saturday
        self.assertEqual(mc.session(T("2026-11-26T12:00")), "closed")  # Thanksgiving
    def test_early_close(self):
        self.assertEqual(mc.session(T("2026-11-27T13:30")), "after")
        self.assertEqual(mc.session(T("2026-11-27T12:30")), "regular")
    def test_utc_input(self):
        self.assertEqual(mc.session(dt.datetime(2026, 10, 15, 14, 0, tzinfo=dt.timezone.utc)), "regular")
    def test_next_trading_day(self):
        self.assertEqual(mc.next_trading_day(dt.date(2026, 11, 25)), dt.date(2026, 11, 27))


class Indicators(unittest.TestCase):
    def test_sma(self): self.assertEqual(ind.sma([1, 2, 3, 4], 2), 3.5); self.assertIsNone(ind.sma([1], 2))
    def test_rsi_extremes(self):
        self.assertEqual(ind.rsi(list(range(1, 30))), 100.0)
        self.assertLess(ind.rsi(list(range(30, 1, -1))), 1)
    def test_golden_cross_fixture(self):
        self.assertEqual(ind.ma_cross(quotes()["NVDA"]["closes"]), "golden")


class Watchlist(unittest.TestCase):
    def setUp(self):
        self.p = os.path.join(tempfile.mkdtemp(), "wl.json")
    def test_crud_roundtrip(self):
        wl = wlm.load(self.p)
        wlm.add(wl, "nvda", thesis="AI", entry=120, targets=[150], stop=105, tags=["ai"],
                alerts=[wlm.parse_alert("price_below:110")])
        wlm.save(wl, self.p)
        wl = wlm.load(self.p); self.assertEqual(wl["tickers"][0]["symbol"], "NVDA")
        wlm.update(wl, "NVDA", tags=["semis"], append=True); self.assertEqual(wl["tickers"][0]["tags"], ["ai", "semis"])
        with self.assertRaises(ValueError): wlm.add(wl, "NVDA")
        wlm.remove(wl, "NVDA"); self.assertEqual(wl["tickers"], [])
    def test_validation(self):
        wl = {"tickers": [{"symbol": "bad$", "alerts": [{"type": "nope"}]},
                          {"symbol": "X", "entry": 10, "stop": 12}]}
        errs = wlm.validate(wl)
        self.assertTrue(any("bad symbol" in e for e in errs))
        self.assertTrue(any("unknown alert" in e for e in errs))
        self.assertTrue(any("stop" in e for e in errs))
        self.assertEqual(wlm.validate(wlm.load(WL)), [])
    def test_class_shares_symbol(self):
        self.assertTrue(wlm.SYMBOL_RE.match("BRK.B")); self.assertTrue(wlm.SYMBOL_RE.match("BF-B"))
    def test_cli(self):
        self.assertIsNone(wlm.main(["--file", self.p, "add", "AMD", "--entry", "150", "--stop", "130", "--tag", "semis"]))
        self.assertEqual(wlm.main(["--file", self.p, "validate"]), 0)


class Alerts(unittest.TestCase):
    def setUp(self):
        self.wl = wlm.load(WL); self.q = quotes()
    def types(self, res, sym): return {a["type"] for a in res["alerts"] if a["symbol"] == sym}
    def test_expected_fires(self):
        res = alerts.run(self.wl, {"fired": {}}, self.q, T("2026-10-15T10:00"))
        self.assertFalse(res["skipped"])
        self.assertTrue({"price_above", "near_52w_high", "earnings_within"} <= self.types(res, "AAPL"))
        self.assertTrue({"pct_change_down", "gap_down", "volume_spike", "earnings_within"} <= self.types(res, "TSLA"))
        self.assertIn("golden_cross", self.types(res, "NVDA"))
        self.assertNotIn("price_below", self.types(res, "NVDA"))
    def test_skips_outside_session(self):
        res = alerts.run(self.wl, {"fired": {}}, self.q, T("2026-10-17T10:00"))
        self.assertTrue(res["skipped"]); self.assertEqual(res["alerts"], [])
        self.assertFalse(alerts.run(self.wl, {"fired": {}}, self.q, T("2026-10-17T10:00"), force_session=True)["skipped"])
    def test_dedupe_and_cooldown(self):
        st = {"fired": {}}
        first = alerts.run(self.wl, st, self.q, T("2026-10-15T10:00"))["alerts"]
        self.assertTrue(first)
        self.assertEqual(alerts.run(self.wl, st, self.q, T("2026-10-15T10:30"))["alerts"], [])
        # daily-type alerts don't refire same trading day even after cooldown
        self.assertEqual(alerts.run(self.wl, st, self.q, T("2026-10-15T15:00"))["alerts"], [])
        nxt = alerts.run(self.wl, st, self.q, T("2026-10-16T10:00"))["alerts"]
        self.assertTrue({a["type"] for a in nxt} <= alerts.DAILY and nxt)  # daily events may refire next day; latched levels don't
    def test_level_rearm_hysteresis(self):
        wl = {"settings": {"cooldown_minutes": 1}, "tickers": [{"symbol": "AAPL", "alerts": [{"type": "price_above", "value": 240}]}]}
        st = {"fired": {}}; q = copy.deepcopy(self.q)
        self.assertEqual(len(alerts.run(wl, st, q, T("2026-10-15T10:00"))["alerts"]), 1)
        q["AAPL"]["price"] = 239.9  # dips under but within rearm band
        alerts.run(wl, st, q, T("2026-10-15T10:05")); q["AAPL"]["price"] = 241
        self.assertEqual(alerts.run(wl, st, q, T("2026-10-15T10:10"))["alerts"], [])
        q["AAPL"]["price"] = 236  # clearly back below -> rearm
        alerts.run(wl, st, q, T("2026-10-15T10:15")); q["AAPL"]["price"] = 241
        self.assertEqual(len(alerts.run(wl, st, q, T("2026-10-15T10:20"))["alerts"]), 1)
    def test_stop_and_target_implicit(self):
        wl = {"tickers": [{"symbol": "AAPL", "entry": 260, "stop": 245, "targets": [300]},
                          {"symbol": "NVDA", "entry": 150, "stop": 100, "targets": [160]}]}
        res = alerts.run(wl, {"fired": {}}, self.q, T("2026-10-15T10:00"))
        self.assertIn("stop_hit", self.types(res, "AAPL"))
        self.assertIn("target_hit", self.types(res, "NVDA"))
    def test_missing_quote_reported(self):
        wl = {"tickers": [{"symbol": "ZZZZ", "alerts": [{"type": "price_above", "value": 1}]}]}
        res = alerts.run(wl, {"fired": {}}, {"ZZZZ": {"error": "not found"}}, T("2026-10-15T10:00"))
        self.assertEqual(res["errors"][0]["symbol"], "ZZZZ")
    def test_cli_state_file(self):
        d = tempfile.mkdtemp(); st = os.path.join(d, "s.json")
        alerts.main(["--watchlist", WL, "--state", st, "--fixture", FX, "--now", "2026-10-15T10:00:00-04:00"])
        self.assertTrue(json.load(open(st))["fired"])


class Brief(unittest.TestCase):
    def test_render(self):
        out = brief.render(wlm.load(WL), quotes(), "morning", T("2026-10-15T08:30"))
        self.assertIn("| AAPL |", out); self.assertIn("Biggest movers", out); self.assertIn("not financial advice", out)
    def test_closed_day_note(self):
        self.assertIn("Market closed", brief.render(wlm.load(WL), quotes(), "morning", T("2026-11-26T08:30")))


if __name__ == "__main__":
    unittest.main()
