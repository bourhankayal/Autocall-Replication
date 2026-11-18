"""Optimisation pathwise de la réplication avec contrôle explicite de l'ES.

Ce module reste volontairement séparé du solveur historique. Il permet de
comparer, à architecture de portefeuille identique, une calibration standard
et une calibration par importance sampling, avec ou sans contrainte de risque
de queue. Une ligne de ``A`` représente une trajectoire complète et ``b-Aw``
est le shortfall actualisé de l'émetteur : une valeur positive est une perte.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .risk import empirical_var_es


TailObjective = Literal["rmse", "penalized_es", "constrained_es"]
SUPPORTED_CONVEX_PENALTIES = ("l1", "l2", "elastic_net")


def rmse_sparse_alpha_reference(
    A: np.ndarray,
    b: np.ndarray,
    *,
    l1_ratio: float,
    unpenalized_indices: tuple[int, ...] = (),
    sample_weights: np.ndarray | None = None,
) -> float:
    """Alpha annulant les options pour RMSE + alpha * pénalité Elastic Net.

    La référence est calculée dans les coordonnées des poids financiers que
    pénalise ``solve_tail_risk_replication``. Elle ne peut pas être remplacée
    par l'alpha du solveur quadratique, dont la perte et l'échelle diffèrent.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape[0] != len(b) or A.shape[1] == 0:
        raise ValueError("A et b doivent définir une régression non vide.")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(b)):
        raise ValueError("A et b doivent être finis.")
    if not 0.0 < l1_ratio <= 1.0:
        raise ValueError("l1_ratio doit appartenir à ]0, 1].")
    cash_indices = tuple(int(index) for index in unpenalized_indices)
    if len(set(cash_indices)) != len(cash_indices) or any(
        index < 0 or index >= A.shape[1] for index in cash_indices
    ):
        raise ValueError("Indices non pénalisés invalides.")
    if sample_weights is None:
        probabilities = np.full(len(b), 1.0 / len(b))
    else:
        weights = np.asarray(sample_weights, dtype=float).reshape(-1)
        if weights.shape != b.shape or not np.all(np.isfinite(weights)) or np.any(weights < 0):
            raise ValueError("sample_weights doit contenir un poids positif par trajectoire.")
        if float(weights.sum()) <= 0.0:
            raise ValueError("La somme des poids doit être strictement positive.")
        probabilities = weights / weights.sum()
    residual = b.copy()
    if cash_indices:
        root_probabilities = np.sqrt(probabilities)
        cash_matrix = A[:, cash_indices]
        cash_weights, *_ = np.linalg.lstsq(
            cash_matrix * root_probabilities[:, None],
            b * root_probabilities,
            rcond=None,
        )
        residual -= cash_matrix @ cash_weights
    rmse = float(np.sqrt(np.sum(probabilities * residual**2)))
    if rmse <= 1e-12:
        raise ValueError("La RMSE de référence est nulle : aucun alpha sparse identifiable.")
    option_mask = np.ones(A.shape[1], dtype=bool)
    option_mask[list(cash_indices)] = False
    if not np.any(option_mask):
        raise ValueError("La base ne contient aucun instrument pénalisé.")
    gradient = A[:, option_mask].T @ (probabilities * residual) / rmse
    alpha_reference = float(np.max(np.abs(gradient)) / l1_ratio)
    if not np.isfinite(alpha_reference) or alpha_reference <= 0.0:
        raise ValueError("La référence alpha RMSE doit être finie et positive.")
    return alpha_reference


def rmse_ridge_alpha_reference(
    A: np.ndarray,
    b: np.ndarray,
    reference_weights: np.ndarray,
    *,
    unpenalized_indices: tuple[int, ...] = (),
) -> float:
    """Crossover scale for RMSE + alpha * ||w_options||_2² / 2.

    At this scale, the L2 charge of the supplied *fixed* reference portfolio
    equals its RMSE improvement relative to a cash-only least-squares fit.
    It is a search scale, not an analytic L2 sparsity threshold.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    weights = np.asarray(reference_weights, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape != (len(b), len(weights)):
        raise ValueError("A, b et reference_weights doivent être compatibles.")
    cash_indices = tuple(int(index) for index in unpenalized_indices)
    if not cash_indices or len(set(cash_indices)) != len(cash_indices):
        raise ValueError("La référence L2 requiert des colonnes cash distinctes.")
    if any(index < 0 or index >= A.shape[1] for index in cash_indices):
        raise ValueError("Indice cash hors de la matrice A.")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(b)) or not np.all(np.isfinite(weights)):
        raise ValueError("Les données de référence L2 doivent être finies.")
    cash_fit, *_ = np.linalg.lstsq(A[:, cash_indices], b, rcond=None)
    cash_rmse = float(np.sqrt(np.mean((b - A[:, cash_indices] @ cash_fit) ** 2)))
    portfolio_rmse = float(np.sqrt(np.mean((b - A @ weights) ** 2)))
    option_mask = np.ones(A.shape[1], dtype=bool)
    option_mask[list(cash_indices)] = False
    option_norm_sq = float(np.sum(weights[option_mask] ** 2))
    improvement = cash_rmse - portfolio_rmse
    if improvement <= 0.0 or option_norm_sq <= 1e-16:
        weights, *_ = np.linalg.lstsq(A, b, rcond=None)
        portfolio_rmse = float(np.sqrt(np.mean((b - A @ weights) ** 2)))
        option_norm_sq = float(np.sum(weights[option_mask] ** 2))
        improvement = cash_rmse - portfolio_rmse
    if improvement <= 0.0 or option_norm_sq <= 1e-16:
        raise ValueError("La référence L2 doit améliorer la RMSE cash avec des options non nulles.")
    return 2.0 * improvement / option_norm_sq


@dataclass(frozen=True)
class TailRiskOptimizationConfig:
    """Paramètres d'une calibration avec risque de queue.

    ``lambda_es`` et ``es_budget`` sont des hyperparamètres de recherche. Ils
    ne doivent pas être sélectionnés sur l'échantillon final réservé.
    """

    objective: TailObjective = "rmse"
    penalty: str = "l1"
    alpha: float = 1e-4
    l1_ratio: float = 0.5
    es_level: float = 0.975
    lambda_es: float = 0.0
    es_budget: float | None = None
    scale_features: bool = True
    unpenalized_indices: tuple[int, ...] = ()
    active_threshold: float = 1e-6
    max_iter: int = 3000
    tolerance: float = 1e-8


@dataclass(frozen=True)
class TailRiskOptimizationResult:
    weights: np.ndarray
    value_at_risk: float
    expected_shortfall: float
    rmse: float
    objective_value: float
    converged: bool
    feasible: bool
    n_iterations: int
    message: str
    config: TailRiskOptimizationConfig

    def metadata(self) -> dict[str, object]:
        content = asdict(self)
        content.pop("weights")
        config = content.pop("config")
        return {**config, **content}


def _validated_inputs(
    A: np.ndarray,
    b: np.ndarray,
    sample_weights: np.ndarray | None,
    config: TailRiskOptimizationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape[0] != len(b) or A.shape[1] == 0:
        raise ValueError("A et b doivent définir un problème de régression non vide.")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(b)):
        raise ValueError("A et b doivent contenir uniquement des valeurs finies.")
    if sample_weights is None:
        probabilities = np.full(len(b), 1.0 / len(b), dtype=float)
    else:
        weights = np.asarray(sample_weights, dtype=float).reshape(-1)
        if weights.shape != b.shape:
            raise ValueError("sample_weights doit contenir un poids par trajectoire.")
        if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
            raise ValueError("sample_weights doit contenir des poids finis et positifs.")
        if float(np.sum(weights)) <= 0.0:
            raise ValueError("La somme de sample_weights doit être strictement positive.")
        probabilities = weights / np.sum(weights)
    if config.objective not in {"rmse", "penalized_es", "constrained_es"}:
        raise ValueError("objective doit être rmse, penalized_es ou constrained_es.")
    if config.penalty not in SUPPORTED_CONVEX_PENALTIES:
        raise ValueError(
            "Le contrôle direct de l'ES accepte d'abord les pénalités convexes "
            f"{SUPPORTED_CONVEX_PENALTIES}. L0 et L1/2 restent évaluables a posteriori."
        )
    if not 0.5 < config.es_level < 1.0:
        raise ValueError("es_level doit appartenir à ]0.5, 1[.")
    if config.alpha < 0.0 or config.lambda_es < 0.0:
        raise ValueError("alpha et lambda_es doivent être positifs ou nuls.")
    if config.objective == "constrained_es":
        if config.es_budget is None or not np.isfinite(config.es_budget):
            raise ValueError("Une optimisation contrainte requiert un es_budget fini.")
    if any(index < 0 or index >= A.shape[1] for index in config.unpenalized_indices):
        raise ValueError("Un indice non pénalisé est hors des colonnes de A.")
    return A, b, probabilities


def _penalty_value_gradient(
    original_weights: np.ndarray,
    column_scale: np.ndarray,
    config: TailRiskOptimizationConfig,
) -> tuple[float, np.ndarray]:
    mask = np.ones(len(original_weights), dtype=bool)
    mask[list(config.unpenalized_indices)] = False
    selected = original_weights[mask]
    if config.penalty == "l1":
        l1_strength, l2_strength = 1.0, 0.0
    elif config.penalty == "l2":
        l1_strength, l2_strength = 0.0, 1.0
    else:
        l1_strength = float(config.l1_ratio)
        l2_strength = 1.0 - l1_strength
    value = config.alpha * (
        l1_strength * float(np.sum(np.abs(selected)))
        + 0.5 * l2_strength * float(np.sum(selected**2))
    )
    gradient_original = np.zeros_like(original_weights)
    gradient_original[mask] = config.alpha * (
        l1_strength * np.sign(selected) + l2_strength * selected
    )
    # z = w * scale, donc dw/dz = 1/scale.
    return value, gradient_original / column_scale


def solve_tail_risk_replication(
    A: np.ndarray,
    b: np.ndarray,
    config: TailRiskOptimizationConfig,
    sample_weights: np.ndarray | None = None,
    initial_weights: np.ndarray | None = None,
) -> TailRiskOptimizationResult:
    """Calibre un portefeuille par RMSE, ES pénalisé ou ES contraint.

    L'ES est écrite avec la représentation de Rockafellar--Uryasev et une
    variable auxiliaire ``eta``. Les poids statistiques sont uniformes en MC
    standard et proportionnels à ``dP/dQ`` en importance sampling.
    """
    A, b, probabilities = _validated_inputs(A, b, sample_weights, config)
    if config.scale_features:
        column_scale = np.sqrt(np.sum(probabilities[:, None] * A**2, axis=0))
        column_scale[column_scale < 1e-12] = 1.0
    else:
        column_scale = np.ones(A.shape[1], dtype=float)
    A_fit = A / column_scale

    if initial_weights is None:
        weighted_A = A_fit * np.sqrt(probabilities)[:, None]
        weighted_b = b * np.sqrt(probabilities)
        z0, *_ = np.linalg.lstsq(weighted_A, weighted_b, rcond=None)
    else:
        initial_weights = np.asarray(initial_weights, dtype=float).reshape(-1)
        if initial_weights.shape != (A.shape[1],):
            raise ValueError("initial_weights doit contenir un poids par colonne de A.")
        z0 = initial_weights * column_scale
    initial_losses = b - A_fit @ z0
    eta0 = float(empirical_var_es(initial_losses, config.es_level, probabilities)["var"])
    x0 = np.concatenate([z0, [eta0]])
    tail_denominator = 1.0 - config.es_level

    def components(x: np.ndarray) -> tuple[float, np.ndarray, float, np.ndarray]:
        z, eta = x[:-1], float(x[-1])
        losses = b - A_fit @ z
        rmse = float(np.sqrt(np.sum(probabilities * losses**2)))
        safe_rmse = max(rmse, 1e-14)
        rmse_gradient = -(A_fit.T @ (probabilities * losses)) / safe_rmse
        active = losses > eta
        excess_weights = probabilities * active
        cvar = eta + float(np.sum(probabilities * np.maximum(losses - eta, 0.0))) / tail_denominator
        cvar_gradient = np.empty_like(x)
        cvar_gradient[:-1] = -(A_fit.T @ excess_weights) / tail_denominator
        cvar_gradient[-1] = 1.0 - float(np.sum(excess_weights)) / tail_denominator
        return rmse, rmse_gradient, cvar, cvar_gradient

    def objective_and_gradient(x: np.ndarray) -> tuple[float, np.ndarray]:
        rmse, rmse_gradient, cvar, cvar_gradient = components(x)
        original_weights = x[:-1] / column_scale
        penalty_value, penalty_gradient = _penalty_value_gradient(
            original_weights, column_scale, config
        )
        value = rmse + penalty_value
        gradient = np.concatenate([rmse_gradient + penalty_gradient, [0.0]])
        if config.objective == "penalized_es":
            value += config.lambda_es * cvar
            gradient += config.lambda_es * cvar_gradient
        return float(value), gradient

    constraints = ()
    method = "L-BFGS-B"
    if config.objective == "constrained_es":
        method = "SLSQP"

        def constraint_value(x: np.ndarray) -> float:
            return float(config.es_budget - components(x)[2])

        def constraint_jacobian(x: np.ndarray) -> np.ndarray:
            return -components(x)[3]

        constraints = ({"type": "ineq", "fun": constraint_value, "jac": constraint_jacobian},)

    result = minimize(
        fun=lambda x: objective_and_gradient(x)[0],
        jac=lambda x: objective_and_gradient(x)[1],
        x0=x0,
        method=method,
        constraints=constraints,
        options={"maxiter": config.max_iter, "ftol": config.tolerance}
        if method == "SLSQP"
        else {"maxiter": config.max_iter, "ftol": config.tolerance, "gtol": config.tolerance},
    )
    original_weights = np.asarray(result.x[:-1], dtype=float) / column_scale
    losses = b - A @ original_weights
    risk = empirical_var_es(losses, config.es_level, probabilities)
    rmse = float(np.sqrt(np.sum(probabilities * losses**2)))
    objective_value = float(objective_and_gradient(np.asarray(result.x, dtype=float))[0])
    feasibility_tolerance = max(1e-7, 10.0 * config.tolerance)
    feasible = bool(
        config.objective != "constrained_es"
        or float(risk["es"]) <= float(config.es_budget) + feasibility_tolerance
    )
    return TailRiskOptimizationResult(
        weights=original_weights,
        value_at_risk=float(risk["var"]),
        expected_shortfall=float(risk["es"]),
        rmse=rmse,
        objective_value=objective_value,
        converged=bool(result.success),
        feasible=feasible,
        n_iterations=int(getattr(result, "nit", 0)),
        message=str(result.message),
        config=config,
    )


def run_four_tail_risk_experiments(
    *,
    standard_A: np.ndarray,
    standard_b: np.ndarray,
    importance_A: np.ndarray,
    importance_b: np.ndarray,
    importance_weights: np.ndarray,
    evaluation_A: np.ndarray,
    evaluation_b: np.ndarray,
    penalty: str,
    alpha: float,
    es_budget: float,
    l1_ratio: float = 0.5,
    es_level: float = 0.975,
    unpenalized_indices: tuple[int, ...] = (),
    active_threshold: float = 1e-6,
) -> dict[str, object]:
    """Exécute le plan 2x2 MC/IS et RMSE/contrainte ES.

    L'échantillon ``evaluation_*`` reste indépendant des deux échantillons de
    calibration. Les quatre stratégies sont donc comparées sur exactement les
    mêmes trajectoires hors calibration.
    """
    calibration_sets = {
        "standard_mc": (standard_A, standard_b, None),
        "importance_sampling": (importance_A, importance_b, importance_weights),
    }
    risk_controls = {
        "rmse_only": "rmse",
        "es_constraint": "constrained_es",
    }
    rows: list[dict[str, object]] = []
    results: dict[tuple[str, str], TailRiskOptimizationResult] = {}
    for sampling_name, (A, b, weights) in calibration_sets.items():
        for control_name, objective in risk_controls.items():
            config = TailRiskOptimizationConfig(
                objective=objective,
                penalty=penalty,
                alpha=alpha,
                l1_ratio=l1_ratio,
                es_level=es_level,
                es_budget=es_budget if objective == "constrained_es" else None,
                unpenalized_indices=unpenalized_indices,
                active_threshold=active_threshold,
            )
            fitted = solve_tail_risk_replication(A, b, config, sample_weights=weights)
            results[(sampling_name, control_name)] = fitted
            evaluation_losses = np.asarray(evaluation_b) - np.asarray(evaluation_A) @ fitted.weights
            evaluation_risk = empirical_var_es(evaluation_losses, es_level)
            rows.append(
                {
                    "calibration_sampling": sampling_name,
                    "risk_control": control_name,
                    "penalty": penalty,
                    "alpha": alpha,
                    "es_level": es_level,
                    "es_budget": es_budget if objective == "constrained_es" else np.nan,
                    "converged": fitted.converged,
                    "constraint_feasible_in_calibration": fitted.feasible,
                    "calibration_rmse": fitted.rmse,
                    "calibration_es": fitted.expected_shortfall,
                    "evaluation_rmse": float(np.sqrt(np.mean(evaluation_losses**2))),
                    "evaluation_mean_error": float(np.mean(evaluation_losses)),
                    "evaluation_mae": float(np.mean(np.abs(evaluation_losses))),
                    "evaluation_under_replication_rate": float(np.mean(evaluation_losses > 0)),
                    "evaluation_max_loss": float(np.max(evaluation_losses)),
                    "evaluation_var": float(evaluation_risk["var"]),
                    "evaluation_es": float(evaluation_risk["es"]),
                    "n_active_coefficients": int(
                        np.sum(np.abs(fitted.weights) > active_threshold)
                    ),
                    "n_iterations": fitted.n_iterations,
                    "message": fitted.message,
                }
            )
    return {"summary": pd.DataFrame(rows), "results": results}


def run_penalized_es_sensitivity(
    *,
    A: np.ndarray,
    b: np.ndarray,
    lambda_values: tuple[float, ...],
    penalty: str,
    alpha: float,
    sample_weights: np.ndarray | None = None,
    l1_ratio: float = 0.5,
    es_level: float = 0.975,
    unpenalized_indices: tuple[int, ...] = (),
) -> dict[str, object]:
    """Calcule une frontière RMSE--ES pour une grille externe de lambda ES."""
    if len(lambda_values) == 0:
        raise ValueError("lambda_values doit contenir au moins une valeur.")
    rows: list[dict[str, object]] = []
    results: dict[float, TailRiskOptimizationResult] = {}
    initial_weights: np.ndarray | None = None
    for lambda_es in sorted(float(value) for value in lambda_values):
        fitted = solve_tail_risk_replication(
            A,
            b,
            TailRiskOptimizationConfig(
                objective="penalized_es",
                penalty=penalty,
                alpha=alpha,
                l1_ratio=l1_ratio,
                es_level=es_level,
                lambda_es=lambda_es,
                unpenalized_indices=unpenalized_indices,
            ),
            sample_weights=sample_weights,
            initial_weights=initial_weights,
        )
        initial_weights = fitted.weights
        results[lambda_es] = fitted
        rows.append(
            {
                "lambda_es": lambda_es,
                "penalty": penalty,
                "alpha": alpha,
                "rmse": fitted.rmse,
                "es": fitted.expected_shortfall,
                "var": fitted.value_at_risk,
                "n_active_coefficients": int(
                    np.sum(np.abs(fitted.weights) > fitted.config.active_threshold)
                ),
                "converged": fitted.converged,
                "n_iterations": fitted.n_iterations,
            }
        )
    return {
        "summary": pd.DataFrame(rows),
        "results": results,
        "selection_status": "research_grid_not_selected_on_final_sample",
    }


def run_es_budget_frontier(
    *,
    A: np.ndarray,
    b: np.ndarray,
    budgets: tuple[float, ...],
    penalty: str,
    alpha: float,
    sample_weights: np.ndarray | None = None,
    l1_ratio: float = 0.5,
    es_level: float = 0.975,
    unpenalized_indices: tuple[int, ...] = (),
) -> dict[str, object]:
    """Calcule hors notebook principal une frontière de budgets d'ES."""
    if len(budgets) == 0:
        raise ValueError("budgets doit contenir au moins une valeur.")
    rows: list[dict[str, object]] = []
    results: dict[float, TailRiskOptimizationResult] = {}
    initial_weights: np.ndarray | None = None
    # On part du budget le moins contraignant pour fournir un warm start.
    for budget in sorted((float(value) for value in budgets), reverse=True):
        fitted = solve_tail_risk_replication(
            A,
            b,
            TailRiskOptimizationConfig(
                objective="constrained_es",
                penalty=penalty,
                alpha=alpha,
                l1_ratio=l1_ratio,
                es_level=es_level,
                es_budget=budget,
                unpenalized_indices=unpenalized_indices,
            ),
            sample_weights=sample_weights,
            initial_weights=initial_weights,
        )
        if fitted.converged and fitted.feasible:
            initial_weights = fitted.weights
        results[budget] = fitted
        rows.append(
            {
                "es_budget": budget,
                "penalty": penalty,
                "alpha": alpha,
                "rmse": fitted.rmse,
                "es": fitted.expected_shortfall,
                "var": fitted.value_at_risk,
                "n_active_coefficients": int(
                    np.sum(np.abs(fitted.weights) > fitted.config.active_threshold)
                ),
                "converged": fitted.converged,
                "feasible": fitted.feasible,
                "n_iterations": fitted.n_iterations,
            }
        )
    return {
        "summary": pd.DataFrame(rows).sort_values("es_budget").reset_index(drop=True),
        "results": results,
        "selection_status": "research_grid_not_selected_on_final_sample",
    }


def run_conditional_tail_risk_experiments(
    *,
    base_result: dict[str, object],
    product: object,
    spot0: float,
    valuation_date: object,
    maturity_date: object,
    rate: float,
    dividend_yield: float,
    vol: float,
    penalty: str,
    profile: str = "compromise",
    alpha_override: float | None = None,
    l1_ratio_override: float | None = None,
    calibration_paths: int = 1000,
    evaluation_paths: int = 2000,
    standard_seed: int = 51000,
    importance_seed: int = 52000,
    evaluation_seed: int = 53000,
    es_level: float = 0.975,
    es_budget_ratio: float = 0.90,
    es_budget: float | None = None,
    tilts: tuple[float, ...] = (0.0, -1.0, -2.0),
    mixture_probabilities: tuple[float, ...] = (0.50, 0.30, 0.20),
    importance_sampling_method: str = "importance_sampling",
) -> dict[str, object]:
    """Orchestre les quatre expériences sur une politique conditionnelle.

    Les substitutions explicites permettent d'appliquer le couple (alpha, rho)
    retenu sur une grille de validation externe à la politique de base.
    """
    from .importance_sampling import build_conditional_policy_sampling_design

    if importance_sampling_method not in {"standard_mc", "importance_sampling"}:
        raise ValueError("importance_sampling_method invalide.")

    profiles = pd.DataFrame(base_result["profiles"])
    selected = profiles.loc[
        (profiles["penalty"] == penalty) & (profiles["profile"] == profile)
    ]
    if len(selected) != 1:
        raise ValueError("penalty/profile doit identifier un profil stable unique.")
    selected = selected.iloc[0]
    alpha = float(selected["alpha"])
    l1_ratio = (
        0.5
        if "l1_ratio" not in selected or pd.isna(selected["l1_ratio"])
        else float(selected["l1_ratio"])
    )
    if alpha_override is not None:
        alpha = float(alpha_override)
    if l1_ratio_override is not None:
        l1_ratio = float(l1_ratio_override)
    if not np.isfinite(alpha) or alpha < 0.0:
        raise ValueError("alpha doit être positif ou nul et fini.")
    if not np.isfinite(l1_ratio) or not 0.0 <= l1_ratio <= 1.0:
        raise ValueError("l1_ratio doit appartenir à [0, 1].")
    common = {
        "base_result": base_result,
        "product": product,
        "spot0": spot0,
        "valuation_date": valuation_date,
        "maturity_date": maturity_date,
        "rate": rate,
        "dividend_yield": dividend_yield,
        "vol": vol,
    }
    standard = build_conditional_policy_sampling_design(
        **common,
        n_paths=calibration_paths,
        seed=standard_seed,
        sampling_method="standard_mc",
    )
    importance = build_conditional_policy_sampling_design(
        **common,
        n_paths=calibration_paths,
        seed=importance_seed,
        sampling_method=importance_sampling_method,
        tilts=tilts,
        mixture_probabilities=mixture_probabilities,
    )
    evaluation = build_conditional_policy_sampling_design(
        **common,
        n_paths=evaluation_paths,
        seed=evaluation_seed,
        sampling_method="standard_mc",
    )
    budget_was_explicit = es_budget is not None
    if es_budget is None:
        reference = solve_tail_risk_replication(
            standard["A"],
            standard["b"],
            TailRiskOptimizationConfig(
                objective="rmse",
                penalty=penalty,
                alpha=alpha,
                l1_ratio=l1_ratio,
                es_level=es_level,
                unpenalized_indices=tuple(base_result["unpenalized_indices"]),
            ),
        )
        es_budget = float(es_budget_ratio) * reference.expected_shortfall
    experiment = run_four_tail_risk_experiments(
        standard_A=standard["A"],
        standard_b=standard["b"],
        importance_A=importance["A"],
        importance_b=importance["b"],
        importance_weights=importance["likelihood_weights"],
        evaluation_A=evaluation["A"],
        evaluation_b=evaluation["b"],
        penalty=penalty,
        alpha=alpha,
        es_budget=float(es_budget),
        l1_ratio=l1_ratio,
        es_level=es_level,
        unpenalized_indices=tuple(base_result["unpenalized_indices"]),
        active_threshold=float(base_result["active_threshold"]),
    )
    if importance_sampling_method == "standard_mc":
        experiment["summary"].loc[
            experiment["summary"]["calibration_sampling"].eq("importance_sampling"),
            "calibration_sampling",
        ] = "standard_mc_repeat"
    experiment["summary"].insert(0, "profile", profile)
    experiment["summary"].insert(0, "family", base_result["family"])
    return {
        **experiment,
        "standard_design": standard,
        "importance_design": importance,
        "evaluation_design": evaluation,
        "importance_sampling_diagnostics": importance["sampling_diagnostics_table"],
        "importance_component_summary": importance["component_summary"],
        "es_budget_source": (
            "explicit" if budget_was_explicit else "ratio_of_standard_rmse_es"
        ),
        "applied_alpha": alpha,
        "applied_l1_ratio": l1_ratio,
        "applied_es_budget_ratio": es_budget_ratio if not budget_was_explicit else None,
        "test_status": "independent_evaluation_used_final_sample_untouched",
    }

