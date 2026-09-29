"""Interface commune des solveurs de réplication."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .common import fit_linear


@dataclass(frozen=True)
class SolverConfig:
    """Configuration indépendante des futurs algorithmes d'optimisation."""

    solver: str = "legacy"
    penalty: str = "l2"
    alpha: float = 1e-4
    l1_ratio: float = 0.5
    scale_features: bool = True
    huber_delta: float = 1.0
    eps: float = 1e-12
    max_iter: int = 5000
    tolerance: float = 1e-6
    unpenalized_indices: tuple[int, ...] = (0,)
    penalty_weights: tuple[float, ...] | None = None
    fixed_cost_strength: float = 1.0
    proportional_cost_strength: float = 1.0


@dataclass(frozen=True)
class SolverResult:
    """Poids et informations communes retournés par tous les solveurs."""

    weights: np.ndarray
    solver: str
    penalty: str
    alpha: float
    l1_ratio: float
    scale_features: bool
    unpenalized_indices: tuple[int, ...]
    converged: bool
    n_iterations: int | None
    objective_value: float | None
    message: str

    def metadata(self) -> dict[str, object]:
        """Retourne les informations sérialisables sans dupliquer les poids."""
        content = asdict(self)
        content.pop("weights")
        return content


def available_solvers() -> tuple[str, ...]:
    """Liste stable des solveurs accessibles par l'interface."""
    return ("legacy", "fista", "proximal")


def _validate_problem(
    A: np.ndarray,
    b: np.ndarray,
    config: SolverConfig,
) -> tuple[np.ndarray, np.ndarray]:
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    if A.ndim != 2:
        raise ValueError("A doit être une matrice 2D.")
    if A.shape[0] != b.shape[0]:
        raise ValueError("A et b doivent avoir le même nombre de lignes.")
    if A.shape[1] == 0:
        raise ValueError("A doit contenir au moins une colonne.")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(b)):
        raise ValueError("A et b doivent contenir uniquement des valeurs finies.")
    if config.solver not in available_solvers():
        raise ValueError(
            f"Solveur '{config.solver}' inconnu. "
            f"Solveurs disponibles : {available_solvers()}."
        )
    if not np.isfinite(config.alpha) or config.alpha < 0.0:
        raise ValueError("alpha doit être un nombre fini positif ou nul.")
    if not np.isfinite(config.l1_ratio) or not 0.0 <= config.l1_ratio <= 1.0:
        raise ValueError("l1_ratio doit appartenir à [0, 1].")
    if config.max_iter <= 0:
        raise ValueError("max_iter doit être strictement positif.")
    if not np.isfinite(config.tolerance) or config.tolerance <= 0.0:
        raise ValueError("tolerance doit être un nombre fini strictement positif.")

    unpenalized = tuple(config.unpenalized_indices)
    if len(set(unpenalized)) != len(unpenalized):
        raise ValueError("unpenalized_indices ne doit pas contenir de doublon.")
    if any(not isinstance(index, int) for index in unpenalized):
        raise ValueError("unpenalized_indices doit contenir uniquement des entiers.")
    if any(index < 0 or index >= A.shape[1] for index in unpenalized):
        raise ValueError("Un indice non pénalisé est hors des colonnes de A.")

    if config.solver == "fista" and config.penalty not in {
        "l1",
        "l2",
        "elastic_net",
        "weighted_l1",
    }:
        raise ValueError(
            "Le solveur FISTA accepte uniquement les pénalités convexes L1, "
            "L2, Elastic Net ou L1 pondérée."
        )
    if config.solver == "proximal" and config.penalty not in {
        "l0",
        "weighted_l1",
        "fixed_proportional",
    }:
        raise ValueError(
            "Le solveur proximal accepte uniquement L0, L1 pondérée ou "
            "coûts fixes + proportionnels."
        )
    if config.solver == "legacy" and unpenalized != (0,):
        raise ValueError(
            "Le solveur legacy sait uniquement laisser la première colonne "
            "non pénalisée."
        )
    if config.solver == "legacy" and config.penalty_weights is not None:
        raise ValueError("Le solveur legacy ne prend pas en charge penalty_weights.")
    if config.penalty_weights is not None:
        penalty_weights = np.asarray(config.penalty_weights, dtype=float)
        if penalty_weights.shape != (A.shape[1],):
            raise ValueError("penalty_weights doit contenir un coût par colonne de A.")
        if not np.all(np.isfinite(penalty_weights)) or np.any(penalty_weights < 0.0):
            raise ValueError("penalty_weights doit contenir des coûts finis et positifs ou nuls.")
    for name, value in {
        "fixed_cost_strength": config.fixed_cost_strength,
        "proportional_cost_strength": config.proportional_cost_strength,
    }.items():
        if not np.isfinite(value) or value < 0.0:
            raise ValueError(f"{name} doit être fini et positif ou nul.")
    return A, b


def _scaled_problem(
    A: np.ndarray,
    scale_features: bool,
) -> tuple[np.ndarray, np.ndarray]:
    if scale_features:
        column_scale = np.sqrt(np.mean(A**2, axis=0))
        column_scale[column_scale < 1e-12] = 1.0
    else:
        column_scale = np.ones(A.shape[1], dtype=float)
    return A / column_scale, column_scale


def _soft_threshold(values: np.ndarray, threshold: float) -> np.ndarray:
    return np.sign(values) * np.maximum(np.abs(values) - threshold, 0.0)


def _fista_objective(
    A: np.ndarray,
    b: np.ndarray,
    weights: np.ndarray,
    alpha: float,
    l1_strength: float,
    l2_strength: float,
    penalized_mask: np.ndarray,
    penalty_weights: np.ndarray,
    fixed_cost_strength: float = 0.0,
    proportional_cost_strength: float = 0.0,
) -> float:
    residual = A @ weights - b
    penalized_weights = weights[penalized_mask]
    return float(
        0.5 * np.mean(residual**2)
        + alpha * l1_strength * np.sum(
            penalty_weights[penalized_mask] * np.abs(penalized_weights)
        )
        + 0.5 * alpha * l2_strength * np.sum(penalized_weights**2)
        + alpha * fixed_cost_strength * np.count_nonzero(penalized_weights)
        + alpha * proportional_cost_strength * np.sum(
            penalty_weights[penalized_mask] * np.abs(penalized_weights)
        )
    )


def _cost_proximal_operator(
    values: np.ndarray,
    *,
    step_size: float,
    alpha: float,
    penalty_weights: np.ndarray,
    fixed_cost_strength: float,
    proportional_cost_strength: float,
) -> np.ndarray:
    """Prox de coût fixe L0 et coût proportionnel L1 pondéré, coordonnée par coordonnée."""

    proportional_threshold = (
        step_size * alpha * proportional_cost_strength * penalty_weights
    )
    candidate = _soft_threshold(values, proportional_threshold)
    if fixed_cost_strength == 0.0:
        return candidate

    nonzero_cost = (
        0.5 * (candidate - values) ** 2
        + proportional_threshold * np.abs(candidate)
        + step_size * alpha * fixed_cost_strength
    )
    zero_cost = 0.5 * values**2
    return np.where(nonzero_cost < zero_cost, candidate, 0.0)


def _solve_fista(
    A: np.ndarray,
    b: np.ndarray,
    config: SolverConfig,
    initial_weights: np.ndarray | None = None,
) -> SolverResult:
    A_fit, column_scale = _scaled_problem(A, config.scale_features)
    n_observations, n_features = A_fit.shape

    penalized_mask = np.ones(n_features, dtype=bool)
    penalized_mask[list(config.unpenalized_indices)] = False
    penalty_weights = (
        np.ones(n_features, dtype=float)
        if config.penalty_weights is None
        else np.asarray(config.penalty_weights, dtype=float)
    )
    penalty_weights = penalty_weights.copy()
    if config.penalty in {"weighted_l1", "fixed_proportional"}:
        # Ces poids représentent un coût par unité du poids financier original.
        # Le solveur travaille sur w_scaled = w_original * column_scale.
        penalty_weights = penalty_weights / column_scale
    penalty_weights[~penalized_mask] = 0.0

    fixed_cost_strength = 0.0
    proportional_cost_strength = 0.0
    if config.penalty == "l1":
        l1_strength, l2_strength = 1.0, 0.0
    elif config.penalty == "l2":
        l1_strength, l2_strength = 0.0, 1.0
    elif config.penalty == "elastic_net":
        l1_strength = config.l1_ratio
        l2_strength = 1.0 - config.l1_ratio
    elif config.penalty == "weighted_l1":
        l1_strength, l2_strength = 1.0, 0.0
    elif config.penalty == "l0":
        l1_strength, l2_strength = 0.0, 0.0
        fixed_cost_strength = 1.0
    else:
        l1_strength, l2_strength = 0.0, 0.0
        fixed_cost_strength = config.fixed_cost_strength
        proportional_cost_strength = config.proportional_cost_strength

    # La norme spectrale donne la constante de Lipschitz exacte du gradient de
    # la perte quadratique. Elle est nettement moins conservatrice que la norme
    # de Frobenius lorsque les payoffs d'options sont fortement corrélés.
    spectral_norm = float(np.linalg.norm(A_fit, ord=2))
    lipschitz = spectral_norm**2 / n_observations
    lipschitz += config.alpha * l2_strength
    if not np.isfinite(lipschitz) or lipschitz <= 0.0:
        lipschitz = 1.0
    step_size = 1.0 / lipschitz

    if initial_weights is None:
        weights = np.zeros(n_features, dtype=float)
        if np.any(~penalized_mask):
            unpenalized_weights, *_ = np.linalg.lstsq(
                A_fit[:, ~penalized_mask], b, rcond=None
            )
            weights[~penalized_mask] = unpenalized_weights
    else:
        initial_weights = np.asarray(initial_weights, dtype=float).reshape(-1)
        if len(initial_weights) != n_features:
            raise ValueError(
                "initial_weights doit avoir une valeur par colonne de A."
            )
        if not np.all(np.isfinite(initial_weights)):
            raise ValueError("initial_weights doit contenir des valeurs finies.")
        # Les poids fournis et retournés utilisent les unités originales. Le
        # solveur travaille, lui, dans les coordonnées normalisées.
        weights = initial_weights * column_scale
    extrapolated = weights.copy()
    momentum = 1.0
    converged = False
    n_iterations = 0

    for iteration in range(1, config.max_iter + 1):
        residual = A_fit @ extrapolated - b
        gradient = (A_fit.T @ residual) / n_observations
        gradient[penalized_mask] += (
            config.alpha * l2_strength * extrapolated[penalized_mask]
        )

        next_weights = extrapolated - step_size * gradient
        if fixed_cost_strength > 0.0 or proportional_cost_strength > 0.0:
            next_weights[penalized_mask] = _cost_proximal_operator(
                next_weights[penalized_mask],
                step_size=step_size,
                alpha=config.alpha,
                penalty_weights=penalty_weights[penalized_mask],
                fixed_cost_strength=fixed_cost_strength,
                proportional_cost_strength=proportional_cost_strength,
            )
        else:
            next_weights[penalized_mask] = _soft_threshold(
                next_weights[penalized_mask],
                step_size * config.alpha * l1_strength
                * penalty_weights[penalized_mask],
            )

        difference = np.linalg.norm(next_weights - weights)
        reference = max(1.0, np.linalg.norm(next_weights))
        n_iterations = iteration
        if difference <= config.tolerance * reference:
            weights = next_weights
            converged = True
            break

        # Les pénalités contenant L0 sont non convexes : on utilise alors un
        # gradient proximal sans accélération afin d'éviter que le momentum ne
        # fasse osciller le support actif.
        if fixed_cost_strength > 0.0:
            extrapolated = next_weights.copy()
            weights = next_weights
            momentum = 1.0
            continue

        # Redémarrage adaptatif : lorsque l'extrapolation pointe à l'opposé de
        # la progression proximale, on annule le momentum. Cela évite les
        # oscillations persistantes sur les bases d'options très corrélées.
        should_restart = float(
            np.dot(extrapolated - next_weights, next_weights - weights)
        ) > 0.0
        if should_restart:
            next_momentum = 1.0
            extrapolated = next_weights.copy()
        else:
            next_momentum = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * momentum**2))
            extrapolated = next_weights + (
                (momentum - 1.0) / next_momentum
            ) * (next_weights - weights)
        weights = next_weights
        momentum = next_momentum

    objective_value = _fista_objective(
        A=A_fit,
        b=b,
        weights=weights,
        alpha=config.alpha,
        l1_strength=l1_strength,
        l2_strength=l2_strength,
        penalized_mask=penalized_mask,
        penalty_weights=penalty_weights,
        fixed_cost_strength=fixed_cost_strength,
        proportional_cost_strength=proportional_cost_strength,
    )
    final_weights = weights / column_scale
    if not np.all(np.isfinite(final_weights)) or not np.isfinite(objective_value):
        raise RuntimeError("FISTA a produit un résultat non fini.")

    return SolverResult(
        weights=final_weights,
        solver=config.solver,
        penalty=config.penalty,
        alpha=float(config.alpha),
        l1_ratio=float(config.l1_ratio),
        scale_features=bool(config.scale_features),
        unpenalized_indices=tuple(config.unpenalized_indices),
        converged=converged,
        n_iterations=n_iterations,
        objective_value=objective_value,
        message=(
            ("Gradient proximal a convergé." if config.solver == "proximal" else "FISTA a convergé.")
            if converged
            else (
                "Gradient proximal a atteint max_iter avant le critère de convergence."
                if config.solver == "proximal"
                else "FISTA a atteint max_iter avant le critère de convergence."
            )
        ),
    )


def solve_replication(
    A: np.ndarray,
    b: np.ndarray,
    config: SolverConfig | None = None,
    initial_weights: np.ndarray | None = None,
) -> SolverResult:
    """Résout la calibration avec une interface commune et rétrocompatible.

    ``legacy`` préserve les résultats historiques via ``fit_linear``. ``fista``
    traite les objectifs convexes L1, L2, Elastic Net et L1 pondérée.
    ``proximal`` traite L0 et la combinaison coût fixe + proportionnel par
    seuillage dur, sans garantie d'optimum global. L1, L1 pondérée et Elastic
    Net peuvent produire des zéros exacts ; L2 réduit les poids sans garantir
    leur annulation.
    """
    config = config or SolverConfig()
    A, b = _validate_problem(A, b, config)

    if config.solver in {"fista", "proximal"}:
        return _solve_fista(A, b, config, initial_weights=initial_weights)

    if initial_weights is not None:
        raise ValueError(
            "Le solveur legacy ne prend pas en charge initial_weights."
        )

    weights = fit_linear(
        A=A,
        b=b,
        scale_features=config.scale_features,
        penalty=config.penalty,
        alpha=config.alpha,
        l1_ratio=config.l1_ratio,
        huber_delta=config.huber_delta,
        eps=config.eps,
        max_iter=config.max_iter,
        tol=config.tolerance,
    )
    weights = np.asarray(weights, dtype=float).reshape(-1)
    if not np.all(np.isfinite(weights)):
        raise RuntimeError("Le solveur legacy a retourné des poids non finis.")

    return SolverResult(
        weights=weights,
        solver=config.solver,
        penalty=config.penalty,
        alpha=float(config.alpha),
        l1_ratio=float(config.l1_ratio),
        scale_features=bool(config.scale_features),
        unpenalized_indices=tuple(config.unpenalized_indices),
        converged=True,
        n_iterations=None,
        objective_value=None,
        message=(
            "Résultat produit par fit_linear. Le nombre d'itérations et la "
            "valeur de l'objectif ne sont pas exposés par l'ancienne interface."
        ),
    )
