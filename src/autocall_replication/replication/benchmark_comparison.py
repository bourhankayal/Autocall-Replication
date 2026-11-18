"""Canonical comparison table for heterogeneous replication benchmarks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd


BENCHMARK_COLUMNS = (
    "method",
    "family",
    "construction",
    "rebalancing",
    "sparse",
    "risk_object",
    "comparison_scope",
    "capital_aligned",
    "transaction_costs_included",
    "mean_error_pct_notional",
    "mae_pct_notional",
    "rmse_pct_notional",
    "under_replication_rate",
    "es_975_pct_notional",
    "max_loss_pct_notional",
    "mean_rebalances",
    "mean_gross_turnover",
    "limitations",
)


def build_unified_benchmark_table(
    records: Iterable[Mapping[str, object]],
) -> pd.DataFrame:
    """Return one auditable table without inventing missing comparability.

    Every row must state its risk object and comparison scope.  Missing cost,
    turnover or capital information remains missing rather than being silently
    interpreted as zero.
    """
    rows = [dict(record) for record in records]
    if not rows:
        raise ValueError("At least one benchmark record is required.")
    required = {
        "method",
        "family",
        "construction",
        "rebalancing",
        "sparse",
        "risk_object",
        "comparison_scope",
        "capital_aligned",
        "transaction_costs_included",
        "mean_error_pct_notional",
        "mae_pct_notional",
        "rmse_pct_notional",
        "under_replication_rate",
        "es_975_pct_notional",
        "max_loss_pct_notional",
    }
    missing = [sorted(required.difference(row)) for row in rows]
    if any(missing):
        raise ValueError(f"Incomplete benchmark records: {missing}.")

    table = pd.DataFrame(rows)
    for column in BENCHMARK_COLUMNS:
        if column not in table:
            table[column] = np.nan
    for column in (
        "mean_error_pct_notional", "mae_pct_notional", "rmse_pct_notional",
        "under_replication_rate", "es_975_pct_notional", "max_loss_pct_notional",
    ):
        values = pd.to_numeric(table[column], errors="coerce")
        if values.isna().any() or (~np.isfinite(values)).any():
            raise ValueError(f"{column} must contain finite values.")
        if column in {"mae_pct_notional", "rmse_pct_notional", "es_975_pct_notional"} and (values < 0).any():
            raise ValueError(f"{column} must contain nonnegative values.")
        if column == "under_replication_rate" and ((values < 0).any() or (values > 1).any()):
            raise ValueError("under_replication_rate must lie between zero and one.")
        table[column] = values
    if table[["method", "family"]].duplicated().any():
        raise ValueError("Each method/family pair must be unique.")
    return table.loc[:, BENCHMARK_COLUMNS].sort_values(
        ["family", "method"], kind="stable",
    ).reset_index(drop=True)
