
import numpy as np
import pandas as pd  
import matplotlib.pyplot as plt

from ..products import AutocallProduct, VanillaProduct, Cash, _year_fraction
from .pathwise_payoff import vanilla_discounted_payoff_from_path
from ..monte_carlo import simulate_gbm_path
from .common import benchmark_metrics, build_naive_vanilla_basis, contractual_simulation_end_date
from .optimization import SolverConfig, solve_replication
from .portfolio_diagnostics import grouped_portfolio_weight_metrics
from .static_cashflows import (
    autocall_value_curve_on_path,
    build_timewise_curve_dataset,
    effective_date_on_path,
)

# ============================================================
# BENCHMARK CONDITIONNEL SEMI-STATIQUE : un panier par date et par état observable du produit
# ============================================================

# ------------------------------------------------------------
# 0) Construction de la base conditionnelle :  une jambe cash et des vanilles à chaque date d'observation
# ------------------------------------------------------------
def build_conditional_vanilla_basis(
    product: AutocallProduct,spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    family: str,
    spot_min_mult: float = 0.70,spot_max_mult: float = 1.30) -> list[VanillaProduct]:
    """Construit une base de vanilles organisée par date d'observation.
    Chaque date contient :
    - une jambe cash ;
    - les calls ;
    - éventuellement les puts et les binaires."""
    valuation_date = pd.Timestamp(valuation_date)
    effective_contract_start = pd.offsets.BDay().rollforward(
        valuation_date.normalize()
    )
    maturity_date = contractual_simulation_end_date(
        product=product,
        contract_start_date=effective_contract_start,
        requested_maturity_date=maturity_date,
    )

    vanilla_basis = build_naive_vanilla_basis(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,product=product,strike_step=5.0,strike_min_mult=spot_min_mult,strike_max_mult=spot_max_mult,family=family)
    observation_dates = sorted(
        {
            pd.offsets.BDay().rollforward(pd.Timestamp(date).normalize())
            for date in product.build_observation_dates(effective_contract_start)
            if valuation_date
            < pd.offsets.BDay().rollforward(pd.Timestamp(date).normalize())
            <= maturity_date
        }
        | {maturity_date}
    )
    vanillas = []

    for observation_date in observation_dates:
        # Une jambe cash par date.
        # Le panier n'est détenu que si l'autocall est encore vivant.
        cash = Cash(name=f"CASH_{observation_date.strftime('%Y%m%d')}",strike=0.0,maturity_date=observation_date,notional=float(product.notional))
        vanillas.append(cash)
        date_vanillas = [v for v in vanilla_basis if (not isinstance(v, Cash) and pd.Timestamp(v.maturity_date) == observation_date)]
        vanillas.extend(date_vanillas)

    return vanillas


# ------------------------------------------------------------
# 1) États observables du produit le long d'un path
# ------------------------------------------------------------

def autocall_state_curve_on_path(
    product: AutocallProduct,path: pd.Series,
    valuation_date: str | pd.Timestamp,curve_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Retourne les états observables du produit à chaque date :
    - alive_before : le produit est vivant juste avant l'observation ;
    - barrier_hit  : la barrière basse a déjà été touchée jusqu'à cette date."""
    valuation_date = pd.Timestamp(valuation_date)
    curve_dates = pd.DatetimeIndex(curve_dates)
    path = path.sort_index().dropna()
    path = path.loc[path.index >= valuation_date]

    full_res = product.compute_autocall_payoff(path,start_date=valuation_date)
    call_date = full_res["call_date"]
    if call_date is not None:           call_date = pd.Timestamp(call_date)

    spot_initial = float(full_res["spot_initial"])
    barrier_level = float(product.down_barrier) * spot_initial
    alive_before = np.zeros(len(curve_dates),dtype=bool)
    barrier_hit = np.zeros(len(curve_dates),dtype=bool)

    for i, d in enumerate(curve_dates):
        d = pd.Timestamp(d)
        alive_before[i] = (call_date is None or call_date >= d)     # À la date de rappel, le produit est encore vivant juste avant l'observation et doit produire son cashflow.
        path_until_date = path.loc[path.index <= d]
        barrier_hit[i] = bool((path_until_date <= barrier_level).any())

    return pd.DataFrame({
        "date": curve_dates,
        "alive_before": alive_before,
        "barrier_hit": barrier_hit})
    
    

# ------------------------------------------------------------
# 2) Dataset conditionnel :   on enrichit le dataset actuel avec les états du produit
# ------------------------------------------------------------
def build_conditional_curve_dataset(
    product: AutocallProduct,vanillas: list[VanillaProduct],spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,vol: float,
    n_paths: int = 2000,seed: int = 42) -> list[dict[str, object]]:
    """Construit le dataset pathwise puis ajoute :
    - alive_before ;
    - barrier_hit."""
    dataset = build_timewise_curve_dataset(product=product,vanillas=vanillas,spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=seed)

    for path_data in dataset:
        state_curve = autocall_state_curve_on_path(product=product,path=path_data["path"],valuation_date=valuation_date,curve_dates=path_data["dates"])
        path_data["alive_before"] = (state_curve["alive_before"].to_numpy(dtype=bool))
        path_data["barrier_hit"] = (state_curve["barrier_hit"].to_numpy(dtype=bool))

    return dataset


def predict_conditional_path_data(
    path_data: dict[str, object],
    models: dict,
    split_final_by_barrier: bool = True,
) -> np.ndarray:
    """Applique les paniers conditionnels à une trajectoire."""
    n_dates = len(path_data["dates"])
    prediction = np.zeros(n_dates, dtype=float)

    for date_index in range(n_dates):
        if not bool(path_data["alive_before"][date_index]):
            continue

        is_final_date = date_index == n_dates - 1
        state = (
            bool(path_data["barrier_hit"][date_index])
            if is_final_date and split_final_by_barrier
            else None
        )
        model_key = (date_index, state)
        if model_key not in models:
            model_key = (date_index, None)

        model = models[model_key]
        feature_indices = model["feature_indices"]
        prediction[date_index] = float(
            path_data["X_curve"][date_index, feature_indices]
            @ model["weights"]
        )

    return prediction


def run_conditional_benchmark_curve(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    family: str = "full",
    n_paths: int = 2000,
    spot_min_mult: float = 0.70,
    spot_max_mult: float = 1.30,
    penalty: str = "l2",
    alpha: float = 1e-4,
    train_frac: float = 0.7,
    seed: int = 42,
    split_final_by_barrier: bool = True,
    min_state_paths: int = 20,
    solver: str = "legacy",
) -> dict[str, object]:
    """Calibre un panier par date et, à maturité, par état de barrière."""
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

    split = max(1, min(int(train_frac * n_paths), n_paths - 1 if n_paths > 1 else 1))
    train_set = dataset[:split]
    test_set = dataset[split:]
    dates = pd.DatetimeIndex(dataset[0]["dates"])
    first_path = dataset[0]["path"]

    feature_indices_by_date = {}
    for date_index, date in enumerate(dates):
        indices = [
            feature_index
            for feature_index, vanilla in enumerate(vanillas)
            if effective_date_on_path(first_path, vanilla.maturity_date) == date
        ]
        if not indices:
            raise ValueError(f"Aucune vanille disponible à la date {date}.")
        feature_indices_by_date[date_index] = np.asarray(indices, dtype=int)

    models = {}
    for date_index, date in enumerate(dates):
        feature_indices = feature_indices_by_date[date_index]
        alive_mask = np.asarray(
            [bool(item["alive_before"][date_index]) for item in train_set]
        )
        X_date = np.vstack(
            [item["X_curve"][date_index, feature_indices] for item in train_set]
        )
        y_date = np.asarray([item["y_curve"][date_index] for item in train_set])
        if not np.any(alive_mask):
            raise ValueError(f"Aucun path vivant pour la date {date}.")

        optimization_result = solve_replication(
            A=X_date[alive_mask],
            b=y_date[alive_mask],
            config=SolverConfig(
                solver=solver,
                scale_features=True,
                penalty=penalty,
                alpha=alpha,
            ),
        )
        models[(date_index, None)] = {
            "date": pd.Timestamp(date),
            "state": None,
            "feature_indices": feature_indices,
            "weights": optimization_result.weights,
            "optimization": optimization_result.metadata(),
            "n_train_paths": int(np.sum(alive_mask)),
        }

        if date_index == len(dates) - 1 and split_final_by_barrier:
            for barrier_state in (False, True):
                barrier_mask = np.asarray(
                    [
                        bool(item["barrier_hit"][date_index]) == barrier_state
                        for item in train_set
                    ]
                )
                state_mask = alive_mask & barrier_mask
                if int(np.sum(state_mask)) < min_state_paths:
                    continue
                state_optimization_result = solve_replication(
                    A=X_date[state_mask],
                    b=y_date[state_mask],
                    config=SolverConfig(
                        solver=solver,
                        scale_features=True,
                        penalty=penalty,
                        alpha=alpha,
                    ),
                )
                models[(date_index, barrier_state)] = {
                    "date": pd.Timestamp(date),
                    "state": barrier_state,
                    "feature_indices": feature_indices,
                    "weights": state_optimization_result.weights,
                    "optimization": state_optimization_result.metadata(),
                    "n_train_paths": int(np.sum(state_mask)),
                }

    pred_train_matrix = np.vstack(
        [
            predict_conditional_path_data(
                item, models, split_final_by_barrier=split_final_by_barrier
            )
            for item in train_set
        ]
    )
    y_train_matrix = np.vstack([item["y_curve"] for item in train_set])
    if test_set:
        pred_test_matrix = np.vstack(
            [
                predict_conditional_path_data(
                    item, models, split_final_by_barrier=split_final_by_barrier
                )
                for item in test_set
            ]
        )
        y_test_matrix = np.vstack([item["y_curve"] for item in test_set])
    else:
        pred_test_matrix = np.empty((0, len(dates)))
        y_test_matrix = np.empty((0, len(dates)))

    metrics_train = benchmark_metrics(
        y_train_matrix.reshape(-1), pred_train_matrix.reshape(-1)
    )
    metrics_test = (
        benchmark_metrics(y_test_matrix.reshape(-1), pred_test_matrix.reshape(-1))
        if test_set
        else {}
    )
    train_alive_mask = np.vstack(
        [item["alive_before"] for item in train_set]
    ).astype(bool)
    metrics_train_alive = benchmark_metrics(
        y_train_matrix[train_alive_mask], pred_train_matrix[train_alive_mask]
    )
    if test_set:
        test_alive_mask = np.vstack(
            [item["alive_before"] for item in test_set]
        ).astype(bool)
        metrics_test_alive = benchmark_metrics(
            y_test_matrix[test_alive_mask], pred_test_matrix[test_alive_mask]
        )
    else:
        test_alive_mask = np.empty((0, len(dates)), dtype=bool)
        metrics_test_alive = {}

    metrics_by_date = []
    if test_set:
        for date_index, date in enumerate(dates):
            y_date = y_test_matrix[:, date_index]
            pred_date = pred_test_matrix[:, date_index]
            alive_date = test_alive_mask[:, date_index]
            row = {
                "date": pd.Timestamp(date),
                "n_test": int(len(y_date)),
                "n_alive": int(np.sum(alive_date)),
                **benchmark_metrics(y_date, pred_date),
            }
            if np.any(alive_date):
                alive_metrics = benchmark_metrics(
                    y_date[alive_date], pred_date[alive_date]
                )
                row.update({f"{key}_alive": value for key, value in alive_metrics.items()})
            metrics_by_date.append(row)
    metrics_by_date = pd.DataFrame(metrics_by_date)

    weight_rows = []
    for (date_index, state), model in models.items():
        state_name = "alive" if state is None else (
            "barrier_hit" if state else "barrier_not_hit"
        )
        for local_index, feature_index in enumerate(model["feature_indices"]):
            vanilla = vanillas[feature_index]
            weight_rows.append(
                {
                    "date": model["date"],
                    "state": state_name,
                    "n_train_paths": model["n_train_paths"],
                    "name": vanilla.name,
                    "kind": vanilla.__class__.__name__,
                    "maturity_date": pd.Timestamp(vanilla.maturity_date),
                    "strike": float(vanilla.strike),
                    "weight": float(model["weights"][local_index]),
                }
            )
    weights = pd.DataFrame(weight_rows)
    weights["absolute_weight"] = weights["weight"].abs()
    weights = weights.sort_values(
        ["date", "state", "absolute_weight"], ascending=[True, True, False]
    ).reset_index(drop=True)
    portfolio_metrics = grouped_portfolio_weight_metrics(weights)

    optimization_rows = []
    for (_, state), model in models.items():
        state_name = "alive" if state is None else (
            "barrier_hit" if state else "barrier_not_hit"
        )
        optimization_rows.append(
            {
                "date": model["date"],
                "state": state_name,
                **model["optimization"],
            }
        )
    optimization = pd.DataFrame(optimization_rows)

    return {
        "vanillas": vanillas,
        "dates": dates,
        "dataset": dataset,
        "train_set": train_set,
        "test_set": test_set,
        "models": models,
        "weights": weights,
        "pred_train_matrix": pred_train_matrix,
        "pred_test_matrix": pred_test_matrix,
        "y_train_matrix": y_train_matrix,
        "y_test_matrix": y_test_matrix,
        "metrics_train": metrics_train,
        "metrics_test": metrics_test,
        "metrics_train_alive": metrics_train_alive,
        "metrics_test_alive": metrics_test_alive,
        "metrics_by_date": metrics_by_date,
        "optimization": optimization,
        "portfolio_metrics": portfolio_metrics,
        "family": family,
        "split": split,
        "split_final_by_barrier": split_final_by_barrier,
    }


def conditional_features_on_path(
    vanillas: list[VanillaProduct],
    path: pd.Series,
    valuation_date: str | pd.Timestamp,
    rate: float,
    curve_dates: pd.DatetimeIndex,
) -> np.ndarray:
    """Construit les payoffs des vanilles sur un nouveau chemin."""
    valuation_date = pd.Timestamp(valuation_date)
    curve_dates = pd.DatetimeIndex(curve_dates)
    path = path.sort_index().dropna().loc[lambda series: series.index >= valuation_date]
    X_curve = np.zeros((len(curve_dates), len(vanillas)), dtype=float)
    date_to_index = {pd.Timestamp(date): index for index, date in enumerate(curve_dates)}

    for feature_index, vanilla in enumerate(vanillas):
        payment_date = effective_date_on_path(path, vanilla.maturity_date)
        if payment_date not in date_to_index:
            raise ValueError(
                f"La maturité {payment_date} de {vanilla.name} "
                "ne correspond à aucune date de la courbe."
            )
        X_curve[date_to_index[payment_date], feature_index] = (
            vanilla_discounted_payoff_from_path(
                vanilla=vanilla,
                path=path,
                valuation_date=valuation_date,
                rate=rate,
            )
        )
    return X_curve


def conditional_portfolio_value_curve_on_path(
    result: dict[str, object],
    product: AutocallProduct,
    path: pd.Series,
    valuation_date: str | pd.Timestamp,
    rate: float,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    """Applique les paniers conditionnels à un nouveau chemin."""
    curve_dates = pd.DatetimeIndex(result["dates"])
    target_curve = autocall_value_curve_on_path(
        product=product,
        path=path,
        valuation_date=valuation_date,
        rate=rate,
        curve_dates=curve_dates,
    )
    X_curve = conditional_features_on_path(
        vanillas=result["vanillas"],
        path=path,
        valuation_date=valuation_date,
        rate=rate,
        curve_dates=curve_dates,
    )
    state_curve = autocall_state_curve_on_path(
        product=product,
        path=path,
        valuation_date=valuation_date,
        curve_dates=curve_dates,
    )
    path_data = {
        "path": path,
        "dates": curve_dates,
        "X_curve": X_curve,
        "y_curve": target_curve.to_numpy(dtype=float),
        "alive_before": state_curve["alive_before"].to_numpy(dtype=bool),
        "barrier_hit": state_curve["barrier_hit"].to_numpy(dtype=bool),
    }
    replica_curve = pd.Series(
        predict_conditional_path_data(
            path_data=path_data,
            models=result["models"],
            split_final_by_barrier=result["split_final_by_barrier"],
        ),
        index=curve_dates,
        name="conditional_replica_cashflow",
    )
    return target_curve, replica_curve, state_curve

