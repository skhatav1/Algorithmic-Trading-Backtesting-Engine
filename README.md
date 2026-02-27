# Beginner-Friendly Backtesting MVP (Single Symbol)

This project is a minimal, educational backtester for **one symbol** using OHLCV data.

It is intentionally simple:
- Strategy: **SMA Crossover**
- Execution model: **signal at close of day _t_, trade at open of day _t+1_**
- Portfolio: tracks **cash**, **shares**, and **equity**
- Costs: **commission** and **slippage** in basis points (bps)
- Metrics: total return, CAGR, volatility, Sharpe (risk-free = 0), max drawdown

## Files

- `backtest_mvp.py`: all logic (data loading, indicators, signals, backtest loop, metrics, plotting)
- `results.json`: created after each run (metrics + parameters)

## Input Data Format

CSV columns must be:
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

`timestamp` should be parseable by pandas datetime.

## Important Concepts (Simple Explanations)

### 1) Lookahead Bias
Lookahead bias means accidentally using future information when making past decisions.

In this project:
- At day `t` close, we compute the signal using known data up to `close[t]`.
- The earliest we can trade is **next bar**, so execution is at `open[t+1]`.

This is much more realistic than buying at the same close that created the signal.

### 2) Commission
Commission is broker fee per trade.

Here it is given in **basis points (bps)**:
- `1 bps = 0.01%`
- Example: `commission_bps = 1` means `0.01%` per buy or sell.

### 3) Slippage
Slippage models worse execution than the visible market price.

In this MVP:
- Buy uses: `open * (1 + slippage + commission)`
- Sell uses: `open * (1 - slippage - commission)`

Both are applied per trade side.

## Installation

Use Python 3.9+ and install dependencies:

```bash
pip install pandas numpy matplotlib
```

(Plotting is optional. If matplotlib is unavailable, the script will still run and skip plotting.)

## Run Examples

### With your own CSV

```bash
python backtest_mvp.py --csv data.csv --short 10 --long 50 --cash 100000 --commission_bps 1 --slippage_bps 2
```

### Without CSV (uses built-in synthetic data)

```bash
python backtest_mvp.py --short 10 --long 50 --cash 100000 --commission_bps 1 --slippage_bps 2
```

### Disable plotting

```bash
python backtest_mvp.py --no_plot
```

## Terminal Output

The script prints:
- total return
- CAGR
- volatility
- Sharpe ratio
- max drawdown
- number of trades

It also saves these results to `results.json`.

## Notes on Simplicity

This is an MVP for learning. It uses:
- long-only logic (flat or long)
- all-in / all-out position sizing
- no fractional shares
- one symbol only

These choices keep the code easy to read while still preserving correct backtesting mechanics.
