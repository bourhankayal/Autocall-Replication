"""Persistent, auditable exports for research-notebook runs."""

from __future__ import annotations

import json
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


def _json_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_name(name: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "_" for character in str(name))
    return "_".join(part for part in cleaned.split("_") if part) or "result"


def _as_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, pd.Series):
        return value.rename(value.name or "value").to_frame()
    if isinstance(value, Mapping):
        return pd.DataFrame([value])
    raise TypeError("Chaque table exportée doit être un DataFrame, une Series ou un mapping.")


def conditional_policy_weights_table(
    stable_profile_results: Mapping[str, Mapping[str, Any]],
) -> pd.DataFrame:
    """Return one auditable row per feature and retained conditional policy."""

    rows: list[dict[str, Any]] = []
    for family, result in stable_profile_results.items():
        profiles = pd.DataFrame(result.get("profiles", pd.DataFrame()))
        feature_table = pd.DataFrame(result.get("feature_table", pd.DataFrame())).reset_index(drop=True)
        if profiles.empty or feature_table.empty:
            continue
        for _, profile in profiles.iterrows():
            penalty = str(profile["penalty"])
            solution_index = int(profile["solution_index"])
            solution = result["results"][penalty]["solutions"][solution_index]
            weights = np.asarray(solution["weights"], dtype=float)
            if len(weights) != len(feature_table):
                raise ValueError("Les poids et la table des caractéristiques n'ont pas la même longueur.")
            for column_index, (weight, feature) in enumerate(zip(weights, feature_table.to_dict("records"))):
                rows.append(
                    {
                        "family": family,
                        "penalty": penalty,
                        "profile": profile["profile"],
                        "solution_index": solution_index,
                        "column_index": column_index,
                        "weight": float(weight),
                        "is_active": bool(abs(weight) > float(result.get("active_threshold", 1e-6))),
                        **feature,
                    }
                )
    return pd.DataFrame(rows)


def export_research_run(
    *,
    output_root: str | Path,
    run_mode: str,
    configuration: Mapping[str, Any],
    tables: Mapping[str, Any],
    figures: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    timestamp: datetime | None = None,
    update_latest: bool = True,
) -> dict[str, Any]:
    """Save a dated run and optionally refresh ``output/latest``.

    Dated runs are immutable: a numeric suffix is added if a directory already
    exists. ``latest`` is a convenience copy and may be replaced.
    """

    created_at = timestamp or datetime.now().astimezone()
    root = Path(output_root)
    runs_root = root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    base_run_id = f"{created_at:%Y-%m-%d_%H%M%S}_{_safe_name(run_mode)}"
    run_id = base_run_id
    suffix = 1
    while (runs_root / run_id).exists() or (runs_root / f".{run_id}.tmp").exists():
        suffix += 1
        run_id = f"{base_run_id}_{suffix}"

    run_dir = runs_root / run_id
    staging_dir = runs_root / f".{run_id}.tmp"
    table_dir = staging_dir / "tables"
    figure_dir = staging_dir / "figures"
    table_dir.mkdir(parents=True)
    figure_dir.mkdir(parents=True)

    table_manifest: list[dict[str, Any]] = []
    for name, value in tables.items():
        if value is None:
            continue
        frame = _as_frame(value)
        safe_name = _safe_name(name)
        path = table_dir / f"{safe_name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        table_manifest.append(
            {
                "name": str(name),
                "file": str(path.relative_to(staging_dir)).replace("\\", "/"),
                "rows": int(len(frame)),
                "columns": [str(column) for column in frame.columns],
            }
        )

    figure_manifest: list[dict[str, Any]] = []
    for name, figure in (figures or {}).items():
        if figure is None:
            continue
        safe_name = _safe_name(name)
        pdf_path = figure_dir / f"{safe_name}.pdf"
        png_path = figure_dir / f"{safe_name}.png"
        figure.savefig(pdf_path, bbox_inches="tight")
        figure.savefig(png_path, dpi=180, bbox_inches="tight")
        figure_manifest.append(
            {
                "name": str(name),
                "pdf": str(pdf_path.relative_to(staging_dir)).replace("\\", "/"),
                "png": str(png_path.relative_to(staging_dir)).replace("\\", "/"),
            }
        )

    manifest = {
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "run_mode": str(run_mode),
        "completed": True,
        "configuration": _json_value(configuration),
        "metadata": _json_value(metadata or {}),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "tables": table_manifest,
        "figures": figure_manifest,
    }
    (staging_dir / "configuration.json").write_text(
        json.dumps(_json_value(configuration), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (staging_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    staging_dir.rename(run_dir)
    manifest_path = run_dir / "manifest.json"

    latest_dir = root / "latest"
    if update_latest:
        latest_tmp = root / ".latest_tmp"
        if latest_tmp.exists():
            shutil.rmtree(latest_tmp)
        shutil.copytree(run_dir, latest_tmp)
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        latest_tmp.rename(latest_dir)

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "latest_dir": latest_dir if update_latest else None,
        "manifest_path": manifest_path,
        "n_tables": len(table_manifest),
        "n_figures": len(figure_manifest),
    }
