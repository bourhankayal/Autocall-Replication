import unittest

from autocall_replication.products import AutocallProduct
from autocall_replication.replication.mean_payoff import run_naive_benchmark_payoff
from autocall_replication.replication.pathwise_payoff import (
    run_naive_benchmark_payoff_pathwise,
)
from autocall_replication.replication.price_surface import run_naive_benchmark_price
from autocall_replication.replication.semi_static import run_conditional_benchmark_curve
from autocall_replication.replication.static_cashflows import run_naive_benchmark_curve


class FistaPipelineTests(unittest.TestCase):
    def test_fista_runs_through_all_five_replication_pipelines(self):
        product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        common = dict(
            product=product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls",
            penalty="l1",
            solver="fista",
            alpha=1e-2,
        )
        results = {
            "price": run_naive_benchmark_price(
                **common, n_spots=3, n_paths=4
            ),
            "mean_payoff": run_naive_benchmark_payoff(
                **common, n_spots=3, n_paths=4
            ),
            "pathwise": run_naive_benchmark_payoff_pathwise(
                **common, n_paths=20
            ),
            "static_cashflows": run_naive_benchmark_curve(
                **common, n_paths=20
            ),
            "conditional": run_conditional_benchmark_curve(
                **common, n_paths=50, min_state_paths=2
            ),
        }

        for name, result in results.items():
            with self.subTest(pipeline=name):
                optimization = result["optimization"]
                if isinstance(optimization, dict):
                    self.assertEqual(optimization["solver"], "fista")
                    self.assertTrue(optimization["converged"])
                else:
                    self.assertEqual(set(optimization["solver"]), {"fista"})
                    self.assertTrue(optimization["converged"].all())
                self.assertIn("portfolio_metrics", result)


if __name__ == "__main__":
    unittest.main()

