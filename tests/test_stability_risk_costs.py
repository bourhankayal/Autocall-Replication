import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd

from autocall_replication.products import (
    AutocallProduct,
    BinaryCall,
    Cash,
    EuropeanCall,
)
from autocall_replication.replication.pathwise_payoff import (
    run_pathwise_penalty_comparison,
)
from autocall_replication.replication.risk import (
    compare_transaction_cost_to_risk_reduction,
    evaluate_pathwise_profile_risk,
    risk_table_in_notional_units,
    tail_risk_metrics,
)
from autocall_replication.replication.stability import (
    apply_stability_filter,
    run_pathwise_profile_stability,
)
from autocall_replication.replication.transaction_costs import (
    OTC_COST_SCENARIOS,
    download_yfinance_option_snapshot,
    estimate_profile_model_values,
    estimate_profile_transaction_costs,
    synthetic_binary_quote,
    validate_option_snapshot,
)


class StabilityRiskCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        cls.base = run_pathwise_penalty_comparison(
            product=cls.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls",
            penalties=("l1",),
            n_paths=30,
            n_alphas=4,
            min_alpha_ratio=1e-2,
            seed=321,
        )

    def test_stability_uses_ten_calibrations_and_keeps_test_closed(self):
        stability = run_pathwise_profile_stability(
            base_result=self.base,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_calibrations=10,
            n_paths=30,
        )

        self.assertEqual(stability["n_calibrations"], 10)
        self.assertEqual(len(stability["seeds"]), 10)
        self.assertEqual(stability["test_status"], "reserved_not_evaluated")
        self.assertEqual(
            stability["details"].groupby(["penalty", "profile"]).size().unique().tolist(),
            [10],
        )
        self.assertIn("passes_stability_filter", stability["summary"])
        filtered = apply_stability_filter(self.base, stability)
        self.assertLessEqual(len(filtered["profiles"]), len(self.base["profiles"]))
        self.assertEqual(
            filtered["stability_filter_status"]["n_profiles_before"],
            len(self.base["profiles"]),
        )

    def test_risk_is_evaluated_on_an_independent_sample(self):
        risk = evaluate_pathwise_profile_risk(
            base_result=self.base,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=100,
            seed=900,
        )

        self.assertEqual(
            risk["evaluation_status"],
            "independent_sample_not_used_for_alpha_selection",
        )
        self.assertEqual(risk["test_status"], "reserved_not_evaluated")
        self.assertIn("es_975_reduction", risk["comparison"])
        self.assertIn("es_975_relative_reduction", risk["comparison"])
        self.assertIn("barrier_hit", set(risk["residual_risk"]["condition"]))
        self.assertIn("conditional_comparison", risk)
        self.assertIn("condition_summary", risk)
        self.assertIn("risk_summary", risk)
        self.assertIn("pct_notional", risk["gross_risk_units"])
        self.assertIn("bps_notional", risk["residual_risk_units"])
        self.assertEqual(
            risk["loss_convention"],
            "issuer_shortfall_positive_autocall_minus_replication",
        )
        self.assertEqual(risk["dynamic_hedging_status"], "level_3_not_implemented")

    def test_tail_risk_metrics_are_consistent(self):
        metrics = tail_risk_metrics(np.arange(1.0, 101.0))
        self.assertGreaterEqual(metrics["es_99"], metrics["var_99"])
        self.assertEqual(metrics["max_loss"], 100.0)
        self.assertEqual(metrics["mae"], 50.5)
        self.assertEqual(metrics["under_replication_rate"], 1.0)

    def test_risk_units_and_invalid_relative_reduction_are_explicit(self):
        table = pd.DataFrame([{"condition": "all", "rmse": 2.0, "es_975": 3.0}])
        units = risk_table_in_notional_units(table, 200.0, ("condition",))
        rmse = units.loc[units["metric"] == "rmse"].iloc[0]
        self.assertEqual(rmse["pct_notional"], 1.0)
        self.assertEqual(rmse["bps_notional"], 100.0)

    def test_yfinance_snapshot_is_validated_without_network(self):
        calls = pd.DataFrame(
            {
                "contractSymbol": ["C100"],
                "strike": [100.0],
                "bid": [5.0],
                "ask": [5.2],
                "volume": [10],
                "openInterest": [100],
                "impliedVolatility": [0.2],
                "contractSize": ["REGULAR"],
                "currency": ["USD"],
                "lastTradeDate": [pd.Timestamp("2026-08-19", tz="UTC")],
            }
        )
        puts = calls.assign(contractSymbol="P100", bid=4.8, ask=5.0)

        class FakeTicker:
            options = ("2027-06-22",)

            def option_chain(self, expiry):
                self.requested = expiry
                return SimpleNamespace(calls=calls, puts=puts)

        snapshot = download_yfinance_option_snapshot(
            "spy",
            expiries=["2027-06-22"],
            ticker_factory=lambda _: FakeTicker(),
            snapshot_utc=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )

        self.assertEqual(len(snapshot), 2)
        self.assertTrue(snapshot["is_valid_quote"].all())
        self.assertEqual(set(snapshot["option_type"]), {"call", "put"})

    def test_invalid_quotes_and_otc_scenarios_are_explicit(self):
        expiry = pd.Timestamp("2027-06-22")
        snapshot = pd.DataFrame(
            {
                "expiry": [expiry, expiry, expiry],
                "option_type": ["call", "call", "call"],
                "strike": [95.0, 100.0, 105.0],
                "bid": [7.0, 4.9, 2.5],
                "ask": [7.2, 5.1, 2.7],
            }
        )
        validated = validate_option_snapshot(snapshot)
        binary = BinaryCall("BC100", 100.0, expiry, 1.0)
        synthetic = synthetic_binary_quote(binary, validated)

        self.assertTrue(synthetic["available"])
        self.assertEqual(set(OTC_COST_SCENARIOS), {
            "otc_favorable",
            "otc_central",
            "otc_stressed",
        })

    def test_profile_costs_and_cost_risk_filter_cover_three_otc_scenarios(self):
        expiry = pd.Timestamp("2027-06-22")
        vanillas = [
            Cash("cash", 0.0, expiry, 100.0),
            EuropeanCall("C100", 100.0, expiry, 1.0),
            BinaryCall("BC100", 100.0, expiry, 1.0),
        ]
        base = {
            "profiles": pd.DataFrame(
                [{"penalty": "l1", "profile": "performance", "solution_index": 0}]
            ),
            "vanillas": vanillas,
            "results": {
                "l1": {"solutions": [{"weights": np.array([1.0, 2.0, 3.0])}]}
            },
        }
        snapshot = pd.DataFrame(
            {
                "expiry": [expiry, expiry, expiry],
                "option_type": ["call", "call", "call"],
                "strike": [95.0, 100.0, 105.0],
                "bid": [7.0, 4.9, 2.5],
                "ask": [7.2, 5.1, 2.7],
            }
        )
        costs = estimate_profile_transaction_costs(base, snapshot, 100.0)
        summary = costs["summary"]

        self.assertEqual(len(summary), 3)
        self.assertTrue(summary["cost_complete"].all())
        ordered = summary.set_index("cost_scenario")["transaction_cost"]
        self.assertLessEqual(ordered["otc_favorable"], ordered["otc_central"])
        self.assertLessEqual(ordered["otc_central"], ordered["otc_stressed"])

        risk = pd.DataFrame(
            [
                {
                    "penalty": "l1",
                    "profile": "performance",
                    "es_975_reduction": 10.0,
                    "gross_max_loss": 20.0,
                    "residual_max_loss": 15.0,
                }
            ]
        )
        comparison = compare_transaction_cost_to_risk_reduction(
            risk,
            summary,
            autocall_notional=100.0,
        )
        self.assertTrue(comparison["passes_cost_risk_filter"].all())
        self.assertIn("transaction_cost_pct_notional", comparison)
        self.assertIn("cost_to_risk_reduction_ratio", comparison)
        self.assertIn("net_risk_reduction_bps", comparison)

        model_values = estimate_profile_model_values(
            base,
            spot0=100.0,
            valuation_date="2026-06-20",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            autocall_model_value=100.0,
            autocall_notional=100.0,
        )
        self.assertEqual(len(model_values), 1)
        self.assertIn("portfolio_model_value", model_values)
        self.assertIn("initial_model_funding_gap_bps_notional", model_values)


if __name__ == "__main__":
    unittest.main()
