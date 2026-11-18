# Rapport de résultats — exécution REPORT du 10–11 novembre 2026

## 1. Statut de l’exécution

- Identifiant : `2026-11-10_230230_report`
- Durée : environ 1 h 36 min, de 23:02 à 00:38
- Statut : exécution complète et exportée
- Valorisation : 20 000 trajectoires
- Évaluation du risque : 20 000 trajectoires indépendantes
- Bootstrap d’importance sampling : 300 réplications
- Expérience de risque de queue : 2 000 trajectoires de calibration et 10 000 d’évaluation
- Test final : toujours réservé et non évalué pour les deux familles

Le run est donc exploitable comme résultat REPORT indépendant, sans ouverture du test final.

## 2. Valorisation

La valeur Black–Scholes Monte Carlo de l’autocall est de **100,4229** pour un nominal de 100.

- erreur standard : **0,0548** ;
- intervalle de confiance à 95 % : **[100,3155 ; 100,5304]**.

Il s’agit d’une valeur de modèle, pas d’un prix de marché exécutable.

## 3. Résultat principal des politiques parcimonieuses

Les quatre profils compromis Lasso et Elastic Net ont été évalués sur les mêmes 20 000 trajectoires indépendantes.

| Univers | Pénalisation | RMSE résiduelle | Réduction de RMSE | ES 97,5 % | Perte maximale observée |
|---|---:|---:|---:|---:|---:|
| Calls + Puts | Lasso | 2,379 | 69,4 % | 9,488 | 26,810 |
| Calls + Puts | Elastic Net | 2,376 | 69,4 % | 9,481 | 26,441 |
| Full | Lasso | 2,353 | 69,7 % | 9,239 | 26,246 |
| Full | Elastic Net | **2,344** | **69,8 %** | **9,166** | 26,744 |
| Passif brut centré | — | 7,760 | — | 4,423 | — |

Lecture : les politiques absorbent environ 70 % de la variation quadratique du passif, mais leur Expected Shortfall vaut encore un peu plus du double de celui du passif brut centré. Le meilleur profil compromis dans ces résultats est Full Elastic Net, mais son avantage sur Full Lasso et Calls + Puts Elastic Net reste faible.

## 4. Où se forme la queue résiduelle ?

Pour Elastic Net compromis :

- Calls + Puts : 90,2 % de l’ES provient de trajectoires arrivant à maturité sans franchissement antérieur de la barrière de protection, 9,7 % de trajectoires à maturité avec barrière touchée, et 0,1 % de trajectoires rappelées ;
- Full : les parts correspondantes sont 93,2 %, 6,6 % et 0,2 %.

La perte extrême ne vient donc pas principalement des trajectoires déjà rappelées. Le prochain diagnostic doit porter sur la région de maturité, en particulier les scénarios qui manquent une barrière de rappel ou de coupon puis survivent jusqu’au terme.

## 5. Comparaison avec les autres méthodes

La comparaison unifiée donne les ordres de grandeur suivants :

| Méthode | RMSE | ES 97,5 % | Interprétation |
|---|---:|---:|---|
| Delta quotidien | 1,149 | 3,646 | Meilleures métriques brutes parmi les références exécutables |
| Delta tous les cinq jours | 2,140 | 6,734 | RMSE proche, ES inférieure aux politiques parcimonieuses |
| OLS conditionnel Full | 0,489 | 0,179 | Borne de capacité dense avec digitales théoriques |
| Elastic Net conditionnel Full | 2,239 | 8,742 | Meilleure politique parcimonieuse dans ce tableau unifié |
| Elastic Net Calls + Puts | 2,268 | 9,064 | Alternative sans digitales théoriques |

Cette comparaison n’est pas un classement économique : les lignes delta utilisent un P&L terminal autofinancé, les lignes d’options des déficits de flux actualisés, le capital initial n’est pas aligné et les coûts de transaction sont absents. Elle montre néanmoins que la méthode parcimonieuse ne bat pas le delta sur les métriques brutes de risque dans ce modèle.

## 6. Statique, conditionnel et objectif d’ajustement

- Un panier statique reste peu précis : RMSE de 27,46 pour Calls + Puts Lasso et 26,12 pour Full Ridge.
- Avec un objectif par échéance, Full reproduit presque exactement les paiements simulés : RMSE de 0,01 à 0,37 selon la pénalisation convexe.
- Avec Calls + Puts, le même objectif laisse une RMSE de paiements proche de 10,29.
- L’objectif portant sur le total actualisé réduit la RMSE terminale à environ 1,96–2,33, mais laisse une RMSE des paiements proche de 49.

Conclusion : ajuster le total terminal n’est pas équivalent à financer les paiements aux bonnes dates.

## 7. Importance sampling

Pour Elastic Net compromis :

| Univers | ES Monte Carlo | ES importance sampling | Conclusion |
|---|---:|---:|---|
| Calls + Puts | 9,481 | 9,149 | Intervalles bootstrap chevauchants |
| Full | 9,166 | 9,080 | Intervalles bootstrap chevauchants |

Les ratios de taille effective sont de 69,8 % pour Calls + Puts et 75,8 % pour Full, soit environ 13 956 et 15 151 observations effectives sur 20 000. Les poids ne sont pas excessivement concentrés. L’importance sampling confirme donc les ordres de grandeur sans révéler de conflit statistique avec le Monte Carlo standard.

## 8. Expérience avec contrainte d’ES

La contrainte d’ES n’apporte pas une amélioration systématique :

- sous calibration standard, elle change très peu l’ES pour Calls + Puts et Full ;
- sous calibration par importance sampling, elle améliore Full de 7,08 à 6,71, mais dégrade légèrement Calls + Puts de 7,96 à 8,09.

Cette expérience reste exploratoire et ne doit pas remplacer automatiquement les politiques parcimonieuses retenues.

## 9. Financement : interprétation obligatoire

Le besoin de financement P95 des profils compromis se situe autour de 3,7–3,9 % du nominal. Ces montants sont **théoriques et implicites au modèle** :

- les calls et puts sont valorisés aux prix Black–Scholes théoriques ;
- les digitales sont soit valorisées théoriquement, soit remplacées par des spreads eux-mêmes valorisés au prix de modèle ;
- aucun bid–ask, collatéral OTC, marge, impact de marché, risque de contrepartie ou coût réel de débouclage après rappel n’est inclus.

Ces chiffres ne mesurent donc pas le capital effectivement nécessaire pour exécuter la stratégie sur le marché.

## 10. Décision rapide

- **Meilleur compromis statistique parmi les politiques parcimonieuses :** Full Elastic Net.
- **Choix le plus prudent en matière d’implémentation :** Calls + Puts Elastic Net, légèrement moins précis mais sans digitales théoriques.
- **Si la priorité absolue est le risque brut dans Black–Scholes :** le delta quotidien reste meilleur.
- **Si la priorité est une décomposition interprétable avec peu de lignes :** conserver Elastic Net ou Lasso, pas Ridge.
- **À ne pas retenir actuellement :** les profils L0 Full, dont la taille est instable après recalibration et dont l’ES est nettement plus élevée.

La conclusion générale est inchangée mais mieux établie : la réplication parcimonieuse constitue une couche d’explication et de réduction de l’erreur moyenne ; elle n’est pas encore une couverture de queue ni une stratégie démontrée moins coûteuse que le delta.
