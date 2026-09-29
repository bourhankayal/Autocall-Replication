import unittest

import pandas as pd

from autocall_replication.replication.industry_benchmark import (
    build_internal_hedge_benchmark,
    build_three_price_table,
    compare_commercial_cushion_to_public_benchmark,
    public_structured_note_pricing_benchmark,
)


class IndustryBenchmarkTests(unittest.TestCase):
    def test_three_prices_follow_economic_order(self):
        prices = build_three_price_table(
            {"initial_autocall_premium": 100.48, "terminal_pnl_mean": -0.23},
            theoretical_price=100.48,
            notional=100.0,
            target_margin_pct_notional=1.0,
        )
        values = prices.set_index("price_type")["price"]
        self.assertAlmostEqual(values["minimum_coverage"], 100.71)
        self.assertAlmostEqual(values["commercial"], 101.71)
        self.assertLess(values["theoretical"], values["minimum_coverage"])
        self.assertLess(values["minimum_coverage"], values["commercial"])

    def test_public_gap_range_is_positive_and_not_labelled_as_pnl(self):
        benchmark = public_structured_note_pricing_benchmark()
        self.assertTrue((benchmark["gap_pct_low"] >= 0.0).all())
        self.assertTrue((benchmark["gap_pct_high"] >= benchmark["gap_pct_low"]).all())
        self.assertTrue(benchmark["benchmark_scope"].str.contains("not realized").all())

    def test_internal_benchmark_compares_full_to_calls_puts_like_for_like(self):
        risk = pd.DataFrame(
            [
                {"family": "calls_puts", "penalty": "l1", "profile": "compromise", "gross_rmse": 10.0, "residual_rmse": 5.0, "gross_es_975": 20.0, "residual_es_975": 12.0},
                {"family": "full", "penalty": "l1", "profile": "compromise", "gross_rmse": 10.0, "residual_rmse": 4.0, "gross_es_975": 20.0, "residual_es_975": 9.0},
            ]
        )
        result = build_internal_hedge_benchmark(risk)
        full = result.loc[result["family"].eq("full")].iloc[0]
        self.assertAlmostEqual(full["rmse_improvement_vs_unhedged"], 0.60)
        self.assertAlmostEqual(full["rmse_improvement_vs_reference"], 0.20)
        self.assertAlmostEqual(full["es_975_improvement_vs_reference"], 0.25)

    def test_commercial_cushion_comparison_is_explicit(self):
        prices = build_three_price_table(
            {"initial_autocall_premium": 100.0, "terminal_pnl_mean": 0.0},
            theoretical_price=100.0,
            notional=100.0,
            target_margin_pct_notional=2.0,
        )
        comparison = compare_commercial_cushion_to_public_benchmark(prices)
        self.assertAlmostEqual(comparison["our_commercial_cushion_pct_notional"], 2.0)
        self.assertIn("not desk P&L", comparison["interpretation_limit"])


if __name__ == "__main__":
    unittest.main()
