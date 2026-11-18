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
    def test_conditional_elastic_net_reuses_paths_for_ratio_search(self):
        common = dict(
            product=AutocallProduct(coupon_rate=0.02, down_barrier=0.70),
            spot0=100.0, valuation_date="2026-06-20",
            maturity_date="2027-06-22", rate=0.03,
            dividend_yield=0.01, vol=0.20, family="calls",
            penalty="elastic_net", solver="legacy", alpha=0.1,
            n_paths=30, seed=421, min_state_paths=100,
        )
        first = run_conditional_benchmark_curve(**common, l1_ratio=0.2)
        second = run_conditional_benchmark_curve(
            **common, l1_ratio=0.8, precomputed_dataset=first["dataset"],
        )
        self.assertIs(second["dataset"], first["dataset"])
        self.assertEqual(len(first["dataset"]), 30)
        self.assertEqual(set(first["optimization"]["l1_ratio"]), {0.2})
        self.assertEqual(set(second["optimization"]["l1_ratio"]), {0.8})

    def test_l0_multistart_runs_through_both_temporal_benchmarks(self):
        common = dict(
            product=AutocallProduct(coupon_rate=0.02, down_barrier=0.70),
            spot0=100.0, valuation_date="2026-06-20",
            maturity_date="2027-06-22", rate=0.03,
            dividend_yield=0.01, vol=0.20, family="calls",
            penalty="l0", solver="proximal", alpha=0.02,
            n_paths=20, seed=421,
        )
        static = run_naive_benchmark_curve(**common)
        conditional = run_conditional_benchmark_curve(
            **common, min_state_paths=100,
        )
        self.assertGreaterEqual(len(static["l0_initialization_audit"]), 2)
        self.assertEqual(set(static["l0_initialization_audit"]["selected"]), {False, True})
        self.assertGreaterEqual(len(conditional["l0_initialization_audit"]), 2)
        self.assertEqual(set(conditional["optimization"]["solver"]), {"proximal"})

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

