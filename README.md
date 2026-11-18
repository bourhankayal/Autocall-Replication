# Autocall Replication

**A reproducible research framework for pricing, replicating and stress-testing an autocall's dated cash flows.** The project studies a single-underlying autocall under Black--Scholes dynamics. Its central question is not merely whether a portfolio matches the product's average payoff, but whether it can meet payments **at the right dates**, with a manageable number of options and acceptable tail risk.

The code and notebooks cover Monte Carlo pricing, conditional option replication, regularized portfolio selection, independent risk evaluation, importance sampling and funding diagnostics. This is a **research study**, not a trade recommendation or an executable market price.

## Start here

| If you want to… | Open |
|---|---|
| Read the research report | [English PDF](overleaf/rapport_autocall_v1_en.pdf) · [French PDF](overleaf/rapport_autocall_v1_fr.pdf) · [LaTeX sources](overleaf/) |
| See the latest completed REPORT analysis | [Numerical results and interpretation](reports/REPORT_RUN_RESULTS_2026-11-11.md) |
| Inspect the main experiment | [Main notebook](notebooks/autocall_research.ipynb) |
| Understand model selection | [Hyperparameter notebook](notebooks/hyperparameter_research.ipynb) · [methodology](reports/HYPERPARAMETER_RESEARCH.md) |
| Find the contract definition | [Functional term sheet](docs/TERM_SHEET.md) |
| Browse reproducible outputs | [Latest export](output/latest/) · [dated run history](output/runs/) |

The bilingual PDFs are **report drafts**: their figures and numbers must be reconciled with the latest validated run before being cited as final results. The November REPORT results above are the more recent numerical reference. The reserved final test set has not been opened.

## Research design

The contract has four quarterly observation dates, conditional coupons, possible early redemption and a path-dependent protection barrier. We simulate its cash flows, then compare several ways to approximate or hedge them:

1. **Static option portfolios:** one basket held across dates, as a deliberately simple benchmark.
2. **Conditional option portfolios:** date- and state-dependent baskets built from calls and puts, optionally augmented with theoretical binary options. We study both payment-by-payment and aggregate-discounted-cash-flow objectives; a good aggregate fit can conceal missed intermediate payments.
3. **Dynamic delta hedging:** daily and five-business-day Black--Scholes rebalancing benchmarks.
4. **Structural payoff construction:** a rule-based benchmark derived from the product's payoff structure.

Portfolio fitting compares **L0, L1, L2 and Elastic Net** regularization. Hyperparameters are researched separately, promoted explicitly and then imported by the main notebook. Candidate policies are checked for out-of-sample error, sparsity, recalibration stability, 97.5% Expected Shortfall (ES), funding needs and sensitivity to importance sampling. A separate experiment also fits portfolios with an explicit ES penalty or constraint.

These methods do **not** all measure the same economic object or assume the same information at decision time. In particular, the payment-by-payment construction is a diagnostic of replication capacity when it uses the barrier state observed on the payment date; it should not be presented as an executable pre-payment hedge. The delta and option-portfolio comparisons are informative benchmarks, not a cost- and capital-matched trading contest.

## What the completed REPORT run shows

On **20,000 independent risk-evaluation paths**, the selected sparse conditional policies achieved the following results. Values are percentages of a notional of 100; the RMSE reduction is relative to the **centered, unhedged liability**, not to the product's price or to an investable hedge.

| Instrument universe | Penalty | Residual RMSE | RMSE reduction | Residual ES 97.5% |
|---|---|---:|---:|---:|
| Calls + Puts | L1 | 2.379 | 69.4% | 9.488 |
| Calls + Puts | Elastic Net | 2.376 | 69.4% | 9.481 |
| Full, including theoretical binaries | L1 | 2.353 | 69.7% | 9.239 |
| Full, including theoretical binaries | Elastic Net | **2.344** | **69.8%** | **9.166** |
| Centered, unhedged liability | — | 7.760 | — | 4.423 |

The finding is a trade-off, **not an overall risk reduction**: average replication error falls substantially, yet residual ES remains a little more than twice the unhedged benchmark's ES. Full Elastic Net is the best of these four on the reported metrics, but its small numerical edge relies on theoretical binary options. Daily delta hedging has lower raw RMSE and ES in this model, although its P&L and the option portfolios' cash-flow deficits are not economically identical comparisons. [Read the full REPORT analysis](reports/REPORT_RUN_RESULTS_2026-11-11.md) for conventions, tail-event decomposition, importance-sampling results and caveats.

## Reproduce the study

Requires **Python 3.11–3.13**. From the repository root:

```bash
python -m venv .venv
```

Activate it with `.\.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux, then run:

```bash
python -m pip install -e ".[dev,notebook]"
python scripts/validate.py
jupyter lab
```

In Jupyter, run `notebooks/hyperparameter_research.ipynb` for a **new** parameter study, review and promote its selections, then run `notebooks/autocall_research.ipynb` from a clean kernel. Existing promoted configurations in `config/` allow the main notebook to run without repeating the entire hyperparameter search. Set `RUN_MODE` near the top of each notebook to `sprint` (visual smoke test), `fast` (working analysis) or `report` (larger simulation). The modes keep the same product and methodology; they change simulation volumes and repetitions, so small-sample results should not be treated as final estimates.

The last cell of the main notebook exports CSV tables, PDF/PNG figures, configuration and a manifest to `output/runs/<date>_<time>_<mode>/`. `output/latest/` is a copy of the most recent **complete** export; previous dated runs remain available. Running only part of the notebook does not create a valid complete export. The notebooks do **not** generate the academic report automatically: the LaTeX documents in `overleaf/` are updated and reviewed manually. See [installation and validation](docs/DEVELOPMENT.md) and [output conventions](output/README.md).

## Repository map

| Path | Purpose |
|---|---|
| [`src/autocall_replication/`](src/autocall_replication/) | Product, simulation, optimization, risk and export code |
| [`notebooks/`](notebooks/) | Main study, external hyperparameter search and isolated exploratory benchmarks |
| [`tests/`](tests/) | Automated checks; also run in [GitHub Actions](.github/workflows/ci.yml) |
| [`output/`](output/) | Dated numerical results and figure exports |
| [`overleaf/`](overleaf/) | English/French LaTeX reports and report figures |
| [`reports/`](reports/) | Detailed methodology, run analyses and research notes |

## Scope and limitations

- Black--Scholes is a controlled modelling environment, not a calibrated market model. The term sheet uses a simplified business-day calendar.
- Binary options in the Full universe are theoretical; market bid--ask spreads, liquidity, impact, collateral and counterparty costs are not calibrated. Funding figures are therefore model-based diagnostics, not executable capital requirements.
- L0 is non-convex and initialization-sensitive. Solver convergence alone does not establish a stable instrument set or a global optimum.
- Importance sampling reweights simulated paths to estimate rare-event risk; its precision must be assessed against standard Monte Carlo, and it does not by itself improve a fixed hedge.
- The final holdout test is reserved. Conclusions here concern model-based validation, not proven out-of-sample trading performance.

For the exact product conventions, start with the [term sheet](docs/TERM_SHEET.md). For the broader research roadmap and remaining work, see [ROADMAP](docs/ROADMAP.md).
