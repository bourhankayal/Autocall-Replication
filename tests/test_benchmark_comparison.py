import pandas as pd
import pytest

from autocall_replication.replication.benchmark_comparison import (
    BENCHMARK_COLUMNS,
    build_unified_benchmark_table,
)


def _record(method: str, family: str = "reference") -> dict[str, object]:
    return {
        "method": method,
        "family": family,
        "construction": "test",
        "rebalancing": "none",
        "sparse": False,
        "risk_object": "discounted cashflow shortfall",
        "comparison_scope": "same external paths",
        "capital_aligned": False,
        "transaction_costs_included": False,
        "mean_error_pct_notional": 0.0,
        "mae_pct_notional": 0.5,
        "rmse_pct_notional": 1.0,
        "under_replication_rate": 0.5,
        "es_975_pct_notional": 2.0,
        "max_loss_pct_notional": 3.0,
    }


def test_unified_table_keeps_missing_economic_fields_explicit():
    table = build_unified_benchmark_table([_record("delta"), _record("ols", "full")])
    assert tuple(table.columns) == BENCHMARK_COLUMNS
    assert table["mean_gross_turnover"].isna().all()
    assert set(table["comparison_scope"]) == {"same external paths"}


def test_unified_table_rejects_ambiguous_or_invalid_rows():
    with pytest.raises(ValueError, match="unique"):
        build_unified_benchmark_table([_record("delta"), _record("delta")])
    bad = _record("bad")
    bad["rmse_pct_notional"] = -1.0
    with pytest.raises(ValueError, match="nonnegative"):
        build_unified_benchmark_table([bad])
    incomplete = _record("missing")
    incomplete.pop("comparison_scope")
    with pytest.raises(ValueError, match="Incomplete"):
        build_unified_benchmark_table([incomplete])
