"""Politique conditionnelle chronologique de réplication de l'autocall.

Une position associée à une date de paiement est choisie au temps initial ou
juste après l'observation précédente. L'état constaté à la date de paiement ne
peut donc jamais servir à choisir rétroactivement cette position.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..products import AutocallProduct, VanillaProduct
from .common import benchmark_metrics, contractual_simulation_end_date
from .portfolio_diagnostics import DEFAULT_ACTIVE_THRESHOLD
from .regularization_path import solve_penalty_comparison
from .semi_static import (
    build_conditional_curve_dataset,
    build_conditional_vanilla_basis,
)
from .static_cashflows import effective_date_on_path


INITIAL_STATE = "initial"
POOLED_STATE = "pooled"
BARRIER_CLEAR_STATE = "barrier_clear"
BARRIER_HIT_STATE = "barrier_hit"


def _state_before_payment(path_data: dict[str, object], date_index: int) -> str:
    """État disponible au dernier instant de décision, sans anticipation."""
    if date_index == 0:
        return INITIAL_STATE
    return (
        BARRIER_HIT_STATE
        if bool(path_data["barrier_hit"][date_index - 1])
        else BARRIER_CLEAR_STATE
    )


def _alive_at_decision(path_data: dict[str, object], date_index: int) -> bool:
    """Indique si un panier peut être ouvert pour la prochaine échéance."""
    if date_index == 0:
        return True
    # alive_before à i vaut faux si un rappel a eu lieu à une date antérieure.
    return bool(path_data["alive_before"][date_index])


def _features_by_payment_date(
    vanillas: Sequence[VanillaProduct],
    dates: pd.DatetimeIndex,
    reference_path: pd.Series,
) -> dict[int, np.ndarray]:
    result: dict[int, np.ndarray] = {}
    for date_index, date in enumerate(dates):
        indices = [
            index
            for index, vanilla in enumerate(vanillas)
            if effective_date_on_path(reference_path, vanilla.maturity_date) == date
        ]
        if not indices:
            raise ValueError(f"Aucun instrument ne paie à la date {date}.")
        result[date_index] = np.asarray(indices, dtype=int)
    return result


def build_policy_nodes(
    dataset: Sequence[dict[str, object]],
    train_stop: int,
    feature_indices_by_date: dict[int, np.ndarray],
    min_state_paths: int = 20,
) -> tuple[list[dict[str, object]], dict[tuple[int, str], int]]:
    """Définit les portefeuilles disponibles à partir du seul bloc train.

    À partir de la deuxième échéance, un nœud spécifique est créé si l'état
    compte assez de trajectoires train. Sinon la trajectoire utilise le nœud
    mutualisé de la date. Ce repli évite d'apprendre l'existence d'un état sur
    la validation ou le test.
    """
    if min_state_paths < 1:
        raise ValueError("min_state_paths doit être strictement positif.")
    if not 1 <= train_stop <= len(dataset):
        raise ValueError("train_stop est incompatible avec le dataset.")

    dates = pd.DatetimeIndex(dataset[0]["dates"])
    nodes: list[dict[str, object]] = []
    assignments: dict[tuple[int, str], int] = {}

    def add_node(date_index: int, state: str, n_train_paths: int) -> int:
        node_index = len(nodes)
        nodes.append(
            {
                "node_index": node_index,
                "payment_date_index": date_index,
                "payment_date": pd.Timestamp(dates[date_index]),
                "decision_date": (
                    None if date_index == 0 else pd.Timestamp(dates[date_index - 1])
                ),
                "decision_state": state,
                "feature_indices": feature_indices_by_date[date_index].copy(),
                "n_train_paths": int(n_train_paths),
            }
        )
        return node_index

    for date_index in range(len(dates)):
        alive_train = [
            item
            for item in dataset[:train_stop]
            if _alive_at_decision(item, date_index)
        ]
        if not alive_train:
            continue
        if date_index == 0:
            assignments[(date_index, INITIAL_STATE)] = add_node(
                date_index, INITIAL_STATE, len(alive_train)
            )
            continue

        pooled_index = add_node(date_index, POOLED_STATE, len(alive_train))
        assignments[(date_index, POOLED_STATE)] = pooled_index
        for state in (BARRIER_CLEAR_STATE, BARRIER_HIT_STATE):
            count = sum(_state_before_payment(item, date_index) == state for item in alive_train)
            assignments[(date_index, state)] = (
                add_node(date_index, state, count)
                if count >= min_state_paths
                else pooled_index
            )
    return nodes, assignments


def assemble_policy_design(
    dataset: Sequence[dict[str, object]],
    nodes: Sequence[dict[str, object]],
    assignments: dict[tuple[int, str], int],
    vanillas: Sequence[VanillaProduct],
) -> dict[str, object]:
    """Assemble la matrice bloc de la politique et la cible totale pathwise."""
    column_offsets: dict[int, tuple[int, int]] = {}
    feature_vanillas: list[VanillaProduct] = []
    feature_rows: list[dict[str, object]] = []
    cursor = 0
    for node in nodes:
        node_index = int(node["node_index"])
        indices = np.asarray(node["feature_indices"], dtype=int)
        start, stop = cursor, cursor + len(indices)
        column_offsets[node_index] = (start, stop)
        for local_index, vanilla_index in enumerate(indices):
            vanilla = vanillas[int(vanilla_index)]
            feature_vanillas.append(vanilla)
            feature_rows.append(
                {
                    "column_index": start + local_index,
                    "node_index": node_index,
                    "payment_date": node["payment_date"],
                    "decision_date": node["decision_date"],
                    "decision_state": node["decision_state"],
                    "instrument_index": int(vanilla_index),
                    "name": vanilla.name,
                    "kind": vanilla.__class__.__name__,
                    "strike": float(vanilla.strike),
                    "maturity_date": pd.Timestamp(vanilla.maturity_date),
                }
            )
        cursor = stop

    A = np.zeros((len(dataset), cursor), dtype=float)
    b = np.zeros(len(dataset), dtype=float)
    visit_rows: list[dict[str, object]] = []
    for path_index, path_data in enumerate(dataset):
        b[path_index] = float(np.sum(path_data["y_curve"]))
        n_dates = len(path_data["dates"])
        for date_index in range(n_dates):
            if not _alive_at_decision(path_data, date_index):
                continue
            state = _state_before_payment(path_data, date_index)
            node_index = assignments.get(
                (date_index, state), assignments.get((date_index, POOLED_STATE))
            )
            if node_index is None:
                continue
            node = nodes[node_index]
            indices = np.asarray(node["feature_indices"], dtype=int)
            start, stop = column_offsets[node_index]
            A[path_index, start:stop] = path_data["X_curve"][date_index, indices]
            visit_rows.append(
                {
                    "path_index": path_index,
                    "payment_date_index": date_index,
                    "payment_date": pd.Timestamp(path_data["dates"][date_index]),
                    "information_date": (
                        None
                        if date_index == 0
                        else pd.Timestamp(path_data["dates"][date_index - 1])
                    ),
                    "observed_state": state,
                    "selected_node_index": node_index,
                    "selected_node_state": node["decision_state"],
                    "uses_fallback": state != node["decision_state"],
                }
            )

    unpenalized_indices = tuple(
        row["column_index"] for row in feature_rows if row["kind"] == "Cash"
    )
    return {
        "A": A,
        "b": b,
        "feature_vanillas": feature_vanillas,
        "feature_table": pd.DataFrame(feature_rows),
        "visits": pd.DataFrame(visit_rows),
        "column_offsets": column_offsets,
        "unpenalized_indices": unpenalized_indices,
    }


def _add_policy_diagnostics(result: dict[str, object]) -> None:
    feature_table = pd.DataFrame(result["feature_table"])
    visits = pd.DataFrame(result["visits"])
    visit_frequency = visits["selected_node_index"].value_counts(normalize=True)
    for penalty_result in result["results"].values():
        for solution in penalty_result["solutions"]:
            weights = np.asarray(solution["weights"], dtype=float)
            active = np.abs(weights) > result["active_threshold"]
            active_options = active & feature_table["kind"].ne("Cash").to_numpy()
            active_by_node = (
                pd.DataFrame(
                    {
                        "node": feature_table["node_index"],
                        "active": active_options,
                        "abs_weight": np.abs(weights),
                    }
                )
                .groupby("node")
                .agg(n_active=("active", "sum"), gross_weight=("abs_weight", "sum"))
            )
            frequencies = active_by_node.index.to_series().map(visit_frequency).fillna(0.0)
            solution["policy_metrics"] = {
                "n_policy_nodes": int(feature_table["node_index"].nunique()),
                "n_unique_instruments": int(
                    feature_table.loc[active, ["name", "maturity_date"]].drop_duplicates().shape[0]
                ),
                "mean_active_options_per_visited_node": float(
                    np.average(active_by_node["n_active"], weights=frequencies)
                    if frequencies.sum() > 0
                    else 0.0
                ),
                "max_active_options_in_node": int(active_by_node["n_active"].max()),
                "expected_gross_weight_per_visit": float(
                    np.average(active_by_node["gross_weight"], weights=frequencies)
                    if frequencies.sum() > 0
                    else 0.0
                ),
            }


def run_conditional_policy_penalty_comparison(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    family: str,
    penalties: tuple[str, ...] = ("l1", "l2", "elastic_net"),
    elastic_net_l1_ratio: float = 0.5,
    n_paths: int = 3000,
    spot_min_mult: float = 0.70,
    spot_max_mult: float = 1.30,
    n_alphas: int = 25,
    min_alpha_ratio: float = 1e-3,
    ridge_min_alpha_ratio: float = 1e-4,
    ridge_max_alpha_ratio: float = 1e2,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
    min_candidate_options: int = 2,
    max_candidate_options: int = 100,
    min_state_paths: int = 20,
    max_iter: int = 5000,
    tolerance: float = 1e-6,
    seed: int = 42,
) -> dict[str, object]:
    """Sélectionne un alpha global pour une politique conditionnelle pathwise.

    Une ligne de la régression représente une trajectoire entière. Les colonnes
    sont les instruments propres aux nœuds date/état visités. La validation
    minimise donc l'écart sur le payoff total actualisé de chaque trajectoire.
    """
    if family not in {"calls_puts", "full"}:
        raise ValueError("La politique conditionnelle accepte calls_puts ou full.")
    if n_paths < 3:
        raise ValueError("n_paths doit être supérieur ou égal à 3.")
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = contractual_simulation_end_date(
        product=product,
        contract_start_date=valuation_date,
        requested_maturity_date=maturity_date,
    )
    vanillas = build_conditional_vanilla_basis(
        product=product,
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        family=family,
        spot_min_mult=spot_min_mult,
        spot_max_mult=spot_max_mult,
    )
    dataset = build_conditional_curve_dataset(
        product=product,
        vanillas=vanillas,
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
    )
    n_train = max(1, int(train_fraction * n_paths))
    n_validation = max(1, int(validation_fraction * n_paths))
    if n_train + n_validation >= n_paths:
        n_validation = n_paths - n_train - 1
    dates = pd.DatetimeIndex(dataset[0]["dates"])
    features_by_date = _features_by_payment_date(
        vanillas, dates, dataset[0]["path"]
    )
    nodes, assignments = build_policy_nodes(
        dataset,
        train_stop=n_train,
        feature_indices_by_date=features_by_date,
        min_state_paths=min_state_paths,
    )
    design = assemble_policy_design(dataset, nodes, assignments, vanillas)
    result = solve_penalty_comparison(
        A=design["A"],
        b=design["b"],
        vanillas=design["feature_vanillas"],
        penalties=penalties,
        l1_ratio=elastic_net_l1_ratio,
        n_alphas=n_alphas,
        min_alpha_ratio=min_alpha_ratio,
        ridge_min_alpha_ratio=ridge_min_alpha_ratio,
        ridge_max_alpha_ratio=ridge_max_alpha_ratio,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
        unpenalized_indices=design["unpenalized_indices"],
        active_threshold=active_threshold,
        min_candidate_options=min_candidate_options,
        max_candidate_options=max_candidate_options,
        max_iter=max_iter,
        tolerance=tolerance,
    )
    result.update(
        {
            "vanillas": design["feature_vanillas"],
            "product": product,
            "source_vanillas": vanillas,
            "dataset": dataset,
            "A": design["A"],
            "b": design["b"],
            "dates": dates,
            "nodes": nodes,
            "assignments": assignments,
            "feature_table": design["feature_table"],
            "visits": design["visits"],
            "unpenalized_indices": design["unpenalized_indices"],
            "family": family,
            "n_paths": n_paths,
            "seed": seed,
            "active_threshold": active_threshold,
            "min_state_paths": min_state_paths,
            "chronology": "state_at_previous_observation_selects_next_payment_portfolio",
            "selection_objective": "total_discounted_pathwise_payoff_error",
            "post_recall_policy": "stop_no_new_position",
            "liquidation_policy": "zero_by_construction_one_period_positions_mature_at_observation",
        }
    )
    for policy in result["candidate_policies"]:
        policy["family"] = family
    if not result["profiles"].empty:
        result["profiles"].insert(0, "family", family)
    result["profile_policies"] = result["profiles"].to_dict(orient="records")
    _add_policy_diagnostics(result)
    return result


def policy_profile_metrics(
    result: dict[str, object],
    evaluate_test: bool = False,
) -> pd.DataFrame:
    """Présente les métriques pathwise des profils, test fermé par défaut."""
    A = np.asarray(result["A"], dtype=float)
    b = np.asarray(result["b"], dtype=float)
    split = result["split"]
    train = slice(0, int(split["n_train"]))
    validation = slice(train.stop, train.stop + int(split["n_validation"]))
    test = slice(validation.stop, len(b))
    rows: list[dict[str, object]] = []
    for _, profile in pd.DataFrame(result["profiles"]).iterrows():
        penalty = str(profile["penalty"])
        solution = result["results"][penalty]["solutions"][int(profile["solution_index"])]
        weights = np.asarray(solution["weights"], dtype=float)
        row = {
            "family": result["family"],
            "penalty": penalty,
            "profile": profile["profile"],
            **{f"train_{key}": value for key, value in benchmark_metrics(b[train], A[train] @ weights).items()},
            **{f"validation_{key}": value for key, value in benchmark_metrics(b[validation], A[validation] @ weights).items()},
            **solution["policy_metrics"],
            "test_status": "evaluated" if evaluate_test else "reserved_not_evaluated",
        }
        if evaluate_test:
            row.update(
                {f"test_{key}": value for key, value in benchmark_metrics(b[test], A[test] @ weights).items()}
            )
        rows.append(row)
    return pd.DataFrame(rows)


def policy_information_audit(result: dict[str, object]) -> pd.DataFrame:
    """Prouve que chaque choix utilise une information strictement antérieure."""
    visits = pd.DataFrame(result["visits"]).copy()
    visits["chronology_valid"] = visits["information_date"].isna() | (
        visits["information_date"] < visits["payment_date"]
    )
    return visits


def build_external_policy_design(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int,
    seed: int,
) -> dict[str, object]:
    """Projette de nouveaux paths sur la structure figée d'une politique.

    Les nœuds, replis et instruments proviennent exclusivement de la
    calibration de base. Le nouvel échantillon ne peut donc modifier la
    politique avant son évaluation ou sa recalibration de stabilité.
    """
    dataset = build_conditional_curve_dataset(
        product=product,
        vanillas=list(base_result["source_vanillas"]),
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
    )
    design = assemble_policy_design(
        dataset=dataset,
        nodes=list(base_result["nodes"]),
        assignments=dict(base_result["assignments"]),
        vanillas=list(base_result["source_vanillas"]),
    )
    design["dataset"] = dataset
    return design


def conditional_policy_cashflow_ledger(
    result: dict[str, object],
    penalty: str,
    profile: str,
    path_index: int,
) -> pd.DataFrame:
    """Détaille décisions, règlements et arrêt de la politique sur un path.

    Le compte cash est exprimé en valeur actualisée à la date de valorisation.
    Il cumule le surplus de la réplication après paiement de l'autocall. Les
    positions sont de maturité une période : elles expirent à l'observation et
    aucune position résiduelle ne doit être liquidée en cas de rappel.
    """
    dataset = list(result["dataset"])
    if not 0 <= path_index < len(dataset):
        raise IndexError("path_index est hors du dataset de calibration.")
    profiles = pd.DataFrame(result["profiles"])
    selected = profiles.loc[
        (profiles["penalty"] == penalty) & (profiles["profile"] == profile)
    ]
    if len(selected) != 1:
        raise ValueError("Le couple penalty/profile doit identifier un profil unique.")
    solution_index = int(selected.iloc[0]["solution_index"])
    weights = np.asarray(
        result["results"][penalty]["solutions"][solution_index]["weights"],
        dtype=float,
    )
    feature_table = pd.DataFrame(result["feature_table"])
    path_data = dataset[path_index]
    payoff = result["product"].compute_autocall_payoff(
        path_data["path"], start_date=pd.Timestamp(path_data["path"].index[0])
    )
    call_date = (
        None if payoff["call_date"] is None else pd.Timestamp(payoff["call_date"])
    )
    cash_account = 0.0
    rows: list[dict[str, object]] = []
    for date_index, payment_date in enumerate(path_data["dates"]):
        alive = _alive_at_decision(path_data, date_index)
        state = _state_before_payment(path_data, date_index)
        node_index = result["assignments"].get(
            (date_index, state), result["assignments"].get((date_index, POOLED_STATE))
        )
        target = float(path_data["y_curve"][date_index])
        replica = 0.0
        selected_state = None
        n_active_options = 0
        if alive and node_index is not None:
            columns = feature_table.index[
                feature_table["node_index"].eq(node_index)
            ].to_numpy(dtype=int)
            node = result["nodes"][node_index]
            source_indices = np.asarray(node["feature_indices"], dtype=int)
            replica = float(
                path_data["X_curve"][date_index, source_indices] @ weights[columns]
            )
            selected_state = node["decision_state"]
            kinds = feature_table.loc[columns, "kind"].to_numpy()
            n_active_options = int(
                np.sum(
                    (np.abs(weights[columns]) > result["active_threshold"])
                    & (kinds != "Cash")
                )
            )
        surplus = replica - target
        cash_before = cash_account
        cash_account += surplus
        recalled_here = bool(call_date is not None and call_date == payment_date)
        rows.append(
            {
                "path_index": path_index,
                "payment_date": pd.Timestamp(payment_date),
                "information_date": (
                    None
                    if date_index == 0
                    else pd.Timestamp(path_data["dates"][date_index - 1])
                ),
                "observed_state_at_decision": state,
                "selected_node_state": selected_state,
                "alive_at_decision": alive,
                "target_cashflow_pv": target,
                "replica_cashflow_pv": replica,
                "replication_surplus_pv": surplus,
                "cash_account_before_settlement_pv": cash_before,
                "cash_account_after_settlement_pv": cash_account,
                "n_active_options_settled": n_active_options,
                "recalled_at_payment": recalled_here,
                "new_position_after_recall": False,
                "remaining_positions_after_settlement": 0,
                "liquidation_value_pv": 0.0,
                "liquidation_reason": (
                    "one_period_positions_expired_at_observation"
                    if recalled_here
                    else "not_applicable"
                ),
            }
        )
    ledger = pd.DataFrame(rows)
    ledger.attrs["cash_account_convention"] = (
        "discounted_replica_cashflows_minus_discounted_autocall_cashflows"
    )
    ledger.attrs["funding_status"] = "initial_purchase_and_margin_not_yet_modelled"
    ledger.attrs["lookahead_status"] = "forbidden_and_audited"
    return ledger
