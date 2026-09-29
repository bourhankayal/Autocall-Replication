# Term-sheet fonctionnelle — Autocall mono-sous-jacent

Statut : **version 1.0 validée le 8 août 2026**  
Rôle : source de vérité contractuelle pour le code, les tests et les notebooks.  
Périmètre : définition pédagogique du produit actuellement implémenté ; il ne s'agit pas d'une documentation juridique.

Décisions contractuelles validées :

- barrière de protection surveillée sur toutes les cotations disponibles pendant la vie du produit ;
- remboursement après activation de la barrière égal à `N × S(T)/S₀`, sans plafond contractuel explicite ;
- rappel déclenché lorsque le spot est supérieur **ou égal** au seuil ;
- calendrier pédagogique simplifié du lundi au vendredi, sans jours fériés.

## 1. Identification du produit

Le produit est un autocall discret mono-sous-jacent, proche d'un Athena sans mémoire, avec :

- remboursement anticipé conditionnel ;
- coupon conditionnel à chaque date d'observation ;
- coupon sans mémoire ;
- barrière de protection surveillée sur les dates de cotation disponibles ;
- remboursement final dépendant du franchissement antérieur de la barrière de protection.

Cette dénomination reste descriptive : les règles ci-dessous, et non le nom « Athena », définissent juridiquement et numériquement le payoff.

## 2. Paramètres contractuels par défaut

| Paramètre | Symbole | Valeur par défaut | Interprétation |
|---|---:|---:|---|
| Nominal | `N` | 100 | Montant de référence |
| Spot initial | `S₀` | fixé au départ | Première cotation disponible à partir de la date de fixing demandée |
| Seuil de rappel | `Bᴀ` | 100 % de `S₀` | Rappel si `S(tᵢ) ≥ Bᴀ × S₀` |
| Barrière coupon | `Bᴄ` | 80 % de `S₀` | Coupon si `S(tᵢ) ≥ Bᴄ × S₀` |
| Coupon périodique | `c` | 2 % du nominal | `c × N = 2` à chaque observation éligible |
| Barrière de protection | `Bᴘ` | 70 % de `S₀` | Touchée si `S(t) ≤ Bᴘ × S₀` |
| Observations | `tᵢ` | 3, 6, 9 et 12 mois | Dates calculées depuis le fixing effectif |
| Maturité | `T` | 12 mois | Dernière date d'observation |

Tous les seuils sont exprimés relativement au spot initial contractuel `S₀`, jamais relativement au spot courant à la date de valorisation.

## 3. Dates et calendrier

1. La date de fixing effective est la première date de cotation disponible supérieure ou égale à la date de départ demandée.
2. Les dates contractuelles d'observation sont obtenues en ajoutant 3, 6, 9 et 12 mois à cette date de fixing effective.
3. Les samedis et dimanches ne sont pas des jours de cotation. Si une date contractuelle tombe un week-end ou n'est pas présente dans la série de prix, l'observation utilise la première cotation disponible postérieure : convention **following sur les données disponibles**.
4. La dernière observation effective est aussi la date de remboursement final lorsque le produit n'a pas été rappelé.
5. Le calendrier pédagogique ne possède pas de liste de jours fériés : un jour du lundi au vendredi est potentiellement ouvré. Une future version de marché devra remplacer cette convention par un calendrier de place identifié.
6. Les fractions d'année et l'actualisation utilisent ACT/365 et une capitalisation continue.

## 4. Coupon

À chaque date d'observation effective `tᵢ`, tant que le produit est vivant, le coupon `Cᵢ` vaut :

```text
Si S(tᵢ) ≥ Bᴄ × S₀ : Cᵢ = c × N
Sinon               : Cᵢ = 0
```

Conventions :

- les coupons sont conditionnels ;
- les coupons ne sont pas garantis ;
- les coupons non payés sont définitivement perdus : **aucune mémoire** ;
- si le produit est rappelé à une observation, le coupon `Cᵢ` de cette observation est évalué et payé avant le remboursement du nominal ;
- aucun flux ni risque contractuel ne subsiste après le rappel.

## 5. Rappel anticipé

À chaque date d'observation effective `tᵢ`, après évaluation du coupon :

```text
Rappel à tᵢ si et seulement si S(tᵢ) ≥ Bᴀ × S₀
```

En cas de rappel, le produit verse :

```text
Remboursement de rappel : Rᵢ = N
```

auquel s'ajoute éventuellement le coupon `Cᵢ` de la même observation.

La comparaison est **inclusive**. Un spot exactement égal au seuil de rappel déclenche le rappel.

## 6. Barrière de protection

La barrière est considérée comme touchée lorsqu'au moins une cotation surveillée, entre le fixing effectif et le dernier cashflow du produit inclus, vérifie :

```text
S(t) ≤ Bᴘ × S₀
```

La surveillance est donc discrète sur les données disponibles, même si elle approxime une surveillance quotidienne dans les simulations.

La barrière n'affecte ni les coupons intermédiaires ni un remboursement anticipé. Elle sert uniquement à déterminer le remboursement final d'un produit qui n'a jamais été rappelé.

## 7. Remboursement à maturité

Si le produit n'a jamais été rappelé, le remboursement à la dernière observation est actuellement :

```text
Si la barrière n'a jamais été touchée : R(T) = N
Si la barrière a été touchée           : R(T) = N × S(T) / S₀
```

Le coupon final `C(T)`, s'il est dû, s'ajoute à ce remboursement.

Cette formule est retenue sans plafond contractuel explicite. Avec les paramètres par défaut, un spot final supérieur ou égal à `S₀` déclenche le rappel à la dernière observation : le remboursement de la branche « barrière touchée » ne dépasse donc pas le nominal. Si le seuil de rappel est relevé ultérieurement au-dessus de 100 %, cette propriété disparaît et la formule pourra produire un remboursement supérieur au nominal.

## 8. Table exhaustive des scénarios

| État à une observation | Condition coupon | Condition rappel | Flux versé | Suite du contrat |
|---|---|---|---|---|
| Produit vivant, observation avant maturité | `S(tᵢ) < Bᴄ × S₀` | impossible avec les paramètres par défaut | 0 | Le produit continue |
| Produit vivant, observation avant maturité | `Bᴄ × S₀ ≤ S(tᵢ) < Bᴀ × S₀` | non | `c × N` | Le produit continue |
| Produit vivant, observation avant maturité | `S(tᵢ) ≥ Bᴀ × S₀` | oui | `c × N + N` avec les paramètres par défaut | Le produit s'arrête |
| Non rappelé à maturité, barrière jamais touchée | selon `S(T) ≥ Bᴄ × S₀` | non | `C(T) + N` | Le produit s'arrête |
| Non rappelé à maturité, barrière touchée | selon `S(T) ≥ Bᴄ × S₀` | non | `C(T) + N × S(T)/S₀` | Le produit s'arrête |
| Spot exactement égal au seuil de rappel | coupon payé avec les paramètres par défaut | oui, car règle inclusive | `c × N + N` | Le produit s'arrête |
| Spot exactement égal à la barrière coupon | oui | selon seuil de rappel | `c × N`, plus remboursement éventuel | Selon rappel/maturité |
| Spot exactement égal à la barrière de protection | barrière considérée touchée | indépendant | aucun effet immédiat | Effet éventuel sur `R(T)` |

## 9. Valeur actualisée

Pour une date de valorisation `t`, la valeur Monte-Carlo d'une trajectoire est :

```text
PV(t) = somme, pour chaque date u ≥ t, de : CF(u) × exp[-r × τ(t,u)]
```

où `τ(t,u)` suit ACT/365 et `r` est un taux continu constant dans l'implémentation actuelle.

Le prix Monte-Carlo est la moyenne des valeurs `PV(t)` simulées sous la mesure risque-neutre Black-Scholes :

```text
dS(t) / S(t) = (r - q) × dt + σ × dW(t)
```

## 10. Valorisation d'un contrat en cours de vie

Une valorisation postérieure au fixing doit recevoir explicitement :

- la date de départ contractuelle ;
- le spot initial contractuel `S₀` ;
- la date de valorisation ;
- l'information « barrière déjà touchée avant la valorisation » ;
- la confirmation que le produit est encore vivant.

Si le produit a déjà été rappelé, sa valeur future est nulle après paiement des flux de rappel. L'état des coupons passés n'est pas nécessaire dans la version sans mémoire.

## 11. Cas invalides

Le moteur doit rejeter explicitement :

- une trajectoire vide ;
- une trajectoire sans index de dates ;
- un spot initial nul, négatif ou non fini ;
- des dates non ordonnées ou impossibles à interpréter ;
- une trajectoire ne couvrant pas une observation future requise ;
- une valorisation postérieure à la maturité ;
- un nombre de trajectoires Monte-Carlo inférieur à deux pour l'estimation d'une erreur standard.

## 12. Décisions contractuelles validées

Les quatre décisions suivantes changent directement le payoff, son prix ou les dates de paiement. Les options non retenues sont conservées pour documenter le raisonnement.

### Question 1 — Quand observe-t-on la barrière de protection à 70 % ?

Exemple commun aux deux options : `S₀ = 100`. Le spot descend à 55 pendant la vie du produit, remonte ensuite à 75 à maturité et le produit n'a jamais été rappelé.

**Option A — Barrière européenne, observée uniquement à maturité**

- On compare uniquement le spot final `S(T)` à 60.
- Dans l'exemple, `S(T) = 75`, donc la protection fonctionne et le remboursement final est 100.
- Une baisse temporaire sous 60 n'a aucun effet si le spot termine au-dessus de 60.
- Le produit est plus simple à expliquer, tester et répliquer.

**Option B — Barrière surveillée pendant toute la vie du produit**

- Chaque cotation disponible entre le fixing et la maturité est comparée à 60.
- Dans l'exemple, le passage à 55 active définitivement la barrière.
- Même si le spot remonte ensuite à 75, le remboursement final devient 75 avec la formule actuelle.
- Le produit est plus path-dependent et son risque de couverture est plus difficile.

**Décision retenue : option B — barrière surveillée pendant toute la vie.** Dans le modèle actuel, cette surveillance est discrète sur chaque cotation disponible ; elle ne doit pas être présentée comme une surveillance mathématiquement continue entre deux cotations.

### Question 2 — Quelle formule appliquer lorsque la protection ne fonctionne plus ?

Cette question intervient seulement si le produit n'a jamais été rappelé et si la condition de protection définie à la question 1 n'est pas satisfaite.

Exemple : `N = 100`, `S₀ = 100` et `S(T) = 45`.

**Option A — Participation un-pour-un à la baisse, plafonnée au nominal**

```text
R(T) = N × min[1 ; S(T)/S₀]
```

- Dans l'exemple, le remboursement est `100 × 45/100 = 45`.
- Le remboursement ne peut jamais dépasser 100 hors coupon.
- Cela exprime clairement que l'investisseur subit la baisse du sous-jacent, sans recevoir un gain supplémentaire via cette jambe.

**Option B — Formule actuelle sans plafond**

```text
R(T) = N × S(T)/S₀
```

- Dans l'exemple, le remboursement est également 45.
- Si les paramètres de rappel sont modifiés et que `S(T) > S₀` sans rappel, le remboursement peut dépasser 100.
- Cette possibilité doit être voulue explicitement ; sinon elle crée un comportement surprenant.

**Décision retenue : option B — formule `N × S(T)/S₀` sans plafond explicite.** La cohérence de cette formule dépend du seuil de rappel ; tout changement futur de ce seuil devra déclencher une revue du remboursement terminal.

### Question 3 — Le spot exactement égal au seuil déclenche-t-il le rappel ?

Exemple : `S₀ = 100`, seuil de rappel à 100 %, et `S(tᵢ) = 100` exactement à une observation.

**Option A — Comparaison inclusive `S(tᵢ) ≥ Bᴀ × S₀`**

- Dans l'exemple, le produit est rappelé.
- Il verse le coupon éligible de 2 puis rembourse le nominal de 100.
- Total versé à cette date : 105.

**Option B — Comparaison stricte `S(tᵢ) > Bᴀ × S₀`**

- Dans l'exemple, le produit n'est pas rappelé.
- Il verse seulement le coupon éligible de 2 et continue, sauf s'il s'agit de la maturité.
- C'est le comportement du code actuel.

**Décision retenue : option A — comparaison inclusive `≥`.** Le code et les tests doivent donc rappeler le produit lorsque le spot est exactement égal au seuil.

### Question 4 — Quel calendrier détermine les dates d'observation et de paiement ?

Exemple : une observation contractuelle tombe un dimanche ou un jour férié de la place de cotation.

**Option A — Calendrier pédagogique simplifié, du lundi au vendredi**

- Le samedi et le dimanche sont exclus.
- Les jours fériés ne sont pas connus : ils sont traités comme des jours ouvrés s'ils apparaissent dans les données.
- L'observation est reportée à la première date disponible suivante.
- Cette convention suffit pour les simulations théoriques, mais ne reproduit pas exactement un contrat réel.

**Option B — Calendrier réel d'une place de cotation identifiée**

- Il faut d'abord choisir le sous-jacent et sa place principale : par exemple un indice européen, un indice américain ou une action précise.
- Les week-ends, jours fériés, fermetures exceptionnelles et règles de report sont alors déterminés par ce calendrier.
- Cette solution est nécessaire avant l'utilisation de données de marché ou la comparaison avec un produit réel.

**Décision retenue : option A — calendrier lundi-vendredi simplifié.** Les week-ends sont exclus, les jours fériés ne sont pas modélisés et la convention following utilise la première cotation disponible suivante.

### Synthèse des réponses validées

```text
Q1 : B — barrière surveillée pendant toute la vie
Q2 : B — remboursement N × S(T)/S₀ sans plafond explicite
Q3 : A — rappel avec ≥
Q4 : A — calendrier lundi-vendredi simplifié
```

La term-sheet est désormais en version 1.0. Chaque ligne de la table de scénarios doit correspondre à au moins un test automatisé avant que le moteur de payoff soit considéré comme validé.
