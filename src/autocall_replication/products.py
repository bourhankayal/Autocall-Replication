import math
import pandas as pd
from abc import ABC, abstractmethod

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _prepare_price_series(prices: pd.Series) -> pd.Series:
    """Valide et normalise une trajectoire selon le calendrier contractuel."""
    if not isinstance(prices, pd.Series):
        raise ValueError("prices doit être une Series pandas.")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("prices doit être une Series pandas indexée par des dates.")
    if not prices.index.is_monotonic_increasing:
        raise ValueError("Les dates de prices doivent être ordonnées par ordre croissant.")
    if prices.index.has_duplicates:
        raise ValueError("Les dates de prices ne doivent pas contenir de doublons.")
    if prices.isna().any():
        raise ValueError("prices ne doit pas contenir de valeur manquante.")

    try:
        values = prices.to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Tous les prix doivent être numériques.") from exc
    if not all(math.isfinite(value) and value > 0 for value in values):
        raise ValueError("Tous les prix doivent être finis et strictement positifs.")

    path = prices.astype(float)
    path = path.loc[path.index.dayofweek < 5]
    if path.empty:
        raise ValueError("La trajectoire ne contient aucune cotation du lundi au vendredi.")
    return path


@dataclass
class AutocallProduct:
    """Autocall simple, discret, mono-sous-jacent.

    Hypothèses :
    - maturité de 1 an
    - observations trimestrielles
    - autocall si S_t >= autocall_strike * S0
    - coupon fixe versé à chaque date d'observation tant que le produit n'est pas appelé
    - barrière down observée par approximation quotidienne
    - payoff terminal simple si le produit n'a jamais été appelé"""

    # ============================================================
    # 1) PARAMÈTRES PRODUIT
    # ============================================================
    notional: float = 100.0            # Nominal du produit : c'est le montant investi 
    autocall_strike: float = 1.00      # 100% du spot initial, trigger d'autocall
    coupon_barrier: float = 0.80       # 80% du spot initial
    coupon_rate: float = 0.02          # 2% du nominal à chaque date d'observation
    down_barrier: float = 0.70         # 70% du spot initial
    observation_months: List[int] = field(default_factory=lambda: [3, 6, 9, 12])

    # ============================================================
    # 2) GÉNÉRATION DES DATES D’OBSERVATION
    # ============================================================
    def build_observation_dates(self, start_date: str | pd.Timestamp) -> List[pd.Timestamp]:
        """Construit les dates d'observation à partir de la date de départ"""
        start = pd.Timestamp(start_date)
        return [start + pd.DateOffset(months=m) for m in self.observation_months]

    # ============================================================
    # 3) CALCUL DU PAYOFF SUR UNE TRAJECTOIRE
    # ============================================================
    def compute_autocall_payoff(self, prices: pd.Series,start_date: Optional[str | pd.Timestamp] = None) -> Dict[str, Any]:
        """Calcule le payoff d'un autocall sur une trajectoire de prix quotidienne.

        Paramètres
        ----------
        prices : pd.Series
            Série de prix quotidiens indexée par dates. Ex : cours de clôture de SPY.
        start_date : str | pd.Timestamp, optional
            Date de départ de l'autocall.
            Si None, on prend la première date disponible dans la série.

        Retour
        ------
        dict avec :
            - called : bool
            - call_date : date du rappel si appelé
            - barrier_hit : bool
            - barrier_hit_date : première date de franchissement de la barrière
            - spot_initial : S0
            - undiscounted_payoff : somme brute des cashflows
            - cashflows : DataFrame détaillant les flux"""
            
        # --------------------------------------------------------
        # 3.1) Contrôles d'entrée
        # --------------------------------------------------------
        prices = _prepare_price_series(prices)
        fixing_date = pd.Timestamp(start_date) if start_date is not None else prices.index[0]

        path = prices.loc[prices.index >= fixing_date].copy()
        if path.empty: raise ValueError("Aucune donnée de prix disponible à partir de la date de fixing.")
        fixing_date = path.index[0]     # Date de fixing réelle utilisée pour le calcul (première date disponible >= start_date)
        # Spot initial observé au début du produit
        s0 = float(path.iloc[0])

        # Dates contractuelles d'observation
        observation_dates = self.build_observation_dates(fixing_date)

        # Flux de cashflow construits au fil de la trajectoire
        cashflows = []
        # Etat du produit
        called = False
        call_date = None
        barrier_hit = False
        barrier_hit_date = None

        # Pour la barrière, on veut limiter l'horizon au moment où le produit s'arrête réellement
        effective_path_end = path.index.max()

        # --------------------------------------------------------
        # 3.2) Boucle sur les dates de constatation
        # --------------------------------------------------------
        coupon_amount = self.coupon_rate * self.notional

        for obs_date in observation_dates:
            # obersvation_date contient des informations de la forme 2024-03-31 00:00:00
            eligible = path.loc[path.index >= obs_date]
            if eligible.empty: continue

            # On prend la première date disponible à partir de la date contractuelle.
            obs_dt = eligible.index[0]
            s_obs = float(eligible.iloc[0])

            # On enregistre le coupon versé à cette date, même si le produit est appelé
            # Coupon Athena : payé seulement si la barrière coupon est franchie
            if s_obs >= self.coupon_barrier * s0:
                cashflows.append({"date": obs_dt,"type": "coupon","amount": coupon_amount,"spot": s_obs})

            # On vérifie si le produit est appelé à cette date
            if s_obs >= self.autocall_strike * s0:
                called = True
                call_date = obs_dt
                cashflows.append({"date": obs_dt,"type": "autocall_redemption","amount": self.notional,"spot": s_obs})
                effective_path_end = obs_dt
                break

        # --------------------------------------------------------
        # 3.3) Si le produit n’a pas été appelé, déterminer le fixing final
        # --------------------------------------------------------
        if not called:
            final_obs_date = observation_dates[-1]
            eligible = path.loc[path.index >= final_obs_date]
            if eligible.empty:
                raise ValueError(
                    "La trajectoire ne couvre pas la date de maturité "
                    f"{final_obs_date.date()} ni un jour de règlement ultérieur."
                )

            # Même convention que pour les observations intermédiaires :
            # première date disponible à partir de la date contractuelle.
            maturity_date = eligible.index[0]
            s_T = float(eligible.iloc[0])
            effective_path_end = maturity_date

        # --------------------------------------------------------
        # 3.4) Surveiller la barrière jusqu'au dernier cashflow inclus
        # --------------------------------------------------------
        relevant_path = path.loc[path.index <= effective_path_end]
        barrier_level = self.down_barrier * s0
        barrier_mask = relevant_path <= barrier_level
        barrier_hit = bool(barrier_mask.any())
        barrier_hit_date = barrier_mask[barrier_mask].index.min() if barrier_hit else None

        if not called:
            if barrier_hit: final_redemption = self.notional * (s_T / s0)
            else:           final_redemption = self.notional
            cashflows.append({"date": maturity_date,"type": "final_redemption","amount": final_redemption,"spot": s_T})

        # --------------------------------------------------------
        # 3.5) Assemblage final du résultat
        # --------------------------------------------------------
        cashflows_df = pd.DataFrame(cashflows, columns=["date", "type", "amount", "spot"])
        undiscounted_payoff = float(cashflows_df["amount"].sum()) if not cashflows_df.empty else 0.0
        return {
            "called": called,
            "call_date": call_date,
            "barrier_hit": barrier_hit,
            "barrier_hit_date": barrier_hit_date,
            "spot_initial": s0,
            "undiscounted_payoff": undiscounted_payoff,
            "cashflows": cashflows_df}

    def compute_remaining_payoff(
        self,
        prices: pd.Series,
        contract_start_date: str | pd.Timestamp,
        spot_initial: float,
        valuation_date: Optional[str | pd.Timestamp] = None,
        barrier_hit_before: bool = False,
    ) -> Dict[str, Any]:
        """Calcule uniquement les flux restant à payer d'un contrat existant.

        Le produit est supposé encore vivant à ``valuation_date``. Les dates
        d'observation et les barrières restent rattachées au fixing original,
        contrairement à :meth:`compute_autocall_payoff` qui initialise un
        nouveau contrat au début de la trajectoire.
        """
        if not math.isfinite(float(spot_initial)) or float(spot_initial) <= 0:
            raise ValueError("spot_initial doit être strictement positif.")

        path = _prepare_price_series(prices)

        contract_start_date = pd.offsets.BDay().rollforward(
            pd.Timestamp(contract_start_date).normalize()
        )
        valuation_date = (
            pd.Timestamp(valuation_date)
            if valuation_date is not None
            else pd.Timestamp(path.index[0])
        )
        path = path.loc[path.index >= valuation_date]
        if path.empty:
            raise ValueError("Aucune donnée de prix disponible à partir de valuation_date.")

        observation_dates = self.build_observation_dates(contract_start_date)
        final_observation_date = observation_dates[-1]
        final_effective_date = pd.offsets.BDay().rollforward(final_observation_date)
        if valuation_date > final_effective_date:
            raise ValueError("Le contrat est déjà arrivé à maturité à valuation_date.")

        s0 = float(spot_initial)
        coupon_amount = self.coupon_rate * self.notional
        cashflows = []
        called = False
        call_date = None
        effective_path_end = path.index.max()

        for obs_date in observation_dates:
            if obs_date < valuation_date:
                continue

            eligible = path.loc[path.index >= obs_date]
            if eligible.empty:
                raise ValueError(
                    "La trajectoire ne couvre pas la date d'observation "
                    f"{obs_date.date()} ni un jour de règlement ultérieur."
                )

            obs_dt = eligible.index[0]
            s_obs = float(eligible.iloc[0])

            if s_obs >= self.coupon_barrier * s0:
                cashflows.append(
                    {"date": obs_dt, "type": "coupon", "amount": coupon_amount, "spot": s_obs}
                )

            if s_obs >= self.autocall_strike * s0:
                called = True
                call_date = obs_dt
                cashflows.append(
                    {
                        "date": obs_dt,
                        "type": "autocall_redemption",
                        "amount": self.notional,
                        "spot": s_obs,
                    }
                )
                effective_path_end = obs_dt
                break

        if not called:
            eligible = path.loc[path.index >= final_observation_date]
            if eligible.empty:
                raise ValueError(
                    "La trajectoire ne couvre pas la date de maturité "
                    f"{final_observation_date.date()} ni un jour de règlement ultérieur."
                )
            maturity_date = eligible.index[0]
            s_T = float(eligible.iloc[0])
            effective_path_end = maturity_date

        # La barrière ne doit jamais être observée après le dernier cashflow du
        # produit (rappel anticipé ou remboursement final).
        relevant_path = path.loc[path.index <= effective_path_end]
        barrier_mask = relevant_path <= self.down_barrier * s0
        barrier_hit_on_remaining_path = bool(barrier_mask.any())
        barrier_hit = bool(barrier_hit_before or barrier_hit_on_remaining_path)
        barrier_hit_date = (
            barrier_mask[barrier_mask].index.min()
            if barrier_hit_on_remaining_path
            else None
        )

        if not called:
            final_redemption = self.notional * (s_T / s0) if barrier_hit else self.notional
            cashflows.append(
                {
                    "date": maturity_date,
                    "type": "final_redemption",
                    "amount": final_redemption,
                    "spot": s_T,
                }
            )

        cashflows_df = pd.DataFrame(cashflows, columns=["date", "type", "amount", "spot"])
        undiscounted_payoff = (
            float(cashflows_df["amount"].sum()) if not cashflows_df.empty else 0.0
        )
        return {
            "called": called,
            "call_date": call_date,
            "barrier_hit": barrier_hit,
            "barrier_hit_date": barrier_hit_date,
            "spot_initial": s0,
            "undiscounted_payoff": undiscounted_payoff,
            "cashflows": cashflows_df,
        }
        
# ============================================================
# CLASSE MÈRE
# ============================================================
@dataclass
class VanillaProduct(ABC):
    """Classe mère pour les vanilles utilisées dans le panier de réplication.
    Convention :
    - strike en niveau absolu
    - maturity_date en date absolue
    - notional utilisé pour mettre l'échelle du payoff"""
    
    name: str
    strike: float
    maturity_date: pd.Timestamp
    notional: float = 1.0

    # Quotes de marché optionnelles
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    implied_vol: Optional[float] = None

    # --------------------------------------------------------
    # Interface commune
    # --------------------------------------------------------
    @abstractmethod
    def payoff(self, spot_T: float) -> float:
        """Payoff terminal à maturité."""
        raise NotImplementedError

    @abstractmethod
    def price_bs(self,spot: float,valuation_date: pd.Timestamp,rate: float,dividend_yield: float,vol: float) -> float:
        """Prix Black-Scholes."""
        raise NotImplementedError

    # --------------------------------------------------------
    # Utilitaires
    # --------------------------------------------------------
    def time_to_maturity(self, valuation_date: pd.Timestamp) -> float:
        """Renvoie le temps restant jusqu'à maturité en années fractionnaires"""
        return _year_fraction(pd.Timestamp(valuation_date), pd.Timestamp(self.maturity_date))

    def to_row(self) -> Dict[str, Any]:
        """Format pratique pour construire un DataFrame."""
        return {
            "name": self.name,
            "strike": self.strike,
            "maturity_date": pd.Timestamp(self.maturity_date),
            "notional": self.notional,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "implied_vol": self.implied_vol,
            "kind": self.__class__.__name__}

# ============================================================
# CALL/PUT EUROPÉENS
# ============================================================
@dataclass
class EuropeanCall(VanillaProduct):
    def payoff(self, spot_T: float) -> float:
        return self.notional * max(spot_T - self.strike, 0.0)

    def price_bs(self, spot: float, valuation_date: pd.Timestamp, rate: float, dividend_yield: float, vol: float) -> float:
        """Prix Black-Scholes.
        avec C = S0 * exp(-q*T) * N(d1) - K * exp(-r*T) * N(d2)"""
        t = self.time_to_maturity(valuation_date)
        if t <= 0:  return self.payoff(spot)

        d1, d2 = bs_d1_d2(spot, self.strike, t, rate, dividend_yield, vol)
        price = spot * math.exp(-dividend_yield * t) * norm_cdf(d1) - self.strike * math.exp(-rate * t) * norm_cdf(d2)
        return self.notional * price            
    # on multiplie par le nominal pour obtenir le prix total du produit, sans quoi le prix serait celui d'une seule option


@dataclass
class EuropeanPut(VanillaProduct):
    def payoff(self, spot_T: float) -> float:
        return self.notional * max(self.strike - spot_T, 0.0)

    def price_bs(self, spot: float, valuation_date: pd.Timestamp, rate: float, dividend_yield: float, vol: float) -> float:
        """Prix Black-Scholes.
        avec P = K * exp(-r*T) * N(-d2) - S0 * exp(-q*T) * N(-d1)"""
        t = self.time_to_maturity(valuation_date)
        if t <= 0: return self.payoff(spot)

        d1, d2 = bs_d1_d2(spot, self.strike, t, rate, dividend_yield, vol)
        price = self.strike * math.exp(-rate * t) * norm_cdf(-d2) - spot * math.exp(-dividend_yield * t) * norm_cdf(-d1)
        return self.notional * price


# ============================================================
# BINARY CALL/PUT CASH-OR-NOTHING
# ============================================================
@dataclass
class BinaryCall(VanillaProduct):
    def payoff(self, spot_T: float) -> float:
        """Payoff = notional si S_T > K, sinon 0."""
        return self.notional if spot_T > self.strike else 0.0

    def price_bs(self, spot: float, valuation_date: pd.Timestamp, rate: float, dividend_yield: float, vol: float) -> float:
        """Prix Black-Scholes.
        avec BC = exp(-r*T) * N(d2)"""
        t = self.time_to_maturity(valuation_date)
        if t <= 0:  return self.payoff(spot)

        _, d2 = bs_d1_d2(spot, self.strike, t, rate, dividend_yield, vol)
        return self.notional * math.exp(-rate * t) * norm_cdf(d2)

@dataclass
class BinaryPut(VanillaProduct):
    def payoff(self, spot_T: float) -> float:
        return self.notional if spot_T < self.strike else 0.0

    def price_bs(self, spot: float, valuation_date: pd.Timestamp, rate: float, dividend_yield: float, vol: float) -> float:
        """Prix Black-Scholes.
        avec BP = exp(-r*T) * N(-d2)"""
        t = self.time_to_maturity(valuation_date)
        if t <= 0:  return self.payoff(spot)

        _, d2 = bs_d1_d2(spot, self.strike, t, rate, dividend_yield, vol)
        return self.notional * math.exp(-rate * t) * norm_cdf(-d2)
    
    from dataclasses import dataclass


@dataclass
class Cash(VanillaProduct):
    def payoff(self, spot_T: float) -> float:
        return self.notional

    def price_bs(self, spot: float, valuation_date: pd.Timestamp, rate: float, dividend_yield: float, vol: float) -> float:
        t = self.time_to_maturity(valuation_date)
        if t <= 0:
            return self.notional
        return self.notional * math.exp(-rate * t)

# ============================================================
# OUTILS PRATIQUES
# ============================================================
def build_vanilla_universe() -> list[VanillaProduct]:
    """Exemple de grille simple de vanilles. À adapter ensuite à tes données de marché."""
    maturity = pd.Timestamp("2027-12-20")
    return [
        EuropeanCall(name="C_90", strike=90.0, maturity_date=maturity),
        EuropeanCall(name="C_100", strike=100.0, maturity_date=maturity),
        EuropeanCall(name="C_110", strike=110.0, maturity_date=maturity),
        EuropeanPut(name="P_90", strike=90.0, maturity_date=maturity),
        EuropeanPut(name="P_100", strike=100.0, maturity_date=maturity),
        EuropeanPut(name="P_110", strike=110.0, maturity_date=maturity),
        BinaryCall(name="BC_100", strike=100.0, maturity_date=maturity),
        BinaryPut(name="BP_100", strike=100.0, maturity_date=maturity)]

def vanilla_universe_to_dataframe(vanillas: list[VanillaProduct]) -> pd.DataFrame:
    return pd.DataFrame([v.to_row() for v in vanillas])



# ============================================================
# UTILITAIRES BLACK-SCHOLES
# ============================================================
def norm_cdf(x: float) -> float:
    """CDF/Fonction de répartition de la loi normale standard"""   
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))       # erf = fonction d'erreur

def norm_pdf(x: float) -> float:
    """PDF/Fonction de densité de la loi normale standard"""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def _year_fraction(start: pd.Timestamp, end: pd.Timestamp, basis: float = 365.0) -> float:
    """Conventit une différence de dates en année fractionnaire
    exemple : start = 1er janvier 2025, end = 1er juillet 2025 --> renvoie 181/365 = 0.4959"""
    return max((pd.Timestamp(end) - pd.Timestamp(start)).days / basis, 0.0)

def bs_d1_d2(spot: float,strike: float,maturity_years: float,rate: float,dividend_yield: float,vol: float) -> tuple[float, float]:
    """Calcule d1 et d2 Black-Scholes
    la solution pour BS est C = S0 * exp(-q*T) * N(d1) - K * exp(-r*T) * N(d2) pour un call européen, 
                         et P = K * exp(-r*T) * N(-d2) - S0 * exp(-q*T) * N(-d1) pour put européen
    avec d1 = (ln(S0/K) + (r - q + 0.5 * sigma^2) * T) / (sigma * sqrt(T))
    et d2 = d1 - sigma * sqrt(T)
    """
    if maturity_years <= 0:                     raise ValueError("La maturité doit être strictement positive.")
    if spot <= 0 or strike <= 0 or vol <= 0:    raise ValueError("spot, strike et vol doivent être strictement positifs.")

    sqrt_t = math.sqrt(maturity_years)
    num = math.log(spot / strike) + (rate - dividend_yield + 0.5 * vol * vol) * maturity_years
    den = vol * sqrt_t
    d1 = num / den
    d2 = d1 - den
    return d1, d2
