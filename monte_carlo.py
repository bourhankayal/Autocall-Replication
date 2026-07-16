import pandas as pd
import math
import numpy as np
from typing import Any, Dict, Optional

from products_core import AutocallProduct, _year_fraction


def simulate_gbm_path(
    spot0: float,
    start_date: pd.Timestamp, end_date: pd.Timestamp,
    rate: float, dividend_yield: float,
    vol: float, seed: Optional[int] = None) -> pd.Series:
    """Simule une trajectoire quotidienne sous Black-Scholes d'un actif sous-jacent avec rendement continu q et volatilité sigma
    Retourne une Series pandas indexée par jours ouvrés"""
    
    # On utilise un calendrier journalier pour rester robuste quand une date de constatation tombe un week-end
    dates = pd.bdate_range(pd.Timestamp(start_date).normalize(), pd.Timestamp(end_date).normalize(), freq="D")
    if len(dates) < 2:    return pd.Series([spot0], index=dates)

    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0

    # formule BS, dynamique du log spot : dlnS/S = (r - q - 0.5 * sigma^2) dt + sigma dW
    shocks = rng.normal(size=len(dates) - 1)        # tirages aléatoires pour les incréments de Brownien
    diffusion = vol * math.sqrt(dt) * shocks
    
    # drift déterministe du log-price ln(St) : (r - q - 0.5 * sigma^2) * dt 
    drift = (rate - dividend_yield - 0.5 * vol * vol) * dt     
    log_returns = drift + diffusion

    prices = np.empty(len(dates), dtype=float)
    prices[0] = spot0
    prices[1:] = spot0 * np.exp(np.cumsum(log_returns))
    return pd.Series(prices, index=dates)



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
    n_paths: int = 20000, seed: Optional[int] = 42) -> Dict[str, Any]:
    """Prix d'un autocall par simulation Monte-Carlo 
    avec un modèle Black-Scholes constant pour le sous-jacent
    bs_mc = Black-Scholes Monte Carlo
    
    Retourne :
      - price : valeur actuelle estimée
      - std_error : erreur standard Monte Carlo
      - path_values : liste optionnelle des cashflows bruts simulés"""
    
    valuation_date = pd.Timestamp(valuation_date)
    maturity_date = pd.Timestamp(maturity_date)

    cashflows = np.empty(n_paths, dtype=float)

    for p in range(n_paths):
        # On simule une trajectoire de prix sous Black-Scholes
        path = simulate_gbm_path(spot0=spot0,start_date=valuation_date,end_date=maturity_date,rate=rate,dividend_yield=dividend_yield,vol=vol,seed=None if seed is None else seed + p,)

        # on calcule le payoff de l'autocall sur cette trajectoire simulée
        res = product.compute_autocall_payoff(path, start_date=valuation_date) 
        cf = res["cashflows"]       
        # DataFrame des flux de cashflow simulés sur cette trajectoire ressemble à :
        #         date                 type            amount       spot
        # 0 2025-03-31 00:00:00       coupon             2          101
        # 1 2025-03-31 00:00:00  autocall_redemption    100         101      
        
        pv = 0.0
        for _, row in cf.iterrows():        # on actualise chaque flux de cashflow à la date de valorisation
            t = _year_fraction(valuation_date, pd.Timestamp(row["date"]))
            pv += float(row["amount"]) * math.exp(-rate * t)

        cashflows[p] = pv     # on stocke la valeur actualisée du payoff simulé pour cette trajectoire

    actualized_price = float(np.mean(cashflows))                                   # prix moyen des trajectoires simulées, donc estimateur Monte Carlo du prix
    std_error = float(np.std(cashflows, ddof=1) / math.sqrt(n_paths))   # erreur standard de l'estimateur Monte Carlo
    return {"actualized_price": actualized_price,"std_error": std_error,"path_values": cashflows,"n_paths": n_paths}