# Backtester: Event-Driven, Beginner-Friendly Engine

This repository refactors the original single-file MVP into a modular, production-style package while preserving beginner clarity.
It now includes both a command-line research package and a lightweight Vercel-ready browser dashboard.

Core ideas are unchanged:
- Single symbol
- Long-only (flat or long)
- No lookahead bias
- Signal generated from completed bar `t`
- Trade filled at next bar open `t+1`

## Architecture

```text
CSV/Synthetic Data
       |
       v
+--------------------+
|  Backtest Engine    |
|  (event queue)      |
+--------------------+
       |
       +--> MarketEvent ----> Strategy ----> SignalEvent
       |                                        |
       |                                        v
       |                                  Portfolio
       |                                  (signal -> order)
       |                                        |
       |                                        v
       +<---- FillEvent <---- Broker <---- OrderEvent
                         (next-open fills + costs)

Portfolio marks equity at each bar close.
Analytics computes metrics from equity curve.
```

## Repo Layout

```text
backtester/
  config.py
  data/
    loaders.py
    bars.py
  events/
    base.py
    event_types.py
  strategies/
    base.py
    sma_crossover.py
    mean_reversion.py
  execution/
    broker.py
    costs.py
  portfolio/
    portfolio.py
    position_sizing.py
    risk.py
  analytics/
    metrics.py
    report.py
  engine/
    backtest_engine.py
    grid_search.py
    walkforward.py
  cli/
    main.py
api/
  backtest.py
tests/
  test_benchmark_alignment.py
  test_metrics.py
  test_engine_smoke.py
  test_grid_search_outputs_csv.py
  test_walkforward_split_order.py
```

## Web App

The browser dashboard is in `public/index.html` and calls the Vercel Python Function in `api/backtest.py`.

It supports:
- Synthetic demo data
- CSV upload with `timestamp, open, high, low, close, volume`
- SMA crossover and mean reversion
- Commission/slippage controls
- Equity chart
- Metrics and trade log
- JSON result download

### Deploy on Vercel

1. Push this repo to GitHub.
2. Import the repo in Vercel.
3. Use the default project settings. The included `vercel.json` sets `public` as the static output directory.
4. Vercel will serve `public/index.html` and route `/api/backtest` to the Python function.

The included `requirements.txt` keeps the deployed Python runtime small:

```text
numpy
pandas
```

### Local Web Preview

For the full API-backed web app, install the Vercel CLI and run:

```bash
npm install -g vercel
vercel dev
```

Then open the local URL Vercel prints in your terminal.

## Installation

```bash
python -m pip install -e .[dev]
```

If your shell needs quotes:

```bash
python -m pip install -e ".[dev]"
```

Plotting is optional:

```bash
python -m pip install -e ".[plot]"
```

## Run the CLI

### SMA crossover with CSV

```bash
python -m backtester.cli.main --csv data.csv --strategy sma --short 10 --long 50 --cash 100000 --commission_bps 1 --slippage_bps 2 --no_plot
```

### Mean reversion with synthetic data

```bash
python -m backtester.cli.main --strategy mean_reversion --lookback 20 --entry_z 1.0 --exit_z 0.25 --cash 100000 --commission_bps 1 --slippage_bps 2 --no_plot
```

### Position sizing options

- All-in/all-out (default): `--sizer all_in`
- Fixed fraction of equity: `--sizer fixed_fraction --fraction 0.10`

### Benchmark comparison

Benchmark CSV files need `timestamp` and `close` columns. The benchmark is aligned to strategy timestamps with an inner join.

```bash
python -m backtester.cli.main --benchmark_csv benchmark.csv --strategy sma --short 10 --long 50 --no_plot
```

Benchmark output includes:
- Benchmark equity curve starting from the same initial cash
- Benchmark metrics
- Alpha, beta, and correlation versus benchmark returns

### Walk-forward evaluation

```bash
python -m backtester.cli.main --strategy sma --short 10 --long 50 --walkforward --split_ratio 0.7 --no_plot
```

The split is strictly chronological:
- First 70%: in-sample
- Last 30%: out-of-sample

### SMA grid search

```bash
python -m backtester.cli.main --strategy sma --grid_search --short_grid 5,10,20 --long_grid 30,50,100 --split_ratio 0.7 --no_plot
```

Grid search ranks parameters by:
- Best out-of-sample Sharpe
- Tie-breaker: less severe max drawdown

## No Lookahead Bias (How It Is Enforced)

1. Each bar arrival creates a `MarketEvent` for completed bar `t`.
2. Strategy reads history up to `t` close only and emits `SignalEvent`.
3. Portfolio turns signal into an `OrderEvent`.
4. Broker stores that order and executes it only when bar `t+1` arrives, at `open[t+1]` with costs.

## Trading Costs

Costs are in basis points (bps):
- `1 bps = 0.01%`

Effective fill prices:
- Buy: `open * (1 + commission + slippage)`
- Sell: `open * (1 - commission - slippage)`

## Outputs

Each run produces:
- `results.json` (metrics + run parameters)
- `results.txt` (human-readable summary)
- `equity_curve.csv` (equity and return history)
- `trades.csv` (trade log)
- `grid_results.csv` (when grid search is enabled)
- Optional equity plot (if matplotlib available and `--no_plot` not used)

Metrics include:
- Total return
- CAGR
- Volatility
- Sharpe
- Max drawdown
- Sortino
- Calmar
- Alpha, beta, and correlation when a benchmark is provided

## Testing

Run tests:

```bash
pytest
```

Current tests:
- `test_metrics.py`: deterministic checks for drawdown, volatility, Sharpe
- `test_engine_smoke.py`: full synthetic run smoke test
- `test_benchmark_alignment.py`: benchmark timestamp alignment and alpha/beta checks
- `test_walkforward_split_order.py`: chronological split validation
- `test_grid_search_outputs_csv.py`: grid-search CSV and best-parameter checks

## Migration Notes

### What changed from MVP

- Moved from one script to a package with clear modules.
- Added an explicit event model (`MarketEvent`, `SignalEvent`, `OrderEvent`, `FillEvent`).
- Added pluggable strategy interface and second strategy (mean reversion).
- Added broker and cost model abstractions.
- Added position sizing abstractions (`AllInSizer`, `FixedFractionSizer`).
- Added analytics/report module and text report output.
- Added automated tests and packaging metadata.
- Added benchmark comparison, walk-forward evaluation, and SMA grid search.

### How to run the new CLI

```bash
python -m backtester.cli.main --strategy sma --short 10 --long 50 --cash 100000 --commission_bps 1 --slippage_bps 2 --no_plot
```

Add `--csv path.csv` to use real data. Without it, deterministic synthetic data is used.

### How to add a new strategy

1. Create a new class in `backtester/strategies/` that subclasses `StrategyBase`.
2. Implement `on_bar(market_event, history, current_position)` and return `SignalEvent` (target 0/1).
3. Register it in `backtester/cli/main.py` inside `build_strategy` and CLI arguments.
4. Add at least one smoke/unit test in `tests/`.
