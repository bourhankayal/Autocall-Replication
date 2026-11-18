# Audit du run complet et guide de décision

Date : 10 novembre 2026  
Statut : exécution complète en mode de travail ; résultats indicatifs avant l'exécution finale à grande taille et avant l'ouverture de l'échantillon de test réservé.

## 1. Conclusion rapide

Le run valide la chaîne complète : valorisation, construction des paniers, sélection des hyperparamètres, comparaison des objectifs, mesure du risque résiduel, importance sampling, financement et synthèse décisionnelle.

Le meilleur choix pratique à ce stade est un panier conditionnel **Calls + Puts**, ajusté aux dates d'observation, avec une pénalisation **Lasso ou Elastic Net**. Les deux solutions utilisent 19 options et donnent presque les mêmes résultats. Elastic Net demande légèrement moins de financement P95 ; Lasso obtient une RMSE et une ES très légèrement meilleures. Ces écarts sont trop faibles pour désigner un vainqueur définitif avec ce run.

Le panier **Full Elastic Net** est le meilleur résultat numérique parmi les profils compromis, mais il emploie 32 positions et inclut des options binaires théoriques. Il constitue donc surtout un benchmark de capacité de réplication.

## 2. Méthode complète

1. Définir le contrat ou, plus généralement, le payoff à reproduire et figer toutes ses conventions.
2. Choisir un modèle de marché et simuler des trajectoires. Le moteur actuel utilise Black--Scholes, mais l'architecture permet de remplacer ce modèle.
3. Calculer les cashflows du payoff sur chaque trajectoire et à chaque date de paiement.
4. Construire le dictionnaire d'instruments :
   - **Calls + Puts** pour une solution composée de vanilles ;
   - **Full** pour mesurer la capacité maximale en ajoutant des binaires.
5. À chaque date d'observation, construire une politique qui dépend uniquement de l'information alors disponible : survie du produit, spot courant et historique de barrière.
6. Ajuster les portefeuilles avec Ridge, Lasso, Elastic Net ou une heuristique L0.
7. Sélectionner les hyperparamètres sur calibration et validation, puis vérifier la stabilité sur plusieurs recalibrations.
8. Évaluer les poids figés sur des trajectoires indépendantes avec la RMSE, l'Expected Shortfall, les régimes contractuels et l'importance sampling.
9. Vérifier le calendrier réel des paiements avec un compte de financement. Un bon résultat terminal ne suffit pas si le portefeuille manque de cash avant l'échéance.
10. Choisir le panier selon l'objectif : précision, parcimonie, risque de queue, financement et disponibilité des instruments.

## 3. Guide de choix rapide

| Besoin | Choix conseillé | Pourquoi | Réserve principale |
|---|---|---|---|
| Réplication pratique avec vanilles | Calls + Puts, conditionnel par échéance, Lasso ou Elastic Net | 19 positions, bonne RMSE, bonne stabilité | L'ES résiduelle reste supérieure à celle du passif brut centré |
| Moindre financement parmi les candidats pratiques | Calls + Puts, Elastic Net, compromis | Capital P95 de 3,22 % | Avantage très faible face au Lasso |
| Risque résiduel légèrement plus faible avec vanilles | Calls + Puts, Lasso, compromis | RMSE 2,11 %, ES 8,17 % | Écart non significatif face à Elastic Net à cette taille d'échantillon |
| Benchmark de capacité maximale | Full, Elastic Net, compromis | Meilleurs RMSE et ES des profils compromis | Binaires théoriques et 32 positions |
| Très peu de lignes | L0 | 5 à 8 lignes dans le panier sélectionné | Taille très instable après recalibration et risque plus élevé |
| Contrôle de l'ES prioritaire | Optimisation sous contrainte d'ES | Le Full contraint atteint une ES d'environ 6,97 % dans l'expérience | Solution encore dense : 214 coefficients actifs |
| Approximation du total terminal seulement | Politique totale pathwise | Faible erreur terminale | Très mauvaise correspondance des paiements datés ; ne pas l'utiliser comme hedge de cashflows |

## 4. Profils compromis retenus

Les montants sont exprimés en pourcentage du nominal.

| Univers | Pénalité | Positions | RMSE résiduelle | ES 97,5 % | Financement P95 | Lecture |
|---|---:|---:|---:|---:|---:|---|
| Calls + Puts | Lasso | 19 | 2,1119 | 8,1698 | 3,2670 | Meilleure lecture risque parmi les deux choix pratiques |
| Calls + Puts | Elastic Net | 19 | 2,1143 | 8,1754 | 3,2246 | Choix pratique par défaut grâce au financement légèrement plus faible |
| Full | Lasso | 24 | 2,1084 | 8,0359 | 3,3105 | Benchmark théorique plus parcimonieux |
| Full | Elastic Net | 32 | 2,1071 | 7,9584 | 3,2766 | Meilleur profil compromis numérique, mais non directement tradable |
| Calls + Puts | L0 | 8 | 2,4755 | 10,2872 | 3,7168 | Trop instable et moins protecteur pour être le choix principal |

Le passif brut centré a une RMSE de 7,9404 % et une ES 97,5 % de 4,4883 %. Les paniers réduisent donc la variation moyenne d'environ 73 %, mais dégradent encore la queue défavorable. Le prochain enjeu n'est plus seulement l'ajustement moyen : il faut contrôler les scénarios de maturité et de barrière qui portent l'ES.

## 5. Comparaison avec les autres méthodes

Cette table reprend le tableau unifié du notebook. Elle sert à comparer les ordres de grandeur et la nature des méthodes, pas à établir un classement économique : le capital initial, l'objet de risque et les coûts de transaction ne sont pas encore alignés.

| Méthode | RMSE (% nominal) | ES 97,5 % | Objet mesuré | Conclusion |
|---|---:|---:|---|---|
| Autocall non couvert | 8,646 | 4,833 | Dispersion du passif centré | Référence de risque brut |
| Delta quotidien | 1,222 | 3,976 | P&L terminal autofinancé | Très bon benchmark dynamique sous Black--Scholes, mais objet différent |
| Delta tous les 5 jours | 2,175 | 6,517 | P&L terminal autofinancé | Dégradation logique avec moins de rééquilibrages |
| Statique OLS Calls + Puts | 48,596 | 93,464 | Déficit de cashflows actualisés | Un panier initial unique ne capture pas la maturité aléatoire et l'état du produit |
| Notre conditionnel Calls + Puts Elastic Net | 2,475 | 9,852 | Déficit de cashflows actualisés | Forte amélioration face à la réplication statique ; risque de queue encore à traiter |

La synthèse de risque dédiée donne 2,114 de RMSE et 8,175 d'ES pour le même profil compromis. La différence vient de la convention et du bloc d'évaluation utilisés. Les deux chiffres ne doivent pas être mélangés dans une même colonne sans préciser leur source.

## 6. Financement : ce qu'il faut conserver

Le financement doit rester dans la méthode, car il révèle les compensations entre dates qu'une erreur terminale peut masquer. En revanche, le rapport principal n'a besoin que de trois informations : coût initial, besoin de financement P95 et ES de la perte après financement.

Les ledgers trajectoire par trajectoire, les détails de compte de cash et les scénarios de coûts OTC doivent rester dans le notebook d'audit ou en annexe. Ils ne doivent pas piloter la sélection principale tant que les coûts de marché ne sont pas calibrés.

## 7. Expérience de contrôle de l'ES

L'expérience la plus intéressante est le Full calibré par Monte-Carlo standard sous contrainte d'ES : RMSE 2,5548 %, ES 6,9668 %, mais 214 coefficients actifs. Elle montre que la queue peut être améliorée, au prix d'une solution beaucoup trop dense. Pour Calls + Puts, la contrainte donne RMSE 2,3386 %, ES 8,2863 % et 152 coefficients : elle n'améliore pas assez la solution sparse actuelle pour justifier cette complexité.

## 8. Statut technique

L'étape 9 était bloquée uniquement parce que l'export cherchait encore des colonnes de coûts OTC supprimées du notebook principal. Le générateur de vues accepte désormais les tables de financement sans ces colonnes, et les tests associés passent.

Si le noyau du notebook est encore ouvert, il suffit de relancer la cellule de la section 9. Aucun recalcul des sections 0 à 8 n'est nécessaire.

## 9. Durée estimée du run final

Le dernier run final historique du notebook principal a pris environ 4 h 25, mais le notebook contient maintenant davantage de diagnostics. L'estimation raisonnable est **5 à 7 heures**, avec une marge prudente de **4 h 30 à 8 heures** selon la machine et la convergence des solveurs. L'étude complète d'hyperparamètres déjà exécutée en environ 25 heures n'a pas à être relancée : ses sélections sont importées par le notebook principal.
