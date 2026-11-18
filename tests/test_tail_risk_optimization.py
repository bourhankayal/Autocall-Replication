import unittest

import numpy as np

from autocall_replication.replication.tail_risk_optimization import (
    TailRiskOptimizationConfig,
    run_es_budget_frontier,
    run_four_tail_risk_experiments,
    run_penalized_es_sensitivity,
    rmse_sparse_alpha_reference,
    rmse_ridge_alpha_reference,
    solve_tail_risk_replication,
)


class TailRiskOptimizationTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(123)
        self.A = np.column_stack([np.ones(300), rng.normal(size=(300, 2))])
        self.b = 1.5 + self.A[:, 1] - 0.5 * self.A[:, 2]
        self.b[-12:] += np.linspace(2.0, 8.0, 12)

    def test_rmse_solver_returns_finite_weights(self):
        result = solve_tail_risk_replication(
            self.A,
            self.b,
            TailRiskOptimizationConfig(
                objective="rmse",
                penalty="l2",
                alpha=1e-4,
                unpenalized_indices=(0,),
            ),
        )
        self.assertTrue(np.all(np.isfinite(result.weights)))
        self.assertTrue(np.isfinite(result.expected_shortfall))
        self.assertLess(result.rmse, np.std(self.b))

    def test_ridge_alpha_reference_is_positive_crossover_scale(self):
        weights, *_ = np.linalg.lstsq(self.A, self.b, rcond=None)
        reference = rmse_ridge_alpha_reference(
            self.A, self.b, weights, unpenalized_indices=(0,)
        )
        self.assertTrue(np.isfinite(reference))
        self.assertGreater(reference, 0.0)

    def test_rmse_alpha_reference_matches_cash_only_kkt_threshold(self):
        reference = rmse_sparse_alpha_reference(
            self.A, self.b, l1_ratio=0.5, unpenalized_indices=(0,)
        )
        residual = self.b - np.mean(self.b)
        gradient = self.A[:, 1:].T @ residual / (len(self.b) * np.sqrt(np.mean(residual**2)))
        self.assertAlmostEqual(reference, np.max(np.abs(gradient)) / 0.5)
        self.assertGreater(reference, 0.0)

    def test_rmse_alpha_reference_uses_weighted_original_features(self):
        weighted = rmse_sparse_alpha_reference(
            self.A, self.b, l1_ratio=1.0,
            unpenalized_indices=(0,), sample_weights=np.linspace(0.5, 1.5, len(self.b)),
        )
        rescaled = rmse_sparse_alpha_reference(
            self.A * np.array([1.0, 10.0, 1.0]), self.b,
            l1_ratio=1.0, unpenalized_indices=(0,),
            sample_weights=np.linspace(0.5, 1.5, len(self.b)),
        )
        self.assertNotAlmostEqual(weighted, rescaled)

    def test_es_constraint_is_enforced_on_calibration_sample(self):
        baseline = solve_tail_risk_replication(
            self.A,
            self.b,
            TailRiskOptimizationConfig(
                objective="rmse",
                penalty="l2",
                alpha=1e-4,
                unpenalized_indices=(0,),
            ),
        )
        budget = 0.9 * baseline.expected_shortfall
        constrained = solve_tail_risk_replication(
            self.A,
            self.b,
            TailRiskOptimizationConfig(
                objective="constrained_es",
                penalty="l2",
                alpha=1e-4,
                es_budget=budget,
                unpenalized_indices=(0,),
            ),
            initial_weights=baseline.weights,
        )
        self.assertTrue(constrained.converged)
        self.assertTrue(constrained.feasible)
        self.assertLessEqual(constrained.expected_shortfall, budget + 1e-5)

    def test_four_experiments_use_common_independent_evaluation(self):
        result = run_four_tail_risk_experiments(
            standard_A=self.A[:180],
            standard_b=self.b[:180],
            importance_A=self.A[60:240],
            importance_b=self.b[60:240],
            importance_weights=np.linspace(0.5, 1.5, 180),
            evaluation_A=self.A[240:],
            evaluation_b=self.b[240:],
            penalty="l2",
            alpha=1e-4,
            es_budget=10.0,
            unpenalized_indices=(0,),
        )
        summary = result["summary"]
        self.assertEqual(len(summary), 4)
        self.assertEqual(set(summary["calibration_sampling"]), {"standard_mc", "importance_sampling"})
        self.assertEqual(set(summary["risk_control"]), {"rmse_only", "es_constraint"})
        self.assertIn("n_active_coefficients", summary.columns)

    def test_external_hyperparameter_frontiers_do_not_select_on_final_sample(self):
        penalized = run_penalized_es_sensitivity(
            A=self.A,
            b=self.b,
            lambda_values=(0.0, 0.1),
            penalty="l2",
            alpha=1e-4,
            unpenalized_indices=(0,),
        )
        constrained = run_es_budget_frontier(
            A=self.A,
            b=self.b,
            budgets=(8.0, 10.0),
            penalty="l2",
            alpha=1e-4,
            unpenalized_indices=(0,),
        )
        self.assertEqual(len(penalized["summary"]), 2)
        self.assertEqual(len(constrained["summary"]), 2)
        self.assertEqual(
            penalized["selection_status"],
            "research_grid_not_selected_on_final_sample",
        )
        self.assertEqual(
            constrained["selection_status"],
            "research_grid_not_selected_on_final_sample",
        )
        self.assertIn("n_active_coefficients", penalized["summary"].columns)
        self.assertIn("n_active_coefficients", constrained["summary"].columns)

    def test_nonconvex_penalty_is_explicitly_rejected(self):
        with self.assertRaisesRegex(ValueError, "pénalités convexes"):
            solve_tail_risk_replication(
                self.A,
                self.b,
                TailRiskOptimizationConfig(objective="rmse", penalty="l0"),
            )


if __name__ == "__main__":
    unittest.main()
