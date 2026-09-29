# Validation du moteur Monte-Carlo

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Le moteur Monte-Carlo fournit le prix de référence de l’autocall. |
| **Problème** | Vérifier convergence, incertitude numérique et antithétiques. |
| **Méthode** | Comparaison de tailles d’échantillon et intervalle de confiance. |
| **Modifications** | Ajout des diagnostics et conventions de surveillance. |
| **Résultats** | Une configuration de référence chiffrée est validée dans ce rapport. |


Statut : validation numérique initiale  
Date : 8 août 2026  
Contrat : term-sheet fonctionnelle v1.0

## 1. Configuration de référence

| Paramètre | Valeur |
|---|---:|
| Spot initial | 100 |
| Date de valorisation | 2026-06-20 |
| Maturité | 2027-06-22 |
| Taux continu | 3 % |
| Rendement de dividende continu | 1 % |
| Volatilité | 20 % |
| Nombre de trajectoires | 20 000 |
| Seed | 42 |
| Antithétiques | Oui |
| Surveillance contractuelle | Chaque jour de cotation lundi-vendredi |

Les 20 000 trajectoires correspondent à 10 000 paires antithétiques indépendantes. L'erreur standard et l'intervalle de confiance sont calculés sur les moyennes de ces paires.

## 2. Résultat de référence

| Mesure | Résultat |
|---|---:|
| Prix estimé | 100,422920 |
| Erreur standard | 0,054813 |
| Borne basse à 95 % | 100,315489 |
| Borne haute à 95 % | 100,530352 |

## 3. Convergence en nombre de trajectoires

Les lignes utilisent la même seed et des variables antithétiques.

| Trajectoires | Prix | Erreur standard | Borne basse 95 % | Borne haute 95 % | Largeur de l'intervalle |
|---:|---:|---:|---:|---:|---:|
| 500 | 99,413079 | 0,417697 | 98,594408 | 100,231749 | 1,637341 |
| 1 000 | 100,195398 | 0,255754 | 99,694129 | 100,696668 | 1,002539 |
| 5 000 | 100,465821 | 0,107509 | 100,255107 | 100,676535 | 0,421428 |
| 10 000 | 100,570939 | 0,074872 | 100,424192 | 100,717685 | 0,293493 |

La largeur de l'intervalle diminue lorsque le nombre de trajectoires augmente. Les prix ponctuels ne sont pas supposés évoluer de façon monotone ; ils fluctuent à l'intérieur de leur incertitude statistique.

## 4. Fréquence de surveillance de la barrière

La term-sheet définit une surveillance discrète à chaque cotation disponible. La fréquence quotidienne `1` est donc la référence contractuelle. Les fréquences plus faibles servent uniquement à mesurer l'erreur créée par un sous-échantillonnage.

| Pas entre deux observations de barrière | Interprétation approximative | Prix | Écart au prix quotidien |
|---:|---|---:|---:|
| 21 | mensuelle | 100,696402 | +0,273482 |
| 10 | bimensuelle | 100,584159 | +0,161239 |
| 5 | hebdomadaire | 100,512486 | +0,089566 |
| 1 | quotidienne | 100,422920 | 0 |

Dans cette configuration, observer moins souvent la barrière manque certaines activations défavorables à l'investisseur et surestime donc le prix. L'écart mesuré dépend fortement du niveau de barrière, de la volatilité et de la maturité ; il ne doit pas être généralisé sans nouveaux stress.

## 5. Variable de contrôle

La variable de contrôle testée est le spot terminal actualisé, dont l'espérance risque-neutre est connue dans le modèle GBM.

| Méthode | Prix | Erreur standard |
|---|---:|---:|
| Antithétiques sans contrôle | 100,422920 | 0,054813 |
| Antithétiques avec contrôle | 100,390169 | 0,033270 |

Le ratio de réduction de variance mesuré est d'environ `2,71`. Dans cette configuration, la variable de contrôle est donc utile. Elle reste optionnelle via `control_variate=True`, afin que les résultats bruts et ajustés puissent être comparés.

## 6. Contrôles automatisés

Les tests vérifient notamment :

- la reproductibilité avec une seed fixe ;
- la symétrie des chocs antithétiques ;
- le calcul de l'erreur standard sur les paires indépendantes ;
- l'intervalle de confiance dans un cas déterministe ;
- l'identité entre payoff vectorisé et moteur contractuel, trajectoire par trajectoire ;
- le format des tables de convergence ;
- la référence quotidienne de surveillance de la barrière ;
- la réduction effective de variance par la variable de contrôle.

## 7. Limites restantes

- Le calendrier ignore les jours fériés.
- La barrière est contractuellement discrète ; aucune correction Brownian bridge n'est nécessaire pour cette définition, mais elle le deviendrait pour une barrière continue.
- Le modèle reste Black-Scholes à volatilité constante.
- Les résultats ne constituent pas une validation indépendante ni un prix de marché.
- Une étude de stress doit encore varier volatilité, niveau de barrière, taux, dividendes et maturité.

## 8. Reproduction

```python
from autocall_replication import AutocallProduct
from autocall_replication.monte_carlo import (
    price_autocall_bs_mc,
    run_autocall_mc_convergence,
    run_barrier_monitoring_convergence,
)

product = AutocallProduct()

result = price_autocall_bs_mc(
    product=product,
    spot0=100.0,
    valuation_date="2026-06-20",
    maturity_date="2027-06-22",
    rate=0.03,
    dividend_yield=0.01,
    vol=0.20,
    n_paths=20_000,
    seed=42,
    antithetic=True,
    control_variate=True,
)

paths_table = run_autocall_mc_convergence(
    product,
    100.0,
    "2026-06-20",
    "2027-06-22",
    0.03,
    0.01,
    0.20,
)

barrier_table = run_barrier_monitoring_convergence(
    product,
    100.0,
    "2026-06-20",
    "2027-06-22",
    0.03,
    0.01,
    0.20,
)
```
