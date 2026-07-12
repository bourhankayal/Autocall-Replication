import numpy as np
import pandas as pd

from products_core import AutocallProduct, VanillaProduct, _year_fraction
from monte_carlo import simulate_gbm_path
from benchmark_general import fit_linear, benchmark_metrics, build_naive_vanilla_basis, build_autocall_training_grid_axes

#### “est-ce que mon portefeuille reproduit la surface de prix de l’autocall ?”
#### “Est-ce qu’un portefeuille de vanilles reproduit bien l’espérance du payoff brut de l’autocall sur une grille (t,S) ?”
####  C’est donc un benchmark plutôt “payoff moyen / surface moyenne”.

# ------------------------------------------------------------
# 0) Helper : moyenne MC du payoff brut d'un autocall
# ------------------------------------------------------------
def mean_undiscounted_payoff_mc(
    product: AutocallProduct,spot0: float,
    valuation_date: str | pd.Timestamp, maturity_date: str | pd.Timestamp,
    rate: float, dividend_yield: float, vol: float,
    n_paths: int = 300,seed: int = 42) -> dict[str, float]:
    """Retourne la moyenne Monte-Carlo du payoff brut NON actualisé de l'autocall."""
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    payoffs = np.empty(n_paths, dtype=float)
    for p in range(n_paths):
        path = simulate_gbm_path(spot0=spot0, start_date=valuation_date,end_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,seed=None if seed is None else seed + p)
        res = product.compute_autocall_payoff(path, start_date=valuation_date)
        payoffs[p] = float(res["undiscounted_payoff"])

    return {"mean_undiscounted_payoff": float(np.mean(payoffs)),"std_error": float(np.std(payoffs, ddof=1) / np.sqrt(n_paths))}


# ------------------------------------------------------------
# 1) Cible : espérance du payoff brut de l'autocall sur une grille
# ------------------------------------------------------------
def autocall_meanpayoff_on_grid_mc(
    product: AutocallProduct, spots: np.ndarray,
    dates: pd.DatetimeIndex, maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,
    vol: float,n_paths: int = 300,seed: int = 42) -> np.ndarray:
    """Retourne une matrice (len(dates), len(spots)) avec la moyenne MC du payoff brut de l'autocall pour chaque point de la grille."""
    maturity_date = pd.Timestamp(maturity_date)
    target = np.empty((len(dates), len(spots)), dtype=float)

    for i, d in enumerate(dates):
        d = pd.Timestamp(d)
        for j, s in enumerate(spots):
            out = mean_undiscounted_payoff_mc(product=product,spot0=float(s),valuation_date=d,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=seed + 1000 * i + j,)
            target[i, j] = out["mean_undiscounted_payoff"]
    return target

# ------------------------------------------------------------
# 2) Réplique : espérance de payoff brut du portefeuille de vanilles
# ------------------------------------------------------------

def vanilla_basis_expected_payoff_on_grid(
    vanillas: list[VanillaProduct],
    dates: pd.DatetimeIndex,
    spots: np.ndarray,
    rate: float,dividend_yield: float,vol: float,) -> np.ndarray:
    """ Retourne une matrice A de taille (len(dates) * len(spots), len(vanillas)) contenant, pour chaque point de grille, l'espérance du payoff brut de chaque vanille."""
    n_obs = len(dates) * len(spots)
    A = np.empty((n_obs, len(vanillas)), dtype=float)

    row = 0
    for d in dates:
        d = pd.Timestamp(d)
        for s in spots:
            s = float(s)
            for j, v in enumerate(vanillas):
                tau = v.time_to_maturity(d)

                if tau <= 0:
                    A[row, j] = v.payoff(s)
                else:
                    # price_bs = valeur actualisée ; on remonte à l'espérance du payoff brut, E[payoff] = price_bs * exp(r * tau)
                    price = v.price_bs(spot=s,valuation_date=d,rate=rate,dividend_yield=dividend_yield,vol=vol)
                    A[row, j] = price * np.exp(rate * tau)
            row += 1
    return A

# ------------------------------------------------------------
# 3) Pipeline complet : fit sur payoff brut
# ------------------------------------------------------------
def run_naive_benchmark_payoff(
    product: AutocallProduct,spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float, vol: float,
    family: str,
    penalty: str = "l2", alpha: float = 1e-8,
    n_spots: int = 15,n_paths: int = 3000,
    spot_min_mult: float = 0.70,spot_max_mult: float = 1.30,
    l2: float = 1e-8,train_frac: float = 0.7,seed: int = 42) -> dict[str, object]:
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    dates, spots = build_autocall_training_grid_axes(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,n_spots=n_spots,spot_min_mult=spot_min_mult,spot_max_mult=spot_max_mult,include_call_dates=True,product=product)

    target_tensor = autocall_meanpayoff_on_grid_mc(product=product,dates=dates,spots=spots,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=seed)
    y = target_tensor.reshape(-1)

    vanillas = build_naive_vanilla_basis(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,product=product,strike_step=5.0,strike_min_mult=0.70,strike_max_mult=1.30,family=family)
    A = vanilla_basis_expected_payoff_on_grid(vanillas=vanillas,dates=dates,spots=spots,rate=rate,dividend_yield=dividend_yield,vol=vol)

    n_dates = len(dates)
    split = max(1, int(train_frac * n_dates))

    idx_train = np.arange(split * len(spots))
    idx_test = np.arange(split * len(spots), n_dates * len(spots))

    A_train, y_train = A[idx_train], y[idx_train]
    A_test, y_test = A[idx_test], y[idx_test]

    w = fit_linear(A_train, y_train, penalty=penalty, alpha=l2)

    pred_train = A_train @ w
    pred_test = A_test @ w

    metrics_train = benchmark_metrics(y_train, pred_train)
    metrics_test = benchmark_metrics(y_test, pred_test) if len(idx_test) > 0 else {}

    weights = pd.DataFrame(
        {
            "name": [v.name for v in vanillas],
            "kind": [v.__class__.__name__ for v in vanillas],
            "maturity_date": [pd.Timestamp(v.maturity_date) for v in vanillas],
            "strike": [float(v.strike) for v in vanillas],
            "weight": w,
        }
    ).sort_values("weight", key=lambda s: s.abs(), ascending=False)

    fitted_tensor = (A @ w).reshape(target_tensor.shape)

    return {"dates": dates,"spots": spots,"target_tensor": target_tensor,"fitted_tensor": fitted_tensor,
        "vanillas": vanillas,
        "weights": weights,"metrics_train": metrics_train,
        "metrics_test": metrics_test,"family": family,
        "A": A,"w": w}
