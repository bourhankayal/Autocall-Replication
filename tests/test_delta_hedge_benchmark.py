"""Focused checks for the independent Black--Scholes delta comparator."""

import numpy as np
import pandas as pd
import pytest

from autocall_replication.products import AutocallProduct
from autocall_replication.replication.delta_hedge_benchmark import (
    build_delta_surface,
    evaluate_delta_hedge,
)


def test_cash_only_deterministic_contract_hedges_exactly():
    product = AutocallProduct(
        autocall_strike=2.0, coupon_barrier=2.0, down_barrier=0.7,
    )
    start = pd.Timestamp("2026-06-22")
    maturity = pd.offsets.BDay().rollforward(product.build_observation_dates(start)[-1])
    surface = build_delta_surface(
        product=product, spot0=100.0, valuation_date=start,
        maturity_date=maturity, rate=0.03, dividend_yield=0.01, vol=0.0,
        spot_nodes=801, quadrature_nodes=8,
    )
    path = pd.Series(100.0, index=surface.dates)
    summary, detail = evaluate_delta_hedge(
        surface=surface, product=product, paths=[path],
        rate=0.03, dividend_yield=0.01, rebalance_every=5,
    )
    expected_price = 100.0 * np.exp(-0.03 * (maturity - start).days / 365.0)
    assert surface.initial_price == pytest.approx(expected_price, abs=0.05)
    assert summary.iloc[0]["rmse"] < 0.05
    assert abs(detail.iloc[0]["discounted_loss"]) < 0.05


def test_surface_rejects_other_dates_and_does_not_use_future_prices_for_initial_delta():
    product = AutocallProduct()
    start = pd.Timestamp("2026-06-22")
    maturity = pd.offsets.BDay().rollforward(product.build_observation_dates(start)[-1])
    surface = build_delta_surface(
        product=product, spot0=100.0, valuation_date=start,
        maturity_date=maturity, rate=0.03, dividend_yield=0.01, vol=0.2,
        spot_nodes=101, quadrature_nodes=8,
    )
    first_delta = surface.delta(0, 100.0, False)
    path_a = pd.Series(100.0, index=surface.dates)
    path_b = path_a.copy()
    path_b.iloc[1:] = 110.0
    assert surface.delta(0, 100.0, False) == first_delta
    _, details = evaluate_delta_hedge(
        surface=surface, product=product, paths=[path_a, path_b],
        rate=0.03, dividend_yield=0.01, rebalance_every=5,
    )
    assert details["initial_shares"].iloc[0] == details["initial_shares"].iloc[1]
    assert details["initial_cash"].iloc[0] == details["initial_cash"].iloc[1]
    with pytest.raises(ValueError, match="business-day grid"):
        evaluate_delta_hedge(
            surface=surface, product=product, paths=[path_a.iloc[:-1]],
            rate=0.03, dividend_yield=0.01, rebalance_every=1,
        )
    assert path_b.iloc[-1] != path_a.iloc[-1]


def test_weekend_valuation_anchor_discounts_price_and_payoffs_consistently():
    product = AutocallProduct(autocall_strike=2.0, coupon_barrier=2.0, down_barrier=0.7)
    valuation = pd.Timestamp("2026-06-20")
    fixing = pd.Timestamp("2026-06-22")
    maturity = pd.offsets.BDay().rollforward(product.build_observation_dates(fixing)[-1])
    rate = 0.03
    surface = build_delta_surface(
        product=product, spot0=100.0, valuation_date=valuation,
        maturity_date=maturity, rate=rate, dividend_yield=0.01, vol=0.0,
        spot_nodes=801, quadrature_nodes=8,
    )
    path = pd.Series(100.0, index=surface.dates)
    summary, details = evaluate_delta_hedge(
        surface=surface, product=product, paths=[path],
        rate=rate, dividend_yield=0.01, rebalance_every=1,
        valuation_date=valuation,
    )
    expected_pv = 100.0 * np.exp(-rate * (maturity - valuation).days / 365.0)
    assert summary.iloc[0]["initial_capital"] == pytest.approx(expected_pv, abs=0.05)
    assert details.iloc[0]["autocall_payoff_pv"] == pytest.approx(expected_pv)
    assert abs(details.iloc[0]["discounted_loss"]) < 0.05
