####  “Sur une trajectoire simulée donnée, est-ce qu’un portefeuille fixe de vanilles reproduit bien le payoff actualisé scénario par scénario de l’autocall ?”

import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from ..products import AutocallProduct, VanillaProduct, Cash, _year_fraction
from ..monte_carlo import simulate_gbm_path
from .common import benchmark_metrics, build_naive_vanilla_basis, contractual_simulation_end_date
from .optimization import SolverConfig, solve_replication
from .portfolio_diagnostics import portfolio_weight_metrics
from .regularization_path import solve_penalty_comparison, solve_regularization_path


def vanilla_discounted_payoff_from_path(
    vanilla: VanillaProduct,
    path: pd.Series,
    valuation_date: str | pd.Timestamp,
    rate: float) -> float:
    """Calcule la valeur actualisée d'une vanille sur une trajectoire donnée.
    Ici on prend le spot à maturité de la vanille sur la trajectoire simulée, puis on actualise le payoff terminal."""
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(vanilla.maturity_date)
    tau = _year_fraction(valuation_date, maturity_date)

    if valuation_date > maturity_date:
        return 0.0

    position = path.index.searchsorted(maturity_date, side="left")
    if position >= len(path):
        raise ValueError(
            f"La trajectoire ne couvre pas la maturité {maturity_date}."
        )

    s_T = float(path.iloc[position])

    if valuation_date == maturity_date:
        return float(vanilla.payoff(s_T))

    tau = _year_fraction(valuation_date, maturity_date)

    if isinstance(vanilla, Cash):
        return float(vanilla.notional) * math.exp(-rate * tau)

    payoff = float(vanilla.payoff(s_T))
    return payoff * math.exp(-rate * tau)




def build_pathwise_payoff_dataset(
    product: AutocallProduct,vanillas: list[VanillaProduct],
    spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,vol: float,
    n_paths: int = 3000,
    seed: int = 42,
    return_metadata: bool = False,
) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Construit le dataset de régression pathwise.
    Sortie :
    - X : matrice (n_paths, n_vanillas) avec les payoffs actualisés des vanilles calculés sur les mêmes trajectoires.
    - y : vecteur (n_paths,) avec le payoff actualisé de l'autocall """
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)
    simulation_end_date = contractual_simulation_end_date(
        product=product,
        contract_start_date=valuation_date,
        requested_maturity_date=maturity_date,
    )

    X = np.empty((n_paths, len(vanillas)), dtype=float)
    y = np.empty(n_paths, dtype=float)
    metadata_rows: list[dict[str, object]] = []

    for p in range(n_paths):
        seed_p = None if seed is None else seed + p

        # Une seule trajectoire sert à la fois pour la cible et pour les features.
        path = simulate_gbm_path(spot0=spot0,start_date=valuation_date,end_date=simulation_end_date,rate=rate,dividend_yield=dividend_yield,vol=vol,seed=seed_p)
        # Cible : payoff actualisé de l'autocall. Le résultat contractuel est
        # conservé lorsque l'analyse de risque demande les états rappel/barrière.
        contract_result = product.compute_autocall_payoff(
            path,
            start_date=valuation_date,
        )
        present_value = 0.0
        for _, cashflow in contract_result["cashflows"].iterrows():
            tau = _year_fraction(valuation_date, pd.Timestamp(cashflow["date"]))
            present_value += float(cashflow["amount"]) * math.exp(-rate * tau)
        y[p] = present_value
        if return_metadata:
            metadata_rows.append(
                {
                    "path_index": p,
                    "called": bool(contract_result["called"]),
                    "call_date": contract_result["call_date"],
                    "barrier_hit": bool(contract_result["barrier_hit"]),
                    "barrier_hit_date": contract_result["barrier_hit_date"],
                }
            )

        # Features : payoffs actualisés des vanilles sur la même trajectoire
        for j, v in enumerate(vanillas):
            X[p, j] = vanilla_discounted_payoff_from_path(vanilla=v,path=path,valuation_date=valuation_date,rate=rate)

    if return_metadata:
        return X, y, pd.DataFrame(metadata_rows)
    return X, y

def run_naive_benchmark_payoff_pathwise(
    product: AutocallProduct,spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,vol: float,
    family: str,
    penalty: str = "l2", alpha: float = 1e-8,
    n_paths: int = 3000,
    spot_min_mult: float = 0.70,spot_max_mult: float = 1.30,
    train_frac: float = 0.7,seed: int = 42,
    solver: str = "legacy") -> dict[str, object]:
    """
    Benchmark pathwise :
    - cible = payoff actualisé de l'autocall sur chaque trajectoire
    - features = payoffs actualisés des vanilles sur les mêmes trajectoires

    C'est la version la plus fidèle si tu veux tester la qualité de réplication.
    """
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    # Base de vanilles
    vanillas = build_naive_vanilla_basis(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,product=product,strike_step=5.0,strike_min_mult=spot_min_mult,strike_max_mult=spot_max_mult,family=family)

    # Dataset pathwise : on calcule le payoff actualisé de l'autocall et des vanilles sur les mêmes trajectoires simulées.
    X, y = build_pathwise_payoff_dataset(product=product,vanillas=vanillas,spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=seed)

    # Split train/test robuste
    split = int(train_frac * n_paths)
    split = max(1, min(split, n_paths - 1 if n_paths > 1 else 1))

    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    # Fit ridge
    optimization_result = solve_replication(
        X_train,
        y_train,
        SolverConfig(solver=solver, penalty=penalty, alpha=alpha),
    )
    w = optimization_result.weights

    pred_train = X_train @ w
    pred_test = X_test @ w if len(X_test) > 0 else np.array([])

    metrics_train = benchmark_metrics(y_train, pred_train)
    metrics_test = benchmark_metrics(y_test, pred_test) if len(X_test) > 0 else {}

    weights = pd.DataFrame(
        {
            "name": [v.name for v in vanillas],
            "kind": [v.__class__.__name__ for v in vanillas],
            "maturity_date": [pd.Timestamp(v.maturity_date) for v in vanillas],
            "strike": [float(v.strike) for v in vanillas],
            "weight": w,
        }).sort_values("weight", key=lambda s: s.abs(), ascending=False)

    replica = X @ w
    error = replica - y

    return {
        "vanillas": vanillas,
        "X": X,
        "y": y,
        "replica": replica,
        "error": error,
        "weights": weights,
        "metrics_train": metrics_train,
        "metrics_test": metrics_test,
        "family": family,
        "w": w,
        "split": split,
        "optimization": optimization_result.metadata(),
        "portfolio_metrics": portfolio_weight_metrics(vanillas, w),
    }


def run_pathwise_regularization_path(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    family: str,
    penalty: str = "l1",
    l1_ratio: float = 0.5,
    n_paths: int = 3000,
    spot_min_mult: float = 0.70,
    spot_max_mult: float = 1.30,
    n_alphas: int = 25,
    min_alpha_ratio: float = 1e-3,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    active_threshold: float = 1e-6,
    max_iter: int = 5000,
    tolerance: float = 1e-6,
    seed: int = 42,
) -> dict[str, object]:
    """Construit le chemin L1/Elastic Net du benchmark payoff pathwise.

    Les trajectoires sont simulées une seule fois puis partagées entre tous les
    alphas. Le dernier bloc de 20 % est réservé sans être évalué.
    """
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)
    vanillas = build_naive_vanilla_basis(
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        product=product,
        strike_step=5.0,
        strike_min_mult=spot_min_mult,
        strike_max_mult=spot_max_mult,
        family=family,
    )
    X, y = build_pathwise_payoff_dataset(
        product=product,
        vanillas=vanillas,
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
    )
    result = solve_regularization_path(
        A=X,
        b=y,
        vanillas=vanillas,
        penalty=penalty,
        l1_ratio=l1_ratio,
        n_alphas=n_alphas,
        min_alpha_ratio=min_alpha_ratio,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
        active_threshold=active_threshold,
        max_iter=max_iter,
        tolerance=tolerance,
    )
    result.update(
        {
            "vanillas": vanillas,
            "family": family,
            "penalty": penalty,
            "l1_ratio": l1_ratio,
            "n_paths": n_paths,
            "seed": seed,
        }
    )
    return result


def run_pathwise_penalty_comparison(
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    family: str,
    penalties: tuple[str, ...] = ("l1", "l2", "elastic_net"),
    elastic_net_l1_ratio: float = 0.5,
    n_paths: int = 3000,
    spot_min_mult: float = 0.70,
    spot_max_mult: float = 1.30,
    n_alphas: int = 25,
    min_alpha_ratio: float = 1e-3,
    ridge_min_alpha_ratio: float = 1e-4,
    ridge_max_alpha_ratio: float = 1e2,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    active_threshold: float = 1e-6,
    min_candidate_options: int = 2,
    max_candidate_options: int = 100,
    max_iter: int = 5000,
    tolerance: float = 1e-6,
    seed: int = 42,
) -> dict[str, object]:
    """Compare les pénalités demandées sur les mêmes trajectoires pathwise.

    Le dataset est simulé une seule fois. Le ratio Elastic Net est fixé et le
    bloc de test final reste réservé sans prédiction ni métrique.
    """
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)
    vanillas = build_naive_vanilla_basis(
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        product=product,
        strike_step=5.0,
        strike_min_mult=spot_min_mult,
        strike_max_mult=spot_max_mult,
        family=family,
    )
    X, y = build_pathwise_payoff_dataset(
        product=product,
        vanillas=vanillas,
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
    )
    result = solve_penalty_comparison(
        A=X,
        b=y,
        vanillas=vanillas,
        penalties=penalties,
        l1_ratio=elastic_net_l1_ratio,
        n_alphas=n_alphas,
        min_alpha_ratio=min_alpha_ratio,
        ridge_min_alpha_ratio=ridge_min_alpha_ratio,
        ridge_max_alpha_ratio=ridge_max_alpha_ratio,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
        active_threshold=active_threshold,
        min_candidate_options=min_candidate_options,
        max_candidate_options=max_candidate_options,
        max_iter=max_iter,
        tolerance=tolerance,
    )
    result.update(
        {
            "vanillas": vanillas,
            "family": family,
            "n_paths": n_paths,
            "seed": seed,
        }
    )
    for policy in result["candidate_policies"]:
        policy["family"] = family
    if not result["profiles"].empty:
        result["profiles"].insert(0, "family", family)
    result["profile_policies"] = result["profiles"].to_dict(orient="records")
    return result
    
    
def plot_pathwise_benchmark(
    y: np.ndarray,
    replica: np.ndarray,
    title_prefix: str = "",
    n_bins: int = 20):
    """
    Affichage lisible du benchmark pathwise.

    Gauche :
        comparaison binned (par quantiles du payoff autocall)
        avec moyennes et barres d'erreur.

    Droite :
        distribution des erreurs (réplique - cible).
    """
    y = np.asarray(y, dtype=float).reshape(-1)
    replica = np.asarray(replica, dtype=float).reshape(-1)
    err = replica - y

    # Sécurités
    mask = np.isfinite(y) & np.isfinite(replica)
    y = y[mask]
    replica = replica[mask]
    err = err[mask]

    if len(y) == 0:
        raise ValueError("Les vecteurs y et replica sont vides ou non valides.")

    # Métriques utiles pour l'affichage
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    bias = float(np.mean(err))
    corr = float(np.corrcoef(y, replica)[0, 1]) if len(y) > 1 and np.std(y) > 0 and np.std(replica) > 0 else np.nan

    # ============================================================
    # Binning par quantiles sur la cible
    # ============================================================
    df = pd.DataFrame({"y": y, "replica": replica, "err": err})

    # qcut peut fusionner des bords identiques ; duplicates="drop" rend ça robuste
    df["bin"] = pd.qcut(df["y"], q=n_bins, duplicates="drop")

    grouped = (
        df.groupby("bin", observed=True)
        .agg(
            y_mean=("y", "mean"),
            y_std=("y", "std"),
            r_mean=("replica", "mean"),
            r_std=("replica", "std"),
            count=("y", "size"),
        )
        .reset_index(drop=True)
    )

    # Remplissage des NaN de std si un bin n'a qu'un point
    grouped["y_std"] = grouped["y_std"].fillna(0.0)
    grouped["r_std"] = grouped["r_std"].fillna(0.0)

    # ============================================================
    # Figure
    # ============================================================
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # ------------------------------------------------------------
    # 1) Comparaison binned cible vs réplique
    # ------------------------------------------------------------
    x = grouped["y_mean"].to_numpy()
    y_plot = grouped["y_mean"].to_numpy()
    r_plot = grouped["r_mean"].to_numpy()

    axes[0].errorbar(x,y_plot,yerr=grouped["y_std"].to_numpy(),fmt="o-",capsize=4,label="Cible autocall (moyenne par bin)",linewidth=2)
    axes[0].errorbar(x,r_plot,yerr=grouped["r_std"].to_numpy(),fmt="o-",capsize=4,label="Réplique (moyenne par bin)",linewidth=2)

    lo = float(min(y.min(), replica.min()))
    hi = float(max(y.max(), replica.max()))
    axes[0].plot([lo, hi], [lo, hi], linestyle="--", linewidth=1.5, label="Parfait alignement")

    axes[0].set_title(f"{title_prefix}Cible vs réplique\n(par quantiles du payoff autocall)")
    axes[0].set_xlabel("Payoff actualisé autocall")
    axes[0].set_ylabel("Payoff actualisé réplique")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    # Petit bloc de métriques
    text = (
        f"N = {len(y)}\n"
        f"MAE  = {mae:.4f}\n"
        f"RMSE = {rmse:.4f}\n"
        f"Bias = {bias:.4f}\n"
        f"Corr = {corr:.4f}" if np.isfinite(corr) else
        f"N = {len(y)}\nMAE  = {mae:.4f}\nRMSE = {rmse:.4f}\nBias = {bias:.4f}\nCorr = n/a")
    
    axes[0].text(
        0.02, 0.98, text,
        transform=axes[0].transAxes,
        va="top", ha="left",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))

    # ------------------------------------------------------------
    # 2) Distribution de l'erreur
    # ------------------------------------------------------------
    err_lim = np.quantile(np.abs(err), 0.98)
    err_lim = float(err_lim) if err_lim > 0 else float(np.max(np.abs(err)) + 1e-12)

    axes[1].hist(err, bins=25, alpha=0.85, edgecolor="black")
    axes[1].axvline(0.0, linestyle="--", linewidth=1.5, label="0")
    axes[1].axvline(bias, linestyle="-", linewidth=1.5, label=f"moyenne = {bias:.2f}")
    axes[1].axvline(np.median(err), linestyle=":", linewidth=1.5, label=f"médiane = {np.median(err):.2f}")

    axes[1].set_xlim(-err_lim, err_lim)
    axes[1].set_title(f"{title_prefix}Distribution de l'erreur")
    axes[1].set_xlabel("Réplique - cible")
    axes[1].set_ylabel("Fréquence")
    axes[1].legend()
    axes[1].grid(alpha=0.25)

    plt.tight_layout()
    plt.show()
