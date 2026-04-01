# Backtester: Event-Driven, Beginner-Friendly Engine

This repository refactors the original single-file MVP into a modular, production-style package while preserving beginner clarity.

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
  cli/
    main.py
tests/
  test_metrics.py
  test_engine_smoke.py
```

## Installation

```bash
python -m pip install -e .[dev]
```

If your shell needs quotes:

```bash
python -m pip install -e ".[dev]"
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
- Optional equity plot (if matplotlib available and `--no_plot` not used)

Metrics include:
- Total return
- CAGR
- Volatility
- Sharpe
- Max drawdown
- Sortino
- Calmar

## Testing

Run tests:

```bash
pytest
```

Current tests:
- `test_metrics.py`: deterministic checks for drawdown, volatility, Sharpe
- `test_engine_smoke.py`: full synthetic run smoke test

## Migration Notes

### What changed from MVP

- Moved from one script to a package with clear modules.
- Added an explicit event model (`MarketEvent`, `SignalEvent`, `OrderEvent`, `FillEvent`).
- Added pluggable strategy interface and second strategy (mean reversion).
- Added broker and cost model abstractions.
- Added position sizing abstractions (`AllInSizer`, `FixedFractionSizer`).
- Added analytics/report module and text report output.
- Added automated tests and packaging metadata.

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
