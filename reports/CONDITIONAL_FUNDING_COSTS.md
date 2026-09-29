# Coût et financement de la politique conditionnelle

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | La politique conditionnelle reproduit les cashflows de l’autocall mais son financement intermédiaire devait encore être vérifié. |
| **Problème** | Une faible erreur terminale peut masquer des achats successifs coûteux, du levier ou un besoin d’emprunt important. |
| **Méthode** | Valorisation Black-Scholes de chaque nœud, compte cash autofinancé et comparaison de trois traitements des binaires. |
| **Modifications** | Ajout du moteur de financement, des spreads verticaux, des scénarios OTC, des métriques normalisées, des graphiques et des tests comptables. |
| **Résultats** | Chaque profil peut désormais être évalué en coût net, exposition brute, besoin de financement et P&L terminal sur un échantillon indépendant. |

## 1. Point de vue économique

L’émetteur vend l’autocall, reçoit sa prime, achète le premier panier et place
ou emprunte le solde au taux sans risque. À chaque observation, il encaisse le
payoff du panier, paie le client et, si le produit survit, achète le panier de la
période suivante. Aucune injection de cash n’est ajoutée silencieusement.

La récurrence est :

```text
cash avant règlement = cash précédent × exp(r × durée)
cash après règlement = cash avant + payoff options - flux autocall
cash après transaction = cash après règlement - coût du panier suivant
```

Un solde négatif représente un emprunt. Le capital supplémentaire nécessaire
pour interdire tout emprunt vaut l’opposé du minimum du compte cash lorsqu’il
est négatif.

## 2. Prix Black-Scholes affichés dans le notebook

Avec :

```text
d1 = [ln(S/K) + (r - q + sigma²/2)T] / [sigma sqrt(T)]
d2 = d1 - sigma sqrt(T)
```

les calls et puts utilisent leurs formules Black-Scholes européennes. Une
binaire call et une binaire put cash-or-nothing de payout `Q` valent :

```text
BC = Q exp(-rT) N(d2)
BP = Q exp(-rT) N(-d2)
```

Deux mesures sont toujours séparées :

```text
valeur nette = somme poids × prix
exposition brute = somme |poids × prix|
```

La première mesure le cash net requis ; la seconde révèle les grandes positions
longues et courtes qui se compensent.

## 3. Trois traitements des binaires

### A. Full théorique

Les binaires exactes sont conservées et valorisées à leur prix Black-Scholes.
Ce cas mesure le potentiel mathématique maximal de la base `full`, sans conclure
à sa négociabilité.

### B. Full transformé en spreads verticaux

Chaque binaire est remplacée après calibration par deux options vanilles. Pour
deux strikes `K1 < K < K2` :

```text
binary call ≈ Q / (K2-K1) × [Call(K1) - Call(K2)]
binary put  ≈ Q / (K2-K1) × [Put(K2) - Put(K1)]
```

Le moteur recalcule les prix, les payoffs, le financement et le P&L de ces
positions transformées. Il ne se contente pas d’attribuer un nouveau coût à la
binaire originale. La largeur est configurable et vaut 5 unités dans le
notebook par défaut.

### C. Full OTC

Le payoff binaire exact est conservé. Faute de quote de dealer, seule une charge
minimale transparente en bps du payout est utilisée :

| Variante OTC | Charge minimale |
|---|---:|
| Favorable | 5 bps |
| Centrale | 10 bps |
| Stressée | 25 bps |

Ces nombres sont des hypothèses provisoires, pas des données observées. Le prix
acheteur/vendeur est borné entre zéro et le payout actualisé.

## 4. Comparaisons produites

Le pipeline présente :

- `Calls + Puts` calibré directement ;
- `Full` avec binaires théoriques ;
- `Full` transformé en spreads ;
- `Full OTC` favorable, central et stressé.

Pour chaque pénalité et profil, il publie le coût initial net, l’exposition
brute, la fréquence d’emprunt, le besoin de financement moyen/P95/maximal, les
achats bruts cumulés, le P&L terminal, sa RMSE, sa VaR et son Expected Shortfall.
Les métriques principales sont aussi exprimées en pourcentage et points de base
du nominal.

Les trajectoires de financement sont indépendantes de la calibration. Alpha,
poids et topologie restent figés et le test final n’est pas ouvert.

## 5. Limites

- Le bid-ask des calls et puts est volontairement reporté.
- Les spreads verticaux sont actuellement valorisés au mid Black-Scholes et non
  à des quotes exécutables.
- Les charges OTC ne sont pas des cotations de dealer.
- Le compte est suivi aux dates d’observation, pas quotidiennement.
- La marge, le collatéral, les commissions et l’impact de marché restent hors
  de cette version.
- Le P&L permet maintenant de diagnostiquer la cohérence financière, mais le
  mark-to-market continu de l’autocall et le hedge dynamique restent à faire.

## 6. Fichiers et validation

- `replication/funding.py` : valorisation, transformation et ledger ;
- `notebooks/autocall_research.ipynb` : formules, tables et graphiques ;
- `tests/test_funding.py` : spreads, ordre des coûts OTC, identité comptable,
  arrêt au rappel et échantillon indépendant ;
- `scripts/validate.py` : inclusion du nouveau module dans la validation locale.

