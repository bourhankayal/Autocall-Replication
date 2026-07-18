import pandas as pd
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
import numpy as np
from typing import Any, Dict, Optional

from products_core import AutocallProduct, VanillaProduct, EuropeanCall, EuropeanPut, BinaryCall, BinaryPut, Cash, _year_fraction


def build_autocall_training_grid_axes(
    spot0: float,
    valuation_date: str | pd.Timestamp,  maturity_date: str | pd.Timestamp,
    n_spots: int = 21,  # nombre de points de spot à générer, nombre impair pour avoir le spot initial au milieu de la grille, 21 car on veut 10 points de part et d'autre du spot initial
    spot_min_mult: float = 0.6,    spot_max_mult: float = 1.4,
    include_call_dates: bool = True,
    product: Optional[AutocallProduct] = None) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Construit une grille de points (spot, date) pour entraîner un modèle de pricing d'autocall.
    Si product est fourni, on inclut les dates d'observation de l'autocall
    Sinon, on se limite à la date de valorisation et la date de maturité.

    Elle sert à construire un dataset simple :
        plusieurs spots autour de spot0
        plusieurs dates pertinentes
        une table exploitable pour du ML, de l’interpolation ou une surface de prix
    
    Retours 
    -------
    DataFrame avec colonnes :
        - valuation_date : date de valorisation
        - spot : niveau du spot simulé """
    if n_spots % 2 == 0:    raise ValueError("n_spots doit être impair pour inclure spot0 au centre de la grille.")
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    spots = np.linspace(spot_min_mult * spot0, spot_max_mult * spot0, n_spots)

    if include_call_dates and product is not None:
                dates = [d for d in product.build_observation_dates(valuation_date) if d <= maturity_date]
    else:       dates = [valuation_date, maturity_date]

    dates = pd.to_datetime(dates)
    return dates, spots

# ------------------------------------------------------------
# Construction d'une base de vanilles "naïve"
# ------------------------------------------------------------

def build_naive_vanilla_basis(spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    product: AutocallProduct | None = None,
    strike_step: float = 5.0,
    strike_min_mult: float = 0.70,strike_max_mult: float = 1.30,
    family: str = "calls") -> list[VanillaProduct]:
    """Construit un panier naïf de vanilles.
    family:
        - "calls"
        - "calls_puts"
        - "full"  -> calls + puts + binaires"""
    valid_families = {"calls", "calls_puts", "full"}
    if family not in valid_families:
        raise ValueError(f"family='{family}' inconnu. Choisir parmi {sorted(valid_families)}.")

    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    # Maturités : dates de call si on a l'autocall, puis maturité finale
    maturities: list[pd.Timestamp] = [maturity_date]
    if product is not None:
        obs_dates = [pd.Timestamp(d) for d in product.build_observation_dates(valuation_date)]
        obs_dates = [d for d in obs_dates if d <= maturity_date]
        maturities = sorted(set(maturities + [valuation_date + pd.DateOffset(months=m) for m in range(1, 13)]))
        maturities = [d for d in maturities if d <= maturity_date]
    
    strike_min = strike_step * np.floor(strike_min_mult * spot0 / strike_step)
    strike_max = strike_step * np.ceil(strike_max_mult * spot0 / strike_step)
    strikes = np.arange(strike_min, strike_max + 0.5 * strike_step, strike_step, dtype=float)

    # The cash leg is the product's funding base, not one extra feature per
    # option maturity. Matching notionals also makes its weight interpretable.
    cash_notional = float(product.notional) if product is not None else float(spot0)
    basis: list[VanillaProduct] = [
        Cash(
            name=f"CASH_{maturity_date.strftime('%Y%m%d')}",
            strike=0.0,
            maturity_date=maturity_date,
            notional=cash_notional,
        )
    ]
    for T in maturities:
        tag = T.strftime("%Y%m%d")
        for k in strikes:
            k = float(k)
            basis.append(EuropeanCall(name=f"C_{tag}_{k:.2f}", strike=k, maturity_date=T, notional=1.0))

            if family in ("calls_puts", "full"):
                basis.append(EuropeanPut(name=f"P_{tag}_{k:.2f}", strike=k, maturity_date=T, notional=1.0))
            if family == "full":
                basis.append(BinaryCall(name=f"BC_{tag}_{k:.2f}",strike=k,maturity_date=T,notional=1.0))
                basis.append(BinaryPut(name=f"BP_{tag}_{k:.2f}",strike=k,maturity_date=T,notional=1.0))
    return basis






def _smooth_abs(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Approximation lisse de |x|"""
    return np.sqrt(x * x + eps)

def _smooth_abs_grad(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """d/dx sqrt(x^2 + eps)"""
    return x / np.sqrt(x * x + eps)

def _smooth_l12(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Approximation lisse de |x|^(1/2)"""
    # Approximation lisse de |x|^(1/2)
    return np.power(x * x + eps, 0.25)

def _smooth_l12_grad(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """d/dx (x^2 + eps)^(1/4)"""
    return 0.5 * x * np.power(x * x + eps, -0.75)


def fit_linear(A: np.ndarray,b: np.ndarray,penalty: str = "l2",alpha: float = 1e-8,l1_ratio: float = 0.5,huber_delta: float = 1.0,eps: float = 1e-12,max_iter: int = 5000,tol: float = 1e-10) -> np.ndarray:
    """Régression linéaire avec choix du type de pénalisation / robustification.
    Paramètres
    ----------
    penalty :
        - "none"        : moindres carrés
        - "l2"          : ridge
        - "l1"          : lasso lisse (approximation)
        - "elastic_net" : mélange L1/L2, penalisation = L1_ratio * L1 + (1-L1_ratio) * L2
        - "huber"       : perte Huber sur les résidus, avec L2 sur les poids
        - "l1_2"        : pénalité |w|^(1/2) (approximation lisse)

    Convention
    ----------
    Si la première colonne de A correspond à CASH / intercept, elle n'est pas pénalisée.
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    n_obs, n_features = A.shape

    if A.ndim != 2:                 raise ValueError("A doit être une matrice 2D.")
    if A.shape[0] != b.shape[0]:    raise ValueError("A et b doivent avoir le même nombre de lignes.")

    # Cas simple : moindres carrés, solution analytique sans pénalisation
    if penalty == "none":
        w, *_ = np.linalg.lstsq(A, b, rcond=None)
        return w

    # Cas fermé : ridge
    if penalty == "l2":         # ridge : approximation lisse de L2
        ATA = A.T @ A
        ATb = A.T @ b
        reg = alpha * np.eye(n_features)                    # On ajoute alpha sur la diagonale pour régulariser, plus alpha est grand, plus on pénalise les poids
        reg[0, 0] = 0.0  # CASH / intercept non pénalisé
        return np.linalg.solve(ATA + reg, ATb)

    # Point de départ : moindres carrés
    w0, *_ = np.linalg.lstsq(A, b, rcond=None)
    
    def objective_and_grad(w: np.ndarray):
        r = A @ w - b
        # Terme d'ajustement
        loss = 0.5 * np.mean(r * r)
        grad = (A.T @ r) / n_obs

        # On ne pénalise pas CASH / intercept
        w_reg = w.copy()
        w_reg[0] = 0.0

        if penalty == "l1":             # lasso lisse (approximation)
            pen = alpha * np.sum(_smooth_abs(w_reg, eps=eps))
            grad_pen = alpha * _smooth_abs_grad(w_reg, eps=eps)
            grad_pen[0] = 0.0

        elif penalty == "elastic_net":  # mélange L1/L2    
            l1_part = np.sum(_smooth_abs(w_reg, eps=eps))
            l2_part = 0.5 * np.sum(w_reg * w_reg)
            pen = alpha * (l1_ratio * l1_part + (1.0 - l1_ratio) * l2_part)

            grad_pen = alpha * (l1_ratio * _smooth_abs_grad(w_reg, eps=eps) + (1.0 - l1_ratio) * w_reg)
            grad_pen[0] = 0.0

        elif penalty == "huber":
            abs_r = np.abs(r)
            quad = abs_r <= huber_delta

            huber_loss = np.where(quad,0.5 * r * r,huber_delta * (abs_r - 0.5 * huber_delta))
            loss = np.mean(huber_loss)

            huber_grad_r = np.where(quad, r, huber_delta * np.sign(r))
            grad = (A.T @ huber_grad_r) / n_obs

            # On ajoute un petit ridge sur les poids hors CASH pour stabiliser
            pen = 0.5 * alpha * np.sum(w_reg * w_reg)
            grad_pen = alpha * w_reg
            grad_pen[0] = 0.0

        elif penalty == "l1_2":
            pen = alpha * np.sum(_smooth_l12(w_reg, eps=eps))
            grad_pen = alpha * _smooth_l12_grad(w_reg, eps=eps)
            grad_pen[0] = 0.0

        else:       raise ValueError(f"penalty='{penalty}' inconnu. ""Choisir parmi: 'none', 'l2', 'l1', 'elastic_net', 'huber', 'l1_2'.")

        obj = loss + pen
        grad_total = grad + grad_pen
        return obj, grad_total

    res = minimize(fun=lambda x: objective_and_grad(x)[0],x0=w0,jac=lambda x: objective_and_grad(x)[1],method="L-BFGS-B",options={"maxiter": max_iter, "ftol": tol})
    return res.x


def fit_lstsq(A: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Moindres carrés classiques."""
    return fit_linear(A, b, penalty="none")














def benchmark_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Calcule des métriques d'erreur entre la vérité terrain et la prédiction.
    Retour
    dict[str, float]
        - mae : erreur absolue moyenne
        - rmse : racine de l'erreur quadratique moyenne
        - max_abs_error : erreur absolue maximale
        - mean_error : erreur moyenne signée"""
    y_true = np.asarray(y_true, dtype=float).reshape(-1)        # On s'assure que y_true est un vecteur 1D
    y_pred = np.asarray(y_pred, dtype=float).reshape(-1)
    err = y_pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "max_abs_error": float(np.max(np.abs(err))),
        "mean_error": float(np.mean(err))}
    
    
def plot_benchmark_surface(dates: pd.DatetimeIndex,spots: np.ndarray,target_tensor: np.ndarray,fitted_tensor: np.ndarray, title_prefix=""):
    """Compare la cible et la réplique sur une grille discrète (dates x spots).
    Retourne un graphique avec deux sous-graphes : la surface cible et la surface répliquée par le benchmark naïf."""
    fig, axes = plt.subplots(1, 3, figsize=(21, 5), sharey=True)
    all_vals = np.r_[target_tensor.ravel(), fitted_tensor.ravel()]
    vmin, vcenter, vmax = np.quantile(all_vals, [0.05, 0.50, 0.95])
    norm_main = TwoSlopeNorm(vmin=vmin, vcenter=vcenter, vmax=vmax)

    err_tensor = fitted_tensor - target_tensor
    err_lim = np.quantile(np.abs(err_tensor), 0.95)
    norm_err = TwoSlopeNorm(vmin=-err_lim, vcenter=0.0, vmax=err_lim)

    cmap_main = LinearSegmentedColormap.from_list("white_to_black", ["white", "black"])

    im0 = axes[0].imshow(target_tensor, aspect="auto", origin="lower", extent=[spots[0], spots[-1], 0, len(dates) - 1], cmap=cmap_main, norm=norm_main)
    axes[0].set_title(f"{title_prefix}Cible autocall")
    axes[0].set_xlabel("Spot")
    axes[0].set_ylabel("Index de date")
    plt.colorbar(im0, ax=axes[0])

    im1 = axes[1].imshow(fitted_tensor, aspect="auto", origin="lower", extent=[spots[0], spots[-1], 0, len(dates) - 1], cmap=cmap_main, norm=norm_main)
    axes[1].set_title(f"{title_prefix}Réplique naive")
    axes[1].set_xlabel("Spot")
    plt.colorbar(im1, ax=axes[1])
    
    im2 = axes[2].imshow(err_tensor, aspect="auto", origin="lower", extent=[spots[0], spots[-1], 0, len(dates) - 1], cmap="RdBu_r", norm=norm_err)      # RdBu_r est une colormap rouge-bleu inversée, donc les erreurs négatives sont en bleu et les erreurs positives en rouge
    axes[2].set_title(f"{title_prefix}Erreur (réplique - cible)")
    axes[2].set_xlabel("Spot")
    plt.colorbar(im2, ax=axes[2])
    
    plt.tight_layout()
    plt.show()
