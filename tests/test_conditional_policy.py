import unittest

import numpy as np
import pandas as pd

from autocall_replication.products import AutocallProduct, Cash, EuropeanCall
from autocall_replication.replication.conditional_policy import (
    build_external_policy_design,
    conditional_policy_cashflow_ledger,
    policy_information_audit,
    policy_profile_metrics,
    run_conditional_policy_penalty_comparison,
)
from autocall_replication.replication.method_comparison import compare_conditional_methods
from autocall_replication.replication.risk import (
    evaluate_conditional_policy_profile_risk,
    tail_risk_metrics,
)
from autocall_replication.replication.importance_sampling import (
    evaluate_conditional_policy_profile_risk_importance,
)
from autocall_replication.replication.stability import (
    run_conditional_policy_candidate_stability,
    run_conditional_policy_profile_stability,
)
from autocall_replication.replication.transaction_costs import (
    estimate_conditional_policy_transaction_costs,
)


class ConditionalPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.product = AutocallProduct(coupon_rate=0.02, down_barrier=0.70)
        cls.result = run_conditional_policy_penalty_comparison(
            product=cls.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls_puts",
            penalties=("l1",),
            n_paths=40,
            n_alphas=4,
            min_alpha_ratio=1e-2,
            min_state_paths=2,
            max_iter=1000,
            seed=421,
        )

    def test_split_objective_and_test_are_explicit(self):
        self.assertEqual(self.result["split"]["n_train"], 24)
        self.assertEqual(self.result["split"]["n_validation"], 8)
        self.assertEqual(self.result["split"]["n_test"], 8)
        self.assertEqual(
            self.result["selection_objective"],
            "total_discounted_pathwise_payoff_error",
        )
        self.assertEqual(self.result["test_status"], "reserved_not_evaluated")
        metrics = policy_profile_metrics(self.result)
        self.assertEqual(set(metrics["test_status"]), {"reserved_not_evaluated"})
        self.assertFalse(any(column.startswith("test_rmse") for column in metrics))

    def test_all_cash_columns_are_unpenalized(self):
        expected = tuple(
            index
            for index, instrument in enumerate(self.result["vanillas"])
            if isinstance(instrument, Cash)
        )
        self.assertEqual(self.result["unpenalized_indices"], expected)
        self.assertGreater(len(expected), 1)

    def test_information_used_precedes_payment(self):
        audit = policy_information_audit(self.result)
        self.assertTrue(audit["chronology_valid"].all())
        non_initial = audit["information_date"].notna()
        self.assertTrue(
            (audit.loc[non_initial, "information_date"] < audit.loc[non_initial, "payment_date"]).all()
        )

    def test_post_recall_has_no_position_and_liquidation_is_zero(self):
        profile = self.result["profiles"].iloc[0]
        ledger = conditional_policy_cashflow_ledger(
            self.result,
            penalty=str(profile["penalty"]),
            profile=str(profile["profile"]),
            path_index=0,
        )
        self.assertTrue((ledger["remaining_positions_after_settlement"] == 0).all())
        self.assertTrue((ledger["liquidation_value_pv"] == 0.0).all())
        self.assertFalse(ledger["new_position_after_recall"].any())
        self.assertTrue(
            np.isclose(
                ledger["cash_account_after_settlement_pv"].iloc[-1],
                ledger["replication_surplus_pv"].sum(),
            )
        )

    def test_external_design_reuses_frozen_topology(self):
        external = build_external_policy_design(
            base_result=self.result,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=3,
            seed=900,
        )
        self.assertEqual(external["A"].shape[1], self.result["A"].shape[1])
        self.assertEqual(len(external["b"]), 3)
        self.assertEqual(
            external["feature_table"]["node_index"].tolist(),
            self.result["feature_table"]["node_index"].tolist(),
        )

    def test_method_comparison_uses_identical_paths_and_frozen_profiles(self):
        external = build_external_policy_design(
            base_result=self.result, product=self.product, spot0=100.0,
            valuation_date="2026-06-20", maturity_date="2027-06-22",
            rate=0.03, dividend_yield=0.01, vol=0.20, n_paths=3, seed=901,
        )
        dataset = external["dataset"]
        n_dates = len(dataset[0]["dates"])
        per_date_result = {
            "dates": dataset[0]["dates"],
            "models": {
                (index, None): {"feature_indices": np.array([0]), "weights": np.array([0.0])}
                for index in range(n_dates)
            },
            "split_final_by_barrier": False,
        }
        profile = str(self.result["profiles"].loc[
            self.result["profiles"]["penalty"].eq("l1"), "profile"
        ].iloc[0])
        comparison = compare_conditional_methods(
            per_date_result, self.result, dataset, dataset,
            penalty="l1", profile=profile, notional=100.0,
        )
        self.assertEqual(set(comparison["summary"]["method"]),
                         {"par_echeance", "total_pathwise"})
        self.assertEqual(len(comparison["by_date"]), 2 * n_dates)
        self.assertTrue(np.isfinite(
            comparison["summary"]["terminal_rmse_pct_notional"]
        ).all())
        external_result = dict(self.result, dataset=dataset)
        ledger_errors = np.array([
            conditional_policy_cashflow_ledger(
                external_result, penalty="l1", profile=profile, path_index=index,
            )["replication_surplus_pv"].sum()
            for index in range(len(dataset))
        ])
        total_rmse = comparison["summary"].set_index("method").loc[
            "total_pathwise", "terminal_rmse_pct_notional"
        ]
        self.assertAlmostEqual(total_rmse, float(np.sqrt(np.mean(ledger_errors**2))))
        summary = comparison["summary"].set_index("method")
        expected = tail_risk_metrics(-ledger_errors, levels=(0.975,))
        for column, metric in {
            "terminal_mean_error_pct_notional": "mean_loss",
            "terminal_mae_pct_notional": "mae",
            "terminal_rmse_pct_notional": "rmse",
            "terminal_under_replication_rate": "under_replication_rate",
            "terminal_es_975_pct_notional": "es_975",
            "terminal_max_loss_pct_notional": "max_loss",
        }.items():
            self.assertAlmostEqual(summary.loc["total_pathwise", column], expected[metric])
        self.assertTrue({"mae_pct_notional", "under_replication_rate", "es_975_pct_notional", "max_loss_pct_notional"}.issubset(comparison["by_date"].columns))
        altered = [dict(item) for item in dataset]
        altered[0] = dict(altered[0], path=altered[1]["path"])
        with self.assertRaisesRegex(ValueError, "non identique"):
            compare_conditional_methods(
                per_date_result, self.result, altered, dataset,
                penalty="l1", profile=profile,
            )

    def test_conditional_stability_uses_ten_calibrations(self):
        stability = run_conditional_policy_profile_stability(
            base_result=self.result,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_calibrations=10,
            n_paths=20,
            min_valid_calibrations=9,
            max_iter=500,
            evaluation_n_paths=80,
            evaluation_seed=84000,
        )
        self.assertEqual(stability["n_calibrations"], 10)
        self.assertEqual(stability["test_status"], "reserved_not_evaluated")
        self.assertEqual(stability["topology_status"], "base_policy_nodes_frozen")
        self.assertEqual(
            stability["common_evaluation_status"],
            "independent_common_paths_not_used_for_selection",
        )
        self.assertTrue(np.isfinite(stability["summary"]["common_evaluation_es_mean"]).all())
        self.assertTrue(
            stability["summary"]["support_pairwise_jaccard_median"].between(0, 1).all()
        )
        self.assertTrue(
            (stability["summary"]["n_options_active_min"]
             <= stability["summary"]["n_options_active_median"]).all()
        )
        joined = self.result["profiles"].merge(
            stability["summary"],
            on=["family", "penalty", "profile", "solution_index"],
            validate="one_to_one",
        )
        self.assertEqual(len(joined), len(self.result["profiles"]))

    def test_candidate_stability_audits_all_initially_eligible_alphas(self):
        stability = run_conditional_policy_candidate_stability(
            base_result=self.result,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_calibrations=10,
            seeds=tuple(range(9300, 9310)),
            n_paths=30,
            min_active_options=2,
            max_active_options=10**9,
            min_valid_calibrations=9,
            max_iter=500,
        )
        eligible = self.result["raw_table"].loc[
            self.result["raw_table"]["converged"]
            & self.result["raw_table"]["n_options_active"].ge(2)
        ]
        self.assertEqual(stability["n_candidates_audited"], len(eligible))
        self.assertEqual(len(stability["summary"]), len(eligible))
        self.assertEqual(len(stability["details"]), 10 * len(eligible))

    def test_conditional_risk_uses_independent_paths(self):
        risk = evaluate_conditional_policy_profile_risk(
            base_result=self.result,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=100,
            seed=950,
            min_condition_observations=5,
        )
        self.assertEqual(
            risk["evaluation_status"],
            "independent_sample_not_used_for_alpha_selection",
        )
        self.assertIn("family", risk["risk_summary"])
        self.assertIn("residual_es_975_pct_notional", risk["risk_summary"])

        grouped = risk["tail_contract_group_diagnostics"]
        dated = risk["tail_payment_date_contributions"]
        for row in risk["risk_summary"].itertuples():
            groups = grouped.loc[grouped["penalty"].eq(row.penalty) & grouped["profile"].eq(row.profile)]
            self.assertEqual(len(groups), 8)
            self.assertEqual(groups["n_paths"].sum(), 100)
            self.assertAlmostEqual(groups["global_es_contribution"].sum(), row.residual_es_975)
            dates = dated.loc[dated["penalty"].eq(row.penalty) & dated["profile"].eq(row.profile)]
            self.assertAlmostEqual(dates["contribution_to_global_es"].sum(), row.residual_es_975)
        events = risk["tail_contract_event_decomposition"]
        for row in risk["risk_summary"].itertuples():
            selected = events.loc[
                events["penalty"].eq(row.penalty) & events["profile"].eq(row.profile)
            ]
            self.assertEqual(selected["n_paths"].sum(), 100)
            self.assertAlmostEqual(selected["share_of_tail_probability"].sum(), 1.0)
            self.assertAlmostEqual(selected["contribution_to_es"].sum(), row.residual_es_975)
            missed = selected["coupon_pattern"].str.count("M")
            self.assertTrue(missed.eq(selected["coupons_missed"]).all())

    def test_importance_risk_keeps_financial_weights_frozen(self):
        risk = evaluate_conditional_policy_profile_risk_importance(
            base_result=self.result,
            product=self.product,
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=100,
            seed=951,
            min_condition_observations=5,
        )
        self.assertEqual(risk["portfolio_weights_status"], "frozen_before_risk_evaluation")
        self.assertEqual(
            risk["calibration_status"],
            "not_recalibrated_with_importance_sampling",
        )
        self.assertEqual(
            risk["evaluation_status"],
            "independent_sample_not_used_for_alpha_selection",
        )
        self.assertIn("residual_es_975_pct_notional", risk["risk_summary"])
        self.assertGreater(risk["sampling_diagnostics"]["effective_sample_size"], 0.0)

    def test_conditional_cost_is_weighted_by_node_reach_probability(self):
        expiry = pd.Timestamp("2027-06-22")
        cash = Cash("cash", 0.0, expiry, 100.0)
        call = EuropeanCall("C100", 100.0, expiry, 1.0)
        base = {
            "family": "calls_puts",
            "n_paths": 2,
            "profiles": pd.DataFrame(
                [{"penalty": "l1", "profile": "performance", "solution_index": 0}]
            ),
            "vanillas": [cash, call],
            "results": {"l1": {"solutions": [{"weights": np.array([1.0, 2.0])}]}},
            "feature_table": pd.DataFrame(
                [
                    {"node_index": 0, "decision_date": pd.NaT, "payment_date": expiry, "decision_state": "initial"},
                    {"node_index": 0, "decision_date": pd.NaT, "payment_date": expiry, "decision_state": "initial"},
                ]
            ),
            "visits": pd.DataFrame(
                [{"path_index": 0, "selected_node_index": 0}]
            ),
        }
        snapshot = pd.DataFrame(
            {
                "expiry": [expiry],
                "option_type": ["call"],
                "strike": [100.0],
                "bid": [4.9],
                "ask": [5.1],
            }
        )
        costs = estimate_conditional_policy_transaction_costs(base, snapshot, 100.0)
        row = costs["summary"].iloc[0]
        self.assertTrue(row["cost_complete"])
        self.assertAlmostEqual(
            row["expected_transaction_cost"],
            0.5 * row["all_nodes_cost_upper_bound"],
        )


if __name__ == "__main__":
    unittest.main()
