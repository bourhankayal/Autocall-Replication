"""Diagnostics de parcimonie des portefeuilles de réplication."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from ..products import Cash, VanillaProduct


DEFAULT_ACTIVE_THRESHOLD = 1e-6


def _validate_inputs(
    weights: np.ndarray,
    cash_mask: np.ndarray,
    active_threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    weights = np.asarray(weights, dtype=float).reshape(-1)
    cash_mask = np.asarray(cash_mask, dtype=bool).reshape(-1)

    if len(weights) != len(cash_mask):
        raise ValueError("weights et cash_mask doivent avoir la même longueur.")
    if not np.all(np.isfinite(weights)):
        raise ValueError("Tous les poids doivent être finis.")
    if not np.isfinite(active_threshold) or active_threshold < 0.0:
        raise ValueError("active_threshold doit être un nombre fini positif ou nul.")
    return weights, cash_mask


def _weight_metrics(
    weights: np.ndarray,
    cash_mask: np.ndarray,
    active_threshold: float,
) -> dict[str, int | float]:
    weights, cash_mask = _validate_inputs(weights, cash_mask, active_threshold)
    option_mask = ~cash_mask
    active_mask = np.abs(weights) > active_threshold
    active_option_mask = active_mask & option_mask
    active_option_weights = weights[active_option_mask]

    sum_abs_option_weights = float(np.sum(np.abs(active_option_weights)))
    sorted_abs_options = np.sort(np.abs(active_option_weights))[::-1]

    def concentration(top_n: int) -> float:
        if sum_abs_option_weights == 0.0:
            return 0.0
        return float(np.sum(sorted_abs_options[:top_n]) / sum_abs_option_weights)

    n_total = int(len(weights))
    n_options_total = int(np.sum(option_mask))
    n_active = int(np.sum(active_mask))
    n_options_active = int(np.sum(active_option_mask))

    return {
        "active_threshold": float(active_threshold),
        "n_instruments_total": n_total,
        "n_instruments_active": n_active,
        "n_instruments_inactive": n_total - n_active,
        "active_ratio": float(n_active / n_total) if n_total else 0.0,
        "n_cash": int(np.sum(cash_mask)),
        "n_cash_active": int(np.sum(active_mask & cash_mask)),
        "n_options_total": n_options_total,
        "n_options_active": n_options_active,
        "option_active_ratio": (
            float(n_options_active / n_options_total) if n_options_total else 0.0
        ),
        "n_options_long": int(np.sum(active_option_weights > 0.0)),
        "n_options_short": int(np.sum(active_option_weights < 0.0)),
        "sum_abs_weights": float(np.sum(np.abs(weights[active_mask]))),
        "net_weight": float(np.sum(weights[active_mask])),
        "net_cash_weight": float(np.sum(weights[active_mask & cash_mask])),
        "sum_abs_option_weights": sum_abs_option_weights,
        "net_option_weight": float(np.sum(active_option_weights)),
        "max_abs_option_weight": (
            float(np.max(np.abs(active_option_weights)))
            if len(active_option_weights)
            else 0.0
        ),
        "top_1_option_concentration": concentration(1),
        "top_5_option_concentration": concentration(5),
    }


def portfolio_weight_metrics(
    vanillas: Sequence[VanillaProduct],
    weights: np.ndarray,
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
) -> dict[str, int | float]:
    """Mesure la parcimonie des poids, en séparant le cash des options.

    Un poids est actif uniquement si ``abs(weight) > active_threshold``. Les
    concentrations sont calculées sur les options actives, hors cash. Ces
    quantités décrivent des nombres de contrats et non des expositions
    monétaires, qui nécessiteront des prix de marché.
    """
    weights = np.asarray(weights, dtype=float).reshape(-1)
    if len(vanillas) != len(weights):
        raise ValueError("Le nombre d'instruments doit être égal au nombre de poids.")
    cash_mask = np.asarray([isinstance(vanilla, Cash) for vanilla in vanillas])
    return _weight_metrics(weights, cash_mask, active_threshold)


def grouped_portfolio_weight_metrics(
    weights_table: pd.DataFrame,
    group_columns: Sequence[str] = ("date", "state"),
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
) -> pd.DataFrame:
    """Calcule les diagnostics pour chaque portefeuille date/état.

    ``weights_table`` doit contenir ``weight`` et ``kind``. Une ligne dont
    ``kind == 'Cash'`` est traitée comme la jambe cash.
    """
    required_columns = {"weight", "kind", *group_columns}
    missing = sorted(required_columns - set(weights_table.columns))
    if missing:
        raise ValueError(f"Colonnes manquantes dans weights_table : {missing}")

    rows: list[dict[str, object]] = []
    grouper: str | list[str] = (
        group_columns[0] if len(group_columns) == 1 else list(group_columns)
    )
    for group_key, group in weights_table.groupby(grouper, dropna=False, sort=True):
        keys = group_key if isinstance(group_key, tuple) else (group_key,)
        metrics = _weight_metrics(
            group["weight"].to_numpy(dtype=float),
            group["kind"].eq("Cash").to_numpy(dtype=bool),
            active_threshold,
        )
        rows.append({**dict(zip(group_columns, keys)), **metrics})

    return pd.DataFrame(rows)


def portfolio_metrics_summary(
    metrics: Mapping[str, int | float] | pd.Series,
) -> str:
    """Produit une phrase courte qui expose le diagnostic principal."""
    values = dict(metrics)
    required = {
        "n_options_active",
        "n_options_total",
        "option_active_ratio",
        "n_options_long",
        "n_options_short",
        "sum_abs_option_weights",
        "net_option_weight",
        "top_5_option_concentration",
    }
    missing = sorted(required - set(values))
    if missing:
        raise ValueError(f"Métriques manquantes pour le résumé : {missing}")

    active_ratio = float(values["option_active_ratio"])
    if active_ratio <= 0.10:
        diagnosis = "portefeuille très parcimonieux"
    elif active_ratio <= 0.35:
        diagnosis = "portefeuille parcimonieux"
    elif active_ratio <= 0.70:
        diagnosis = "parcimonie intermédiaire"
    else:
        diagnosis = "portefeuille peu parcimonieux"

    return (
        f"Parcimonie : {int(values['n_options_active'])} / "
        f"{int(values['n_options_total'])} options actives "
        f"({active_ratio:.2%}) — {diagnosis}.\n"
        f"Positions : {int(values['n_options_long'])} longues | "
        f"{int(values['n_options_short'])} courtes.\n"
        f"Exposition en poids : {float(values['sum_abs_option_weights']):.4f} "
        f"brute | {float(values['net_option_weight']):.4f} nette.\n"
        f"Concentration des cinq premières options : "
        f"{float(values['top_5_option_concentration']):.2%}."
    )


def format_portfolio_metrics(
    metrics: Mapping[str, int | float] | pd.Series,
) -> pd.DataFrame:
    """Transforme le dictionnaire technique en tableau français interprétable.

    Les expositions restent exprimées en nombres de contrats/poids. Elles ne
    constituent pas encore des expositions monétaires faute de prix de marché.
    """
    values = dict(metrics)
    required = {
        "active_threshold",
        "n_options_total",
        "n_options_active",
        "option_active_ratio",
        "n_options_long",
        "n_options_short",
        "sum_abs_option_weights",
        "net_option_weight",
        "max_abs_option_weight",
        "top_1_option_concentration",
        "top_5_option_concentration",
        "net_cash_weight",
    }
    missing = sorted(required - set(values))
    if missing:
        raise ValueError(f"Métriques manquantes pour l'affichage : {missing}")

    rows = [
        (
            "Sélection",
            "Options disponibles",
            f"{int(values['n_options_total'])}",
            "Nombre d'options proposées au solveur.",
        ),
        (
            "Sélection",
            "Options actives",
            f"{int(values['n_options_active'])}",
            "Poids absolu strictement supérieur au seuil.",
        ),
        (
            "Sélection",
            "Taux d'activation",
            f"{float(values['option_active_ratio']):.2%}",
            "Plus ce taux est faible, plus le portefeuille est parcimonieux.",
        ),
        (
            "Sélection",
            "Seuil d'activité",
            f"{float(values['active_threshold']):.2e}",
            "Seuil numérique utilisé pour déclarer un poids actif.",
        ),
        (
            "Direction",
            "Options longues",
            f"{int(values['n_options_long'])}",
            "Options dont le poids est positif.",
        ),
        (
            "Direction",
            "Options courtes",
            f"{int(values['n_options_short'])}",
            "Options dont le poids est négatif.",
        ),
        (
            "Exposition",
            "Poids brut des options",
            f"{float(values['sum_abs_option_weights']):.4f}",
            "Somme des valeurs absolues ; ce n'est pas encore un montant.",
        ),
        (
            "Exposition",
            "Poids net des options",
            f"{float(values['net_option_weight']):.4f}",
            "Somme algébrique des poids longs et courts.",
        ),
        (
            "Risque",
            "Poids maximal absolu",
            f"{float(values['max_abs_option_weight']):.4f}",
            "Plus grande position individuelle en valeur absolue.",
        ),
        (
            "Concentration",
            "Première option",
            f"{float(values['top_1_option_concentration']):.2%}",
            "Part du poids brut portée par la première option.",
        ),
        (
            "Concentration",
            "Cinq premières options",
            f"{float(values['top_5_option_concentration']):.2%}",
            "Part du poids brut portée par les cinq premières options.",
        ),
        (
            "Cash",
            "Poids net du cash",
            f"{float(values['net_cash_weight']):.4f}",
            "Jambe non pénalisée ; ce n'est pas encore un montant monétaire.",
        ),
    ]
    return pd.DataFrame(
        rows, columns=["Catégorie", "Indicateur", "Valeur", "Interprétation"]
    )


def format_grouped_portfolio_metrics(
    metrics_table: pd.DataFrame,
    group_columns: Sequence[str] = ("date", "state"),
) -> pd.DataFrame:
    """Réduit les diagnostics date/état aux colonnes les plus interprétables."""
    required = {
        *group_columns,
        "n_options_total",
        "n_options_active",
        "option_active_ratio",
        "n_options_long",
        "n_options_short",
        "sum_abs_option_weights",
        "net_option_weight",
        "top_5_option_concentration",
        "net_cash_weight",
    }
    missing = sorted(required - set(metrics_table.columns))
    if missing:
        raise ValueError(f"Colonnes manquantes pour l'affichage : {missing}")

    result = metrics_table.loc[
        :,
        [
            *group_columns,
            "n_options_total",
            "n_options_active",
            "option_active_ratio",
            "n_options_long",
            "n_options_short",
            "sum_abs_option_weights",
            "net_option_weight",
            "top_5_option_concentration",
            "net_cash_weight",
        ],
    ].copy()
    result["option_active_ratio"] *= 100.0
    result["top_5_option_concentration"] *= 100.0
    return result.rename(
        columns={
            "n_options_total": "Options disponibles",
            "n_options_active": "Options actives",
            "option_active_ratio": "Taux actif (%)",
            "n_options_long": "Longues",
            "n_options_short": "Courtes",
            "sum_abs_option_weights": "Poids brut options",
            "net_option_weight": "Poids net options",
            "top_5_option_concentration": "Top 5 (%)",
            "net_cash_weight": "Poids cash",
        }
    )
