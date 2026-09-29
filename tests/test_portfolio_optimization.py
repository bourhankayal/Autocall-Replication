import unittest

import numpy as np
import pandas as pd

from autocall_replication.products import Cash, EuropeanCall
from autocall_replication.replication.common import fit_linear
from autocall_replication.replication.optimization import (
    SolverConfig,
    available_solvers,
    solve_replication,
)
from autocall_replication.replication.portfolio_diagnostics import (
    format_grouped_portfolio_metrics,
    format_portfolio_metrics,
    grouped_portfolio_weight_metrics,
    portfolio_metrics_summary,
    portfolio_weight_metrics,
)


def sample_instruments():
    maturity = pd.Timestamp("2027-06-22")
    return [
        Cash("cash", 0.0, maturity, 100.0),
        EuropeanCall("call_90", 90.0, maturity, 1.0),
        EuropeanCall("call_100", 100.0, maturity, 1.0),
        EuropeanCall("call_110", 110.0, maturity, 1.0),
    ]


class PortfolioDiagnosticsTests(unittest.TestCase):
    def test_metrics_separate_cash_and_ignore_numerical_residuals(self):
        metrics = portfolio_weight_metrics(
            sample_instruments(),
            np.array([0.8, 2.0, -1.0, 1e-7]),
            active_threshold=1e-6,
        )

        self.assertEqual(metrics["n_instruments_total"], 4)
        self.assertEqual(metrics["n_instruments_active"], 3)
        self.assertEqual(metrics["n_cash_active"], 1)
        self.assertEqual(metrics["n_options_active"], 2)
        self.assertEqual(metrics["n_options_long"], 1)
        self.assertEqual(metrics["n_options_short"], 1)
        self.assertAlmostEqual(metrics["sum_abs_option_weights"], 3.0)
        self.assertAlmostEqual(metrics["top_1_option_concentration"], 2.0 / 3.0)
        self.assertAlmostEqual(metrics["top_5_option_concentration"], 1.0)

    def test_weight_equal_to_threshold_is_inactive(self):
        metrics = portfolio_weight_metrics(
            sample_instruments(),
            np.array([0.0, 1e-6, 0.0, 0.0]),
            active_threshold=1e-6,
        )
        self.assertEqual(metrics["n_instruments_active"], 0)

    def test_all_zero_portfolio_has_zero_concentration(self):
        metrics = portfolio_weight_metrics(sample_instruments(), np.zeros(4))

        self.assertEqual(metrics["n_options_active"], 0)
        self.assertEqual(metrics["max_abs_option_weight"], 0.0)
        self.assertEqual(metrics["top_1_option_concentration"], 0.0)
        self.assertEqual(metrics["top_5_option_concentration"], 0.0)

    def test_invalid_weights_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "nombre d'instruments"):
            portfolio_weight_metrics(sample_instruments(), np.array([1.0]))
        with self.assertRaisesRegex(ValueError, "finis"):
            portfolio_weight_metrics(
                sample_instruments(), np.array([1.0, np.nan, 0.0, 0.0])
            )
        with self.assertRaisesRegex(ValueError, "active_threshold"):
            portfolio_weight_metrics(
                sample_instruments(), np.zeros(4), active_threshold=-1.0
            )

    def test_grouped_metrics_return_one_row_per_portfolio(self):
        table = pd.DataFrame(
            {
                "date": ["2026-09-22"] * 4 + ["2027-06-22"] * 4,
                "state": ["alive"] * 4 + ["barrier_hit"] * 4,
                "kind": ["Cash", "EuropeanCall", "EuropeanCall", "EuropeanCall"] * 2,
                "weight": [1.0, 2.0, 0.0, 0.0, 1.0, 0.0, -3.0, 0.0],
            }
        )
        result = grouped_portfolio_weight_metrics(table)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["n_options_active"].tolist(), [1, 1])

    def test_readable_metrics_explain_sparsity_without_losing_raw_metrics(self):
        metrics = portfolio_weight_metrics(
            sample_instruments(), np.array([0.8, 2.0, -1.0, 1e-7])
        )
        readable = format_portfolio_metrics(metrics)
        summary = portfolio_metrics_summary(metrics)

        self.assertEqual(
            readable.columns.tolist(),
            ["Catégorie", "Indicateur", "Valeur", "Interprétation"],
        )
        self.assertIn("2 / 3 options actives", summary)
        self.assertIn("1 longues | 1 courtes", summary)
        self.assertEqual(metrics["n_options_active"], 2)

    def test_grouped_metrics_have_a_compact_readable_view(self):
        raw = pd.DataFrame(
            {
                "date": ["2027-06-22"],
                "state": ["alive"],
                "n_options_total": [10],
                "n_options_active": [2],
                "option_active_ratio": [0.2],
                "n_options_long": [1],
                "n_options_short": [1],
                "sum_abs_option_weights": [3.0],
                "net_option_weight": [1.0],
                "top_5_option_concentration": [0.8],
                "net_cash_weight": [0.5],
            }
        )
        readable = format_grouped_portfolio_metrics(raw)

        self.assertEqual(readable.loc[0, "Taux actif (%)"], 20.0)
        self.assertEqual(readable.loc[0, "Top 5 (%)"], 80.0)


class OptimizationInterfaceTests(unittest.TestCase):
    def test_legacy_interface_reproduces_fit_linear(self):
        A = np.array([[1.0, 0.0], [1.0, 1.0], [1.0, 2.0], [1.0, 3.0]])
        b = np.array([1.0, 2.0, 2.5, 4.0])
        config = SolverConfig(solver="legacy", penalty="l2", alpha=1e-4)

        expected = fit_linear(A, b, penalty="l2", alpha=1e-4)
        result = solve_replication(A, b, config)

        np.testing.assert_allclose(result.weights, expected, rtol=0.0, atol=0.0)
        self.assertTrue(result.converged)
        self.assertEqual(result.metadata()["solver"], "legacy")

    def test_unknown_solver_and_invalid_dimensions_are_rejected(self):
        self.assertEqual(available_solvers(), ("legacy", "fista", "proximal"))
        with self.assertRaisesRegex(ValueError, "inconnu"):
            solve_replication(
                np.eye(2), np.ones(2), SolverConfig(solver="unknown")
            )
        with self.assertRaisesRegex(ValueError, "même nombre de lignes"):
            solve_replication(np.eye(2), np.ones(3))

    def test_fista_l1_produces_exact_zeros_and_preserves_unpenalized_cash(self):
        A = np.eye(4)
        b = np.array([1.0, 0.01, 0.0, 2.0])
        result = solve_replication(
            A,
            b,
            SolverConfig(
                solver="fista",
                penalty="l1",
                alpha=0.1,
                scale_features=False,
                tolerance=1e-10,
            ),
        )

        self.assertTrue(result.converged)
        self.assertGreater(result.n_iterations, 0)
        self.assertTrue(np.isfinite(result.objective_value))
        self.assertEqual(result.weights[1], 0.0)
        self.assertEqual(result.weights[2], 0.0)
        self.assertAlmostEqual(result.weights[0], 1.0, places=7)
        self.assertAlmostEqual(result.weights[3], 1.6, places=7)

    def test_stronger_fista_l1_regularization_selects_fewer_features(self):
        A = np.eye(5)
        b = np.array([1.0, 0.2, 0.5, 1.0, 2.0])
        common = dict(
            solver="fista",
            penalty="l1",
            scale_features=False,
            tolerance=1e-10,
        )
        weak = solve_replication(A, b, SolverConfig(alpha=0.02, **common))
        strong = solve_replication(A, b, SolverConfig(alpha=0.30, **common))

        weak_active = np.count_nonzero(weak.weights[1:])
        strong_active = np.count_nonzero(strong.weights[1:])
        self.assertLess(strong_active, weak_active)

    def test_fista_supports_elastic_net(self):
        A = np.eye(4)
        b = np.array([1.0, 0.01, 0.5, 2.0])
        result = solve_replication(
            A,
            b,
            SolverConfig(
                solver="fista",
                penalty="elastic_net",
                alpha=0.1,
                l1_ratio=0.5,
                scale_features=False,
                tolerance=1e-10,
            ),
        )

        self.assertTrue(result.converged)
        self.assertEqual(result.weights[1], 0.0)
        self.assertEqual(result.penalty, "elastic_net")

    def test_fista_supports_ridge_without_penalizing_cash(self):
        A = np.eye(4)
        b = np.array([1.0, 0.5, 1.0, 2.0])
        result = solve_replication(
            A,
            b,
            SolverConfig(
                solver="fista",
                penalty="l2",
                alpha=0.5,
                scale_features=False,
                tolerance=1e-10,
            ),
        )

        self.assertTrue(result.converged)
        self.assertAlmostEqual(result.weights[0], 1.0, places=7)
        self.assertTrue(np.all(np.abs(result.weights[1:]) < np.abs(b[1:])))
        self.assertEqual(result.penalty, "l2")

    def test_penalized_l0_selects_a_support_without_fixing_its_size(self):
        A = np.eye(4)
        b = np.array([1.0, 0.2, 0.5, 2.0])
        result = solve_replication(
            A,
            b,
            SolverConfig(
                solver="proximal",
                penalty="l0",
                alpha=0.1,
                scale_features=False,
                tolerance=1e-10,
            ),
        )

        self.assertTrue(result.converged)
        self.assertAlmostEqual(result.weights[0], 1.0, places=7)
        self.assertEqual(result.weights[1], 0.0)
        self.assertEqual(result.weights[2], 0.0)
        self.assertAlmostEqual(result.weights[3], 2.0, places=7)

    def test_weighted_l1_penalizes_expensive_lines_more_strongly(self):
        A = np.eye(3)
        b = np.array([1.0, 0.5, 0.5])
        result = solve_replication(
            A,
            b,
            SolverConfig(
                solver="fista",
                penalty="weighted_l1",
                alpha=0.1,
                penalty_weights=(0.0, 2.0, 0.25),
                scale_features=False,
                tolerance=1e-10,
            ),
        )

        self.assertTrue(result.converged)
        self.assertEqual(result.weights[1], 0.0)
        self.assertGreater(result.weights[2], 0.0)

    def test_fixed_and_proportional_costs_combine_l0_and_weighted_l1(self):
        A = np.eye(3)
        b = np.array([1.0, 0.3, 1.0])
        result = solve_replication(
            A,
            b,
            SolverConfig(
                solver="proximal",
                penalty="fixed_proportional",
                alpha=0.1,
                penalty_weights=(0.0, 1.0, 1.0),
                fixed_cost_strength=0.1,
                proportional_cost_strength=0.25,
                scale_features=False,
                tolerance=1e-10,
            ),
        )

        self.assertTrue(result.converged)
        self.assertEqual(result.weights[1], 0.0)
        self.assertGreater(result.weights[2], 0.0)

    def test_fista_rejects_unsupported_penalties_and_invalid_indices(self):
        with self.assertRaisesRegex(ValueError, "uniquement"):
            solve_replication(
                np.eye(2),
                np.ones(2),
                SolverConfig(solver="fista", penalty="huber"),
            )
        with self.assertRaisesRegex(ValueError, "hors des colonnes"):
            solve_replication(
                np.eye(2),
                np.ones(2),
                SolverConfig(
                    solver="fista",
                    penalty="l1",
                    unpenalized_indices=(2,),
                ),
            )


if __name__ == "__main__":
    unittest.main()
