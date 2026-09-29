"""Cotations yfinance et scénarios de coûts des portefeuilles de réplication."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from ..products import (
    BinaryCall,
    BinaryPut,
    Cash,
    EuropeanCall,
    EuropeanPut,
    VanillaProduct,
)


OTC_COST_SCENARIOS: dict[str, dict[str, float | str]] = {
    "otc_favorable": {
        "half_spread_multiplier": 1.0,
        "minimum_half_spread_bps_of_payout": 5.0,
        "description": "spread synthétique observable, plancher faible",
    },
    "otc_central": {
        "half_spread_multiplier": 1.5,
        "minimum_half_spread_bps_of_payout": 10.0,
        "description": "marge OTC centrale au-dessus du spread synthétique",
    },
    "otc_stressed": {
        "half_spread_multiplier": 2.5,
        "minimum_half_spread_bps_of_payout": 25.0,
        "description": "liquidité dégradée et marge OTC stressée",
    },
}


SNAPSHOT_COLUMNS = [
    "ticker",
    "snapshot_utc",
    "underlying_price",
    "expiry",
    "market_expiry",
    "option_type",
    "contractSymbol",
    "strike",
    "bid",
    "ask",
    "mid",
    "half_spread",
    "volume",
    "openInterest",
    "impliedVolatility",
    "contractSize",
    "currency",
    "lastTradeDate",
    "is_valid_quote",
    "quote_status",
]


def validate_option_snapshot(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Valide bid/ask et signale les cotations trop illiquides."""
    required = {"expiry", "option_type", "strike", "bid", "ask"}
    missing = required - set(snapshot.columns)
    if missing:
        raise ValueError(f"Colonnes de cotation manquantes : {sorted(missing)}")
    validated = snapshot.copy()
    validated["expiry"] = pd.to_datetime(validated["expiry"]).dt.normalize()
    for column in ("strike", "bid", "ask"):
        validated[column] = pd.to_numeric(validated[column], errors="coerce")
    validated["mid"] = 0.5 * (validated["bid"] + validated["ask"])
    validated["half_spread"] = 0.5 * (validated["ask"] - validated["bid"])
    finite = np.isfinite(validated[["strike", "bid", "ask"]]).all(axis=1)
    positive_bid = validated["bid"] > 0.0
    ordered = validated["ask"] > validated["bid"]
    ask_bid_ratio = validated["ask"] / validated["bid"].replace(0.0, np.nan)
    ratio_is_acceptable = ask_bid_ratio <= 10.0
    validated["is_valid_quote"] = (
        finite & positive_bid & ordered & ratio_is_acceptable.fillna(False)
    )
    validated["quote_status"] = np.select(
        [
            ~finite,
            ~positive_bid,
            ~ordered,
            ~ratio_is_acceptable.fillna(False),
        ],
        [
            "invalid_non_finite",
            "invalid_zero_or_negative_bid",
            "invalid_ask_not_above_bid",
            "invalid_ask_bid_ratio_above_10",
        ],
        default="valid",
    )
    return validated


def download_yfinance_option_snapshot(
    ticker: str,
    expiries: Iterable[str | pd.Timestamp] | None = None,
    ticker_factory: Callable[[str], object] | None = None,
    snapshot_utc: datetime | None = None,
    expiry_tolerance_days: int = 3,
    cache_directory: str | Path | None = None,
) -> pd.DataFrame:
    """Télécharge une photographie courante des calls et puts via yfinance.

    yfinance ne fournit pas ici une chaîne historique. La date du snapshot est
    donc enregistrée et chaque échéance absente est signalée par une exception.
    ``ticker_factory`` permet des tests hors réseau.
    """
    if not ticker or not str(ticker).strip():
        raise ValueError("ticker ne doit pas être vide.")
    if ticker_factory is None:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise ImportError(
                "yfinance est requis pour télécharger les cotations de marché."
            ) from exc
        cache_path = Path(
            cache_directory
            if cache_directory is not None
            else Path(tempfile.gettempdir()) / "autocall-replication-yfinance"
        )
        cache_path.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_path))
        ticker_factory = yf.Ticker

    market = ticker_factory(str(ticker).strip().upper())
    available = tuple(str(expiry) for expiry in market.options)
    requested = (
        available
        if expiries is None
        else tuple(pd.Timestamp(expiry).strftime("%Y-%m-%d") for expiry in expiries)
    )
    if expiry_tolerance_days < 0:
        raise ValueError("expiry_tolerance_days doit être positif ou nul.")
    available_dates = {pd.Timestamp(expiry): expiry for expiry in available}
    expiry_mapping: dict[str, str] = {}
    unavailable: list[str] = []
    for requested_expiry in requested:
        requested_date = pd.Timestamp(requested_expiry)
        if requested_expiry in available:
            expiry_mapping[requested_expiry] = requested_expiry
            continue
        if not available_dates:
            unavailable.append(requested_expiry)
            continue
        nearest_date = min(
            available_dates,
            key=lambda date: abs((date - requested_date).days),
        )
        if abs((nearest_date - requested_date).days) <= expiry_tolerance_days:
            expiry_mapping[requested_expiry] = available_dates[nearest_date]
        else:
            unavailable.append(requested_expiry)
    if unavailable:
        raise ValueError(
            "Aucune échéance yfinance à moins de "
            f"{expiry_tolerance_days} jours pour : " + ", ".join(unavailable)
        )
    timestamp = snapshot_utc or datetime.now(timezone.utc)
    rows: list[pd.DataFrame] = []
    for contractual_expiry, market_expiry in expiry_mapping.items():
        chain = market.option_chain(market_expiry)
        underlying = getattr(chain, "underlying", {}) or {}
        underlying_price = next(
            (
                float(underlying[key])
                for key in ("regularMarketPrice", "currentPrice", "previousClose")
                if key in underlying and np.isfinite(float(underlying[key]))
            ),
            np.nan,
        )
        for option_type, frame in (("call", chain.calls), ("put", chain.puts)):
            if frame is None or frame.empty:
                continue
            quotes = frame.copy()
            quotes["ticker"] = str(ticker).strip().upper()
            quotes["snapshot_utc"] = pd.Timestamp(timestamp)
            quotes["underlying_price"] = underlying_price
            quotes["expiry"] = pd.Timestamp(contractual_expiry)
            quotes["market_expiry"] = pd.Timestamp(market_expiry)
            quotes["option_type"] = option_type
            rows.append(quotes)
    if not rows:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    snapshot = validate_option_snapshot(pd.concat(rows, ignore_index=True))
    for column in SNAPSHOT_COLUMNS:
        if column not in snapshot:
            snapshot[column] = np.nan
    return snapshot.loc[:, SNAPSHOT_COLUMNS]


def _best_exact_quote(
    snapshot: pd.DataFrame,
    expiry: pd.Timestamp,
    option_type: str,
    strike: float,
    strike_tolerance: float,
    max_strike_distance: float,
) -> pd.Series | None:
    allowed_distance = max(float(strike_tolerance), float(max_strike_distance))
    candidates = snapshot.loc[
        snapshot["is_valid_quote"].astype(bool)
        & (pd.to_datetime(snapshot["expiry"]).dt.normalize() == expiry.normalize())
        & (snapshot["option_type"] == option_type)
        & ((snapshot["strike"] - strike).abs() <= allowed_distance)
    ].copy()
    if candidates.empty:
        return None
    for column in ("openInterest", "volume"):
        values = (
            candidates[column]
            if column in candidates
            else pd.Series(0.0, index=candidates.index)
        )
        candidates[column] = pd.to_numeric(values, errors="coerce").fillna(0.0)
    candidates["strike_distance"] = (candidates["strike"] - strike).abs()
    return candidates.sort_values(
        ["strike_distance", "openInterest", "volume", "half_spread"],
        ascending=[True, False, False, True],
        kind="stable",
    ).iloc[0]


def synthetic_binary_quote(
    binary: BinaryCall | BinaryPut,
    snapshot: pd.DataFrame,
    strike_scale: float = 1.0,
) -> dict[str, object]:
    """Construit un bid/ask exécutable de digitale via un vertical spread."""
    option_type = "call" if isinstance(binary, BinaryCall) else "put"
    expiry = pd.Timestamp(binary.maturity_date).normalize()
    chain = snapshot.loc[
        snapshot["is_valid_quote"].astype(bool)
        & (pd.to_datetime(snapshot["expiry"]).dt.normalize() == expiry)
        & (snapshot["option_type"] == option_type)
    ].sort_values("strike")
    market_strike = float(binary.strike) * strike_scale
    lower = chain.loc[chain["strike"] < market_strike]
    upper = chain.loc[chain["strike"] > market_strike]
    if lower.empty or upper.empty:
        return {
            "available": False,
            "status": "missing_bracketing_strikes",
        }
    low = lower.iloc[-1]
    high = upper.iloc[0]
    strike_width = float(high["strike"] - low["strike"])
    payout = float(binary.notional)
    if isinstance(binary, BinaryCall):
        bid = payout * max(0.0, float(low["bid"] - high["ask"]) / strike_width)
        ask = payout * max(bid, float(low["ask"] - high["bid"]) / strike_width)
    else:
        bid = payout * max(0.0, float(high["bid"] - low["ask"]) / strike_width)
        ask = payout * max(bid, float(high["ask"] - low["bid"]) / strike_width)
    return {
        "available": ask > bid >= 0.0,
        "status": "synthetic_vertical_spread" if ask > bid else "invalid_synthetic_spread",
        "bid": bid,
        "ask": ask,
        "mid": 0.5 * (bid + ask),
        "half_spread": 0.5 * (ask - bid),
        "lower_strike": float(low["strike"]),
        "upper_strike": float(high["strike"]),
        "strike_width": strike_width,
        "payout": payout,
        "market_strike": market_strike,
    }


def _instrument_cost(
    instrument: VanillaProduct,
    weight: float,
    snapshot: pd.DataFrame,
    scenario: Mapping[str, float | str],
    strike_tolerance: float,
    strike_scale: float,
    max_strike_distance: float,
) -> dict[str, object]:
    quantity = abs(float(weight))
    market_strike = float(instrument.strike) * strike_scale
    common = {
        "instrument": instrument.name,
        "kind": instrument.__class__.__name__,
        "maturity_date": pd.Timestamp(instrument.maturity_date),
        "strike": float(instrument.strike),
        "weight": float(weight),
        "absolute_quantity": quantity,
        "market_strike": market_strike,
    }
    if isinstance(instrument, Cash):
        return {**common, "available": True, "source": "cash", "cost": 0.0}
    if isinstance(instrument, (EuropeanCall, EuropeanPut)):
        option_type = "call" if isinstance(instrument, EuropeanCall) else "put"
        quote = _best_exact_quote(
            snapshot,
            pd.Timestamp(instrument.maturity_date),
            option_type,
            market_strike,
            strike_tolerance,
            max_strike_distance,
        )
        if quote is None:
            return {
                **common,
                "available": False,
                "source": "yfinance",
                "status": "missing_exact_valid_quote",
                "cost": np.nan,
            }
        matched_strike = float(quote["strike"])
        is_exact = abs(matched_strike - market_strike) <= strike_tolerance
        return {
            **common,
            "available": True,
            "source": "yfinance",
            "status": "exact_valid_quote" if is_exact else "nearest_valid_quote",
            "matched_market_strike": matched_strike,
            "strike_distance": abs(matched_strike - market_strike),
            "bid": float(quote["bid"]),
            "ask": float(quote["ask"]),
            "half_spread": float(quote["half_spread"]),
            # Un payoff de call/put coté dans les unités du marché vaut
            # strike_scale fois le payoff de l'univers normalisé.
            "market_quantity": quantity / strike_scale,
            "cost": quantity / strike_scale * float(quote["half_spread"]),
        }
    if isinstance(instrument, (BinaryCall, BinaryPut)):
        synthetic = synthetic_binary_quote(
            instrument,
            snapshot,
            strike_scale=strike_scale,
        )
        if not bool(synthetic["available"]):
            return {
                **common,
                "available": False,
                "source": "otc_scenario",
                "status": synthetic["status"],
                "cost": np.nan,
            }
        multiplier = float(scenario["half_spread_multiplier"])
        floor_bps = float(scenario["minimum_half_spread_bps_of_payout"])
        payout = float(synthetic["payout"])
        otc_half_spread = max(
            multiplier * float(synthetic["half_spread"]),
            floor_bps * payout / 10_000.0,
        )
        return {
            **common,
            "available": True,
            "source": "otc_scenario",
            "status": synthetic["status"],
            "synthetic_half_spread": float(synthetic["half_spread"]),
            "otc_half_spread": otc_half_spread,
            "cost": quantity * otc_half_spread,
            "lower_strike": synthetic["lower_strike"],
            "upper_strike": synthetic["upper_strike"],
        }
    return {
        **common,
        "available": False,
        "source": "unsupported",
        "status": "unsupported_instrument_type",
        "cost": np.nan,
    }


def estimate_profile_transaction_costs(
    base_result: dict[str, object],
    snapshot: pd.DataFrame,
    autocall_notional: float,
    scenarios: Mapping[str, Mapping[str, float | str]] = OTC_COST_SCENARIOS,
    strike_tolerance: float = 1e-8,
    model_spot0: float | None = None,
    market_spot: float | None = None,
    max_strike_distance_fraction: float = 0.005,
) -> dict[str, pd.DataFrame]:
    """Calcule les coûts de chaque profil sous les trois scénarios OTC."""
    if autocall_notional <= 0.0:
        raise ValueError("autocall_notional doit être strictement positif.")
    validated_snapshot = validate_option_snapshot(snapshot)
    if market_spot is None and "underlying_price" in validated_snapshot:
        observed_spots = pd.to_numeric(
            validated_snapshot["underlying_price"], errors="coerce"
        ).dropna()
        market_spot = float(observed_spots.median()) if not observed_spots.empty else None
    if model_spot0 is None and market_spot is not None:
        raise ValueError("model_spot0 est requis lorsque market_spot est utilisé.")
    if model_spot0 is not None and model_spot0 <= 0.0:
        raise ValueError("model_spot0 doit être strictement positif.")
    strike_scale = (
        float(market_spot) / float(model_spot0)
        if market_spot is not None and model_spot0 is not None
        else 1.0
    )
    if not np.isfinite(strike_scale) or strike_scale <= 0.0:
        raise ValueError("Le facteur de conversion des strikes est invalide.")
    if max_strike_distance_fraction < 0.0:
        raise ValueError("max_strike_distance_fraction doit être positif.")
    max_strike_distance = (
        max_strike_distance_fraction * float(market_spot)
        if market_spot is not None
        else 0.0
    )
    profiles = pd.DataFrame(base_result["profiles"])
    vanillas = list(base_result["vanillas"])
    detail_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for _, profile in profiles.iterrows():
        penalty = str(profile["penalty"])
        profile_name = str(profile["profile"])
        weights = np.asarray(
            base_result["results"][penalty]["solutions"][
                int(profile["solution_index"])
            ]["weights"],
            dtype=float,
        )
        for scenario_name, scenario in scenarios.items():
            rows = [
                {
                    "penalty": penalty,
                    "profile": profile_name,
                    "cost_scenario": scenario_name,
                    **_instrument_cost(
                        instrument,
                        weight,
                        validated_snapshot,
                        scenario,
                        strike_tolerance,
                        strike_scale,
                        max_strike_distance,
                    ),
                }
                for instrument, weight in zip(vanillas, weights)
                if abs(float(weight)) > 1e-6 or isinstance(instrument, Cash)
            ]
            detail_rows.extend(rows)
            available = [row for row in rows if bool(row["available"])]
            missing = [row for row in rows if not bool(row["available"])]
            transaction_cost = float(sum(float(row["cost"]) for row in available))
            summary_rows.append(
                {
                    "penalty": penalty,
                    "profile": profile_name,
                    "cost_scenario": scenario_name,
                    "transaction_cost": transaction_cost,
                    "transaction_cost_bps": (
                        10_000.0 * transaction_cost / autocall_notional
                    ),
                    "transaction_cost_pct_notional": (
                        100.0 * transaction_cost / autocall_notional
                    ),
                    "n_active_lines": len(rows),
                    "n_priced_lines": len(available),
                    "n_missing_lines": len(missing),
                    "cost_complete": len(missing) == 0,
                    "scenario_description": str(scenario["description"]),
                    "model_spot0": model_spot0,
                    "market_spot": market_spot,
                    "strike_scale": strike_scale,
                    "max_strike_distance": max_strike_distance,
                }
            )
    return {
        "details": pd.DataFrame(detail_rows),
        "summary": pd.DataFrame(summary_rows),
        "snapshot": validated_snapshot,
    }


def estimate_conditional_policy_transaction_costs(
    base_result: dict[str, object],
    snapshot: pd.DataFrame,
    autocall_notional: float,
    scenarios: Mapping[str, Mapping[str, float | str]] = OTC_COST_SCENARIOS,
    strike_tolerance: float = 1e-8,
    model_spot0: float | None = None,
    market_spot: float | None = None,
    max_strike_distance_fraction: float = 0.005,
) -> dict[str, pd.DataFrame]:
    """Estime le coût attendu d'une politique selon les nœuds effectivement visités.

    Chaque coût de ligne est pondéré par la probabilité empirique d'atteindre
    son nœud date/état. Cette mesure est distincte d'un coût dynamique complet :
    elle n'inclut ni impact de marché, ni marge, ni liquidation anticipée.
    """
    if autocall_notional <= 0.0:
        raise ValueError("autocall_notional doit être strictement positif.")
    validated_snapshot = validate_option_snapshot(snapshot)
    if market_spot is None and "underlying_price" in validated_snapshot:
        observed_spots = pd.to_numeric(
            validated_snapshot["underlying_price"], errors="coerce"
        ).dropna()
        market_spot = float(observed_spots.median()) if not observed_spots.empty else None
    if model_spot0 is None and market_spot is not None:
        raise ValueError("model_spot0 est requis lorsque market_spot est utilisé.")
    strike_scale = (
        float(market_spot) / float(model_spot0)
        if market_spot is not None and model_spot0 is not None
        else 1.0
    )
    max_strike_distance = (
        max_strike_distance_fraction * float(market_spot)
        if market_spot is not None
        else 0.0
    )
    profiles = pd.DataFrame(base_result["profiles"])
    features = pd.DataFrame(base_result["feature_table"])
    visits = pd.DataFrame(base_result["visits"])
    n_paths = int(base_result["n_paths"])
    visit_probabilities = (
        visits[["path_index", "selected_node_index"]]
        .drop_duplicates()
        .groupby("selected_node_index")
        .size()
        .div(n_paths)
    )
    vanillas = list(base_result["vanillas"])
    detail_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for _, profile in profiles.iterrows():
        penalty, profile_name = str(profile["penalty"]), str(profile["profile"])
        weights = np.asarray(
            base_result["results"][penalty]["solutions"][
                int(profile["solution_index"])
            ]["weights"],
            dtype=float,
        )
        for scenario_name, scenario in scenarios.items():
            rows = []
            for column_index, (instrument, weight) in enumerate(zip(vanillas, weights)):
                if abs(float(weight)) <= 1e-6 and not isinstance(instrument, Cash):
                    continue
                metadata = features.iloc[column_index]
                node_index = int(metadata["node_index"])
                visit_probability = float(visit_probabilities.get(node_index, 0.0))
                cost = _instrument_cost(
                    instrument,
                    weight,
                    validated_snapshot,
                    scenario,
                    strike_tolerance,
                    strike_scale,
                    max_strike_distance,
                )
                cost.update(
                    {
                        "family": base_result["family"],
                        "penalty": penalty,
                        "profile": profile_name,
                        "cost_scenario": scenario_name,
                        "node_index": node_index,
                        "decision_date": metadata["decision_date"],
                        "payment_date": metadata["payment_date"],
                        "decision_state": metadata["decision_state"],
                        "visit_probability": visit_probability,
                        "expected_cost": (
                            visit_probability * float(cost["cost"])
                            if bool(cost["available"])
                            else np.nan
                        ),
                    }
                )
                rows.append(cost)
            detail_rows.extend(rows)
            priced = [row for row in rows if bool(row["available"])]
            missing = [row for row in rows if not bool(row["available"])]
            expected_cost = float(sum(float(row["expected_cost"]) for row in priced))
            upper_bound_cost = float(sum(float(row["cost"]) for row in priced))
            summary_rows.append(
                {
                    "family": base_result["family"],
                    "penalty": penalty,
                    "profile": profile_name,
                    "cost_scenario": scenario_name,
                    "expected_transaction_cost": expected_cost,
                    "expected_transaction_cost_bps": 10_000.0 * expected_cost / autocall_notional,
                    "all_nodes_cost_upper_bound": upper_bound_cost,
                    "n_active_lines": len(rows),
                    "n_priced_lines": len(priced),
                    "n_missing_lines": len(missing),
                    "cost_complete": len(missing) == 0,
                    "scenario_description": str(scenario["description"]),
                    "cost_interpretation": "node_cost_weighted_by_empirical_reach_probability",
                }
            )
    return {
        "details": pd.DataFrame(detail_rows),
        "summary": pd.DataFrame(summary_rows),
        "snapshot": validated_snapshot,
        "visit_probabilities": visit_probabilities.rename("visit_probability").reset_index(),
    }


def estimate_profile_model_values(
    base_result: dict[str, object],
    spot0: float,
    valuation_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    autocall_model_value: float | None = None,
    autocall_notional: float = 100.0,
) -> pd.DataFrame:
    """Valorise théoriquement les paniers au temps initial sous Black-Scholes.

    Cette valeur de modèle est distincte du coût d'exécution bid-ask. Les poids
    restent continus et aucun coût de financement ou de marge n'est ajouté.
    """
    if autocall_notional <= 0.0:
        raise ValueError("autocall_notional doit être strictement positif.")
    profiles = pd.DataFrame(base_result["profiles"])
    vanillas = list(base_result["vanillas"])
    instrument_prices = np.asarray(
        [
            instrument.price_bs(
                float(spot0),
                pd.Timestamp(valuation_date),
                float(rate),
                float(dividend_yield),
                float(vol),
            )
            for instrument in vanillas
        ],
        dtype=float,
    )
    rows: list[dict[str, object]] = []
    for _, profile in profiles.iterrows():
        penalty = str(profile["penalty"])
        profile_name = str(profile["profile"])
        weights = np.asarray(
            base_result["results"][penalty]["solutions"][
                int(profile["solution_index"])
            ]["weights"],
            dtype=float,
        )
        signed_values = weights * instrument_prices
        portfolio_model_value = float(np.sum(signed_values))
        row = {
            "penalty": penalty,
            "profile": profile_name,
            "portfolio_model_value": portfolio_model_value,
            "portfolio_model_value_pct_notional": (
                100.0 * portfolio_model_value / autocall_notional
            ),
            "portfolio_model_value_bps_notional": (
                10_000.0 * portfolio_model_value / autocall_notional
            ),
            "gross_long_model_value": float(np.sum(signed_values[signed_values > 0.0])),
            "gross_short_model_value": float(-np.sum(signed_values[signed_values < 0.0])),
            "gross_absolute_model_value": float(np.sum(np.abs(signed_values))),
        }
        if autocall_model_value is not None:
            funding_gap = float(autocall_model_value) - portfolio_model_value
            row.update(
                {
                    "autocall_model_value": float(autocall_model_value),
                    "initial_model_funding_gap": funding_gap,
                    "initial_model_funding_gap_pct_notional": (
                        100.0 * funding_gap / autocall_notional
                    ),
                    "initial_model_funding_gap_bps_notional": (
                        10_000.0 * funding_gap / autocall_notional
                    ),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)
