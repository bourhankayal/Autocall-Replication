"""Reproduit les principaux résultats du rapport de validation Monte-Carlo."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autocall_replication.monte_carlo import (  # noqa: E402
    price_autocall_bs_mc,
    run_autocall_mc_convergence,
    run_barrier_monitoring_convergence,
)
from autocall_replication.products import AutocallProduct  # noqa: E402


REFERENCE = {
    "product": AutocallProduct(),
    "spot0": 100.0,
    "valuation_date": "2026-06-20",
    "maturity_date": "2027-06-22",
    "rate": 0.03,
    "dividend_yield": 0.01,
    "vol": 0.20,
    "seed": 42,
}


def main() -> int:
    raw = price_autocall_bs_mc(
        **REFERENCE,
        n_paths=20_000,
        antithetic=True,
        control_variate=False,
    )
    controlled = price_autocall_bs_mc(
        **REFERENCE,
        n_paths=20_000,
        antithetic=True,
        control_variate=True,
    )

    print("\nRESULTAT DE REFERENCE")
    print(f"Prix               : {raw['actualized_price']:.6f}")
    print(f"Erreur standard     : {raw['std_error']:.6f}")
    print(
        "Intervalle 95 %     : "
        f"[{raw['ci95_low']:.6f} ; {raw['ci95_high']:.6f}]"
    )

    print("\nVARIABLE DE CONTROLE")
    print(f"Prix ajuste         : {controlled['actualized_price']:.6f}")
    print(f"Erreur standard     : {controlled['std_error']:.6f}")
    print(
        "Reduction variance  : "
        f"{controlled['variance_reduction_ratio']:.6f}"
    )

    print("\nCONVERGENCE EN NOMBRE DE TRAJECTOIRES")
    path_table = run_autocall_mc_convergence(
        **REFERENCE,
        path_counts=(500, 1_000, 5_000, 10_000),
        antithetic=True,
    )
    print(path_table.to_string(index=False, float_format=lambda value: f"{value:.6f}"))

    print("\nFREQUENCE DE SURVEILLANCE DE LA BARRIERE")
    barrier_table = run_barrier_monitoring_convergence(
        **REFERENCE,
        n_paths=20_000,
        monitoring_steps=(21, 10, 5, 1),
        antithetic=True,
    )
    print(barrier_table.to_string(index=False, float_format=lambda value: f"{value:.6f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
