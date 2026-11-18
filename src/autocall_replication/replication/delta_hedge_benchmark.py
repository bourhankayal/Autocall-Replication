"""Black--Scholes delta-hedging benchmark for the project's one-asset autocall.

The value surface is computed once by backward Gaussian quadrature on the same
business-day grid as the simulation.  The state is (spot, down-barrier hit).
This is a discrete, self-financing *dynamic* comparator, not another fitted
static option portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..monte_carlo import _validated_business_grid
from ..products import AutocallProduct
from .risk import tail_risk_metrics


@dataclass(frozen=True)
class DeltaSurface:
    dates: pd.DatetimeIndex
    spots: np.ndarray
    values_after_payment: np.ndarray  # date, hit-state, spot
    deltas_after_payment: np.ndarray
    initial_price: float
    spot0: float

    def delta(self, date_index: int, spot: float, barrier_hit: bool) -> float:
        return float(np.interp(
            spot, self.spots,
            self.deltas_after_payment[date_index, int(barrier_hit)],
        ))


def build_delta_surface(
    *, product: AutocallProduct, spot0: float, valuation_date: pd.Timestamp,
    maturity_date: pd.Timestamp, rate: float, dividend_yield: float, vol: float,
    spot_nodes: int = 801, quadrature_nodes: int = 40,
) -> DeltaSurface:
    """Price and delta conditional on survival and the observed barrier state.

    Observation-date payouts are applied in backward induction. The surface
    after a payment is used only for contracts still alive. The down barrier is
    monitored at each business-day close, matching ``compute_autocall_payoff``.
    """
    if spot0 <= 0 or vol < 0 or spot_nodes < 51 or quadrature_nodes < 4:
        raise ValueError("Invalid delta-surface configuration.")
    dates = _validated_business_grid(pd.Timestamp(valuation_date), pd.Timestamp(maturity_date))
    fixing = dates[0]
    observations = {
        pd.offsets.BDay().rollforward(date)
        for date in product.build_observation_dates(fixing)
    }
    if dates[-1] != max(observations):
        raise ValueError("Maturity must equal the effective last observation date.")
    log_spots = np.linspace(np.log(spot0 * 0.2), np.log(spot0 * 3.0), spot_nodes)
    spots = np.exp(log_spots)
    values_post = np.zeros((len(dates), 2, spot_nodes), dtype=float)
    values_pre = np.zeros_like(values_post)
    nodes, quadrature_weights = np.polynomial.hermite.hermgauss(quadrature_nodes)
    quadrature_weights /= np.sqrt(np.pi)
    down_level = product.down_barrier * spot0
    coupon_level = product.coupon_barrier * spot0
    call_level = product.autocall_strike * spot0
    coupon = product.coupon_rate * product.notional

    for index in range(len(dates) - 1, -1, -1):
        if index < len(dates) - 1:
            dt = (dates[index + 1] - dates[index]).days / 365.0
            next_spots = spots[:, None] * np.exp(
                (rate - dividend_yield - 0.5 * vol**2) * dt
                + vol * np.sqrt(2.0 * dt) * nodes[None, :]
            )
            next_hit = np.interp(next_spots, spots, values_pre[index + 1, 1])
            next_clean = np.interp(next_spots, spots, values_pre[index + 1, 0])
            values_post[index, 1] = np.exp(-rate * dt) * (next_hit @ quadrature_weights)
            values_post[index, 0] = np.exp(-rate * dt) * (
                np.where(next_spots <= down_level, next_hit, next_clean)
                @ quadrature_weights
            )

        values_pre[index] = values_post[index]
        if dates[index] in observations:
            coupon_payment = coupon * (spots >= coupon_level)
            called = spots >= call_level
            if index == len(dates) - 1:
                for hit in (0, 1):
                    redemption = np.where(hit == 1, product.notional * spots / spot0, product.notional)
                    values_pre[index, hit] = coupon_payment + np.where(
                        called, product.notional, redemption,
                    )
            else:
                values_pre[index] = coupon_payment + np.where(
                    called, product.notional, values_post[index],
                )

    deltas_post = np.gradient(values_post, spots, axis=2)
    initial_price = float(np.interp(spot0, spots, values_pre[0, 0]))
    return DeltaSurface(dates, spots, values_post, deltas_post, initial_price, spot0)


def evaluate_delta_hedge(
    *, surface: DeltaSurface, product: AutocallProduct,
    paths: list[pd.Series], rate: float, dividend_yield: float,
    rebalance_every: int, valuation_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Self-financing stock/cash hedge on frozen paths, with no look-ahead.

    Shares are selected after the close and contractual cashflow at date ``t``
    for the interval ``(t,t+1]``. Coupons/redemption are paid from cash.
    Dividends are credited to cash; share trades transfer value between stock
    and cash. Transaction costs are deliberately excluded and turnover reported.
    """
    if rebalance_every < 1 or not paths:
        raise ValueError("Positive rebalance frequency and nonempty paths required.")
    dates = surface.dates
    anchor = pd.Timestamp(valuation_date) if valuation_date is not None else dates[0]
    if anchor > dates[0]:
        raise ValueError("Valuation date must not follow the initial trading date.")
    observations = {
        pd.offsets.BDay().rollforward(date)
        for date in product.build_observation_dates(dates[0])
    }
    barrier_level = product.down_barrier * surface.spot0
    rows = []
    for path_index, path in enumerate(paths):
        if not path.index.equals(dates):
            raise ValueError("Hedge path must use exactly the surface's business-day grid.")
        if not np.isclose(float(path.iloc[0]), surface.spot0):
            raise ValueError("Hedge path has a different initial fixing.")
        if float(path.min()) < surface.spots[0] or float(path.max()) > surface.spots[-1]:
            raise ValueError("Hedge path leaves the precomputed spot grid; enlarge it before evaluation.")
        contract = product.compute_autocall_payoff(path, start_date=dates[0])
        payment_by_date = contract["cashflows"].groupby("date")["amount"].sum().to_dict()
        stop = pd.Timestamp(contract["call_date"]) if contract["called"] else dates[-1]
        stop_index = int(dates.get_loc(stop))
        shares = surface.delta(0, surface.spot0, surface.spot0 <= barrier_level)
        cash = surface.initial_price - shares * surface.spot0
        initial_shares, initial_cash = shares, cash
        turnover = abs(shares * surface.spot0)
        rebalances = 0
        hit = surface.spot0 <= barrier_level
        for index in range(1, stop_index + 1):
            dt = (dates[index] - dates[index - 1]).days / 365.0
            previous_spot = float(path.iloc[index - 1])
            spot = float(path.iloc[index])
            cash = cash * np.exp(rate * dt) + shares * previous_spot * np.expm1(dividend_yield * dt)
            cash -= float(payment_by_date.get(dates[index], 0.0))
            hit = hit or spot <= barrier_level
            if index == stop_index:
                cash += shares * spot
                shares = 0.0
            elif index % rebalance_every == 0 or dates[index] in observations:
                new_shares = surface.delta(index, spot, hit)
                cash -= (new_shares - shares) * spot
                turnover += abs(new_shares - shares) * spot
                shares = new_shares
                rebalances += 1
        discount = np.exp(-rate * (stop - anchor).days / 365.0)
        loss = -cash * discount
        payoff_pv = sum(
            float(row.amount) * np.exp(-rate * (pd.Timestamp(row.date) - anchor).days / 365.0)
            for row in contract["cashflows"].itertuples()
        )
        rows.append({
            "path_index": path_index, "discounted_loss": loss,
            "autocall_payoff_pv": payoff_pv,
            "discounted_hedge_value": payoff_pv - loss,
            "stop_date": stop, "barrier_hit": bool(contract["barrier_hit"]),
            "n_rebalances": rebalances, "gross_turnover": turnover,
            "initial_shares": initial_shares, "initial_cash": initial_cash,
        })
    details = pd.DataFrame(rows)
    metrics = tail_risk_metrics(details["discounted_loss"].to_numpy(), levels=(0.975,))
    summary = pd.DataFrame([{
        "method": f"delta_{rebalance_every}d", "n_paths": len(details),
        "initial_capital": surface.initial_price * np.exp(-rate * (dates[0] - anchor).days / 365.0),
        "mean_error": metrics["mean_loss"], "mae": metrics["mae"],
        "rmse": metrics["rmse"], "es_975": metrics["es_975"],
        "max_loss": metrics["max_loss"],
        "under_replication_rate": metrics["under_replication_rate"],
        "mean_rebalances": details["n_rebalances"].mean(),
        "mean_gross_turnover": details["gross_turnover"].mean(),
        "transaction_costs_included": False,
    }])
    return summary, details
