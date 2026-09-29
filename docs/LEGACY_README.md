

---

## 7. Types de bases de vanilles

La fonction `build_naive_vanilla_basis` permet de choisir plusieurs familles de produits.

### `family="calls"`

Base composée uniquement de calls européens.

```text
C(K, T)
```

### `family="calls_puts"`

Base composée de calls et puts européens.

```text
C(K, T), P(K, T)
```

### `family="full"`

Base composée de calls, puts, binary calls et binary puts.

```text
C(K, T), P(K, T), BC(K, T), BP(K, T)
```

Cette dernière base est plus riche et permet souvent une meilleure approximation des discontinuités ou effets de seuil liés aux barrières et au rappel anticipé.

---

## 8. Métriques

Les benchmarks retournent des métriques d’erreur sous forme de dictionnaire.

```python
{
    "mae": ...,
    "rmse": ...,
    "max_abs_error": ...,
    "mean_error": ...
}
```

### MAE

Erreur absolue moyenne.

```text
MAE = mean(|réplique - cible|)
```

### RMSE

Erreur quadratique moyenne.

```text
RMSE = sqrt(mean((réplique - cible)^2))
```

### Max absolute error

Erreur maximale en valeur absolue.

### Mean error

Erreur moyenne signée, aussi appelée biais.

---

## 9. Différence entre les benchmarks

Il est important de ne pas confondre les trois benchmarks.

### 9.1 Surface de prix

Dans `target_price.py`, on cherche à reproduire :

```text
Prix autocall(t, S)
```

par une combinaison :

```text
Σ wi × Prix vanille_i(t, S)
```

C’est une réplication de valeur de marché.

---

### 9.2 Espérance de payoff brut

Dans `benchmark_mean_payoff.py`, on cherche à reproduire :

```text
E[payoff brut autocall | S_t = S]
```

par :

```text
Σ wi × E[payoff brut vanille_i | S_t = S]
```

Ce benchmark ne travaille pas directement sur des prix actualisés.

---

### 9.3 Payoff pathwise

Dans `benchmark_payoff.py`, on cherche à reproduire, trajectoire par trajectoire :

```text
Payoff actualisé autocall(ω)
```

par :

```text
Σ wi × Payoff actualisé vanille_i(ω)
```

C’est le benchmark le plus strict, car il teste la réplication scénario par scénario.

---

## 10. Points d’attention

### 10.1 La réplication est statique

Le portefeuille de vanilles est fixé une fois pour toutes.

Il ne s’agit pas encore d’une stratégie dynamique de couverture en delta, vega, gamma ou barrier risk.

---

### 10.2 Les vanilles utilisées sont synthétiques

Les options sont pricées via Black-Scholes avec volatilité constante.

Le projet ne prend pas encore en compte :

* surface de volatilité implicite ;
* bid-ask ;
* liquidité ;
* smile ;
* skew ;
* coûts de transaction ;
* funding ;
* dividendes discrets ;
* calendrier de marché réel.

---

### 10.3 Le modèle est Black-Scholes

Les trajectoires sont simulées sous dynamique lognormale :

```text
dS_t / S_t = (r - q) dt + σ dW_t
```

Cela reste une hypothèse simplificatrice forte, notamment pour des produits à barrière ou rappel anticipé.

---

### 10.4 La grille de maturités doit être clarifiée

La base naïve de vanilles peut inclure plusieurs maturités intermédiaires.

Il faut distinguer :

* maturités aux dates d’observation ;
* maturités mensuelles ;
* maturités disponibles sur le marché ;
* maturités personnalisées.

Cette convention a un impact important sur la qualité de réplication.

---

## 11. Roadmap

### Étape 1 — Nettoyage du repository

* Renommer les fichiers sans suffixes `(2)`, `(3)`, etc.
* Séparer les notebooks et les modules `.py`.
* Ajouter un vrai `requirements.txt`.
* Ajouter un script de test rapide.

---

### Étape 2 — Stabilisation du pricing

* Vérifier les conventions de dates.
* Clarifier le calendrier utilisé : jours calendaires ou jours ouvrés.
* Ajouter des tests unitaires sur les payoffs.
* Vérifier les cas limites :

  * autocall immédiat ;
  * barrière touchée ;
  * barrière non touchée ;
  * coupon payé ;
  * coupon non payé ;
  * maturité atteinte sans rappel.

---

### Étape 3 — Amélioration des bases de réplication

* Ajouter un choix explicite de maturités :

  * observation dates ;
  * monthly grid ;
  * custom maturities.
* Ajouter des strikes plus adaptatifs autour des barrières.
* Ajouter des digitals ou call spreads pour approximer les discontinuités.
* Ajouter contraintes de régularisation ou de sparsité.

---

### Étape 4 — Robustesse statistique

* Ajouter intervalles de confiance Monte Carlo.
* Utiliser des seeds contrôlés.
* Ajouter variance reduction :

  * antithetic variates ;
  * control variates ;
  * common random numbers ;
  * quasi-Monte Carlo.

---

### Étape 5 — Passage vers données de marché

* Importer une surface de volatilité implicite.
* Pricer les vanilles à partir de données de marché.
* Calibrer le modèle sur les prix observés.
* Comparer réplication théorique et réplication réaliste.

---

### Étape 6 — Réplication dynamique

* Calculer les Greeks de l’autocall.
* Construire une couverture dynamique.
* Comparer :

  * réplication statique par vanilles ;
  * delta hedging ;
  * hedge hybride statique + dynamique.

---

## 12. Limites actuelles

Le pipeline actuel est un prototype de recherche.

Les résultats ne doivent pas être interprétés comme des prix de marché définitifs ni comme une stratégie de trading directement exploitable.

Les principales limites sont :

* modèle Black-Scholes simplifié ;
* absence de smile de volatilité ;
* absence de coûts de transaction ;
* absence de liquidité et bid-ask ;
* base de vanilles synthétique ;
* conventions calendaires simplifiées ;
* absence de calibration marché ;
* réplication statique uniquement.

---

## 13. Interprétation attendue des résultats

Un bon résultat sur la surface de prix ne garantit pas nécessairement une bonne réplication pathwise.

Inversement, un fit pathwise peut réduire l’erreur scénario par scénario mais produire un portefeuille difficilement interprétable ou instable.

Il faut donc comparer simultanément :

1. les erreurs train/test ;
2. la stabilité des poids ;
3. la concentration du portefeuille ;
4. les erreurs par zone de spot ;
5. les erreurs autour des barrières ;
6. les erreurs autour des dates d’observation ;
7. la robustesse aux paramètres de marché.

---

## 14. Exemple de workflow recommandé

```python
# 1. Définir le produit
product = AutocallProduct()

# 2. Pricer l'autocall par Monte Carlo
mc_price = price_autocall_bs_mc(...)

# 3. Tester une base simple de calls
res_calls = run_naive_benchmark_price(..., family="calls")

# 4. Tester calls + puts
res_calls_puts = run_naive_benchmark_price(..., family="calls_puts")

# 5. Tester base complète avec binaires
res_full = run_naive_benchmark_price(..., family="full")

# 6. Comparer les métriques
print(res_calls["metrics_test"])
print(res_calls_puts["metrics_test"])
print(res_full["metrics_test"])

# 7. Analyser les poids
print(res_full["weights"].head(20))

# 8. Tester la réplication pathwise
pathwise = run_naive_benchmark_payoff_pathwise(..., family="full")
plot_pathwise_benchmark(pathwise["y"], pathwise["replica"])
```

---

## 15. Avertissement

Ce projet est destiné à un usage pédagogique, académique et exploratoire.

Il ne constitue pas un conseil en investissement, un outil de trading validé, ni un moteur de pricing certifié.

Toute utilisation dans un cadre professionnel nécessiterait des validations supplémentaires : tests unitaires, revue quantitative, calibration marché, contrôle du risque modèle, robustesse numérique et validation indépendante.

---

## 16. Auteur

Projet développé dans le cadre d’un travail exploratoire sur la réplication d’autocalls par portefeuilles de vanilles.

---

## 17. Statut du projet

Statut actuel : prototype fonctionnel en développement.

Les prochaines priorités sont :

1. nettoyer l’architecture du repository ;
2. stabiliser les conventions de dates et de maturités ;
3. ajouter des tests unitaires ;
4. améliorer la base de réplication ;
5. intégrer progressivement des données de marché.
