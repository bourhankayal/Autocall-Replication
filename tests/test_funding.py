import unittest

import numpy as np
import pandas as pd

from autocall_replication.products import (
    AutocallProduct,
    BinaryCall,
    BinaryPut,
    Cash,
)
from autocall_replication.replication.conditional_policy import (
    run_conditional_policy_penalty_comparison,
)
from autocall_replication.replication.funding import (
    BINARY_MODES,
    evaluate_conditional_policy_funding,
    expand_conditional_node_positions,
    price_conditional_node,
)


class BinaryImplementationTests(unittest.TestCase):
    def setUp(self):
        expiry = pd.Timestamp("2027-06-22")
        self.cash = Cash("cash", 0.0, expiry, 100.0)
        self.binary_call = BinaryCall("BC100", 100.0, expiry, 1.0)
        self.binary_put = BinaryPut("BP100", 100.0, expiry, 1.0)
        self.result = {
            "vanillas": [self.cash, self.binary_call, self.binary_put],
            "feature_table": pd.DataFrame(
                {"node_index": [0, 0, 0]}, index=[0, 1, 2]
            ),
        }
        self.weights = np.array([1.0, 2.0, -1.5])

    def test_vertical_spread_replaces_each_binary_by_two_vanillas(self):
        positions = expand_conditional_node_positions(
            self.result,
            self.weights,
            node_index=0,
            binary_mode="vertical_spread",
            spread_width=10.0,
        )
        option_positions = [
            position
            for position in positions
            if not isinstance(position["instrument"], Cash)
        ]
        self.assertEqual(len(option_positions), 4)
        self.assertFalse(
            any(
                isinstance(position["instrument"], (BinaryCall, BinaryPut))
                for position in option_positions
            )
        )
        call_legs = [
            position
            for position in option_positions
            if position["source_name"] == "BC100"
        ]
        payoff_above = sum(
            position["quantity"] * position["instrument"].payoff(120.0)
            for position in call_legs
        )
        self.assertAlmostEqual(payoff_above, 2.0)

    def test_otc_costs_are_ordered_and_model_price_is_preserved(self):
        theoretical = price_conditional_node(
            self.result,
            self.weights,
            0,
            100.0,
            "2026-06-20",
            0.03,
            0.01,
            0.20,
            "theoretical",
        )["summary"]
        costs = []
        for mode in ("otc_favorable", "otc_central", "otc_stressed"):
            priced = price_conditional_node(
                self.result,
                self.weights,
                0,
                100.0,
                "2026-06-20",
                0.03,
                0.01,
                0.20,
                mode,
            )["summary"]
            self.assertAlmostEqual(
                priced["net_model_value"], theoretical["net_model_value"]
            )
            costs.append(priced["otc_execution_cost"])
        self.assertLess(costs[0], costs[1])
        self.assertLess(costs[1], costs[2])


class ConditionalFundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        cls.base = run_conditional_policy_penalty_comparison(
            product=cls.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="full",
            penalties=("l1",),
            n_paths=30,
            n_alphas=4,
            min_alpha_ratio=1e-2,
            min_state_paths=2,
            max_iter=1000,
            seed=600,
        )
        cls.funding = evaluate_conditional_policy_funding(
            base_result=cls.base,
            product=cls.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=10,
            seed=900,
            initial_autocall_premium=100.0,
            spread_width=5.0,
        )

    def test_all_binary_modes_share_the_same_paths_and_premium(self):
        self.assertEqual(self.funding["binary_modes"], BINARY_MODES)
        summary = self.funding["summary"]
        self.assertEqual(set(summary["initial_autocall_premium"]), {100.0})
        counts = self.funding["path_summary"].groupby("binary_mode")["path_id"].nunique()
        self.assertTrue((counts == 10).all())
        self.assertEqual(
            self.funding["evaluation_status"],
            "independent_paths_no_refit_no_alpha_selection",
        )
        self.assertEqual(self.funding["test_status"], "reserved_not_evaluated")

    def test_cash_ledger_satisfies_the_accounting_identity(self):
        ledger = self.funding["ledger"]
        observations = ledger.loc[ledger["event_type"] == "observation_settlement"]
        expected = (
            observations["cash_before_event"]
            + observations["interest_on_cash"]
            + observations["option_payoff"]
            - observations["autocall_cashflow"]
            - observations["next_portfolio_net_execution_value"]
        )
        np.testing.assert_allclose(observations["cash_after_event"], expected)
        initial = ledger.loc[ledger["event_type"] == "initial_hedge_purchase"]
        np.testing.assert_allclose(
            initial["cash_after_event"],
            initial["autocall_premium"]
            - initial["next_portfolio_net_execution_value"],
        )

    def test_recall_stops_new_positions_and_funding_is_non_negative(self):
        recalled = self.funding["ledger"].loc[self.funding["ledger"]["recalled"]]
        self.assertFalse(recalled["new_position_opened"].any())
        self.assertTrue(
            (
                self.funding["path_summary"]["additional_capital_without_borrowing"]
                >= 0.0
            ).all()
        )
        self.assertIn("additional_capital_p95_bps_notional", self.funding["summary"])


if __name__ == "__main__":
    unittest.main()
