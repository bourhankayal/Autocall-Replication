import math
import unittest

import numpy as np
import pandas as pd
import autocall_replication.replication.importance_sampling as importance_module

from autocall_replication.replication.importance_sampling import (
    bootstrap_expected_shortfall_interval,
    compare_standard_and_importance_risk,
    compare_fixed_policy_importance_mixtures,
    simulate_gbm_paths_importance,
    tail_scenario_decomposition,
    weighted_tail_risk_metrics,
)
from autocall_replication.replication.risk import (
    empirical_var_es,
    exclusive_autocall_regimes,
    tail_concentration_analysis,
    tail_regime_decomposition,
    tail_risk_metrics,
)


class ImportanceSamplingTests(unittest.TestCase):
    def test_exclusive_contractual_regimes_cover_each_path_once(self):
        called = np.array([True, False, False, True])
        barrier_hit = np.array([False, False, True, True])
        regimes = exclusive_autocall_regimes(called, barrier_hit)
        coverage = np.sum(np.column_stack(list(regimes.values())), axis=1)
        np.testing.assert_array_equal(coverage, np.ones(4))

    def test_tail_concentration_curve_is_monotone_and_complete(self):
        losses = np.arange(100.0)
        result = tail_concentration_analysis(
            losses,
            levels=(0.975, 0.99),
            curve_fractions=(0.10, 0.50, 1.0),
        )
        curve = result["curve"].loc[result["curve"]["level"] == 0.975]
        self.assertTrue(curve["positive_tail_loss_share"].is_monotonic_increasing)
        self.assertAlmostEqual(curve.iloc[-1]["positive_tail_loss_share"], 1.0)
        summary = result["summary"].set_index("level")
        self.assertGreater(summary.loc[0.975, "es_99_to_es_975_ratio"], 1.0)

    def test_exclusive_regime_es_shares_add_to_one(self):
        losses = np.arange(100.0)
        regimes = {
            "low": losses < 50.0,
            "high": losses >= 50.0,
        }
        decomposition = tail_regime_decomposition(losses, regimes, level=0.975)
        self.assertAlmostEqual(decomposition["share_of_tail_probability"].sum(), 1.0)
        self.assertAlmostEqual(decomposition["share_of_es"].sum(), 1.0)

    def test_empirical_es_uses_exact_tail_mass_at_var_atom(self):
        losses = np.array([0.0] * 97 + [10.0] * 3)
        risk = empirical_var_es(losses, level=0.975)
        self.assertEqual(risk["var"], 10.0)
        self.assertAlmostEqual(risk["es"], 10.0)
        self.assertAlmostEqual(
            float(np.sum(risk["tail_probability_contributions"])), 0.025
        )

    def test_weighted_and_unweighted_exact_es_match_for_unit_weights(self):
        losses = np.array([-2.0, 0.0, 1.0, 1.0, 5.0, 9.0])
        standard = empirical_var_es(losses, level=0.75)
        weighted = empirical_var_es(
            losses, level=0.75, likelihood_weights=np.ones(len(losses))
        )
        self.assertAlmostEqual(standard["var"], weighted["var"])
        self.assertAlmostEqual(standard["es"], weighted["es"])

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
        self.assertAlmostEqual(
            simulation["diagnostics"]["effective_sample_ratio"], 1.0
        )
        self.assertAlmostEqual(
            simulation["diagnostics"]["maximum_normalized_weight"], 1.0 / 500.0
        )
        self.assertAlmostEqual(
            simulation["diagnostics"]["normalized_weight_entropy_ratio"], 1.0
        )

    def test_tail_decomposition_reports_exact_tail_mass(self):
        losses = np.arange(100.0)
        conditions = {
            "all": np.ones(100, dtype=bool),
            "upper_half": losses >= 50.0,
        }
        decomposition = tail_scenario_decomposition(
            losses,
            np.ones(100),
            conditions,
            level=0.975,
        ).set_index("condition")
        self.assertAlmostEqual(decomposition.loc["all", "share_of_es_tail"], 1.0)
        self.assertAlmostEqual(
            decomposition.loc["upper_half", "share_of_es_tail"], 1.0
        )
        # Queue exacte de 2,5 observations : 99, 98 et la moitié de 97.
        self.assertAlmostEqual(decomposition.loc["all", "contribution_to_es"], 98.2)

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


def test_is_mixture_is_chosen_for_worst_fixed_policy_not_lowest_es(monkeypatch):
    calls = []

    def fake_design(*, n_paths, seed, sampling_method, tilts, **kwargs):
        calls.append((sampling_method, tuple(tilts), seed))
        A = np.zeros((n_paths, 2))
        if sampling_method == "standard_mc":
            b = np.full(n_paths, 10.0 + seed)
            ess_ratio = 1.0
        elif tuple(tilts) == (0.0, -1.0):
            b = np.full(n_paths, 10.0 + 0.1 * seed)
            A[:, 1] = -5.0 * seed
            ess_ratio = 0.90
        else:
            b = np.full(n_paths, 10.0 + 0.5 * seed)
            ess_ratio = 0.80
        return {
            "A": A, "b": b, "likelihood_weights": np.ones(n_paths),
            "sampling_diagnostics": {
                "effective_sample_ratio": ess_ratio,
                "maximum_normalized_weight": 1.0 / n_paths,
            },
        }

    monkeypatch.setattr(importance_module, "build_conditional_policy_sampling_design", fake_design)
    policies = [
        {"penalty": "l1", "objective": "penalized_es", "profile": "compromise",
         "weights": np.array([0.0, 0.0])},
        {"penalty": "l2", "objective": "constrained_es", "profile": "compromise",
         "weights": np.array([0.0, 1.0])},
    ]
    candidates = [
        {"tilts": (0.0, -1.0), "mixture_probabilities": (0.7, 0.3)},
        {"tilts": (0.0, -2.0), "mixture_probabilities": (0.7, 0.3)},
    ]
    result = compare_fixed_policy_importance_mixtures(
        base_result={}, product=None, spot0=100.0, valuation_date="2026-01-01",
        maturity_date="2026-12-31", rate=0.03, dividend_yield=0.01, vol=0.2,
        policies=policies, candidates=candidates, seeds=(1, 2, 3),
        n_paths=100, es_level=0.9,
    )
    assert result["recommended_candidate_index"] == 1
    assert len(calls) == 9  # un design par graine et mélange, partagé entre politiques
    summary = result["summary"].set_index("candidate_index")
    assert summary.loc[0, "worst_precision_ratio_to_mc"] > 1.0
    assert summary.loc[1, "worst_precision_ratio_to_mc"] < 1.0
    assert result["policy_summary"]["policy_key"].nunique() == 2
    assert "es_mean_difference_to_mc" in result["policy_summary"]
    assert "test_es" not in result["details"]
    assert summary.loc[-1, "worst_precision_ratio_to_mc"] == 1.0

    only_worse_is = compare_fixed_policy_importance_mixtures(
        base_result={}, product=None, spot0=100.0, valuation_date="2026-01-01",
        maturity_date="2026-12-31", rate=0.03, dividend_yield=0.01, vol=0.2,
        policies=policies, candidates=candidates[:1], seeds=(1, 2, 3),
        n_paths=100, es_level=0.9,
    )
    assert only_worse_is["recommended_candidate_index"] == -1
    assert only_worse_is["summary"].set_index("candidate_index").loc[-1, "recommended"]


if __name__ == "__main__":
    unittest.main()
