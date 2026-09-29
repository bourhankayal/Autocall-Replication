"""Coût théorique et financement des politiques conditionnelles pathwise."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..monte_carlo import price_autocall_bs_mc
from ..products import (
    AutocallProduct,
    BinaryCall,
    BinaryPut,
    Cash,
    EuropeanCall,
    EuropeanPut,
    VanillaProduct,
    _year_fraction,
)
from .conditional_policy import build_external_policy_design
from .risk import DEFAULT_RISK_LEVELS, tail_risk_metrics
from .transaction_costs import OTC_COST_SCENARIOS


BINARY_MODES = (
    "theoretical",
    "vertical_spread",
    "otc_favorable",
    "otc_central",
    "otc_stressed",
)


def _validate_binary_mode(binary_mode: str) -> None:
    if binary_mode not in BINARY_MODES and binary_mode != "no_binaries":
        raise ValueError(
            "binary_mode doit valoir theoretical, vertical_spread, "
            "otc_favorable, otc_central, otc_stressed ou no_binaries."
        )


def _vertical_spread_legs(
    binary: BinaryCall | BinaryPut,
    quantity: float,
    spread_width: float,
) -> list[tuple[VanillaProduct, float, str]]:
    """Remplace une binaire par une rampe centrée sur son strike."""
    if not np.isfinite(spread_width) or spread_width <= 0.0:
        raise ValueError("spread_width doit être strictement positif.")
    lower = float(binary.strike) - spread_width / 2.0
    upper = float(binary.strike) + spread_width / 2.0
    if lower <= 0.0:
        raise ValueError("La largeur du spread produit un strike non positif.")
    scale = quantity * float(binary.notional) / spread_width
    if isinstance(binary, BinaryCall):
        return [
            (
                EuropeanCall(
                    name=f"SYN_C_{lower:.4f}",
                    strike=lower,
                    maturity_date=binary.maturity_date,
                    notional=1.0,
                ),
                scale,
                "binary_call_lower_call",
            ),
            (
                EuropeanCall(
                    name=f"SYN_C_{upper:.4f}",
                    strike=upper,
                    maturity_date=binary.maturity_date,
                    notional=1.0,
                ),
                -scale,
                "binary_call_upper_call",
            ),
        ]
    return [
        (
            EuropeanPut(
                name=f"SYN_P_{upper:.4f}",
                strike=upper,
                maturity_date=binary.maturity_date,
                notional=1.0,
            ),
            scale,
            "binary_put_upper_put",
        ),
        (
            EuropeanPut(
                name=f"SYN_P_{lower:.4f}",
                strike=lower,
                maturity_date=binary.maturity_date,
                notional=1.0,
            ),
            -scale,
            "binary_put_lower_put",
        ),
    ]


def expand_conditional_node_positions(
    result: dict[str, object],
    weights: np.ndarray,
    node_index: int,
    binary_mode: str,
    spread_width: float = 5.0,
    active_threshold: float = 1e-6,
) -> list[dict[str, object]]:
    """Retourne les positions réellement valorisées pour un nœud.

    En mode ``vertical_spread``, chaque binaire devient deux options vanilles.
    Les autres modes conservent l'instrument binaire exact.
    """
    _validate_binary_mode(binary_mode)
    weights = np.asarray(weights, dtype=float).reshape(-1)
    features = pd.DataFrame(result["feature_table"])
    if len(weights) != len(features):
        raise ValueError("Le nombre de poids ne correspond pas aux colonnes de politique.")
    columns = features.index[features["node_index"].eq(node_index)].to_numpy(dtype=int)
    positions: list[dict[str, object]] = []
    for column_index in columns:
        instrument = result["vanillas"][int(column_index)]
        quantity = float(weights[column_index])
        if abs(quantity) <= active_threshold and not isinstance(instrument, Cash):
            continue
        if isinstance(instrument, (BinaryCall, BinaryPut)):
            if binary_mode == "no_binaries":
                raise ValueError("Une binaire est présente avec binary_mode='no_binaries'.")
            if binary_mode == "vertical_spread":
                for leg, leg_quantity, role in _vertical_spread_legs(
                    instrument, quantity, spread_width
                ):
                    positions.append(
                        {
                            "instrument": leg,
                            "quantity": leg_quantity,
                            "source_column": int(column_index),
                            "source_name": instrument.name,
                            "source_kind": instrument.__class__.__name__,
                            "implementation_role": role,
                        }
                    )
                continue
        positions.append(
            {
                "instrument": instrument,
                "quantity": quantity,
                "source_column": int(column_index),
                "source_name": instrument.name,
                "source_kind": instrument.__class__.__name__,
                "implementation_role": "original_instrument",
            }
        )
    return positions


def _otc_execution_price(
    instrument: BinaryCall | BinaryPut,
    model_price: float,
    quantity: float,
    valuation_date: pd.Timestamp,
    rate: float,
    binary_mode: str,
) -> tuple[float, float]:
    """Applique uniquement le plancher OTC, sans prétendre observer un spread."""
    if not binary_mode.startswith("otc_"):
        return model_price, 0.0
    scenario = OTC_COST_SCENARIOS[binary_mode]
    tau = max(_year_fraction(valuation_date, instrument.maturity_date), 0.0)
    discounted_payout = float(instrument.notional) * math.exp(-rate * tau)
    floor_bps = float(scenario["minimum_half_spread_bps_of_payout"])
    half_spread = float(instrument.notional) * floor_bps / 10_000.0
    ask = min(discounted_payout, model_price + half_spread)
    bid = max(0.0, model_price - half_spread)
    execution_price = ask if quantity >= 0.0 else bid
    execution_cost = abs(quantity) * abs(execution_price - model_price)
    return execution_price, execution_cost


def price_conditional_node(
    result: dict[str, object],
    weights: np.ndarray,
    node_index: int,
    spot: float,
    valuation_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    binary_mode: str,
    spread_width: float = 5.0,
    active_threshold: float = 1e-6,
) -> dict[str, object]:
    """Valorise un panier au mid BS puis selon le traitement des binaires."""
    valuation_date = pd.Timestamp(valuation_date)
    positions = expand_conditional_node_positions(
        result=result,
        weights=weights,
        node_index=node_index,
        binary_mode=binary_mode,
        spread_width=spread_width,
        active_threshold=active_threshold,
    )
    rows: list[dict[str, object]] = []
    for position in positions:
        instrument = position["instrument"]
        quantity = float(position["quantity"])
        model_price = float(
            instrument.price_bs(spot, valuation_date, rate, dividend_yield, vol)
        )
        execution_price = model_price
        otc_cost = 0.0
        if isinstance(instrument, (BinaryCall, BinaryPut)):
            execution_price, otc_cost = _otc_execution_price(
                instrument,
                model_price,
                quantity,
                valuation_date,
                rate,
                binary_mode,
            )
        signed_model_value = quantity * model_price
        signed_execution_value = quantity * execution_price
        rows.append(
            {
                **{key: value for key, value in position.items() if key != "instrument"},
                "name": instrument.name,
                "kind": instrument.__class__.__name__,
                "strike": float(instrument.strike),
                "maturity_date": pd.Timestamp(instrument.maturity_date),
                "model_price": model_price,
                "execution_price": execution_price,
                "signed_model_value": signed_model_value,
                "signed_execution_value": signed_execution_value,
                "gross_model_value": abs(signed_model_value),
                "long_model_value": max(signed_model_value, 0.0),
                "short_model_value": min(signed_model_value, 0.0),
                "otc_execution_cost": otc_cost,
            }
        )
    details = pd.DataFrame(rows)
    if details.empty:
        totals = {
            "net_model_value": 0.0,
            "net_execution_value": 0.0,
            "gross_model_value": 0.0,
            "long_model_value": 0.0,
            "short_model_value": 0.0,
            "otc_execution_cost": 0.0,
            "n_positions": 0,
        }
    else:
        totals = {
            "net_model_value": float(details["signed_model_value"].sum()),
            "net_execution_value": float(details["signed_execution_value"].sum()),
            "gross_model_value": float(details["gross_model_value"].sum()),
            "long_model_value": float(details["long_model_value"].sum()),
            "short_model_value": float(details["short_model_value"].sum()),
            "otc_execution_cost": float(details["otc_execution_cost"].sum()),
            "n_positions": int(len(details)),
        }
    return {
        "details": details,
        "summary": {
            "node_index": int(node_index),
            "binary_mode": binary_mode,
            "spread_width": float(spread_width),
            "spot": float(spot),
            "valuation_date": valuation_date,
            **totals,
        },
    }


def _node_payoff(positions: Sequence[dict[str, object]], spot: float) -> float:
    return float(
        sum(
            float(position["quantity"]) * position["instrument"].payoff(spot)
            for position in positions
        )
    )


def _spot_on_or_after(path: pd.Series, date: pd.Timestamp) -> float:
    eligible = path.loc[path.index >= pd.Timestamp(date)]
    if eligible.empty:
        raise ValueError(f"La trajectoire ne couvre pas la date {date}.")
    return float(eligible.iloc[0])


def build_conditional_funding_ledger(
    result: dict[str, object],
    weights: np.ndarray,
    path_data: dict[str, object],
    path_id: int,
    initial_autocall_premium: float,
    valuation_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    binary_mode: str,
    spread_width: float = 5.0,
    active_threshold: float = 1e-6,
) -> pd.DataFrame:
    """Construit le compte cash autofinancé d'une trajectoire.

    Un solde négatif est un emprunt au taux sans risque. Aucune injection n'est
    ajoutée silencieusement pendant la trajectoire.
    """
    _validate_binary_mode(binary_mode)
    valuation_date = pd.Timestamp(valuation_date)
    dates = pd.DatetimeIndex(path_data["dates"])
    path = path_data["path"]
    contract_result = result["product"].compute_autocall_payoff(
        path, start_date=valuation_date
    )
    call_date = (
        None
        if contract_result["call_date"] is None
        else pd.Timestamp(contract_result["call_date"])
    )
    visit_lookup = {
        int(row["payment_date_index"]): int(row["selected_node_index"])
        for _, row in pd.DataFrame(path_data["policy_visits"]).iterrows()
    }
    if 0 not in visit_lookup:
        raise ValueError("Le premier nœud de la politique est absent.")

    initial_node = visit_lookup[0]
    current_positions = expand_conditional_node_positions(
        result,
        weights,
        initial_node,
        binary_mode,
        spread_width,
        active_threshold,
    )
    initial_pricing = price_conditional_node(
        result,
        weights,
        initial_node,
        spot=float(path.iloc[0]),
        valuation_date=valuation_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        binary_mode=binary_mode,
        spread_width=spread_width,
        active_threshold=active_threshold,
    )["summary"]
    cash = float(initial_autocall_premium) - float(
        initial_pricing["net_execution_value"]
    )
    running_min_cash = min(float(initial_autocall_premium), cash)
    cumulative_gross_purchases = float(initial_pricing["gross_model_value"])
    cumulative_otc_cost = float(initial_pricing["otc_execution_cost"])
    rows: list[dict[str, object]] = [
        {
            "path_id": int(path_id),
            "event_date": valuation_date,
            "event_type": "initial_hedge_purchase",
            "spot": float(path.iloc[0]),
            "binary_mode": binary_mode,
            "autocall_premium": float(initial_autocall_premium),
            "cash_before_event": float(initial_autocall_premium),
            "interest_on_cash": 0.0,
            "option_payoff": 0.0,
            "autocall_cashflow": 0.0,
            "next_node_index": initial_node,
            "next_portfolio_net_model_value": float(initial_pricing["net_model_value"]),
            "next_portfolio_net_execution_value": float(initial_pricing["net_execution_value"]),
            "next_portfolio_gross_exposure": float(initial_pricing["gross_model_value"]),
            "otc_execution_cost": float(initial_pricing["otc_execution_cost"]),
            "cash_after_event": cash,
            "running_min_cash": running_min_cash,
            "recalled": False,
            "new_position_opened": True,
        }
    ]
    previous_date = valuation_date

    for date_index, event_date in enumerate(dates):
        event_date = pd.Timestamp(event_date)
        spot = _spot_on_or_after(path, event_date)
        cash_before = cash
        accrued_cash = cash * math.exp(rate * _year_fraction(previous_date, event_date))
        interest = accrued_cash - cash
        option_payoff = _node_payoff(current_positions, spot)
        discount_to_valuation = math.exp(
            -rate * _year_fraction(valuation_date, event_date)
        )
        autocall_cashflow = float(path_data["y_curve"][date_index]) / discount_to_valuation
        cash_after_settlement = accrued_cash + option_payoff - autocall_cashflow
        recalled = bool(call_date is not None and call_date == event_date)
        next_node = visit_lookup.get(date_index + 1)
        new_position_opened = bool(not recalled and next_node is not None)
        next_model_value = 0.0
        next_execution_value = 0.0
        next_gross_exposure = 0.0
        otc_execution_cost = 0.0
        current_positions = []
        if new_position_opened:
            next_pricing = price_conditional_node(
                result,
                weights,
                next_node,
                spot=spot,
                valuation_date=event_date,
                rate=rate,
                dividend_yield=dividend_yield,
                vol=vol,
                binary_mode=binary_mode,
                spread_width=spread_width,
                active_threshold=active_threshold,
            )["summary"]
            next_model_value = float(next_pricing["net_model_value"])
            next_execution_value = float(next_pricing["net_execution_value"])
            next_gross_exposure = float(next_pricing["gross_model_value"])
            otc_execution_cost = float(next_pricing["otc_execution_cost"])
            cash = cash_after_settlement - next_execution_value
            cumulative_gross_purchases += next_gross_exposure
            cumulative_otc_cost += otc_execution_cost
            current_positions = expand_conditional_node_positions(
                result,
                weights,
                next_node,
                binary_mode,
                spread_width,
                active_threshold,
            )
        else:
            cash = cash_after_settlement
        running_min_cash = min(running_min_cash, cash)
        rows.append(
            {
                "path_id": int(path_id),
                "event_date": event_date,
                "event_type": "observation_settlement",
                "spot": spot,
                "binary_mode": binary_mode,
                "autocall_premium": 0.0,
                "cash_before_event": cash_before,
                "interest_on_cash": interest,
                "option_payoff": option_payoff,
                "autocall_cashflow": autocall_cashflow,
                "next_node_index": next_node if new_position_opened else np.nan,
                "next_portfolio_net_model_value": next_model_value,
                "next_portfolio_net_execution_value": next_execution_value,
                "next_portfolio_gross_exposure": next_gross_exposure,
                "otc_execution_cost": otc_execution_cost,
                "cash_after_event": cash,
                "running_min_cash": running_min_cash,
                "recalled": recalled,
                "new_position_opened": new_position_opened,
            }
        )
        previous_date = event_date

    ledger = pd.DataFrame(rows)
    ledger.attrs.update(
        {
            "terminal_pnl": float(cash),
            "minimum_cash": float(running_min_cash),
            "additional_capital_without_borrowing": max(0.0, -running_min_cash),
            "cumulative_gross_purchases": cumulative_gross_purchases,
            "cumulative_otc_execution_cost": cumulative_otc_cost,
            "funding_convention": "issuer_premium_then_self_financing_cash_account",
        }
    )
    return ledger


def _funding_modes_for_family(family: str) -> tuple[str, ...]:
    if family == "calls_puts":
        return ("no_binaries",)
    if family == "full":
        return BINARY_MODES
    raise ValueError("Le financement accepte uniquement calls_puts ou full.")


def evaluate_conditional_policy_funding(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int = 2_000,
    seed: int = 20500,
    initial_autocall_premium: float | None = None,
    premium_n_paths: int = 20_000,
    premium_seed: int = 30500,
    spread_width: float = 5.0,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
) -> dict[str, object]:
    """Évalue coût, besoin de financement et P&L sans recalibrer alpha."""
    if n_paths < 10:
        raise ValueError("n_paths doit être supérieur ou égal à 10.")
    if initial_autocall_premium is None:
        premium_result = price_autocall_bs_mc(
            product=product,
            spot0=spot0,
            valuation_date=valuation_date,
            maturity_date=maturity_date,
            rate=rate,
            dividend_yield=dividend_yield,
            vol=vol,
            n_paths=premium_n_paths,
            seed=premium_seed,
            antithetic=True,
            control_variate=True,
        )
        initial_autocall_premium = float(premium_result["actualized_price"])
    else:
        premium_result = {
            "actualized_price": float(initial_autocall_premium),
            "status": "provided_externally",
        }

    design = build_external_policy_design(
        base_result=base_result,
        product=product,
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
    )
    visits = pd.DataFrame(design["visits"])
    profiles = pd.DataFrame(base_result["profiles"])
    modes = _funding_modes_for_family(str(base_result["family"]))
    ledger_frames: list[pd.DataFrame] = []
    path_rows: list[dict[str, object]] = []

    for _, profile in profiles.iterrows():
        penalty, profile_name = str(profile["penalty"]), str(profile["profile"])
        weights = np.asarray(
            base_result["results"][penalty]["solutions"][
                int(profile["solution_index"])
            ]["weights"],
            dtype=float,
        )
        for binary_mode in modes:
            for path_id, path_data in enumerate(design["dataset"]):
                enriched = dict(path_data)
                enriched["policy_visits"] = visits.loc[
                    visits["path_index"].eq(path_id)
                ]
                ledger = build_conditional_funding_ledger(
                    result=base_result,
                    weights=weights,
                    path_data=enriched,
                    path_id=path_id,
                    initial_autocall_premium=float(initial_autocall_premium),
                    valuation_date=valuation_date,
                    rate=rate,
                    dividend_yield=dividend_yield,
                    vol=vol,
                    binary_mode=binary_mode,
                    spread_width=spread_width,
                    active_threshold=float(base_result.get("active_threshold", 1e-6)),
                )
                ledger.insert(0, "family", base_result["family"])
                ledger.insert(1, "penalty", penalty)
                ledger.insert(2, "profile", profile_name)
                ledger_frames.append(ledger)
                contract_result = product.compute_autocall_payoff(
                    path_data["path"], start_date=pd.Timestamp(valuation_date)
                )
                path_rows.append(
                    {
                        "family": base_result["family"],
                        "penalty": penalty,
                        "profile": profile_name,
                        "binary_mode": binary_mode,
                        "path_id": path_id,
                        "called": bool(contract_result["called"]),
                        "barrier_hit": bool(contract_result["barrier_hit"]),
                        "terminal_pnl": ledger.attrs["terminal_pnl"],
                        "minimum_cash": ledger.attrs["minimum_cash"],
                        "additional_capital_without_borrowing": ledger.attrs[
                            "additional_capital_without_borrowing"
                        ],
                        "cumulative_gross_purchases": ledger.attrs[
                            "cumulative_gross_purchases"
                        ],
                        "cumulative_otc_execution_cost": ledger.attrs[
                            "cumulative_otc_execution_cost"
                        ],
                        "initial_net_cost": float(
                            ledger.iloc[0]["next_portfolio_net_execution_value"]
                        ),
                        "initial_gross_exposure": float(
                            ledger.iloc[0]["next_portfolio_gross_exposure"]
                        ),
                    }
                )

    path_summary = pd.DataFrame(path_rows)
    summary_rows: list[dict[str, object]] = []
    condition_rows: list[dict[str, object]] = []
    group_columns = ["family", "penalty", "profile", "binary_mode"]
    for keys, group in path_summary.groupby(group_columns, sort=False):
        losses = -group["terminal_pnl"].to_numpy(dtype=float)
        funding = group["additional_capital_without_borrowing"].to_numpy(dtype=float)
        row = dict(zip(group_columns, keys))
        risk = tail_risk_metrics(losses, levels=levels)
        row.update(
            {
                "n_paths": len(group),
                "initial_autocall_premium": float(initial_autocall_premium),
                "initial_net_cost_mean": float(group["initial_net_cost"].mean()),
                "initial_gross_exposure_mean": float(
                    group["initial_gross_exposure"].mean()
                ),
                "terminal_pnl_mean": float(group["terminal_pnl"].mean()),
                "terminal_pnl_std": float(group["terminal_pnl"].std(ddof=1)),
                "borrowing_frequency": float(np.mean(group["minimum_cash"] < 0.0)),
                "additional_capital_mean": float(np.mean(funding)),
                "additional_capital_p95": float(np.quantile(funding, 0.95)),
                "additional_capital_max": float(np.max(funding)),
                "cumulative_gross_purchases_mean": float(
                    group["cumulative_gross_purchases"].mean()
                ),
                "cumulative_otc_execution_cost_mean": float(
                    group["cumulative_otc_execution_cost"].mean()
                ),
                **{f"loss_{key}": value for key, value in risk.items()},
            }
        )
        for column in (
            "initial_net_cost_mean",
            "initial_gross_exposure_mean",
            "terminal_pnl_mean",
            "additional_capital_mean",
            "additional_capital_p95",
            "additional_capital_max",
            "cumulative_gross_purchases_mean",
            "cumulative_otc_execution_cost_mean",
            "loss_rmse",
            "loss_es_975",
            "loss_max_loss",
        ):
            row[f"{column}_pct_notional"] = 100.0 * float(row[column]) / product.notional
            row[f"{column}_bps_notional"] = 10_000.0 * float(row[column]) / product.notional
        summary_rows.append(row)

        conditions = {
            "all": np.ones(len(group), dtype=bool),
            "recalled": group["called"].to_numpy(dtype=bool),
            "maturity": ~group["called"].to_numpy(dtype=bool),
            "barrier_hit": group["barrier_hit"].to_numpy(dtype=bool),
        }
        for condition, mask in conditions.items():
            if not np.any(mask):
                continue
            condition_rows.append(
                {
                    **dict(zip(group_columns, keys)),
                    "condition": condition,
                    "n_observations": int(mask.sum()),
                    "frequency": float(mask.mean()),
                    **tail_risk_metrics(losses[mask], levels=levels),
                }
            )

    return {
        "summary": pd.DataFrame(summary_rows),
        "conditional_summary": pd.DataFrame(condition_rows),
        "path_summary": path_summary,
        "ledger": pd.concat(ledger_frames, ignore_index=True),
        "premium": premium_result,
        "initial_autocall_premium": float(initial_autocall_premium),
        "binary_modes": modes,
        "spread_width": float(spread_width),
        "n_paths": n_paths,
        "seed": seed,
        "evaluation_status": "independent_paths_no_refit_no_alpha_selection",
        "test_status": base_result.get("test_status", "reserved_not_evaluated"),
        "market_spread_status": "deferred",
        "otc_status": "provisional_payout_floor_scenarios",
    }
