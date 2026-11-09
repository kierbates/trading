# Trading Intelligence — cloud paper trading V1

Three independent **£10,000 GBP virtual portfolios**: Conservative, Active and Aggressive. **No real orders or brokerage credentials**. This is an experimental daily-bar strategy comparison, not proven profitable trading software.

## Quick start

1. Install Python 3.11+, then `pip install -r requirements.txt`.
2. Run `python engine.py` to process the most recent common market bar. This **does not backfill simulated historical trades**; it starts recording forward from the first run.
3. Run `streamlit run dashboard.py` to view the dashboard locally.
4. To run in the cloud: create a **private** GitHub repository containing these files; enable GitHub Actions and workflow write permissions (Settings → Actions → General → Workflow permissions). Run the workflow manually once. It is scheduled at 23:30 UTC weekdays, after US markets typically close. Scheduled runs can be delayed or skipped by GitHub.
5. Deploy `dashboard.py` to Streamlit Community Cloud using the repository, **if you are comfortable with the data visibility and repository access requirements of your Streamlit plan**. Alternatively host Streamlit on a private VPS with authentication. Do not publish personal or broker credentials.

## What it does

* Uses Yahoo Finance via `yfinance` to retrieve adjusted daily OHLC data for SPY, QQQ, IWM, GLD, TLT and XLE, plus GBP/USD FX.
* Each strategy uses a different moving-average and breakout window, position sizing, stop and take-profit thresholds.
* Generates signals at the end of a market day; **queues orders for the next available day's opening price**. A run on a day with no new bar does nothing.
* Tracks virtual cash, positions, trades, approximate execution costs, and GBP equity for each strategy independently.
* Saves `data/state.json` to the repository for persistence. No database is required.

## Critical limitations

* **This is a prototype, not a production trading system.** It has not been validated with a historical backtest or a multi-month forward test.
* Price feed may be stale, delayed, incomplete or adjusted. **Adjusted OHLC data can distort historic entry/exit prices**. Verify data source and corporate-action handling before using results for decisions.
* Yahoo Finance data access and licensing may not be suitable for a production commercial service.
* The system uses **daily closing-price stop signals**, not intraday protective orders; losses can exceed the configured per-trade risk because of price gaps.
* The daily circuit breaker is checked **after** the day's move and only queues liquidation for the next open; it cannot guarantee a maximum loss.
* No shorting, borrowing, margin or leverage. Shares are integer quantities. GBP/USD conversion uses daily FX observations, not executable broker quotes. There is no dividend accounting, interest or UK tax handling.
* The schedule may fire before all upstream prices are published. Check `last_bar` in the dashboard. Missed days are **not replayed**; the system processes only the most recent complete common bar.
* Fees and slippage are hypothetical. Results may differ significantly from real trading. The first run creates an account with £10,000 cash and may queue trades for the next run.
* If you change strategy configuration, the saved state is not automatically reset or migrated. Back up and reset `data/state.json` intentionally for a fresh experiment.

## Next iteration

Add independent historical backtests with walk-forward/out-of-sample testing; source validation and market calendar; robust scheduler and error notifications; true broker paper API execution; private authentication and alerting. Keep live-money trading disabled until those are implemented and tested.
