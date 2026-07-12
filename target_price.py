import pandas as pd
import math
import numpy as np
from typing import Any, Dict, Optional

from products_core import AutocallProduct, VanillaProduct, _year_fraction
from monte_carlo import price_autocall_bs_mc
from benchmark_general import fit_linear, benchmark_metrics, build_naive_vanilla_basis, build_autocall_training_grid_axes

#### “Quel est le prix actualisé de l’autocall à chaque (t,S), et est-ce qu’un portefeuille de vanilles peut reproduire cette surface de prix ?”

def price_autocall_on_tensor_bs_mc(
    product: AutocallProduct,
    dates: pd.DatetimeIndex,
    spots: np.ndarray,
    maturity_date: str | pd.Timestamp,
    rate: float,    dividend_yield: float,
    vol: float,
    n_paths: int = 10000,   seed: Optional[int] = 42) -> np.ndarray:
    """Calcule le prix d'un autocall sur une grille de points (spot, date) par simulation Monte-Carlo
    grid = DataFrame avec colonnes :
        - valuation_date : date de valorisation
        - spot : niveau du spot simulé
    Retourne un tableau numpy de forme (len(dates), len(spots)) :
        - valuation_date : date de valorisation
        - spot : niveau du spot simulé
        - autocall_price : prix estimé de l'autocall à cette date et ce spot"""
        
    maturity_date = pd.Timestamp(maturity_date)

    price_tensor = np.empty((len(dates), len(spots)), dtype=float)

    for i, d in enumerate(dates):
        for j, s in enumerate(spots):
            v = price_autocall_bs_mc(product=product,spot0=float(s),valuation_date=d,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=None if seed is None else seed + i * 1000 + j)
            price_tensor[i, j] = v["actualized_price"]

    return price_tensor     # DataFrame avec les prix simulés sur la grille (dates en lignes, spots en colonnes)


# ------------------------------------------------------------
# 2) Pricing d'un panier sur une grille (dates x spots)
# ------------------------------------------------------------
def price_vanilla_basis_on_grid(
    vanillas: list[VanillaProduct],
    dates: pd.DatetimeIndex,
    spots: np.ndarray,
    rate: float,dividend_yield: float,
    vol: float) -> np.ndarray:
    """
    Retourne une matrice A de taille:
        (len(dates) * len(spots), len(vanillas))
    """
    n_obs = len(dates) * len(spots)
    A = np.empty((n_obs, len(vanillas)), dtype=float)

    row = 0
    for d in dates:
        d = pd.Timestamp(d)
        for s in spots:
            s = float(s)
            for j, v in enumerate(vanillas):
                A[row, j] = v.price_bs(spot=s,valuation_date=d,rate=rate,dividend_yield=dividend_yield,vol=vol)
            row += 1
    return A            # A matrice des prix 

# Si tu as par exemple : 5 dates, 3 spots, alors tu as 5×3=15 observations.
# Les lignes de A sont alors dans cet ordre :
# date 1, spot 1
# date 1, spot 2
# date 1, spot 3
# date 2, spot 1
# date 2, spot 2


def run_naive_benchmark_price(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp, maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,
    vol: float,
    family: str,
    n_spots: int = 15,n_paths: int = 3000,
    spot_min_mult: float = 0.70, spot_max_mult: float = 1.30,
    penalty: str = "l2", alpha: float = 1e-8,
    train_frac: float = 0.7, seed: int = 42) -> dict[str, object]:    
    """Pipeline complet pour entraîner un benchmark naïf sur un autocall.
    target = prix simulé de l'autocall sur une grille (dates x spots)
    features = prix des vanilles sur la même grille"""
    
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)
    dates, spots = build_autocall_training_grid_axes(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,n_spots=n_spots,spot_min_mult=spot_min_mult, spot_max_mult=spot_max_mult,include_call_dates=True,product=product,)
    
    target_tensor = price_autocall_on_tensor_bs_mc(product=product, dates = dates, spots = spots, maturity_date=maturity_date, rate=rate, dividend_yield=dividend_yield, vol=vol, n_paths=n_paths, seed=seed)
    y = target_tensor.reshape(-1)           # On a besoin d'un vecteur 1D pour la régression, donc on aplati le tableau 2D (dates x spots) en un vecteur 1D.

    vanillas = build_naive_vanilla_basis(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,product=product,strike_step=5,strike_min_mult=0.70,strike_max_mult=1.30,family=family)
    A = price_vanilla_basis_on_grid(vanillas=vanillas,dates=dates,spots=spots,rate=rate,dividend_yield=dividend_yield,vol=vol,)

    n_dates = len(dates)
    split = max(1, int(train_frac * n_dates))        # On s'assure d'avoir au moins une date pour l'entraînement, sinon on ne peut pas faire de régression.
    idx_train = np.arange(split * len(spots))
    idx_test = np.arange(split * len(spots), n_dates * len(spots))

    A_train, y_train = A[idx_train], y[idx_train]
    A_test, y_test = A[idx_test], y[idx_test]

    w = fit_linear(A_train, y_train, penalty=penalty, alpha=alpha)
    pred_train = A_train @ w
    pred_test = A_test @ w

    metrics_train = benchmark_metrics(y_train, pred_train)
    metrics_test = benchmark_metrics(y_test, pred_test) if len(idx_test) > 0 else {}

    weights = pd.DataFrame({   "name": [v.name for v in vanillas],
                                "kind": [v.__class__.__name__ for v in vanillas],
                                "maturity_date": [pd.Timestamp(v.maturity_date) for v in vanillas],
                                "strike": [float(v.strike) for v in vanillas],
                                "weight": w}).sort_values("weight", key=lambda s: s.abs(), ascending=False)
    fitted_tensor = (A @ w).reshape(target_tensor.shape)

    return {
        "dates": dates,
        "spots": spots,
        "target_tensor": target_tensor,
        "fitted_tensor": fitted_tensor,
        "vanillas": vanillas,
        "weights": weights,
        "metrics_train": metrics_train,
        "metrics_test": metrics_test,
        "family": family,
        "A": A,
        "w": w}