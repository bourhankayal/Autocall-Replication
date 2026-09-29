
import numpy as np
import pandas as pd  
import matplotlib.pyplot as plt

from ..products import AutocallProduct, VanillaProduct, Cash, _year_fraction
from .pathwise_payoff import vanilla_discounted_payoff_from_path
from ..monte_carlo import simulate_gbm_path
from .common import benchmark_metrics, build_naive_vanilla_basis, contractual_simulation_end_date
from .optimization import SolverConfig, solve_replication
from .portfolio_diagnostics import portfolio_weight_metrics


# ============================================================
# BENCHMARK COURBE PATHWISE : cashflows de l'autocall et du réplica le long d'une trajectoire
# ============================================================-

# ------------------------------------------------------------
# Fonction utilitaire : date réellement disponible sur le path pour une date contractuelle
# ------------------------------------------------------------

def effective_date_on_path(path: pd.Series,contractual_date: str | pd.Timestamp) -> pd.Timestamp:
    """Retourne la date réellement disponible sur le path pour une date contractuelle."""
    contractual_date = pd.Timestamp(contractual_date)
    position = path.index.searchsorted(contractual_date, side="left")
    if position >= len(path):       raise ValueError(f"La trajectoire ne couvre pas la date {contractual_date}.")
    return pd.Timestamp(path.index[position])



# ------------------------------------------------------------
# 0) Courbe cible : cashflows actualisés de l'autocall sur un path
# ------------------------------------------------------------


def autocall_value_curve_on_path(
    product: AutocallProduct, path: pd.Series,
    valuation_date: str | pd.Timestamp,
    rate: float, curve_dates=None) -> pd.Series:
    """Retourne les vrais cashflows actualisés de l'autocall sur une trajectoire sous forme de série temporelle datée.
    Chaque date contient uniquement le cashflow payé à cette date. Les dates postérieures à un autocall anticipé restent présentes avec un cashflow nul."""
    valuation_date = pd.Timestamp(valuation_date)
    path = path.sort_index().dropna()
    path = path.loc[path.index >= valuation_date]           # on ne garde que les dates postérieures à la valuation_date
    if path.empty:      raise ValueError("La trajectoire ne contient aucune date après valuation_date.")

    fixing_date = pd.Timestamp(path.index[0])

    if curve_dates is None:                    # on construit la courbe à partir des dates d'observation du produit, mais on ne garde que celles qui sont couvertes par le path
        contractual_dates = [pd.Timestamp(d) for d in product.build_observation_dates(fixing_date) if pd.Timestamp(d) <= pd.Timestamp(path.index[-1])]
        curve_dates = pd.DatetimeIndex([effective_date_on_path(path=path,contractual_date=d) for d in contractual_dates])
        curve_dates = pd.DatetimeIndex(sorted(set(curve_dates)))
    else:
        curve_dates = pd.DatetimeIndex(curve_dates)

    values = np.zeros(len(curve_dates), dtype=float)
    date_to_index = {pd.Timestamp(d): i for i, d in enumerate(curve_dates)}     # mapping des dates de la courbe vers les indices du tableau values

    # Cashflows complets du produit sur cette trajectoire
    full_res = product.compute_autocall_payoff(path,start_date=valuation_date)
    cashflows = full_res["cashflows"].copy()
    cashflows["date"] = pd.to_datetime(cashflows["date"])

    # Coupon et remboursement peuvent avoir lieu à la même date. On les additionne dans la même observation temporelle.
    for _, cashflow in cashflows.iterrows():
        cashflow_date = pd.Timestamp(cashflow["date"])
        if cashflow_date not in date_to_index:      raise ValueError(f"Le cashflow autocall du {cashflow_date} ne correspond à aucune date de la courbe.")

        i = date_to_index[cashflow_date]
        tau = _year_fraction(valuation_date, cashflow_date)

        values[i] += (float(cashflow["amount"])* np.exp(-rate * tau))           # actualisation du cashflow à la valuation_date
    return pd.Series(values,index=curve_dates,name="autocall_cashflow")




# ------------------------------------------------------------
# 1) Courbe réplique : cashflows actualisés du portefeuille de vanilles sur un path
# ------------------------------------------------------------

def vanilla_portfolio_value_curve_on_path(
    vanillas: list[VanillaProduct], weights: np.ndarray,
    path: pd.Series,valuation_date: str | pd.Timestamp,
    rate: float,curve_dates=None) -> pd.Series:
    """Retourne les vrais cashflows actualisés du portefeuille de vanilles.
    Une vanille contribue uniquement à sa propre date de maturité."""
    valuation_date = pd.Timestamp(valuation_date)
    path = path.sort_index().dropna()
    path = path.loc[path.index >= valuation_date]

    if curve_dates is None:
        curve_dates = pd.DatetimeIndex(sorted(set(effective_date_on_path(path=path,contractual_date=v.maturity_date) for v in vanillas)))    # dates de maturité effectives des vanilles sur le path triées par ordre croissant
    else:
        curve_dates = pd.DatetimeIndex(curve_dates)
    date_to_index = {pd.Timestamp(d): i for i, d in enumerate(curve_dates)}

    values = np.zeros(len(curve_dates), dtype=float)
    weights = np.asarray(weights, dtype=float).reshape(-1)
    if len(weights) != len(vanillas):           raise ValueError("Le nombre de poids doit être égal au nombre de vanilles.")

    for weight, vanilla in zip(weights, vanillas):
        payment_date = effective_date_on_path(path=path,contractual_date=vanilla.maturity_date)
        if payment_date not in date_to_index:       raise ValueError(f"La maturité {payment_date} de {vanilla.name} ne correspond à aucune date de la courbe.")

        i = date_to_index[payment_date]

        unit_pv = vanilla_discounted_payoff_from_path(vanilla=vanilla,path=path,valuation_date=valuation_date,rate=rate)
        values[i] += float(weight) * float(unit_pv)

    return pd.Series(values,index=curve_dates,name="replica_cashflow")


# ------------------------------------------------------------
# 1.1) Affichage du panier retenu sur un path
# ------------------------------------------------------------

def replication_basket_on_path(
    result,path,
    valuation_date,rate, weight_tol=1e-5): 
    """Retourne un DataFrame avec les vanilles, leurs poids et leurs contributions.
    On ne garde que les vanilles avec un poids significatif (> weight_tol)."""
    valuation_date = pd.Timestamp(valuation_date)
    path = path.sort_index().dropna()

    vanillas = result["vanillas"]
    weights = np.asarray(result["w"], dtype=float)

    unit_pv = np.array([vanilla_discounted_payoff_from_path(vanilla=v,path=path,valuation_date=valuation_date,rate=rate) for v in vanillas])
    payment_dates = [effective_date_on_path(path=path,contractual_date=v.maturity_date) for v in vanillas]

    basket = pd.DataFrame({
        "name": [v.name for v in vanillas],
        "type": [v.__class__.__name__ for v in vanillas],
        "maturite": [pd.Timestamp(v.maturity_date) for v in vanillas],
        "date_paiement": payment_dates,
        "strike": [float(v.strike) for v in vanillas],
        "quantite": weights,
        "payoff_actualise_unitaire": unit_pv,
        "weight": weights,
        "contribution": weights * unit_pv})

    basket["contribution_absolue"] = basket["contribution"].abs()
    return (basket.loc[basket["quantite"].abs() > weight_tol].sort_values("weight", ascending=False).reset_index(drop=True))


# ------------------------------------------------------------
# 2) Dataset pathwise temporel :     chaque observation = (path, date de cashflow)
#     """Construit une liste de trajectoires.
#    Pour chaque trajectoire, on stocke :
#    - le path simulé ;
#    - les cashflows actualisés de l'autocall par date ici on note y_curve ;
#    - les cashflows actualisés du réplica par date ici on note X_curve ;
#    - les dates de cashflows observées (y_curve.index)"""
# ------------------------------------------------------------

def build_timewise_curve_dataset(
    product: AutocallProduct, vanillas: list[VanillaProduct],spot0: float,
    valuation_date: str | pd.Timestamp, maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,vol: float,
    n_paths: int = 2000,seed: int = 42) -> list[dict[str, object]]:
    """Construit une liste de trajectoires.
    Pour chaque trajectoire, on stocke :
    - le path simulé ;
    - les cashflows actualisés de l'autocall par date ici on note y_curve ;
    - les cashflows actualisés du réplica par date ici on note X_curve ;
    - les dates de cashflows observées (y_curve.index)"""
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)
    simulation_end_date = contractual_simulation_end_date(
        product=product,
        contract_start_date=valuation_date,
        requested_maturity_date=maturity_date,
    )

    data = []
    common_dates = None

    for p in range(n_paths):
        seed_p = None if seed is None else seed + p

        path = simulate_gbm_path(spot0=spot0,start_date=valuation_date,end_date=simulation_end_date,rate=rate,dividend_yield=dividend_yield,vol=vol,seed=seed_p)
        y_curve = autocall_value_curve_on_path(product=product,path=path,valuation_date=valuation_date,rate=rate,curve_dates=common_dates)

        curve_dates = y_curve.index
        if common_dates is None:                            common_dates = curve_dates
        elif not common_dates.equals(curve_dates):          raise ValueError("Les dates de cashflows diffèrent entre les trajectoires.")

        X_curve = np.zeros((len(curve_dates), len(vanillas)),dtype=float)
        date_to_index = {pd.Timestamp(d): i for i, d in enumerate(curve_dates)}

        # Chaque vanille contribue uniquement à sa propre maturité, en d'autres termes, le cashflow actualisé d'une vanille ne peut apparaître que sur la date de maturité de cette vanille.
        for j, vanilla in enumerate(vanillas):
            payment_date = effective_date_on_path(path=path,contractual_date=vanilla.maturity_date)
            if payment_date not in date_to_index:           raise ValueError(f"La maturité {payment_date} de {vanilla.name} ne correspond à aucune date d'observation.")

            i = date_to_index[payment_date]
            X_curve[i, j] = vanilla_discounted_payoff_from_path(vanilla=vanilla,path=path,valuation_date=valuation_date,rate=rate)

        data.append({
            "path": path,
            "dates": curve_dates,
            "X_curve": X_curve,
            "y_curve": y_curve.to_numpy(dtype=float)})
        
    return data





# ------------------------------------------------------------
# 3) Pipeline complet : fit sur les cashflows pathwise temporels
# ------------------------------------------------------------
def run_naive_benchmark_curve(
    product: AutocallProduct, spot0: float,
    valuation_date: str | pd.Timestamp, maturity_date: str | pd.Timestamp,
    rate: float, dividend_yield: float, vol: float,
    family: str,
    n_paths: int = 2000,
    spot_min_mult: float = 0.70, spot_max_mult: float = 1.30,
    penalty: str = "l2",alpha: float = 1e-6,
    train_frac: float = 0.7,seed: int = 42,
    solver: str = "legacy") -> dict[str, object]:
    """Réplique les cashflows d'un autocall avec un panier fixe de vanilles.
    On apprend les poids sur des observations (path, date de cashflow) puis on teste ces mêmes poids sur des trajectoires jamais utilisées."""
    valuation_date = pd.Timestamp(valuation_date)
    effective_contract_start = pd.offsets.BDay().rollforward(
        valuation_date.normalize()
    )
    maturity_date = contractual_simulation_end_date(
        product=product,
        contract_start_date=effective_contract_start,
        requested_maturity_date=maturity_date,
    )
    vanilla_basis = build_naive_vanilla_basis(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,product=product,strike_step=5.0,strike_min_mult=spot_min_mult,strike_max_mult=spot_max_mult,family=family)

    # On conserve uniquement les dates auxquelles l'autocall peut payer.
    observation_dates = sorted(
        {
            pd.offsets.BDay().rollforward(pd.Timestamp(date).normalize())
            for date in product.build_observation_dates(effective_contract_start)
            if valuation_date
            < pd.offsets.BDay().rollforward(pd.Timestamp(date).normalize())
            <= maturity_date
        }
        | {maturity_date}
    )
    vanillas = [v for v in vanilla_basis if (isinstance(v, Cash) or pd.Timestamp(v.maturity_date) in observation_dates)]
    if len(vanillas) == 0:          raise ValueError("La base de réplication ne contient aucune vanille.")

    dataset = build_timewise_curve_dataset(product=product,vanillas=vanillas,spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=seed)
    split = int(train_frac * n_paths)
    split = max(1,min(split,n_paths - 1 if n_paths > 1 else 1))
    train_set = dataset[:split]
    test_set = dataset[split:]

    # Flatten train
    X_train = np.vstack([d["X_curve"] for d in train_set])          # Chaque ligne correspond à un couple (path, date de cashflow) et chaque colonne correspond à une vanille du panier.          
    y_train = np.concatenate([d["y_curve"] for d in train_set])       

    # Flatten test
    if len(test_set) > 0:
        X_test = np.vstack([d["X_curve"] for d in test_set])
        y_test = np.concatenate([d["y_curve"] for d in test_set])
    else:
        X_test = np.empty((0, len(vanillas)))
        y_test = np.empty((0,))

    ###################################################################
    # Normaliser avant d'appliquer la régression linéaire pour éviter que les colonnes avec des valeurs très grandes dominent le fit.
    ###################################################################
    column_scale = np.sqrt(np.mean(X_train**2, axis=0))   # Racine carrée de la moyenne des carrés pour chaque colonne (vanille) du panier, représentant l'échelle de la vanille sur l'ensemble d'entraînement.      
    column_scale[column_scale < 1e-12] = 1.0    # Colonnes toujours nulles.
    column_scale[0] = 1.0                       # On conserve la convention particulière du cash.

    X_train_scaled = X_train / column_scale

    optimization_result = solve_replication(
        X_train_scaled,
        y_train,
        SolverConfig(solver=solver, penalty=penalty, alpha=alpha),
    )
    scaled_weights = optimization_result.weights

    w = scaled_weights / column_scale

    pred_train = X_train @ w
    pred_test = X_test @ w

    metrics_train = benchmark_metrics(y_train,pred_train)
    metrics_test = (benchmark_metrics(y_test, pred_test) if len(X_test) > 0 else {})
    metrics_by_date = []
    if len(test_set) > 0:
        dates = dataset[0]["dates"]
        for i, d in enumerate(dates):
            y_date = np.array([path_data["y_curve"][i] for path_data in test_set])
            pred_date = np.array([path_data["X_curve"][i] @ w for path_data in test_set])
            metrics_by_date.append({"date": pd.Timestamp(d),**benchmark_metrics(y_date, pred_date)})
    metrics_by_date = pd.DataFrame(metrics_by_date)

    weights = pd.DataFrame({
        "name": [v.name for v in vanillas],
        "kind": [v.__class__.__name__ for v in vanillas],
        "maturity_date": [pd.Timestamp(v.maturity_date) for v in vanillas],
        "strike": [float(v.strike) for v in vanillas],
        "weight": w}).sort_values("weight",key=lambda s: s.abs(),ascending=False)

    return {
        "vanillas": vanillas,
        "weights": weights,
        "w": w,
        "dates": dataset[0]["dates"],
        "train_set": train_set,
        "test_set": test_set,
        "metrics_train": metrics_train,
        "metrics_test": metrics_test,
        "metrics_by_date": metrics_by_date,
        "family": family,
        "split": split,
        "optimization": optimization_result.metadata(),
        "portfolio_metrics": portfolio_weight_metrics(vanillas, w)}
    
    
    
    
    
# ------------------------------------------------------------
# 4) Plot lisible :   cashflows ponctuels et cashflows cumulés
# ------------------------------------------------------------

def plot_timewise_curve_benchmark(
    dates: pd.DatetimeIndex,
    target_curve: np.ndarray,replica_curve: np.ndarray,
    title_prefix: str = ""):
    """Affiche :
    - les vrais cashflows par date ;
    - les cashflows cumulés ;
    - l'erreur de réplication par date."""
    dates = pd.to_datetime(dates)
    target_curve = np.asarray(target_curve,dtype=float).reshape(-1)
    replica_curve = np.asarray(replica_curve,dtype=float).reshape(-1)

    if len(dates) != len(target_curve):             raise ValueError("dates et target_curve doivent avoir la même longueur.")
    if len(target_curve) != len(replica_curve):     raise ValueError("target_curve et replica_curve doivent avoir la même longueur.")

    err = replica_curve - target_curve
    x = np.arange(len(dates))
    width = 0.35

    fig, axes = plt.subplots(3,1,figsize=(14, 10),sharex=True)
    axes[0].bar(x - width / 2,target_curve,width=width,label="Cashflows autocall",alpha=0.80)
    axes[0].bar(x + width / 2,replica_curve,width=width,label="Cashflows réplique",alpha=0.80)
    axes[0].set_title(f"{title_prefix}Cashflows actualisés par date")
    axes[0].set_ylabel("Cashflow actualisé")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    axes[1].step(x,np.cumsum(target_curve),where="mid",label="Autocall cumulé",linewidth=2)
    axes[1].step(x,np.cumsum(replica_curve),where="mid",label="Réplique cumulée",linewidth=2)
    axes[1].set_ylabel("Cashflow cumulé")
    axes[1].legend()
    axes[1].grid(alpha=0.25)

    axes[2].bar(x,err,width=0.50,label="Erreur")
    axes[2].axhline(0.0,linestyle="--",linewidth=1)
    axes[2].set_ylabel("Réplique - cible")
    axes[2].set_xlabel("Date")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([d.strftime("%Y-%m-%d") for d in dates],rotation=30,ha="right")
    axes[2].legend()
    axes[2].grid(alpha=0.25)

    plt.tight_layout()
    plt.show()
