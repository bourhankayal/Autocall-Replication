"""Chemins de régularisation sans contamination du test final."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..products import VanillaProduct
from .common import benchmark_metrics
from .optimization import SolverConfig, solve_replication
from .portfolio_diagnostics import (
    DEFAULT_ACTIVE_THRESHOLD,
    portfolio_weight_metrics,
)


def train_validation_test_slices(
    n_observations: int,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> dict[str, slice]:
    """Construit un split séquentiel reproductible avec trois blocs non vides."""
    if n_observations < 3:
        raise ValueError("Au moins trois observations sont requises pour le split.")
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction doit appartenir à ]0, 1[.")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction doit appartenir à ]0, 1[.")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError(
            "La somme de train_fraction et validation_fraction doit être "
            "strictement inférieure à 1."
        )

    n_train = max(1, int(train_fraction * n_observations))
    n_validation = max(1, int(validation_fraction * n_observations))
    if n_train + n_validation >= n_observations:
        n_validation = n_observations - n_train - 1
    if n_validation < 1:
        raise ValueError("Le split ne laisse aucune observation de validation.")

    return {
        "train": slice(0, n_train),
        "validation": slice(n_train, n_train + n_validation),
        "test": slice(n_train + n_validation, n_observations),
    }


def lasso_alpha_max(
    A: np.ndarray,
    b: np.ndarray,
    scale_features: bool = True,
    l1_ratio: float = 1.0,
    unpenalized_indices: tuple[int, ...] = (0,),
) -> float:
    """Calcule l'alpha annulant toutes les variables pénalisées.

    Les variables non pénalisées sont d'abord ajustées par moindres carrés. La
    formule est exprimée dans les mêmes coordonnées normalisées que FISTA.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape[0] != len(b):
        raise ValueError("A et b ont des dimensions incompatibles.")
    if not 0.0 < l1_ratio <= 1.0:
        raise ValueError("l1_ratio doit appartenir à ]0, 1] pour un chemin sparse.")

    if scale_features:
        column_scale = np.sqrt(np.mean(A**2, axis=0))
        column_scale[column_scale < 1e-12] = 1.0
    else:
        column_scale = np.ones(A.shape[1], dtype=float)
    A_fit = A / column_scale

    unpenalized_mask = np.zeros(A.shape[1], dtype=bool)
    indices = tuple(unpenalized_indices)
    if any(index < 0 or index >= A.shape[1] for index in indices):
        raise ValueError("Un indice non pénalisé est hors des colonnes de A.")
    unpenalized_mask[list(indices)] = True
    penalized_mask = ~unpenalized_mask
    if not np.any(penalized_mask):
        raise ValueError("Le chemin requiert au moins une variable pénalisée.")

    if np.any(unpenalized_mask):
        unpenalized_weights, *_ = np.linalg.lstsq(
            A_fit[:, unpenalized_mask], b, rcond=None
        )
        residual = b - A_fit[:, unpenalized_mask] @ unpenalized_weights
    else:
        residual = b.copy()

    correlations = np.abs(A_fit[:, penalized_mask].T @ residual) / len(b)
    alpha_max = float(np.max(correlations) / l1_ratio)
    if not np.isfinite(alpha_max) or alpha_max <= 0.0:
        raise ValueError(
            "alpha_max est nul : les variables pénalisées n'expliquent aucun "
            "résidu après les variables non pénalisées."
        )
    return alpha_max


def l0_alpha_max(
    A: np.ndarray,
    b: np.ndarray,
    scale_features: bool = True,
    unpenalized_indices: tuple[int, ...] = (0,),
) -> float:
    """Référence L0 annulant le premier pas des variables pénalisées.

    Après ajustement des variables non pénalisées, le gradient proximal utilise
    le seuil ``sqrt(2 * alpha / L)``. La référence ci-dessous est donc
    ``max(gradient_j**2) / (2L)``. Il s'agit d'une référence algorithmique pour
    un problème non convexe, pas d'une garantie d'optimum global.
    """

    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape[0] != len(b):
        raise ValueError("A et b ont des dimensions incompatibles.")
    if scale_features:
        column_scale = np.sqrt(np.mean(A**2, axis=0))
        column_scale[column_scale < 1e-12] = 1.0
    else:
        column_scale = np.ones(A.shape[1], dtype=float)
    A_fit = A / column_scale

    unpenalized_mask = np.zeros(A.shape[1], dtype=bool)
    indices = tuple(unpenalized_indices)
    if any(index < 0 or index >= A.shape[1] for index in indices):
        raise ValueError("Un indice non pénalisé est hors des colonnes de A.")
    unpenalized_mask[list(indices)] = True
    penalized_mask = ~unpenalized_mask
    if not np.any(penalized_mask):
        raise ValueError("Le chemin L0 requiert au moins une variable pénalisée.")

    if np.any(unpenalized_mask):
        unpenalized_weights, *_ = np.linalg.lstsq(
            A_fit[:, unpenalized_mask], b, rcond=None
        )
        residual = A_fit[:, unpenalized_mask] @ unpenalized_weights - b
    else:
        residual = -b.copy()
    gradient = A_fit[:, penalized_mask].T @ residual / len(b)
    lipschitz = float(np.linalg.norm(A_fit, ord=2) ** 2 / len(b))
    reference = float(np.max(gradient**2) / (2.0 * lipschitz))
    if not np.isfinite(reference) or reference <= 0.0:
        raise ValueError("La référence L0 doit être strictement positive.")
    return reference


def logarithmic_alpha_grid(
    alpha_max: float,
    n_alphas: int = 25,
    min_alpha_ratio: float = 1e-3,
) -> np.ndarray:
    """Retourne une grille strictement décroissante d'alpha."""
    if not np.isfinite(alpha_max) or alpha_max <= 0.0:
        raise ValueError("alpha_max doit être fini et strictement positif.")
    if n_alphas < 2:
        raise ValueError("n_alphas doit être supérieur ou égal à 2.")
    if not np.isfinite(min_alpha_ratio) or not 0.0 < min_alpha_ratio < 1.0:
        raise ValueError("min_alpha_ratio doit appartenir à ]0, 1[.")
    return np.geomspace(alpha_max, alpha_max * min_alpha_ratio, n_alphas)


def ridge_alpha_reference(
    A: np.ndarray,
    scale_features: bool = True,
    unpenalized_indices: tuple[int, ...] = (0,),
) -> float:
    """Calcule l'échelle spectrale de référence du chemin Ridge.

    Après la même normalisation que le solveur, la référence est la plus grande
    valeur propre de ``X_options.T @ X_options / n``. Contrairement à
    ``alpha_max`` pour L1, elle n'a pas vocation à annuler exactement les poids.
    """
    A = np.asarray(A, dtype=float)
    if A.ndim != 2 or A.shape[0] == 0 or A.shape[1] == 0:
        raise ValueError("A doit être une matrice 2D non vide.")
    if not np.all(np.isfinite(A)):
        raise ValueError("A doit contenir uniquement des valeurs finies.")

    if scale_features:
        column_scale = np.sqrt(np.mean(A**2, axis=0))
        column_scale[column_scale < 1e-12] = 1.0
    else:
        column_scale = np.ones(A.shape[1], dtype=float)
    A_fit = A / column_scale

    penalized_mask = np.ones(A.shape[1], dtype=bool)
    indices = tuple(unpenalized_indices)
    if any(index < 0 or index >= A.shape[1] for index in indices):
        raise ValueError("Un indice non pénalisé est hors des colonnes de A.")
    penalized_mask[list(indices)] = False
    if not np.any(penalized_mask):
        raise ValueError("Le chemin Ridge requiert une variable pénalisée.")

    options = A_fit[:, penalized_mask]
    largest_singular_value = float(np.linalg.norm(options, ord=2))
    reference = largest_singular_value**2 / A.shape[0]
    if not np.isfinite(reference) or reference <= 0.0:
        raise ValueError("La référence Ridge doit être strictement positive.")
    return reference


def ridge_alpha_grid(
    alpha_reference: float,
    n_alphas: int = 25,
    min_reference_ratio: float = 1e-4,
    max_reference_ratio: float = 1e2,
) -> np.ndarray:
    """Construit le chemin Ridge autour de sa référence spectrale."""
    if not np.isfinite(alpha_reference) or alpha_reference <= 0.0:
        raise ValueError("alpha_reference doit être fini et strictement positif.")
    if n_alphas < 2:
        raise ValueError("n_alphas doit être supérieur ou égal à 2.")
    if not 0.0 < min_reference_ratio < max_reference_ratio:
        raise ValueError(
            "Il faut 0 < min_reference_ratio < max_reference_ratio."
        )
    return np.geomspace(
        alpha_reference * max_reference_ratio,
        alpha_reference * min_reference_ratio,
        n_alphas,
    )


def _pareto_mask(table: pd.DataFrame) -> np.ndarray:
    valid = table["converged"].to_numpy(dtype=bool)
    errors = table["validation_rmse"].to_numpy(dtype=float)
    active = table["n_options_active"].to_numpy(dtype=int)
    pareto = np.zeros(len(table), dtype=bool)

    for index in range(len(table)):
        if not valid[index] or not np.isfinite(errors[index]):
            continue
        dominated = np.any(
            valid
            & (errors <= errors[index])
            & (active <= active[index])
            & ((errors < errors[index]) | (active < active[index]))
        )
        pareto[index] = not dominated
    return pareto


def select_regularization_candidates(
    table: pd.DataFrame,
    min_active_options: int = 2,
    max_active_options: int = 100,
) -> pd.DataFrame:
    """Filtre les candidats et recalcule Pareto au sein de chaque pénalité.

    Les pénalités ne se dominent jamais entre elles. La table complète est
    conservée et annotée avec le motif d'acceptation ou de rejet.
    """
    required = {
        "penalty",
        "converged",
        "validation_rmse",
        "n_options_active",
    }
    missing = sorted(required - set(table.columns))
    if missing:
        raise ValueError(f"Colonnes manquantes pour la sélection : {missing}")
    if min_active_options < 0:
        raise ValueError("min_active_options doit être positif ou nul.")
    if max_active_options < min_active_options:
        raise ValueError(
            "max_active_options doit être supérieur ou égal au minimum."
        )

    selected = table.copy()
    converged = selected["converged"].astype(bool)
    enough_options = selected["n_options_active"] >= min_active_options
    not_too_many_options = selected["n_options_active"] <= max_active_options
    eligible = converged & enough_options & not_too_many_options

    selected["is_candidate_pareto"] = False
    for _, group in selected.loc[eligible].groupby("penalty", sort=False):
        selected.loc[group.index, "is_candidate_pareto"] = _pareto_mask(group)

    selected["is_candidate"] = eligible & selected["is_candidate_pareto"]
    reasons: list[str] = []
    for index, row in selected.iterrows():
        if not bool(row["converged"]):
            reason = "rejected_non_converged"
        elif int(row["n_options_active"]) < min_active_options:
            reason = "rejected_fewer_than_minimum_options"
        elif int(row["n_options_active"]) > max_active_options:
            reason = "rejected_more_than_maximum_options"
        elif not bool(selected.loc[index, "is_candidate_pareto"]):
            reason = "rejected_dominated_within_penalty"
        else:
            reason = "candidate"
        reasons.append(reason)
    selected["selection_status"] = reasons
    return selected


def candidate_policies(candidate_table: pd.DataFrame) -> list[dict[str, object]]:
    """Sérialise les candidats sous une forme réutilisable par les benchmarks."""
    selection_column = (
        "is_candidate_after_duplicates"
        if "is_candidate_after_duplicates" in candidate_table
        else "is_candidate"
    )
    candidates = candidate_table.loc[candidate_table[selection_column]].copy()
    candidates = candidates.sort_values(
        ["penalty", "n_options_active", "validation_rmse", "alpha_relative"],
        kind="stable",
    )
    policies: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(candidates.iterrows(), start=1):
        ratio = row.get("l1_ratio", np.nan)
        policies.append(
            {
                "candidate_id": f"candidate_{rank:02d}",
                "family": None,
                "penalty": str(row["penalty"]),
                "alpha": float(row["alpha"]),
                "alpha_relative": float(row["alpha_relative"]),
                "l1_ratio": None if pd.isna(ratio) else float(ratio),
                "n_options_active": int(row["n_options_active"]),
                "validation_rmse": float(row["validation_rmse"]),
            }
        )
    return policies


def _solution_for_row(
    row: pd.Series,
    results: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Retrouve sans ambiguïté la solution numérique associée à une ligne."""
    return results[str(row["penalty"])]["solutions"][int(row["solution_index"])]


def apply_static_performance_filter(
    table: pd.DataFrame,
    results: dict[str, dict[str, object]],
    n_bootstrap: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 20260819,
) -> pd.DataFrame:
    """Écarte les candidats significativement moins bons dans leur pénalité.

    Le bootstrap est apparié : les mêmes observations de validation sont
    rééchantillonnées pour le candidat et pour la meilleure RMSE de sa norme.
    Le test est unilatéral et ne rejette que si la borne basse de la différence
    de RMSE est strictement positive.
    """
    if n_bootstrap < 100:
        raise ValueError("n_bootstrap doit être supérieur ou égal à 100.")
    if not 0.5 < confidence_level < 1.0:
        raise ValueError("confidence_level doit appartenir à ]0.5, 1[.")

    filtered = table.copy()
    filtered["passes_static_performance"] = False
    filtered["performance_reference_alpha"] = np.nan
    filtered["rmse_difference_vs_best"] = np.nan
    filtered["rmse_difference_ci_lower"] = np.nan
    filtered["rmse_difference_ci_upper"] = np.nan
    rng = np.random.default_rng(seed)

    for _, group in filtered.loc[filtered["is_candidate"]].groupby(
        "penalty", sort=False
    ):
        best_index = group["validation_rmse"].astype(float).idxmin()
        best_row = filtered.loc[best_index]
        best_residuals = np.asarray(
            _solution_for_row(best_row, results)["validation_residuals"],
            dtype=float,
        )
        n_validation = len(best_residuals)
        bootstrap_indices = rng.integers(
            0, n_validation, size=(n_bootstrap, n_validation)
        )
        best_bootstrap_rmse = np.sqrt(
            np.mean(best_residuals[bootstrap_indices] ** 2, axis=1)
        )

        for index, row in group.iterrows():
            residuals = np.asarray(
                _solution_for_row(row, results)["validation_residuals"],
                dtype=float,
            )
            if len(residuals) != n_validation:
                raise ValueError("Les blocs de validation ne sont pas appariés.")
            candidate_bootstrap_rmse = np.sqrt(
                np.mean(residuals[bootstrap_indices] ** 2, axis=1)
            )
            differences = candidate_bootstrap_rmse - best_bootstrap_rmse
            lower = float(np.quantile(differences, 1.0 - confidence_level))
            upper = float(np.quantile(differences, confidence_level))
            filtered.loc[index, "passes_static_performance"] = lower <= 0.0
            filtered.loc[index, "performance_reference_alpha"] = float(
                best_row["alpha"]
            )
            filtered.loc[index, "rmse_difference_vs_best"] = float(
                row["validation_rmse"] - best_row["validation_rmse"]
            )
            filtered.loc[index, "rmse_difference_ci_lower"] = lower
            filtered.loc[index, "rmse_difference_ci_upper"] = upper

    filtered["is_candidate_after_performance"] = (
        filtered["is_candidate"] & filtered["passes_static_performance"]
    )
    return filtered


def _support_jaccard(left: np.ndarray, right: np.ndarray) -> float:
    union = np.count_nonzero(left | right)
    return 1.0 if union == 0 else float(np.count_nonzero(left & right) / union)


def _relative_weight_distance(left: np.ndarray, right: np.ndarray) -> float:
    scale = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1e-15)
    return float(np.linalg.norm(left - right) / scale)


def remove_duplicate_candidates(
    table: pd.DataFrame,
    results: dict[str, dict[str, object]],
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
    quasi_jaccard_threshold: float = 0.95,
    quasi_weight_distance_threshold: float = 0.05,
    strict_rtol: float = 1e-8,
    strict_atol: float = 1e-10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Supprime les doublons stricts puis quasi stricts avec piste d'audit."""
    if not 0.0 <= quasi_jaccard_threshold <= 1.0:
        raise ValueError("quasi_jaccard_threshold doit appartenir à [0, 1].")
    if quasi_weight_distance_threshold < 0.0:
        raise ValueError("quasi_weight_distance_threshold doit être positif.")

    deduplicated = table.copy()
    deduplicated["duplicate_status"] = "not_eligible"
    deduplicated["duplicate_of_alpha"] = np.nan
    deduplicated["is_candidate_after_duplicates"] = False
    audit_rows: list[dict[str, object]] = []
    eligible = deduplicated.loc[
        deduplicated["is_candidate_after_performance"]
    ].copy()
    cost_column = "estimated_transaction_cost"
    if cost_column not in eligible:
        eligible[cost_column] = np.nan

    for penalty, group in eligible.groupby("penalty", sort=False):
        group = group.assign(
            _cost_rank=group[cost_column].fillna(np.inf),
            _has_cost=group[cost_column].notna().astype(int),
        ).sort_values(
            [
                "_has_cost",
                "_cost_rank",
                "n_options_active",
                "validation_rmse",
                "alpha_relative",
            ],
            ascending=[False, True, True, True, False],
            kind="stable",
        )
        kept_indices: list[int] = []
        for index, row in group.iterrows():
            solution = _solution_for_row(row, results)
            weights = np.asarray(solution["weights"], dtype=float)
            predictions = np.asarray(solution["validation_predictions"], dtype=float)
            support = np.abs(weights[1:]) > active_threshold
            duplicate_match: tuple[int, str, float, float] | None = None

            for kept_index in kept_indices:
                kept_row = deduplicated.loc[kept_index]
                kept_solution = _solution_for_row(kept_row, results)
                kept_weights = np.asarray(kept_solution["weights"], dtype=float)
                kept_predictions = np.asarray(
                    kept_solution["validation_predictions"], dtype=float
                )
                kept_support = np.abs(kept_weights[1:]) > active_threshold
                jaccard = _support_jaccard(support, kept_support)
                weight_distance = _relative_weight_distance(weights, kept_weights)
                strict = (
                    np.array_equal(support, kept_support)
                    and np.allclose(weights, kept_weights, rtol=strict_rtol, atol=strict_atol)
                    and np.allclose(
                        predictions,
                        kept_predictions,
                        rtol=strict_rtol,
                        atol=strict_atol,
                    )
                )
                statistically_equivalent = (
                    float(row["rmse_difference_ci_lower"]) <= 0.0
                    and float(kept_row["rmse_difference_ci_lower"]) <= 0.0
                )
                quasi = (
                    jaccard >= quasi_jaccard_threshold
                    and weight_distance <= quasi_weight_distance_threshold
                    and statistically_equivalent
                )
                if strict or quasi:
                    duplicate_match = (
                        kept_index,
                        "strict_duplicate" if strict else "quasi_strict_duplicate",
                        jaccard,
                        weight_distance,
                    )
                    break

            if duplicate_match is None:
                kept_indices.append(index)
                deduplicated.loc[index, "duplicate_status"] = "kept_representative"
                deduplicated.loc[index, "is_candidate_after_duplicates"] = True
                continue

            kept_index, status, jaccard, weight_distance = duplicate_match
            kept_row = deduplicated.loc[kept_index]
            deduplicated.loc[index, "duplicate_status"] = status
            deduplicated.loc[index, "duplicate_of_alpha"] = float(kept_row["alpha"])
            audit_rows.append(
                {
                    "penalty": penalty,
                    "duplicate_type": status,
                    "kept_alpha": float(kept_row["alpha"]),
                    "removed_alpha": float(row["alpha"]),
                    "kept_n_options_active": int(kept_row["n_options_active"]),
                    "removed_n_options_active": int(row["n_options_active"]),
                    "kept_validation_rmse": float(kept_row["validation_rmse"]),
                    "removed_validation_rmse": float(row["validation_rmse"]),
                    "support_jaccard": jaccard,
                    "relative_weight_distance": weight_distance,
                    "reason": (
                        "support, poids et prédictions identiques"
                        if status == "strict_duplicate"
                        else "support >= 95 %, poids proches et performance indiscernable"
                    ),
                }
            )

    audit_columns = [
        "penalty",
        "duplicate_type",
        "kept_alpha",
        "removed_alpha",
        "kept_n_options_active",
        "removed_n_options_active",
        "kept_validation_rmse",
        "removed_validation_rmse",
        "support_jaccard",
        "relative_weight_distance",
        "reason",
    ]
    return deduplicated, pd.DataFrame(audit_rows, columns=audit_columns)


def select_three_profiles_per_penalty(table: pd.DataFrame) -> pd.DataFrame:
    """Choisit performance, compromis et parcimonie dans chaque pénalité."""
    profile_rows: list[dict[str, object]] = []
    pool = table.loc[table["is_candidate_after_duplicates"]].copy()
    for penalty, group in pool.groupby("penalty", sort=False):
        group = group.copy()
        rmse_span = float(group["validation_rmse"].max() - group["validation_rmse"].min())
        active_span = float(group["n_options_active"].max() - group["n_options_active"].min())
        group["normalized_rmse"] = (
            (group["validation_rmse"] - group["validation_rmse"].min()) / rmse_span
            if rmse_span > 0.0
            else 0.0
        )
        group["normalized_complexity"] = (
            (group["n_options_active"] - group["n_options_active"].min()) / active_span
            if active_span > 0.0
            else 0.0
        )
        group["compromise_score"] = np.sqrt(
            group["normalized_rmse"] ** 2 + group["normalized_complexity"] ** 2
        )
        ordered = {
            "performance": group.sort_values(
                ["validation_rmse", "n_options_active", "alpha_relative"],
                ascending=[True, True, False],
                kind="stable",
            ),
            "parsimony": group.sort_values(
                ["n_options_active", "validation_rmse", "alpha_relative"],
                ascending=[True, True, False],
                kind="stable",
            ),
            "compromise": group.sort_values(
                ["compromise_score", "validation_rmse", "n_options_active"],
                kind="stable",
            ),
        }
        used_indices: set[int] = set()
        selected_indices: dict[str, int] = {}
        # La performance est fixée d'abord, puis la parcimonie. Le compromis
        # utilise enfin le meilleur candidat encore non attribué. Cet ordre
        # conserve trois choix réellement différents lorsque c'est possible.
        for profile in ("performance", "parsimony", "compromise"):
            candidates = ordered[profile]
            unused = [index for index in candidates.index if index not in used_indices]
            selected_index = unused[0] if unused else int(candidates.index[0])
            selected_indices[profile] = selected_index
            used_indices.add(selected_index)

        for profile in ("performance", "compromise", "parsimony"):
            index = selected_indices[profile]
            row = group.loc[index]
            profile_rows.append(
                {
                    "penalty": penalty,
                    "profile": profile,
                    "alpha": float(row["alpha"]),
                    "alpha_relative": float(row["alpha_relative"]),
                    "l1_ratio": (
                        None
                        if pd.isna(row.get("l1_ratio", np.nan))
                        else float(row["l1_ratio"])
                    ),
                    "validation_rmse": float(row["validation_rmse"]),
                    "n_options_active": int(row["n_options_active"]),
                    "compromise_score": float(row["compromise_score"]),
                    "profile_reuses_candidate": list(selected_indices.values()).count(index) > 1,
                    "selection_reason": {
                        "performance": "RMSE de validation minimale",
                        "compromise": (
                            "distance normalisée minimale parmi les candidats non attribués"
                        ),
                        "parsimony": (
                            "nombre d'options minimal parmi les candidats non attribués"
                        ),
                    }[profile],
                    "solution_index": int(row["solution_index"]),
                }
            )
    return pd.DataFrame(profile_rows)


def solve_regularization_path(
    A: np.ndarray,
    b: np.ndarray,
    vanillas: Sequence[VanillaProduct],
    penalty: str = "l1",
    l1_ratio: float = 0.5,
    n_alphas: int = 25,
    min_alpha_ratio: float = 1e-3,
    ridge_min_alpha_ratio: float = 1e-4,
    ridge_max_alpha_ratio: float = 1e2,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    scale_features: bool = True,
    unpenalized_indices: tuple[int, ...] = (0,),
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
    max_iter: int = 5000,
    tolerance: float = 1e-6,
) -> dict[str, object]:
    """Calibre le solveur proximal sur train et compare sur validation uniquement.

    Le bloc de test est réservé mais aucune prédiction ni métrique de test n'est
    calculée. Les solutions sont parcourues d'alpha fort vers alpha faible avec
    warm start. L0 reste non convexe : le chemin décrit les solutions obtenues,
    sans certifier un optimum global.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape[0] != len(b):
        raise ValueError("A et b ont des dimensions incompatibles.")
    if len(vanillas) != A.shape[1]:
        raise ValueError("Il faut un instrument par colonne de A.")
    if penalty not in {"l0", "l1", "l2", "elastic_net"}:
        raise ValueError("Le chemin accepte uniquement L0, L1, L2 ou Elastic Net.")

    slices = train_validation_test_slices(
        len(b),
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )
    A_train, b_train = A[slices["train"]], b[slices["train"]]
    A_validation = A[slices["validation"]]
    b_validation = b[slices["validation"]]

    if penalty == "l2":
        alpha_reference = ridge_alpha_reference(
            A_train,
            scale_features=scale_features,
            unpenalized_indices=unpenalized_indices,
        )
        alpha_max = None
        alpha_grid = ridge_alpha_grid(
            alpha_reference,
            n_alphas=n_alphas,
            min_reference_ratio=ridge_min_alpha_ratio,
            max_reference_ratio=ridge_max_alpha_ratio,
        )
        alpha_scale_kind = "ridge_spectral_reference"
    elif penalty == "l0":
        alpha_max = l0_alpha_max(
            A_train,
            b_train,
            scale_features=scale_features,
            unpenalized_indices=unpenalized_indices,
        )
        alpha_reference = alpha_max
        alpha_grid = logarithmic_alpha_grid(
            alpha_max,
            n_alphas=n_alphas,
            min_alpha_ratio=min_alpha_ratio,
        )
        alpha_scale_kind = "l0_hard_threshold_reference"
    else:
        effective_l1_ratio = 1.0 if penalty == "l1" else l1_ratio
        alpha_max = lasso_alpha_max(
            A_train,
            b_train,
            scale_features=scale_features,
            l1_ratio=effective_l1_ratio,
            unpenalized_indices=unpenalized_indices,
        )
        alpha_reference = alpha_max
        alpha_grid = logarithmic_alpha_grid(
            alpha_max,
            n_alphas=n_alphas,
            min_alpha_ratio=min_alpha_ratio,
        )
        alpha_scale_kind = "sparsity_alpha_max"

    rows: list[dict[str, object]] = []
    solutions: list[dict[str, object]] = []
    warm_start: np.ndarray | None = None

    for solution_index, alpha in enumerate(alpha_grid):
        optimization = solve_replication(
            A_train,
            b_train,
            SolverConfig(
                solver="proximal" if penalty == "l0" else "fista",
                penalty=penalty,
                alpha=float(alpha),
                l1_ratio=l1_ratio,
                scale_features=scale_features,
                max_iter=max_iter,
                tolerance=tolerance,
                unpenalized_indices=unpenalized_indices,
            ),
            initial_weights=warm_start,
        )
        weights = optimization.weights
        if optimization.converged:
            warm_start = weights.copy()

        train_metrics = benchmark_metrics(b_train, A_train @ weights)
        validation_metrics = benchmark_metrics(
            b_validation, A_validation @ weights
        )
        portfolio_metrics = portfolio_weight_metrics(
            vanillas, weights, active_threshold=active_threshold
        )
        row = {
            "solution_index": solution_index,
            "alpha": float(alpha),
            "alpha_relative": float(alpha / alpha_reference),
            **optimization.metadata(),
            **{f"train_{key}": value for key, value in train_metrics.items()},
            **{
                f"validation_{key}": value
                for key, value in validation_metrics.items()
            },
            **portfolio_metrics,
        }
        rows.append(row)
        solutions.append(
            {
                "solution_index": solution_index,
                "alpha": float(alpha),
                "weights": weights.copy(),
                "validation_predictions": (A_validation @ weights).copy(),
                "validation_residuals": (A_validation @ weights - b_validation).copy(),
                "optimization": optimization.metadata(),
                "metrics_train": train_metrics,
                "metrics_validation": validation_metrics,
                "portfolio_metrics": portfolio_metrics,
            }
        )

    table = pd.DataFrame(rows)
    table["is_pareto"] = _pareto_mask(table)
    n_train = slices["train"].stop - slices["train"].start
    n_validation = slices["validation"].stop - slices["validation"].start
    n_test = slices["test"].stop - slices["test"].start

    return {
        "alpha_max": alpha_max,
        "alpha_reference": alpha_reference,
        "alpha_scale_kind": alpha_scale_kind,
        "alpha_grid": alpha_grid,
        "table": table,
        "solutions": solutions,
        "split": {
            "n_train": n_train,
            "n_validation": n_validation,
            "n_test": n_test,
            "train_fraction": train_fraction,
            "validation_fraction": validation_fraction,
        },
        "test_status": "reserved_not_evaluated",
    }


def solve_penalty_comparison(
    A: np.ndarray,
    b: np.ndarray,
    vanillas: Sequence[VanillaProduct],
    penalties: tuple[str, ...] = ("l1", "l2", "elastic_net"),
    l1_ratio: float = 0.5,
    min_candidate_options: int = 2,
    max_candidate_options: int = 100,
    **path_kwargs: object,
) -> dict[str, object]:
    """Compare plusieurs pénalités sur un dataset et un split identiques.

    ``l1_ratio`` reste fixe pour Elastic Net. Cette fonction ne réalise aucune
    recherche du ratio et n'évalue jamais le bloc de test final.
    """
    if not penalties or len(set(penalties)) != len(penalties):
        raise ValueError("penalties doit contenir des valeurs uniques.")

    results: dict[str, dict[str, object]] = {}
    tables: list[pd.DataFrame] = []
    for penalty in penalties:
        result = solve_regularization_path(
            A=A,
            b=b,
            vanillas=vanillas,
            penalty=penalty,
            l1_ratio=l1_ratio,
            **path_kwargs,
        )
        results[penalty] = result
        table = result["table"].copy()
        if penalty != "elastic_net":
            table["l1_ratio"] = np.nan
        leading_columns = ["penalty", "l1_ratio", "alpha", "alpha_relative"]
        table = table.loc[
            :, leading_columns + [
                column for column in table.columns if column not in leading_columns
            ]
        ]
        tables.append(table)

    statuses = {result["test_status"] for result in results.values()}
    if statuses != {"reserved_not_evaluated"}:
        raise RuntimeError("Le test final doit rester réservé pour chaque pénalité.")
    raw_table = pd.concat(tables, ignore_index=True)
    annotated_table = select_regularization_candidates(
        raw_table,
        min_active_options=min_candidate_options,
        max_active_options=max_candidate_options,
    )
    performance_table = apply_static_performance_filter(
        annotated_table,
        results=results,
    )
    deduplicated_table, duplicate_report = remove_duplicate_candidates(
        performance_table,
        results=results,
    )
    candidates = deduplicated_table.loc[
        deduplicated_table["is_candidate_after_duplicates"]
    ].copy()
    profiles = select_three_profiles_per_penalty(deduplicated_table)
    profile_coverage = pd.DataFrame(
        [
            {
                "penalty": penalty,
                "n_distinct_candidates": int(
                    (candidates["penalty"] == penalty).sum()
                ),
                "n_profiles": int((profiles["penalty"] == penalty).sum())
                if not profiles.empty
                else 0,
                "status": (
                    "three_distinct_profiles"
                    if int((candidates["penalty"] == penalty).sum()) >= 3
                    else "profiles_reuse_candidates"
                    if int((candidates["penalty"] == penalty).sum()) > 0
                    else "no_candidate_after_filters"
                ),
            }
            for penalty in penalties
        ]
    )
    return {
        "results": results,
        "raw_table": raw_table,
        "table": deduplicated_table,
        "candidates": candidates,
        "candidate_policies": candidate_policies(deduplicated_table),
        "profiles": profiles,
        "profile_coverage": profile_coverage,
        "duplicate_report": duplicate_report,
        "candidate_filters": {
            "min_active_options": min_candidate_options,
            "max_active_options": max_candidate_options,
            "pareto_scope": "within_penalty",
            "static_performance": "paired_bootstrap_2000_one_sided_95pct",
            "strict_duplicate_tolerance": "rtol=1e-8, atol=1e-10",
            "quasi_duplicate_support_jaccard": 0.95,
            "quasi_duplicate_relative_weight_distance": 0.05,
            "profiles_per_penalty": 3,
        },
        "penalties": penalties,
        "elastic_net_l1_ratio": l1_ratio,
        "split": next(iter(results.values()))["split"],
        "test_status": "reserved_not_evaluated",
    }
