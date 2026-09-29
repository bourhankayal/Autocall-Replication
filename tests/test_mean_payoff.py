import unittest

from autocall_replication.products import AutocallProduct
from autocall_replication.monte_carlo import simulate_gbm_path
from autocall_replication.replication.mean_payoff import (
    mean_undiscounted_payoff_mc,
)
from autocall_replication.replication.pathwise_payoff import (
    build_pathwise_payoff_dataset,
)
from autocall_replication.replication.static_cashflows import (
    build_timewise_curve_dataset,
    run_naive_benchmark_curve,
)
from autocall_replication.replication.common import build_naive_vanilla_basis
from autocall_replication.replication.semi_static import (
    build_conditional_curve_dataset,
    build_conditional_vanilla_basis,
    conditional_features_on_path,
    conditional_portfolio_value_curve_on_path,
    predict_conditional_path_data,
    run_conditional_benchmark_curve,
)


class MeanPayoffCalendarTests(unittest.TestCase):
    def test_simulation_covers_contractual_maturity_after_weekend_roll(self):
        result = mean_undiscounted_payoff_mc(
            product=AutocallProduct(coupon_rate=0.0, autocall_strike=2.0),
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            n_paths=2,
            seed=42,
            contract_start_date="2026-06-20",
            initial_spot=100.0,
            barrier_hit_before=False,
        )

        self.assertEqual(result["mean_undiscounted_payoff"], 100.0)
        self.assertEqual(result["std_error"], 0.0)

    def test_pathwise_dataset_covers_same_contractual_maturity(self):
        X, y = build_pathwise_payoff_dataset(
            product=AutocallProduct(coupon_rate=0.0, autocall_strike=2.0),
            vanillas=[],
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            n_paths=2,
            seed=42,
        )

        self.assertEqual(X.shape, (2, 0))
        self.assertEqual(y.tolist(), [100.0, 100.0])

    def test_timewise_dataset_covers_same_contractual_maturity(self):
        dataset = build_timewise_curve_dataset(
            product=AutocallProduct(coupon_rate=0.0, autocall_strike=2.0),
            vanillas=[],
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            n_paths=2,
            seed=42,
        )

        self.assertEqual(len(dataset), 2)
        self.assertEqual(dataset[0]["path"].index[-1].strftime("%Y-%m-%d"), "2027-06-22")

    def test_vanilla_maturities_follow_effective_contract_schedule(self):
        product = AutocallProduct()
        basis = build_naive_vanilla_basis(
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            product=product,
            family="calls",
        )

        maturity_names = {instrument.name for instrument in basis}
        self.assertIn("C_20260922_70.00", maturity_names)
        self.assertNotIn("C_20260920_70.00", maturity_names)

    def test_curve_benchmark_maps_vanillas_to_observation_dates(self):
        result = run_naive_benchmark_curve(
            product=AutocallProduct(coupon_rate=0.02, down_barrier=0.70),
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls",
            n_paths=4,
            penalty="l2",
            alpha=1e-4,
            seed=42,
        )

        self.assertEqual(
            [date.strftime("%Y-%m-%d") for date in result["dates"]],
            ["2026-09-22", "2026-12-22", "2027-03-22", "2027-06-22"],
        )

    def test_conditional_cash_uses_effective_observation_date(self):
        product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        vanillas = build_conditional_vanilla_basis(
            product=product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            family="calls",
        )

        names = {vanilla.name for vanilla in vanillas}
        self.assertIn("CASH_20260922", names)
        self.assertNotIn("CASH_20260920", names)

        dataset = build_conditional_curve_dataset(
            product=product,
            vanillas=vanillas,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=2,
            seed=42,
        )
        self.assertEqual(
            [date.strftime("%Y-%m-%d") for date in dataset[0]["dates"]],
            ["2026-09-22", "2026-12-22", "2027-03-22", "2027-06-22"],
        )

    def test_conditional_pipeline_is_available_from_package(self):
        self.assertTrue(callable(conditional_features_on_path))
        self.assertTrue(callable(predict_conditional_path_data))

        product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        result = run_conditional_benchmark_curve(
            product=product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-20",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls",
            n_paths=50,
            penalty="l2",
            alpha=1e-4,
            seed=42,
            min_state_paths=2,
        )
        path = simulate_gbm_path(
            spot0=100.0,
            start_date="2026-06-20",
            end_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            seed=95020,
        )
        target, replica, states = conditional_portfolio_value_curve_on_path(
            result=result,
            product=product,
            path=path,
            valuation_date="2026-06-20",
            rate=0.03,
        )

        self.assertEqual(len(target), 4)
        self.assertEqual(len(replica), 4)
        self.assertEqual(len(states), 4)


if __name__ == "__main__":
    unittest.main()
