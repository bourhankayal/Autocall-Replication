import unittest

import numpy as np
import pandas as pd

from autocall_replication.products import AutocallProduct, Cash, EuropeanCall
from autocall_replication.replication.optimization import SolverConfig, solve_replication
from autocall_replication.replication.pathwise_payoff import (
    run_pathwise_penalty_comparison,
    run_pathwise_regularization_path,
)
from autocall_replication.replication.regularization_path import (
    apply_static_performance_filter,
    l0_alpha_max,
    lasso_alpha_max,
    logarithmic_alpha_grid,
    ridge_alpha_grid,
    ridge_alpha_reference,
    remove_duplicate_candidates,
    select_regularization_candidates,
    select_three_profiles_per_penalty,
    solve_penalty_comparison,
    solve_regularization_path,
    train_validation_test_slices,
)


def instruments_for_columns(n_options: int):
    maturity = pd.Timestamp("2027-06-22")
    return [Cash("cash", 0.0, maturity, 100.0)] + [
        EuropeanCall(f"call_{index}", 90.0 + index, maturity, 1.0)
        for index in range(n_options)
    ]


class RegularizationPathTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(123)
        features = rng.normal(size=(60, 3))
        self.A = np.column_stack([np.ones(60), features])
        self.b = 1.5 + 2.0 * features[:, 0] + 0.2 * features[:, 1]
        self.vanillas = instruments_for_columns(3)

    def test_split_is_reproducible_and_keeps_test_non_empty(self):
        slices = train_validation_test_slices(60)
        self.assertEqual(slices["train"], slice(0, 36))
        self.assertEqual(slices["validation"], slice(36, 48))
        self.assertEqual(slices["test"], slice(48, 60))

    def test_alpha_grid_is_strictly_decreasing(self):
        grid = logarithmic_alpha_grid(2.0, n_alphas=7, min_alpha_ratio=1e-3)
        self.assertEqual(len(grid), 7)
        self.assertTrue(np.all(np.diff(grid) < 0.0))
        self.assertAlmostEqual(grid[0], 2.0)
        self.assertAlmostEqual(grid[-1], 0.002)

    def test_ridge_grid_uses_spectral_reference(self):
        reference = ridge_alpha_reference(self.A[:36])
        grid = ridge_alpha_grid(
            reference,
            n_alphas=7,
            min_reference_ratio=1e-4,
            max_reference_ratio=1e2,
        )

        self.assertGreater(reference, 0.0)
        self.assertTrue(np.all(np.diff(grid) < 0.0))
        self.assertAlmostEqual(grid[0], reference * 1e2)
        self.assertAlmostEqual(grid[-1], reference * 1e-4)

    def test_alpha_max_sets_all_penalized_weights_to_exact_zero(self):
        alpha_max = lasso_alpha_max(self.A[:36], self.b[:36])
        result = solve_replication(
            self.A[:36],
            self.b[:36],
            SolverConfig(
                solver="fista",
                penalty="l1",
                alpha=alpha_max,
                tolerance=1e-9,
            ),
        )
        self.assertTrue(result.converged)
        self.assertEqual(np.count_nonzero(result.weights[1:]), 0)

    def test_l0_reference_starts_with_an_empty_penalized_support(self):
        reference = l0_alpha_max(self.A[:36], self.b[:36])
        result = solve_replication(
            self.A[:36],
            self.b[:36],
            SolverConfig(
                solver="proximal",
                penalty="l0",
                alpha=reference,
                tolerance=1e-9,
            ),
        )

        self.assertTrue(result.converged)
        self.assertEqual(np.count_nonzero(result.weights[1:]), 0)

    def test_l0_regularization_path_keeps_the_final_test_closed(self):
        result = solve_regularization_path(
            self.A,
            self.b,
            self.vanillas,
            penalty="l0",
            n_alphas=6,
            min_alpha_ratio=1e-3,
            tolerance=1e-8,
        )

        self.assertEqual(result["test_status"], "reserved_not_evaluated")
        self.assertEqual(result["alpha_scale_kind"], "l0_hard_threshold_reference")
        self.assertFalse(any(column.startswith("test_") for column in result["table"]))
        self.assertEqual(result["table"].iloc[0]["n_options_active"], 0)

    def test_path_reserves_test_and_builds_pareto_frontier(self):
        result = solve_regularization_path(
            self.A,
            self.b,
            self.vanillas,
            n_alphas=8,
            min_alpha_ratio=1e-3,
            tolerance=1e-8,
        )
        table = result["table"]

        self.assertEqual(result["test_status"], "reserved_not_evaluated")
        self.assertEqual(result["split"]["n_train"], 36)
        self.assertEqual(result["split"]["n_validation"], 12)
        self.assertEqual(result["split"]["n_test"], 12)
        self.assertFalse(any(column.startswith("test_") for column in table.columns))
        self.assertEqual(table.iloc[0]["n_options_active"], 0)
        self.assertGreaterEqual(
            table.iloc[-1]["n_options_active"],
            table.iloc[0]["n_options_active"],
        )
        self.assertTrue(table["is_pareto"].any())

        pareto = table.loc[table["is_pareto"]]
        for _, candidate in pareto.iterrows():
            dominated = table.loc[
                table["converged"]
                & (table["validation_rmse"] <= candidate["validation_rmse"])
                & (table["n_options_active"] <= candidate["n_options_active"])
                & (
                    (table["validation_rmse"] < candidate["validation_rmse"])
                    | (table["n_options_active"] < candidate["n_options_active"])
                )
            ]
            self.assertTrue(dominated.empty)

    def test_warm_start_reproduces_cold_solution(self):
        alpha_max = lasso_alpha_max(self.A, self.b)
        high = solve_replication(
            self.A,
            self.b,
            SolverConfig(solver="fista", penalty="l1", alpha=alpha_max * 0.5),
        )
        cold = solve_replication(
            self.A,
            self.b,
            SolverConfig(solver="fista", penalty="l1", alpha=alpha_max * 0.1),
        )
        warm = solve_replication(
            self.A,
            self.b,
            SolverConfig(solver="fista", penalty="l1", alpha=alpha_max * 0.1),
            initial_weights=high.weights,
        )

        self.assertTrue(cold.converged)
        self.assertTrue(warm.converged)
        np.testing.assert_allclose(warm.weights, cold.weights, rtol=2e-4, atol=2e-4)

    def test_penalty_comparison_keeps_ratio_fixed_and_test_reserved(self):
        result = solve_penalty_comparison(
            self.A,
            self.b,
            self.vanillas,
            n_alphas=5,
            min_alpha_ratio=1e-2,
            ridge_min_alpha_ratio=1e-2,
            ridge_max_alpha_ratio=1e1,
            tolerance=1e-8,
        )

        self.assertEqual(result["test_status"], "reserved_not_evaluated")
        self.assertEqual(set(result["results"]), {"l1", "l2", "elastic_net"})
        self.assertEqual(len(result["table"]), 15)
        self.assertFalse(
            any(column.startswith("test_") for column in result["table"].columns)
        )
        self.assertEqual(result["elastic_net_l1_ratio"], 0.5)
        self.assertIsNone(result["results"]["l2"]["alpha_max"])
        self.assertEqual(
            result["results"]["l2"]["alpha_scale_kind"],
            "ridge_spectral_reference",
        )
        self.assertEqual(
            result["candidate_filters"]["pareto_scope"], "within_penalty"
        )
        self.assertTrue(
            result["candidates"]["n_options_active"].between(2, 100).all()
        )
        self.assertEqual(
            set(result["profiles"]["profile"]),
            {"performance", "compromise", "parsimony"},
        )
        self.assertEqual(
            result["profiles"].groupby("penalty").size().to_dict(),
            {"elastic_net": 3, "l1": 3, "l2": 3},
        )
        self.assertIn("duplicate_type", result["duplicate_report"].columns)
        self.assertEqual(
            set(result["profile_coverage"]["penalty"]),
            {"l1", "l2", "elastic_net"},
        )

    def test_static_filter_and_duplicate_report_are_auditable(self):
        table = pd.DataFrame(
            {
                "penalty": ["l1", "l1", "l1"],
                "solution_index": [0, 1, 2],
                "is_candidate": [True, True, True],
                "alpha": [1.0, 0.5, 0.25],
                "alpha_relative": [1.0, 0.5, 0.25],
                "validation_rmse": [1.0, 1.0, 1.0],
                "n_options_active": [2, 2, 2],
                "l1_ratio": [np.nan, np.nan, np.nan],
            }
        )
        residuals = np.array([1.0, -1.0, 1.0, -1.0])
        weights = [
            np.array([1.0, 0.5, 0.5]),
            np.array([1.0, 0.5, 0.5]),
            np.array([1.0, 0.49, 0.51]),
        ]
        results = {
            "l1": {
                "solutions": [
                    {
                        "weights": weight,
                        "validation_residuals": residuals.copy(),
                        "validation_predictions": residuals.copy(),
                    }
                    for weight in weights
                ]
            }
        }

        filtered = apply_static_performance_filter(
            table,
            results,
            n_bootstrap=200,
            seed=7,
        )
        deduplicated, report = remove_duplicate_candidates(filtered, results)
        profiles = select_three_profiles_per_penalty(deduplicated)

        self.assertTrue(filtered["passes_static_performance"].all())
        self.assertEqual(
            report["duplicate_type"].tolist(),
            ["strict_duplicate", "quasi_strict_duplicate"],
        )
        self.assertEqual(deduplicated["is_candidate_after_duplicates"].sum(), 1)
        self.assertEqual(len(profiles), 3)
        self.assertTrue(profiles["profile_reuses_candidate"].all())

    def test_candidate_filters_and_pareto_are_applied_within_each_penalty(self):
        table = pd.DataFrame(
            {
                "penalty": ["l1", "l1", "l1", "l1", "elastic_net"],
                "converged": [True, True, True, False, True],
                "validation_rmse": [3.0, 2.8, 2.0, 1.0, 2.5],
                "n_options_active": [1, 20, 101, 10, 20],
                "alpha": [1.0, 0.5, 0.1, 0.05, 0.5],
                "alpha_relative": [1.0, 0.5, 0.1, 0.05, 0.5],
                "l1_ratio": [np.nan, np.nan, np.nan, np.nan, 0.5],
            }
        )
        selected = select_regularization_candidates(table)

        self.assertEqual(
            selected["selection_status"].tolist(),
            [
                "rejected_fewer_than_minimum_options",
                "candidate",
                "rejected_more_than_maximum_options",
                "rejected_non_converged",
                "candidate",
            ],
        )
        self.assertTrue(selected.loc[1, "is_candidate"])
        self.assertTrue(selected.loc[4, "is_candidate"])

    def test_dominated_candidate_is_rejected_only_inside_its_penalty(self):
        table = pd.DataFrame(
            {
                "penalty": ["l1", "l1", "elastic_net"],
                "converged": [True, True, True],
                "validation_rmse": [2.5, 2.7, 2.0],
                "n_options_active": [30, 40, 20],
            }
        )
        selected = select_regularization_candidates(table)

        self.assertTrue(selected.loc[0, "is_candidate"])
        self.assertEqual(
            selected.loc[1, "selection_status"],
            "rejected_dominated_within_penalty",
        )
        self.assertTrue(selected.loc[2, "is_candidate"])

    def test_pathwise_adapter_is_reproducible(self):
        kwargs = dict(
            product=AutocallProduct(coupon_rate=0.02, down_barrier=0.70),
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls",
            n_paths=30,
            n_alphas=5,
            min_alpha_ratio=1e-2,
            seed=321,
        )
        first = run_pathwise_regularization_path(**kwargs)
        second = run_pathwise_regularization_path(**kwargs)

        pd.testing.assert_frame_equal(first["table"], second["table"])
        self.assertEqual(first["test_status"], "reserved_not_evaluated")

    def test_pathwise_penalty_comparison_reuses_one_dataset(self):
        result = run_pathwise_penalty_comparison(
            product=AutocallProduct(coupon_rate=0.02, down_barrier=0.70),
            spot0=100.0,
            valuation_date="2026-06-20",
            maturity_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            family="calls",
            n_paths=30,
            n_alphas=3,
            min_alpha_ratio=1e-2,
            ridge_min_alpha_ratio=1e-2,
            ridge_max_alpha_ratio=1e1,
            seed=321,
        )

        self.assertEqual(result["n_paths"], 30)
        self.assertEqual(len(result["table"]), 9)
        self.assertEqual(result["test_status"], "reserved_not_evaluated")
        self.assertTrue(
            all(policy["family"] == "calls" for policy in result["candidate_policies"])
        )
        self.assertTrue(
            all(policy["family"] == "calls" for policy in result["profile_policies"])
        )


if __name__ == "__main__":
    unittest.main()
