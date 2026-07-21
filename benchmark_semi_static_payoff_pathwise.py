
import numpy as np
import pandas as pd  
import matplotlib.pyplot as plt

from products_core import AutocallProduct, VanillaProduct, Cash, _year_fraction
from benchmark_payoff import vanilla_discounted_payoff_from_path
from monte_carlo import simulate_gbm_path
from benchmark_general import fit_linear, benchmark_metrics, build_naive_vanilla_basis
from benchmark_static_payoff_pathwise  import build_timewise_curve_dataset

# ============================================================
# BENCHMARK CONDITIONNEL SEMI-STATIQUE : un panier par date et par état observable du produit
# ============================================================

# ------------------------------------------------------------
# 0) Construction de la base conditionnelle :  une jambe cash et des vanilles à chaque date d'observation
# ------------------------------------------------------------
def build_conditional_vanilla_basis(
    product: AutocallProduct,spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    family: str,
    spot_min_mult: float = 0.70,spot_max_mult: float = 1.30) -> list[VanillaProduct]:
    """Construit une base de vanilles organisée par date d'observation.
    Chaque date contient :
    - une jambe cash ;
    - les calls ;
    - éventuellement les puts et les binaires."""
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    vanilla_basis = build_naive_vanilla_basis(spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,product=product,strike_step=5.0,strike_min_mult=spot_min_mult,strike_max_mult=spot_max_mult,family=family)
    observation_dates = sorted(set([pd.Timestamp(d) for d in product.build_observation_dates(valuation_date) if valuation_date < pd.Timestamp(d) <= maturity_date] + [maturity_date]))
    vanillas = []

    for observation_date in observation_dates:
        # Une jambe cash par date.
        # Le panier n'est détenu que si l'autocall est encore vivant.
        cash = Cash(name=f"CASH_{observation_date.strftime('%Y%m%d')}",strike=0.0,maturity_date=observation_date,notional=float(product.notional))
        vanillas.append(cash)
        date_vanillas = [v for v in vanilla_basis if (not isinstance(v, Cash) and pd.Timestamp(v.maturity_date) == observation_date)]
        vanillas.extend(date_vanillas)

    return vanillas


# ------------------------------------------------------------
# 1) États observables du produit le long d'un path
# ------------------------------------------------------------

def autocall_state_curve_on_path(
    product: AutocallProduct,path: pd.Series,
    valuation_date: str | pd.Timestamp,curve_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Retourne les états observables du produit à chaque date :
    - alive_before : le produit est vivant juste avant l'observation ;
    - barrier_hit  : la barrière basse a déjà été touchée jusqu'à cette date."""
    valuation_date = pd.Timestamp(valuation_date)
    curve_dates = pd.DatetimeIndex(curve_dates)
    path = path.sort_index().dropna()
    path = path.loc[path.index >= valuation_date]

    full_res = product.compute_autocall_payoff(path,start_date=valuation_date)
    call_date = full_res["call_date"]
    if call_date is not None:           call_date = pd.Timestamp(call_date)

    spot_initial = float(full_res["spot_initial"])
    barrier_level = float(product.down_barrier) * spot_initial
    alive_before = np.zeros(len(curve_dates),dtype=bool)
    barrier_hit = np.zeros(len(curve_dates),dtype=bool)

    for i, d in enumerate(curve_dates):
        d = pd.Timestamp(d)
        alive_before[i] = (call_date is None or call_date >= d)     # À la date de rappel, le produit est encore vivant juste avant l'observation et doit produire son cashflow.
        path_until_date = path.loc[path.index <= d]
        barrier_hit[i] = bool((path_until_date <= barrier_level).any())

    return pd.DataFrame({
        "date": curve_dates,
        "alive_before": alive_before,
        "barrier_hit": barrier_hit})
    
    

# ------------------------------------------------------------
# 2) Dataset conditionnel :   on enrichit le dataset actuel avec les états du produit
# ------------------------------------------------------------
def build_conditional_curve_dataset(
    product: AutocallProduct,vanillas: list[VanillaProduct],spot0: float,
    valuation_date: str | pd.Timestamp,maturity_date: str | pd.Timestamp,
    rate: float,dividend_yield: float,vol: float,
    n_paths: int = 2000,seed: int = 42) -> list[dict[str, object]]:
    """Construit le dataset pathwise puis ajoute :
    - alive_before ;
    - barrier_hit."""
    dataset = build_timewise_curve_dataset(product=product,vanillas=vanillas,spot0=spot0,valuation_date=valuation_date,maturity_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,n_paths=n_paths,seed=seed)

    for path_data in dataset:
        state_curve = autocall_state_curve_on_path(product=product,path=path_data["path"],valuation_date=valuation_date,curve_dates=path_data["dates"])
        path_data["alive_before"] = (state_curve["alive_before"].to_numpy(dtype=bool))
        path_data["barrier_hit"] = (state_curve["barrier_hit"].to_numpy(dtype=bool))

    return dataset

