# Autocall Replication

Naive replication framework for a discrete autocall product using a linear basket of vanilla instruments.

The project compares several ways to approximate the autocall:
- the **price surface** over a grid of `(date, spot)`
- the **expected undiscounted payoff surface**
- the **pathwise discounted payoff** on simulated trajectories

## Project goals

- model a discrete autocall with coupons, autocall trigger, and down barrier
- build a vanilla replication universe (calls, puts, binaries, cash)
- fit a linear portfolio of vanillas to the autocall target
- benchmark replication quality with out-of-sample metrics
- compare price-based, payoff-based, and pathwise replication setups

## Main ideas

- Monte Carlo simulation under Black–Scholes for the underlying
- closed-form Black–Scholes pricing for the vanilla instruments
- least-squares / regularized linear regression for portfolio fitting
- error metrics: MAE, RMSE, max error, signed bias
- visual comparison of target vs replica surfaces and pathwise errors

## Repository structure

- `products_core.py` — autocall and vanilla product definitions
- `monte_carlo.py` — GBM simulation and autocall pricing by Monte Carlo
- `benchmark_general.py` — generic utilities, regression, metrics, plotting
- `benchmark_price.py` — price-surface benchmark
- `benchmark_mean_payoff.py` — expected-payoff benchmark
- `benchmark_payoff.py` — pathwise discounted-payoff benchmark

## Key takeaways

- a linear vanilla basket can approximate the autocall target reasonably well
- pathwise replication is the most faithful benchmark
- regularization helps stabilize the fitted weights
- the quality of replication depends strongly on the chosen basis and grid design
