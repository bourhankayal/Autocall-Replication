"""Diagnostic commun des deux objectifs conditionnels, sans recalibration."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .conditional_policy import POOLED_STATE, _alive_at_decision, _state_before_payment
from .semi_static import predict_conditional_path_data
from .risk import tail_risk_metrics


def compare_conditional_methods(
    per_date_result: dict[str, object],
    total_result: dict[str, object],
    per_date_dataset: list[dict[str, object]],
    total_dataset: list[dict[str, object]],
    penalty: str,
    profile: str = "compromise",
    notional: float = 100.0,
) -> dict[str, pd.DataFrame]:
    """Evaluate frozen weights on identical paths, in percent of notional.

    ``per_date_dataset`` must contain the first method's feature basis and
    ``total_dataset`` the second method's basis, in the same path order. This
    function does not select or train any coefficient or hyperparameter.
    """
    if not np.isfinite(notional) or notional <= 0:
        raise ValueError("notional doit être strictement positif et fini.")
    if not per_date_dataset or len(per_date_dataset) != len(total_dataset):
        raise ValueError("Les deux jeux de trajectoires doivent être non vides et appariés.")

    dates = pd.DatetimeIndex(per_date_result["dates"])
    profiles = pd.DataFrame(total_result["profiles"])
    selected = profiles.loc[
        profiles["penalty"].eq(penalty) & profiles["profile"].eq(profile)
    ]
    if len(selected) != 1:
        raise ValueError(f"Profil absent ou ambigu : {penalty}/{profile}.")
    solution_index = int(selected.iloc[0]["solution_index"])
    weights = np.asarray(
        total_result["results"][penalty]["solutions"][solution_index]["weights"],
        dtype=float,
    )
    feature_table = pd.DataFrame(total_result["feature_table"])
    columns_by_node = {
        int(node["node_index"]): feature_table.index[
            feature_table["node_index"].eq(node["node_index"])
        ].to_numpy(dtype=int)
        for node in total_result["nodes"]
    }
    targets = []
    predictions_by_date = []
    predictions_total = []
    for path_index, (per_date_path, total_path) in enumerate(
        zip(per_date_dataset, total_dataset, strict=True)
    ):
        if not per_date_path["path"].equals(total_path["path"]):
            raise ValueError(f"Trajectoire {path_index} non identique entre méthodes.")
        if not dates.equals(pd.DatetimeIndex(total_path["dates"])):
            raise ValueError("Les dates de paiement diffèrent entre méthodes.")
        target = np.asarray(total_path["y_curve"], dtype=float)
        if not np.allclose(target, per_date_path["y_curve"], atol=1e-10, rtol=0):
            raise ValueError("Les flux contractuels diffèrent entre méthodes.")
        per_date_prediction = predict_conditional_path_data(
            per_date_path,
            per_date_result["models"],
            split_final_by_barrier=per_date_result["split_final_by_barrier"],
        )
        total_prediction = np.zeros(len(dates), dtype=float)
        for date_index in range(len(dates)):
            if not _alive_at_decision(total_path, date_index):
                continue
            state = _state_before_payment(total_path, date_index)
            node_index = total_result["assignments"].get(
                (date_index, state),
                total_result["assignments"].get((date_index, POOLED_STATE)),
            )
            if node_index is None:
                continue
            node = total_result["nodes"][node_index]
            source_indices = np.asarray(node["feature_indices"], dtype=int)
            total_prediction[date_index] = float(
                total_path["X_curve"][date_index, source_indices]
                @ weights[columns_by_node[node_index]]
            )
        if len(total_prediction) != len(dates):
            raise ValueError("Le nombre de paiements de la politique est incohérent.")
        targets.append(target)
        predictions_by_date.append(per_date_prediction)
        predictions_total.append(total_prediction)

    target_matrix = np.stack(targets)
    predictions = {
        "par_echeance": np.stack(predictions_by_date),
        "total_pathwise": np.stack(predictions_total),
    }
    scale = 100.0 / notional
    summary_rows = []
    date_rows = []
    for method, replica in predictions.items():
        shortfall = (target_matrix - replica) * scale
        terminal = shortfall.sum(axis=1)
        funding_need = np.maximum(0.0, np.cumsum(shortfall, axis=1).max(axis=1))
        metrics = tail_risk_metrics(terminal, levels=(0.975,))
        summary_rows.append({
            "method": method,
            "n_paths": len(terminal),
            "cashflow_rmse_pct_notional": float(np.sqrt(np.mean(shortfall**2))),
            "terminal_mean_error_pct_notional": metrics["mean_loss"],
            "terminal_mae_pct_notional": metrics["mae"],
            "terminal_rmse_pct_notional": metrics["rmse"],
            "terminal_under_replication_rate": metrics["under_replication_rate"],
            "terminal_es_975_pct_notional": metrics["es_975"],
            "terminal_max_loss_pct_notional": metrics["max_loss"],
            "mean_funding_need_pct_notional": float(np.mean(funding_need)),
            "p95_funding_need_pct_notional": float(np.quantile(funding_need, 0.95)),
        })
        for date_index, date in enumerate(dates):
            date_metrics = tail_risk_metrics(shortfall[:, date_index], levels=(0.975,))
            date_rows.append({
                "method": method,
                "payment_date": pd.Timestamp(date),
                "rmse_pct_notional": float(np.sqrt(np.mean(shortfall[:, date_index]**2))),
                "mean_shortfall_pct_notional": float(np.mean(shortfall[:, date_index])),
                "mae_pct_notional": date_metrics["mae"],
                "under_replication_rate": date_metrics["under_replication_rate"],
                "es_975_pct_notional": date_metrics["es_975"],
                "max_loss_pct_notional": date_metrics["max_loss"],
            })
    return {"summary": pd.DataFrame(summary_rows), "by_date": pd.DataFrame(date_rows)}
