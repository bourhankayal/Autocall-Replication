"""Benchmarks économiques internes et publics des stratégies de réplication.

Les données publiques portent sur l'écart entre le prix d'émission et la
valeur initiale estimée par l'émetteur. Elles ne mesurent pas le P&L réalisé
par un desk et ne doivent jamais être présentées comme tel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


PUBLIC_STRUCTURED_NOTE_EXAMPLES = (
    {
        "issuer": "JPMorgan",
        "document_date": "2025-04-09",
        "structure": "Auto Callable Notes",
        "issue_price": 1000.0,
        "estimated_value_low": 971.60,
        "estimated_value_high": 971.60,
        "source_url": "https://www.sec.gov/Archives/edgar/data/19617/000121390025028272/ea0236912-01_424b2.htm",
    },
    {
        "issuer": "Barclays",
        "document_date": "2025-11-24",
        "structure": "Auto-Callable Notes",
        "issue_price": 1000.0,
        "estimated_value_low": 940.0,
        "estimated_value_high": 940.0,
        "source_url": "https://www.sec.gov/Archives/edgar/data/312070/000191870425019389/form424b2.htm",
    },
    {
        "issuer": "Morgan Stanley",
        "document_date": "2026-05-14",
        "structure": "Jump Notes with Auto-Callable Feature",
        "issue_price": 1000.0,
        "estimated_value_low": 895.50,
        "estimated_value_high": 975.50,
        "source_url": "https://www.sec.gov/Archives/edgar/data/895421/000183988226023540/ms15872_424b2-15430.htm",
    },
    {
        "issuer": "Goldman Sachs",
        "document_date": "2025-05-01",
        "structure": "Autocallable Contingent Coupon Notes",
        "issue_price": 1000.0,
        "estimated_value_low": 890.0,
        "estimated_value_high": 920.0,
        "source_url": "https://www.sec.gov/Archives/edgar/data/0000886982/000095017025052435/amznco11_auto_prelim.htm",
    },
)


def public_structured_note_pricing_benchmark() -> pd.DataFrame:
    """Retourne des exemples SEC illustratifs, avec un écart en % du prix.

    Pour une valeur estimée publiée sous forme d'intervalle, ``gap_pct_low``
    utilise la valeur haute et ``gap_pct_high`` la valeur basse. L'échantillon
    n'est ni exhaustif ni homogène : il sert de repère documentaire uniquement.
    """
    table = pd.DataFrame(PUBLIC_STRUCTURED_NOTE_EXAMPLES).copy()
    table["document_date"] = pd.to_datetime(table["document_date"])
    table["gap_pct_low"] = 100.0 * (
        table["issue_price"] - table["estimated_value_high"]
    ) / table["issue_price"]
    table["gap_pct_high"] = 100.0 * (
        table["issue_price"] - table["estimated_value_low"]
    ) / table["issue_price"]
    table["gap_pct_mid"] = 0.5 * (table["gap_pct_low"] + table["gap_pct_high"])
    table["benchmark_scope"] = (
        "issue price minus issuer estimated value; not realized desk P&L"
    )
    return table


def build_three_price_table(
    funding_row: pd.Series | dict[str, object],
    theoretical_price: float,
    notional: float,
    target_margin_pct_notional: float = 1.0,
) -> pd.DataFrame:
    """Construit prix théorique, prix de couverture et prix commercial.

    Le P&L moyen de financement a été calculé avec
    ``initial_autocall_premium``. Le prix minimal ajoute donc à cette prime la
    perte moyenne qu'il faut compenser. Le prix commercial ajoute ensuite une
    marge cible explicite ; il ne constitue pas une cotation de marché.
    """
    row = pd.Series(funding_row)
    if notional <= 0.0:
        raise ValueError("notional doit être strictement positif.")
    if target_margin_pct_notional < 0.0:
        raise ValueError("target_margin_pct_notional doit être positif ou nul.")
    required = {"initial_autocall_premium", "terminal_pnl_mean"}
    missing = required - set(row.index)
    if missing:
        raise ValueError(f"Colonnes de financement manquantes : {sorted(missing)}")

    current_premium = float(row["initial_autocall_premium"])
    mean_pnl = float(row["terminal_pnl_mean"])
    minimum_coverage_price = current_premium - mean_pnl
    target_margin = notional * target_margin_pct_notional / 100.0
    commercial_price = minimum_coverage_price + target_margin
    prices = (
        ("theoretical", float(theoretical_price), "valeur du passif sous le modèle"),
        (
            "minimum_coverage",
            minimum_coverage_price,
            "prix annulant le P&L terminal moyen estimé",
        ),
        (
            "commercial",
            commercial_price,
            f"prix minimal + marge cible de {target_margin_pct_notional:.2f}% du nominal",
        ),
    )
    output = pd.DataFrame(prices, columns=["price_type", "price", "definition"])
    output["price_pct_notional"] = 100.0 * output["price"] / notional
    output["cushion_vs_theoretical"] = output["price"] - float(theoretical_price)
    output["cushion_vs_theoretical_pct_notional"] = (
        100.0 * output["cushion_vs_theoretical"] / notional
    )
    output["source_terminal_pnl_mean"] = mean_pnl
    output["target_margin_pct_notional"] = target_margin_pct_notional
    return output


def build_internal_hedge_benchmark(
    risk_summary: pd.DataFrame,
    reference_family: str = "calls_puts",
) -> pd.DataFrame:
    """Compare chaque hedge au non-couvert puis à une famille de référence."""
    required = {
        "family", "penalty", "profile", "gross_rmse", "residual_rmse",
        "gross_es_975", "residual_es_975",
    }
    missing = required - set(risk_summary.columns)
    if missing:
        raise ValueError(f"Colonnes de risque manquantes : {sorted(missing)}")
    output = risk_summary.copy()
    output["rmse_improvement_vs_unhedged"] = np.where(
        output["gross_rmse"] > 0.0,
        1.0 - output["residual_rmse"] / output["gross_rmse"],
        np.nan,
    )
    output["es_975_improvement_vs_unhedged"] = np.where(
        output["gross_es_975"] > 0.0,
        1.0 - output["residual_es_975"] / output["gross_es_975"],
        np.nan,
    )
    reference = output.loc[
        output["family"].eq(reference_family),
        ["penalty", "profile", "residual_rmse", "residual_es_975"],
    ].rename(
        columns={
            "residual_rmse": "reference_residual_rmse",
            "residual_es_975": "reference_residual_es_975",
        }
    )
    output = output.merge(reference, on=["penalty", "profile"], how="left")
    output["rmse_improvement_vs_reference"] = np.where(
        output["reference_residual_rmse"] > 0.0,
        1.0 - output["residual_rmse"] / output["reference_residual_rmse"],
        np.nan,
    )
    output["es_975_improvement_vs_reference"] = np.where(
        output["reference_residual_es_975"] > 0.0,
        1.0 - output["residual_es_975"] / output["reference_residual_es_975"],
        np.nan,
    )
    output["reference_family"] = reference_family
    return output


def compare_commercial_cushion_to_public_benchmark(
    three_prices: pd.DataFrame,
    public_benchmark: pd.DataFrame | None = None,
) -> pd.Series:
    """Positionne le coussin commercial dans l'échantillon documentaire."""
    benchmark = (
        public_structured_note_pricing_benchmark()
        if public_benchmark is None
        else public_benchmark.copy()
    )
    commercial = three_prices.loc[three_prices["price_type"].eq("commercial")]
    if len(commercial) != 1:
        raise ValueError("La table doit contenir exactement un prix commercial.")
    own_gap = float(commercial.iloc[0]["cushion_vs_theoretical_pct_notional"])
    market_mid = benchmark["gap_pct_mid"].to_numpy(dtype=float)
    return pd.Series(
        {
            "our_commercial_cushion_pct_notional": own_gap,
            "public_example_gap_min_pct": float(benchmark["gap_pct_low"].min()),
            "public_example_gap_mid_median_pct": float(np.median(market_mid)),
            "public_example_gap_max_pct": float(benchmark["gap_pct_high"].max()),
            "our_cushion_vs_public_mid_median_ratio": (
                own_gap / float(np.median(market_mid))
                if float(np.median(market_mid)) > 0.0 else np.nan
            ),
            "interpretation_limit": (
                "public gaps include distribution, structuring, hedging costs and projected profit; not desk P&L"
            ),
        },
        name="pricing_benchmark",
    )
