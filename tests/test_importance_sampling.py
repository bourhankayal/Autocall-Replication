import math
import unittest

import numpy as np
import pandas as pd

from autocall_replication.replication.importance_sampling import (
    bootstrap_expected_shortfall_interval,
    compare_standard_and_importance_risk,
    simulate_gbm_paths_importance,
    weighted_tail_risk_metrics,
)
from autocall_replication.replication.risk import tail_risk_metrics


class ImportanceSamplingTests(unittest.TestCase):
    def test_zero_tilt_has_unit_weights(self):
        simulation = simulate_gbm_paths_importance(
            spot0=100.0,
            start_date="2026-06-22",
            end_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=500,
            seed=123,
            tilts=(0.0,),
            mixture_probabilities=(1.0,),
        )
        np.testing.assert_allclose(simulation["likelihood_weights"], 1.0)
        self.assertAlmostEqual(
            simulation["diagnostics"]["effective_sample_size"], 500.0
        )

    def test_equal_weights_reproduce_standard_risk_metrics(self):
        losses = np.linspace(-5.0, 20.0, 501)
        standard = tail_risk_metrics(losses)
        weighted = weighted_tail_risk_metrics(losses, np.ones(len(losses)))
        for metric in ("mean_loss", "mae", "rmse", "max_loss", "under_replication_rate"):
            self.assertAlmostEqual(weighted[metric], standard[metric], places=10)
        self.assertLess(abs(weighted["es_975"] - standard["es_975"]), 0.1)

    def test_mixture_recovers_terminal_spot_expectation(self):
        simulation = simulate_gbm_paths_importance(
            spot0=100.0,
            start_date="2026-06-22",
            end_date="2027-06-22",
            rate=0.03,
            dividend_yield=0.01,
            vol=0.20,
            n_paths=20_000,
            seed=456,
        )
        dates = simulation["dates"]
        elapsed = (dates[-1] - dates[0]).days / 365.0
        expected = 100.0 * math.exp((0.03 - 0.01) * elapsed)
        weights = simulation["likelihood_weights"]
        terminal = simulation["paths"][:, -1]
        estimate = float(np.sum(weights * terminal) / np.sum(weights))
        self.assertLess(abs(estimate - expected) / expected, 0.01)
        self.assertGreater(simulation["diagnostics"]["effective_sample_ratio"], 0.20)
        self.assertEqual(len(simulation["component_summary"]), 3)

    def test_weighted_es_bootstrap_is_reproducible(self):
        losses = np.arange(1.0, 101.0)
        weights = np.linspace(0.5, 1.5, len(losses))
        left = bootstrap_expected_shortfall_interval(
            losses, likelihood_weights=weights, n_bootstrap=30, seed=99
        )
        right = bootstrap_expected_shortfall_interval(
            losses, likelihood_weights=weights, n_bootstrap=30, seed=99
        )
        self.assertEqual(left, right)
        self.assertLessEqual(left["ci_low"], left["estimate"])
        self.assertGreaterEqual(left["ci_high"], left["estimate"])

    def test_comparison_keeps_estimators_separate(self):
        standard = {
            "family": "full",
            "penalty": "l1",
            "profile": "performance",
            "residual_rmse": 4.0,
            "residual_es_975": 8.0,
            "under_replication_rate": 0.5,
        }
        importance = dict(standard, residual_es_975=8.2)
        comparison = compare_standard_and_importance_risk(
            standard_summary=pd.DataFrame([standard]),
            importance_summary=pd.DataFrame([importance]),
        )
        self.assertEqual(comparison.loc[0, "standard_residual_es_975"], 8.0)
        self.assertEqual(comparison.loc[0, "importance_residual_es_975"], 8.2)
        self.assertAlmostEqual(comparison.loc[0, "difference_residual_es_975"], 0.2)


if __name__ == "__main__":
    unittest.main()
