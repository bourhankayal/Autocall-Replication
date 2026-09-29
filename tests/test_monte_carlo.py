import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autocall_replication.monte_carlo import (
    autocall_discounted_payoff_from_path,
    price_autocall_bs_mc,
    run_autocall_mc_convergence,
    run_barrier_monitoring_convergence,
    simulate_gbm_path,
    simulate_gbm_paths,
)
from autocall_replication.products import AutocallProduct


class SimulateGbmPathTests(unittest.TestCase):
    def test_path_contains_only_weekdays(self):
        path = simulate_gbm_path(
            spot0=100.0,
            start_date=pd.Timestamp("2025-01-03"),  # vendredi
            end_date=pd.Timestamp("2025-01-06"),  # lundi
            rate=0.02,
            dividend_yield=0.0,
            vol=0.20,
            seed=1,
        )

        self.assertEqual(
            list(path.index),
            [pd.Timestamp("2025-01-03"), pd.Timestamp("2025-01-06")],
        )
        self.assertTrue(all(date.weekday() < 5 for date in path.index))

    def test_weekend_dates_are_rolled_to_following_weekdays(self):
        path = simulate_gbm_path(
            spot0=100.0,
            start_date=pd.Timestamp("2026-06-20"),  # samedi
            end_date=pd.Timestamp("2027-06-22"),
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            seed=1,
        )

        self.assertEqual(path.index[0], pd.Timestamp("2026-06-22"))
        self.assertEqual(path.index[-1], pd.Timestamp("2027-06-22"))
        self.assertTrue(all(date.weekday() < 5 for date in path.index))

        result = AutocallProduct(autocall_strike=1.10).compute_autocall_payoff(
            path,
            start_date=pd.Timestamp("2026-06-20"),
        )
        self.assertEqual(
            pd.Timestamp(result["cashflows"].iloc[-1]["date"]),
            pd.Timestamp("2027-06-22"),
        )

    def test_deterministic_path_uses_actual_calendar_time(self):
        path = simulate_gbm_path(
            spot0=100.0,
            start_date=pd.Timestamp("2025-01-01"),
            end_date=pd.Timestamp("2026-01-01"),
            rate=0.05,
            dividend_yield=0.01,
            vol=0.0,
            seed=1,
        )

        expected = 100.0 * math.exp(0.04)
        self.assertAlmostEqual(float(path.iloc[-1]), expected, places=12)

    def test_seed_is_reproducible(self):
        kwargs = dict(
            spot0=100.0,
            start_date=pd.Timestamp("2025-01-01"),
            end_date=pd.Timestamp("2025-04-01"),
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            seed=123,
        )

        first = simulate_gbm_path(**kwargs)
        second = simulate_gbm_path(**kwargs)
        np.testing.assert_array_equal(first.to_numpy(), second.to_numpy())

    def test_vectorized_paths_have_expected_shape_and_antithetic_pairs(self):
        dates, paths = simulate_gbm_paths(
            spot0=100.0,
            start_date="2025-01-02",
            end_date="2025-02-03",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=4,
            seed=123,
            antithetic=True,
        )

        self.assertEqual(paths.shape, (4, len(dates)))
        log_returns = np.diff(np.log(paths), axis=1)
        dt = (
            np.diff(dates.values).astype("timedelta64[D]").astype(float) / 365.0
        )
        drift = (0.02 - 0.01 - 0.5 * 0.20**2) * dt
        np.testing.assert_allclose(log_returns[0] + log_returns[2], 2.0 * drift)
        np.testing.assert_allclose(log_returns[1] + log_returns[3], 2.0 * drift)

    def test_invalid_parameters_are_rejected(self):
        common = dict(
            start_date=pd.Timestamp("2025-01-01"),
            end_date=pd.Timestamp("2026-01-01"),
            rate=0.02,
            dividend_yield=0.0,
            vol=0.20,
        )

        with self.assertRaises(ValueError):
            simulate_gbm_path(spot0=0.0, **common)
        with self.assertRaises(ValueError):
            simulate_gbm_path(spot0=100.0, **{**common, "vol": -0.1})
        with self.assertRaises(ValueError):
            simulate_gbm_path(
                spot0=100.0,
                **{
                    **common,
                    "start_date": pd.Timestamp("2026-01-01"),
                    "end_date": pd.Timestamp("2025-01-01"),
                },
            )

    def test_incomplete_path_is_not_redeemed_early(self):
        product = AutocallProduct()
        path = pd.Series(
            [100.0, 90.0],
            index=pd.to_datetime(["2025-01-01", "2025-02-01"]),
        )

        with self.assertRaisesRegex(ValueError, "ne couvre pas la date de maturité"):
            product.compute_autocall_payoff(path, start_date="2025-01-01")


class AutocallPayoffTests(unittest.TestCase):
    START = pd.Timestamp("2025-01-02")
    OBSERVATIONS = pd.to_datetime(
        ["2025-04-02", "2025-07-02", "2025-10-02", "2026-01-02"]
    )

    def _path(self, observation_spots, extra_points=None):
        points = [(self.START, 100.0)]
        if extra_points:
            points.extend(extra_points)
        points.extend(zip(self.OBSERVATIONS, observation_spots))
        points.sort(key=lambda item: item[0])
        return pd.Series(
            [spot for _, spot in points],
            index=pd.DatetimeIndex([date for date, _ in points]),
            dtype=float,
        )

    def test_recall_occurs_at_each_observation_including_exact_threshold(self):
        product = AutocallProduct()

        for call_index, expected_date in enumerate(self.OBSERVATIONS):
            with self.subTest(call_index=call_index):
                spots = [90.0] * 4
                spots[call_index] = 100.0
                path = self._path(spots[: call_index + 1])

                result = product.compute_autocall_payoff(path, start_date=self.START)

                self.assertTrue(result["called"])
                self.assertEqual(result["call_date"], expected_date)
                self.assertEqual(
                    result["cashflows"].iloc[-1]["type"],
                    "autocall_redemption",
                )

    def test_coupon_is_conditional_and_has_no_memory(self):
        product = AutocallProduct()
        result = product.compute_autocall_payoff(
            self._path([71.0, 90.0, 71.0, 75.0]),
            start_date=self.START,
        )

        coupons = result["cashflows"].loc[result["cashflows"]["type"] == "coupon"]
        self.assertEqual(len(coupons), 1)
        self.assertEqual(coupons.iloc[0]["date"], self.OBSERVATIONS[1])
        self.assertEqual(coupons.iloc[0]["amount"], 2.0)
        self.assertEqual(result["undiscounted_payoff"], 102.0)

    def test_exact_coupon_barrier_pays_coupon(self):
        result = AutocallProduct().compute_autocall_payoff(
            self._path([80.0, 71.0, 71.0, 75.0]),
            start_date=self.START,
        )

        coupons = result["cashflows"].loc[result["cashflows"]["type"] == "coupon"]
        self.assertEqual(len(coupons), 1)
        self.assertEqual(coupons.iloc[0]["amount"], 2.0)

    def test_barrier_hit_is_permanent_and_applies_terminal_performance(self):
        result = AutocallProduct().compute_autocall_payoff(
            self._path(
                [70.0, 70.0, 70.0, 75.0],
                extra_points=[(pd.Timestamp("2025-02-03"), 50.0)],
            ),
            start_date=self.START,
        )

        self.assertTrue(result["barrier_hit"])
        self.assertEqual(result["barrier_hit_date"], pd.Timestamp("2025-02-03"))
        final = result["cashflows"].iloc[-1]
        self.assertEqual(final["type"], "final_redemption")
        self.assertEqual(final["amount"], 75.0)

    def test_exact_protection_barrier_counts_as_hit(self):
        result = AutocallProduct().compute_autocall_payoff(
            self._path(
                [71.0, 71.0, 71.0, 75.0],
                extra_points=[(pd.Timestamp("2025-02-03"), 70.0)],
            ),
            start_date=self.START,
        )

        self.assertTrue(result["barrier_hit"])
        self.assertEqual(result["cashflows"].iloc[-1]["amount"], 75.0)

    def test_no_barrier_hit_redeems_full_notional(self):
        result = AutocallProduct().compute_autocall_payoff(
            self._path([71.0, 71.0, 71.0, 75.0]),
            start_date=self.START,
        )

        self.assertFalse(result["barrier_hit"])
        self.assertEqual(result["cashflows"].iloc[-1]["amount"], 100.0)

    def test_barrier_is_not_observed_after_maturity(self):
        path = self._path(
            [71.0, 71.0, 71.0, 90.0],
            extra_points=[(pd.Timestamp("2026-01-05"), 50.0)],
        )
        result = AutocallProduct().compute_autocall_payoff(path, start_date=self.START)

        self.assertFalse(result["barrier_hit"])
        final_redemption = result["cashflows"].loc[
            result["cashflows"]["type"] == "final_redemption", "amount"
        ]
        self.assertEqual(final_redemption.iloc[0], 100.0)

    def test_barrier_history_is_reported_even_if_product_is_recalled(self):
        result = AutocallProduct().compute_autocall_payoff(
            self._path(
                [100.0],
                extra_points=[(pd.Timestamp("2025-02-03"), 50.0)],
            ),
            start_date=self.START,
        )

        self.assertTrue(result["called"])
        self.assertTrue(result["barrier_hit"])
        self.assertEqual(result["undiscounted_payoff"], 102.0)

    def test_prices_after_recall_do_not_create_flows_or_barrier_hits(self):
        result = AutocallProduct().compute_autocall_payoff(
            self._path([101.0, 50.0, 50.0, 50.0]),
            start_date=self.START,
        )

        self.assertTrue(result["called"])
        self.assertFalse(result["barrier_hit"])
        self.assertEqual(result["call_date"], self.OBSERVATIONS[0])
        self.assertEqual(len(result["cashflows"]), 2)
        self.assertEqual(result["undiscounted_payoff"], 102.0)

    def test_empty_or_weekend_only_path_is_rejected(self):
        product = AutocallProduct()
        empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        weekend_only = pd.Series(
            [100.0, 101.0],
            index=pd.to_datetime(["2025-01-04", "2025-01-05"]),
        )

        with self.assertRaisesRegex(ValueError, "lundi au vendredi"):
            product.compute_autocall_payoff(empty)
        with self.assertRaisesRegex(ValueError, "lundi au vendredi"):
            product.compute_autocall_payoff(weekend_only)

    def test_unordered_duplicate_missing_and_invalid_prices_are_rejected(self):
        product = AutocallProduct()
        invalid_paths = [
            pd.Series(
                [100.0, 101.0],
                index=pd.to_datetime(["2025-01-03", "2025-01-02"]),
            ),
            pd.Series(
                [100.0, 101.0],
                index=pd.to_datetime(["2025-01-02", "2025-01-02"]),
            ),
            pd.Series(
                [100.0, np.nan],
                index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
            ),
            pd.Series(
                [100.0, -1.0],
                index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
            ),
            pd.Series(
                [100.0, np.inf],
                index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
            ),
        ]

        for path in invalid_paths:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    product.compute_autocall_payoff(path, start_date=self.START)


class PriceAutocallTests(unittest.TestCase):
    def test_at_least_two_paths_are_required(self):
        with self.assertRaisesRegex(ValueError, "n_paths"):
            price_autocall_bs_mc(
                product=AutocallProduct(),
                spot0=100.0,
                valuation_date="2025-01-01",
                maturity_date="2026-01-01",
                rate=0.02,
                dividend_yield=0.0,
                vol=0.20,
                n_paths=1,
                seed=1,
            )

        with self.assertRaisesRegex(ValueError, "pair"):
            price_autocall_bs_mc(
                product=AutocallProduct(),
                spot0=100.0,
                valuation_date="2025-01-02",
                maturity_date="2026-01-02",
                rate=0.02,
                dividend_yield=0.0,
                vol=0.20,
                n_paths=3,
                seed=1,
                antithetic=True,
            )

    def test_deterministic_price_has_degenerate_confidence_interval(self):
        result = price_autocall_bs_mc(
            product=AutocallProduct(),
            spot0=100.0,
            valuation_date="2025-01-02",
            maturity_date="2026-01-02",
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            n_paths=100,
            seed=7,
        )

        self.assertEqual(result["actualized_price"], 102.0)
        self.assertEqual(result["std_error"], 0.0)
        self.assertEqual(result["confidence_interval_95"], (102.0, 102.0))
        self.assertEqual(result["n_independent_samples"], 50)
        self.assertTrue(result["antithetic"])

    def test_vectorized_price_is_reproducible(self):
        kwargs = dict(
            product=AutocallProduct(),
            spot0=100.0,
            valuation_date="2025-01-02",
            maturity_date="2026-01-02",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=200,
            seed=123,
        )

        first = price_autocall_bs_mc(**kwargs)
        second = price_autocall_bs_mc(**kwargs)
        np.testing.assert_array_equal(first["path_values"], second["path_values"])
        self.assertEqual(first["confidence_interval_95"], second["confidence_interval_95"])
        self.assertLessEqual(first["ci95_low"], first["actualized_price"])
        self.assertGreaterEqual(first["ci95_high"], first["actualized_price"])

    def test_vectorized_payoffs_match_contract_engine_path_by_path(self):
        product = AutocallProduct()
        dates, paths = simulate_gbm_paths(
            spot0=100.0,
            start_date="2025-01-02",
            end_date="2026-01-02",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=20,
            seed=123,
            antithetic=True,
        )
        expected = np.array(
            [
                autocall_discounted_payoff_from_path(
                    product=product,
                    path=pd.Series(path, index=dates),
                    valuation_date="2025-01-02",
                    rate=0.02,
                )
                for path in paths
            ]
        )
        result = price_autocall_bs_mc(
            product=product,
            spot0=100.0,
            valuation_date="2025-01-02",
            maturity_date="2026-01-02",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=20,
            seed=123,
            antithetic=True,
        )

        np.testing.assert_allclose(
            result["path_values"],
            expected,
            rtol=0.0,
            atol=1e-12,
        )

    def test_convergence_table_reports_price_error_and_interval_width(self):
        table = run_autocall_mc_convergence(
            product=AutocallProduct(),
            spot0=100.0,
            valuation_date="2025-01-02",
            maturity_date="2026-01-02",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            path_counts=(20, 40, 80),
            seed=123,
        )

        self.assertEqual(table["n_paths"].tolist(), [20, 40, 80])
        self.assertEqual(
            list(table.columns),
            [
                "n_paths",
                "actualized_price",
                "std_error",
                "ci95_low",
                "ci95_high",
                "ci95_width",
            ],
        )
        self.assertTrue((table["std_error"] >= 0.0).all())
        self.assertTrue((table["ci95_width"] >= 0.0).all())

    def test_barrier_monitoring_converges_to_daily_contract_reference(self):
        table = run_barrier_monitoring_convergence(
            product=AutocallProduct(),
            spot0=100.0,
            valuation_date="2025-01-02",
            maturity_date="2026-01-02",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=400,
            monitoring_steps=(21, 5, 1),
            seed=123,
        )

        self.assertEqual(table["monitoring_step"].tolist(), [21, 5, 1])
        daily = table.loc[table["monitoring_step"] == 1].iloc[0]
        self.assertEqual(daily["bias_vs_daily"], 0.0)
        self.assertEqual(daily["abs_bias_vs_daily"], 0.0)

    def test_terminal_spot_control_variate_reduces_variance(self):
        kwargs = dict(
            product=AutocallProduct(),
            spot0=100.0,
            valuation_date="2025-01-02",
            maturity_date="2026-01-02",
            rate=0.02,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=2000,
            seed=123,
        )
        raw = price_autocall_bs_mc(**kwargs, control_variate=False)
        adjusted = price_autocall_bs_mc(**kwargs, control_variate=True)

        self.assertLess(adjusted["std_error"], raw["std_error"])
        self.assertGreater(adjusted["variance_reduction_ratio"], 1.0)
        self.assertNotEqual(adjusted["control_beta"], 0.0)
        self.assertLess(
            abs(adjusted["actualized_price"] - raw["actualized_price"]),
            3.0 * raw["std_error"],
        )
        self.assertEqual(
            len(adjusted["estimator_samples"]),
            adjusted["n_independent_samples"],
        )

    def test_existing_contract_keeps_its_original_schedule(self):
        result = price_autocall_bs_mc(
            product=AutocallProduct(),
            spot0=100.0,
            valuation_date="2027-06-20",
            maturity_date="2027-06-20",
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            n_paths=4,
            seed=1,
            contract_start_date="2026-06-20",
            initial_spot=100.0,
            barrier_hit_before=False,
        )

        self.assertAlmostEqual(result["actualized_price"], 102.0)
        self.assertEqual(result["std_error"], 0.0)

    def test_barrier_is_not_observed_after_final_cashflow(self):
        product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        result = price_autocall_bs_mc(
            product=product,
            spot0=71.43,
            valuation_date="2027-06-20",
            maturity_date="2027-06-20",
            rate=0.0,
            dividend_yield=0.0,
            vol=0.0,
            n_paths=20,
            seed=42,
            contract_start_date="2026-06-20",
            initial_spot=100.0,
            barrier_hit_before=False,
        )

        self.assertAlmostEqual(result["actualized_price"], 100.0)
        self.assertEqual(result["std_error"], 0.0)

    def test_existing_contract_uses_barrier_history_before_valuation(self):
        product = AutocallProduct()
        path = pd.Series(
            [75.0, 75.0],
            index=pd.to_datetime(["2025-10-03", "2026-01-02"]),
        )

        result = product.compute_remaining_payoff(
            path,
            contract_start_date="2025-01-02",
            spot_initial=100.0,
            valuation_date="2025-10-03",
            barrier_hit_before=True,
        )

        self.assertTrue(result["barrier_hit"])
        self.assertEqual(result["cashflows"].iloc[-1]["amount"], 75.0)

    def test_existing_contract_recall_is_inclusive(self):
        product = AutocallProduct()
        path = pd.Series(
            [90.0, 100.0],
            index=pd.to_datetime(["2025-03-03", "2025-04-02"]),
        )

        result = product.compute_remaining_payoff(
            path,
            contract_start_date="2025-01-02",
            spot_initial=100.0,
            valuation_date="2025-03-03",
        )

        self.assertTrue(result["called"])
        self.assertEqual(result["call_date"], pd.Timestamp("2025-04-02"))
        self.assertEqual(result["undiscounted_payoff"], 102.0)


if __name__ == "__main__":
    unittest.main()
