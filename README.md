# us-watchlist-alerts

Open-source **Agent Skills** for **US stock watchlists and price alerts**: track tickers with a thesis, entry, targets and stop; get de-duplicated alerts on price levels, % moves, gaps, 52-week highs/lows, MA crosses, RSI, volume spikes and earnings; and get morning/close briefs. Aware of NYSE hours, pre/after-market, early closes and holidays, in US/Eastern time.

Works in **Claude Code, Codex CLI, Cursor, Gemini CLI** and any agent that reads the open `SKILL.md` format. **No API keys or MCP required.** It uses free Yahoo Finance data and the Python standard library. Alpaca, Finnhub, Alpha Vantage, `alpaca-mcp-server` and `tradingview-mcp` are optional extras.

> ⚠️ **Not financial advice.** This is an informational tool. The skills tell the agent to **never place, modify or cancel a trade without your explicit confirmation of that specific order**, and to give no buy/sell recommendations. Free market data may be delayed ~15 minutes. Use at your own risk.

## What's inside
| Skill | What it does |
|---|---|
| [`watchlist-manager`](skills/watchlist-manager/SKILL.md) | Add, remove, update, list and validate tickers with thesis, entry, targets, stop, tags and alert rules (JSON/YAML schema) |
| [`price-alerts`](skills/price-alerts/SKILL.md) | 20 alert types, latching, cooldowns, once-per-day events, session gating, NYSE calendar |
| [`watchlist-brief`](skills/watchlist-brief/SKILL.md) | Morning or close summary: table, movers, distance to stop/target, earnings |
| [`HEARTBEAT.md`](HEARTBEAT.md) | Checklist for a scheduled check that stays silent unless something new happens |

Scripts (`scripts/`, stdlib only): `quotes.py` (multi-provider quote fetcher with fallback), `alerts.py` (rule evaluator + `.alert_state.json` cooldown state), `watchlist.py` (CRUD + validation), `brief.py`, `market_calendar.py`, `indicators.py`.

## Quick start
```bash
git clone https://github.com/eli-alvarado/us-watchlist-alerts && cd us-watchlist-alerts
cp examples/watchlist.json watchlist.json
python scripts/quotes.py AAPL NVDA
python scripts/alerts.py --force-session
python scripts/brief.py --kind morning
python -m unittest discover -s tests      # runs offline with fixtures
```

## Install per agent
The skills reference `scripts/` relative to the repo, so install the **whole repo** (or a symlink to it).

**Claude Code**
```bash
git clone https://github.com/eli-alvarado/us-watchlist-alerts ~/.claude/us-watchlist-alerts
mkdir -p ~/.claude/skills
for s in watchlist-manager price-alerts watchlist-brief; do ln -s ~/.claude/us-watchlist-alerts/skills/$s ~/.claude/skills/$s; done
```
For a single project, use `.claude/skills/` instead. Then ask: "add NVDA to my watchlist with a stop at 140".

**Codex CLI**
```bash
git clone https://github.com/eli-alvarado/us-watchlist-alerts ~/.codex/us-watchlist-alerts
mkdir -p ~/.codex/skills && for s in watchlist-manager price-alerts watchlist-brief; do ln -s ~/.codex/us-watchlist-alerts/skills/$s ~/.codex/skills/$s; done
```
Or reference `skills/*/SKILL.md` from your project's `AGENTS.md`.

**Cursor**
Clone the repo into your project (or `~/.cursor/`) and symlink each skill into `.cursor/skills/` (project) or `~/.cursor/skills/` (global). Older Cursor versions can use a rule in `.cursor/rules/` that points to the SKILL.md files.

**Gemini CLI**
```bash
git clone https://github.com/eli-alvarado/us-watchlist-alerts ~/.gemini/us-watchlist-alerts
mkdir -p ~/.gemini/skills && for s in watchlist-manager price-alerts watchlist-brief; do ln -s ~/.gemini/us-watchlist-alerts/skills/$s ~/.gemini/skills/$s; done
```
Or add `@skills/price-alerts/SKILL.md` to `GEMINI.md`.

**Any other agent** (OpenClaw-style bots, custom platforms): load the SKILL.md files as instructions, give the agent shell access to run `python scripts/...`, and run `HEARTBEAT.md` on your scheduler.

## Scheduling
Run the HEARTBEAT checklist every 15–30 min during market hours, or use plain cron (times in ET):
```cron
CRON_TZ=America/New_York
*/15 9-16 * * 1-5  cd ~/us-watchlist-alerts && python scripts/alerts.py >> alerts.log
45 8 * * 1-5       cd ~/us-watchlist-alerts && python scripts/brief.py --kind morning
10 16 * * 1-5      cd ~/us-watchlist-alerts && python scripts/brief.py --kind close
```
`alerts.py` skips holidays and closed sessions by itself.

## Configuration
| Env var | Purpose |
|---|---|
| `WATCHLIST_FILE` | Watchlist path (default `./watchlist.json`) |
| `ALERT_STATE_FILE` | Cooldown state (default `./.alert_state.json`) |
| `WATCHLIST_PROVIDER` | `auto` (default), `yfinance`, `yahoo`, `alpaca`, `finnhub`, `alphavantage` |
| `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` | Optional Alpaca market data |
| `FINNHUB_API_KEY` | Optional Finnhub quotes |
| `ALPHAVANTAGE_API_KEY` | Optional Alpha Vantage daily history |

Watchlist `settings`: `cooldown_minutes`, `rearm_pct`, `sessions` (`regular`/`pre`/`after`), `volume_spike_multiple`, `near_52w_pct`, `earnings_days`, `max_alerts_per_run`.

## How the anti-spam works
- **Level alerts** (price, stop, target, RSI) latch after firing and re-arm only after price moves back through the level by `rearm_pct`.
- **Event alerts** (gaps, % moves, volume, crosses, 52-week highs/lows, earnings) fire at most once per trading day.
- A **cooldown** applies to every re-fire, and each run is capped at `max_alerts_per_run`.

## Limitations
- The holiday calendar is rule-based, so it doesn't know about unscheduled closures.
- The free Yahoo endpoint is unofficial and can change or rate-limit. Install `yfinance` or set a key for more reliability.
- US-listed equities and ETFs only.

## Related
[tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) · [himself65/finance-skills](https://github.com/himself65/finance-skills) · [gauss314/skills](https://github.com/gauss314/skills) · [chjm-ai/stock-monitor-skill](https://github.com/chjm-ai/stock-monitor-skill) (China A-shares; inspiration for this US version)

MIT © 2026 Eli Alvarado
