import pandas as pd
import math
import numpy as np
from typing import Any, Dict, Optional

from .products import AutocallProduct, _year_fraction


def _validated_business_grid(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DatetimeIndex:
    """Construit la grille lundi-vendredi suivant la convention contractuelle."""
    start_date = pd.Timestamp(start_date).normalize()
    end_date = pd.Timestamp(end_date).normalize()
    if end_date < start_date:
        raise ValueError("end_date doit être postérieure ou égale à start_date.")

    effective_start_date = pd.offsets.BDay().rollforward(start_date)
    effective_end_date = pd.offsets.BDay().rollforward(end_date)
    return pd.bdate_range(effective_start_date, effective_end_date)


def _validate_gbm_parameters(
    spot0: float,
    rate: float,
    dividend_yield: float,
    vol: float,
) -> None:
    if not np.isfinite(spot0) or spot0 <= 0:
        raise ValueError("spot0 doit être un nombre strictement positif.")
    if not np.isfinite(vol) or vol < 0:
        raise ValueError("vol doit être un nombre positif ou nul.")
    if not np.isfinite(rate) or not np.isfinite(dividend_yield):
        raise ValueError("rate et dividend_yield doivent être des nombres finis.")


def simulate_gbm_paths(
    spot0: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int,
    seed: Optional[int] = None,
    antithetic: bool = True,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Simule simultanément plusieurs trajectoires GBM sous mesure risque-neutre.

    Retourne la grille de dates et une matrice de forme ``(n_paths, n_dates)``.
    Lorsque ``antithetic`` est vrai, chaque vecteur de chocs est associé à son
    opposé afin de réduire la variance sans modifier la loi marginale.
    """
    if isinstance(n_paths, bool) or not isinstance(n_paths, (int, np.integer)):
        raise ValueError("n_paths doit être un entier strictement positif.")
    if n_paths < 1:
        raise ValueError("n_paths doit être un entier strictement positif.")
    _validate_gbm_parameters(spot0, rate, dividend_yield, vol)
    dates = _validated_business_grid(start_date, end_date)

    paths = np.empty((n_paths, len(dates)), dtype=float)
    paths[:, 0] = float(spot0)
    if len(dates) == 1:
        return dates, paths

    day_gaps = np.diff(dates.values).astype("timedelta64[D]").astype(float)
    dt = day_gaps / 365.0
    rng = np.random.default_rng(seed)

    if antithetic and n_paths > 1:
        n_base = (n_paths + 1) // 2
        base_shocks = rng.normal(size=(n_base, len(dates) - 1))
        shocks = np.concatenate(
            [base_shocks, -base_shocks[: n_paths - n_base]],
            axis=0,
        )
    else:
        shocks = rng.normal(size=(n_paths, len(dates) - 1))

    drift = (rate - dividend_yield - 0.5 * vol * vol) * dt
    diffusion = vol * np.sqrt(dt)[None, :] * shocks
    log_returns = drift[None, :] + diffusion
    paths[:, 1:] = float(spot0) * np.exp(np.cumsum(log_returns, axis=1))
    return dates, paths


def simulate_gbm_path(
    spot0: float,
    start_date: pd.Timestamp, end_date: pd.Timestamp,
    rate: float, dividend_yield: float,
    vol: float, seed: Optional[int] = None) -> pd.Series:
    """Simule une trajectoire Black-Scholes sur une grille de cotation.

    Le temps écoulé entre deux points est mesuré en jours calendaires sur une
    base ACT/365. Le rendement du lundi couvre donc aussi le week-end, sans
    créer de faux points de cotation le samedi et le dimanche.

    Si la date initiale ou finale n'est pas ouvrée, elle est reportée au premier
    jour ouvré suivant selon le calendrier pédagogique lundi-vendredi. Les jours
    fériés ne sont pas modélisés.
    """
    dates, paths = simulate_gbm_paths(
        spot0=spot0,
        start_date=start_date,
        end_date=end_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=1,
        seed=seed,
        antithetic=False,
    )
    return pd.Series(paths[0], index=dates)



def autocall_discounted_payoff_from_path(
    product: AutocallProduct,
    path: pd.Series,
    valuation_date: str | pd.Timestamp,
    rate: float) -> float:
    """Calcule la valeur actualisée de l'autocall sur une trajectoire donnée.
    Principe :
    - on calcule les cashflows bruts avec compute_autocall_payoff
    - on actualise chaque flux à la date de valorisation"""
    valuation_date = pd.Timestamp(valuation_date)
    res = product.compute_autocall_payoff(path, start_date=valuation_date)

    pv = 0.0
    for _, row in res["cashflows"].iterrows():
        t = _year_fraction(valuation_date, pd.Timestamp(row["date"]))
        pv += float(row["amount"]) * math.exp(-rate * t)

    return pv



def price_autocall_bs_mc(
    product: AutocallProduct,    spot0: float,
    valuation_date: str | pd.Timestamp,  maturity_date: str | pd.Timestamp,
    rate: float,   dividend_yield: float,
    vol: float,
    n_paths: int = 20000, seed: Optional[int] = 42,
    contract_start_date: Optional[str | pd.Timestamp] = None,
    initial_spot: Optional[float] = None,
    barrier_hit_before: bool = False,
    antithetic: bool = True,
    barrier_monitoring_step: int = 1,
    control_variate: bool = False) -> Dict[str, Any]:
    """Prix d'un autocall par simulation Monte-Carlo 
    avec un modèle Black-Scholes constant pour le sous-jacent
    bs_mc = Black-Scholes Monte Carlo
    
    Retourne :
      - price : valeur actuelle estimée
      - std_error : erreur standard Monte Carlo
      - path_values : liste optionnelle des cashflows bruts simulés"""
    
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    if isinstance(n_paths, bool) or not isinstance(n_paths, (int, np.integer)) or n_paths < 2:
        raise ValueError("n_paths doit être un entier supérieur ou égal à 2.")
    if antithetic and n_paths < 4:
        raise ValueError(
            "n_paths doit former au moins deux paires, donc être supérieur ou égal "
            "à 4 lorsque antithetic=True."
        )
    if antithetic and n_paths % 2 != 0:
        raise ValueError("n_paths doit être pair lorsque antithetic=True.")
    if (
        isinstance(barrier_monitoring_step, bool)
        or not isinstance(barrier_monitoring_step, (int, np.integer))
        or barrier_monitoring_step < 1
    ):
        raise ValueError("barrier_monitoring_step doit être un entier supérieur ou égal à 1.")
    if maturity_date < valuation_date:
        raise ValueError("maturity_date doit être postérieure ou égale à valuation_date.")
    if contract_start_date is not None and initial_spot is None:
        raise ValueError("initial_spot est requis pour valoriser un contrat existant.")

    effective_contract_start = pd.offsets.BDay().rollforward(
        pd.Timestamp(
            contract_start_date if contract_start_date is not None else valuation_date
        ).normalize()
    )
    contractual_maturity = product.build_observation_dates(effective_contract_start)[-1]
    effective_contractual_maturity = pd.offsets.BDay().rollforward(contractual_maturity)
    simulation_end_date = max(maturity_date, effective_contractual_maturity)

    dates, paths = simulate_gbm_paths(
        spot0=spot0,
        start_date=valuation_date,
        end_date=simulation_end_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
        antithetic=antithetic,
    )

    effective_observation_dates = pd.DatetimeIndex(
        [
            pd.offsets.BDay().rollforward(pd.Timestamp(date).normalize())
            for date in product.build_observation_dates(effective_contract_start)
        ]
    )
    remaining_observation_dates = effective_observation_dates[
        effective_observation_dates >= valuation_date.normalize()
    ]
    if len(remaining_observation_dates) == 0:
        raise ValueError("Aucune observation contractuelle ne reste après valuation_date.")

    observation_indices = dates.searchsorted(remaining_observation_dates, side="left")
    if np.any(observation_indices >= len(dates)):
        raise ValueError("La grille simulée ne couvre pas toutes les observations contractuelles.")

    contract_spot0 = float(initial_spot) if contract_start_date is not None else float(spot0)
    coupon_amount = float(product.coupon_rate * product.notional)
    coupon_level = float(product.coupon_barrier * contract_spot0)
    autocall_level = float(product.autocall_strike * contract_spot0)
    barrier_level = float(product.down_barrier * contract_spot0)

    path_values = np.zeros(n_paths, dtype=float)
    alive = np.ones(n_paths, dtype=bool)

    for observation_date, observation_index in zip(
        remaining_observation_dates,
        observation_indices,
    ):
        observation_spots = paths[:, observation_index]
        discount_factor = math.exp(
            -rate * _year_fraction(valuation_date, observation_date)
        )

        coupon_paid = alive & (observation_spots >= coupon_level)
        path_values[coupon_paid] += coupon_amount * discount_factor

        recalled = alive & (observation_spots >= autocall_level)
        path_values[recalled] += float(product.notional) * discount_factor
        alive[recalled] = False

    final_index = int(observation_indices[-1])
    final_date = remaining_observation_dates[-1]
    final_spots = paths[:, final_index]
    barrier_indices = np.arange(
        0,
        final_index + 1,
        int(barrier_monitoring_step),
        dtype=int,
    )
    if barrier_indices[-1] != final_index:
        barrier_indices = np.append(barrier_indices, final_index)
    barrier_hit = np.full(n_paths, bool(barrier_hit_before), dtype=bool)
    barrier_hit |= np.any(paths[:, barrier_indices] <= barrier_level, axis=1)

    final_redemption = np.where(
        barrier_hit,
        float(product.notional) * final_spots / contract_spot0,
        float(product.notional),
    )
    final_discount_factor = math.exp(
        -rate * _year_fraction(valuation_date, final_date)
    )
    path_values[alive] += final_redemption[alive] * final_discount_factor

    if antithetic:
        half = n_paths // 2
        estimator_samples = 0.5 * (path_values[:half] + path_values[half:])
    else:
        estimator_samples = path_values

    raw_price = float(np.mean(estimator_samples))
    raw_std_error = float(
        np.std(estimator_samples, ddof=1) / math.sqrt(len(estimator_samples))
    )
    control_beta = 0.0
    adjusted_samples = estimator_samples

    if control_variate:
        terminal_discounted_spot = final_spots * final_discount_factor
        if antithetic:
            control_samples = 0.5 * (
                terminal_discounted_spot[:half] + terminal_discounted_spot[half:]
            )
        else:
            control_samples = terminal_discounted_spot

        simulation_tau = _year_fraction(dates[0], final_date)
        discount_tau = _year_fraction(valuation_date, final_date)
        expected_control = float(spot0) * math.exp(
            (rate - dividend_yield) * simulation_tau - rate * discount_tau
        )
        control_variance = float(np.var(control_samples, ddof=1))
        if control_variance > 0.0:
            covariance = float(
                np.cov(estimator_samples, control_samples, ddof=1)[0, 1]
            )
            control_beta = covariance / control_variance
            adjusted_samples = estimator_samples - control_beta * (
                control_samples - expected_control
            )

    actualized_price = float(np.mean(adjusted_samples))
    std_error = float(
        np.std(adjusted_samples, ddof=1) / math.sqrt(len(adjusted_samples))
    )
    variance_reduction_ratio = (
        float((raw_std_error / std_error) ** 2)
        if std_error > 0.0
        else (float("inf") if raw_std_error > 0.0 else 1.0)
    )
    normal_95 = 1.959963984540054
    ci95_low = actualized_price - normal_95 * std_error
    ci95_high = actualized_price + normal_95 * std_error
    return {
        "actualized_price": actualized_price,
        "std_error": std_error,
        "raw_price": raw_price,
        "raw_std_error": raw_std_error,
        "ci95_low": float(ci95_low),
        "ci95_high": float(ci95_high),
        "confidence_interval_95": (float(ci95_low), float(ci95_high)),
        "path_values": path_values,
        "estimator_samples": adjusted_samples,
        "n_paths": n_paths,
        "n_independent_samples": len(estimator_samples),
        "antithetic": bool(antithetic),
        "barrier_monitoring_step": int(barrier_monitoring_step),
        "control_variate": bool(control_variate),
        "control_beta": float(control_beta),
        "variance_reduction_ratio": variance_reduction_ratio,
    }


def run_autocall_mc_convergence(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    path_counts: tuple[int, ...] = (500, 1000, 5000, 10000),
    seed: Optional[int] = 42,
    antithetic: bool = True,
    **contract_state: Any,
) -> pd.DataFrame:
    """Produit une table reproductible de convergence en nombre de trajectoires."""
    if not path_counts:
        raise ValueError("path_counts ne doit pas être vide.")
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 2 for n in path_counts):
        raise ValueError("Chaque élément de path_counts doit être un entier supérieur ou égal à 2.")
    if antithetic and any(n < 4 or n % 2 != 0 for n in path_counts):
        raise ValueError(
            "Tous les path_counts doivent être pairs et supérieurs ou égaux à 4 "
            "avec antithetic=True."
        )

    rows = []
    for n_paths in path_counts:
        result = price_autocall_bs_mc(
            product=product,
            spot0=spot0,
            valuation_date=valuation_date,
            maturity_date=maturity_date,
            rate=rate,
            dividend_yield=dividend_yield,
            vol=vol,
            n_paths=n_paths,
            seed=seed,
            antithetic=antithetic,
            **contract_state,
        )
        rows.append(
            {
                "n_paths": n_paths,
                "actualized_price": result["actualized_price"],
                "std_error": result["std_error"],
                "ci95_low": result["ci95_low"],
                "ci95_high": result["ci95_high"],
                "ci95_width": result["ci95_high"] - result["ci95_low"],
            }
        )
    return pd.DataFrame(rows)


def run_barrier_monitoring_convergence(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int = 20000,
    monitoring_steps: tuple[int, ...] = (21, 10, 5, 1),
    seed: Optional[int] = 42,
    antithetic: bool = True,
    control_variate: bool = False,
    **contract_state: Any,
) -> pd.DataFrame:
    """Compare plusieurs fréquences à la surveillance quotidienne contractuelle.

    ``monitoring_step=1`` observe la barrière à chaque cotation simulée et sert
    de référence. Les autres valeurs représentent un sous-échantillonnage en
    nombre de jours de cotation, avec nombres aléatoires communs.
    """
    if not monitoring_steps or 1 not in monitoring_steps:
        raise ValueError("monitoring_steps doit contenir la référence quotidienne 1.")
    if any(isinstance(step, bool) or not isinstance(step, int) or step < 1 for step in monitoring_steps):
        raise ValueError("Chaque monitoring_step doit être un entier supérieur ou égal à 1.")

    rows = []
    for step in monitoring_steps:
        result = price_autocall_bs_mc(
            product=product,
            spot0=spot0,
            valuation_date=valuation_date,
            maturity_date=maturity_date,
            rate=rate,
            dividend_yield=dividend_yield,
            vol=vol,
            n_paths=n_paths,
            seed=seed,
            antithetic=antithetic,
            barrier_monitoring_step=step,
            control_variate=control_variate,
            **contract_state,
        )
        rows.append(
            {
                "monitoring_step": step,
                "actualized_price": result["actualized_price"],
                "std_error": result["std_error"],
                "ci95_low": result["ci95_low"],
                "ci95_high": result["ci95_high"],
            }
        )

    table = pd.DataFrame(rows)
    daily_price = float(
        table.loc[table["monitoring_step"] == 1, "actualized_price"].iloc[0]
    )
    table["bias_vs_daily"] = table["actualized_price"] - daily_price
    table["abs_bias_vs_daily"] = table["bias_vs_daily"].abs()
    return table
