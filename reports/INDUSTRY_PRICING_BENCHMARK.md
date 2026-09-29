# Trois prix et benchmark public des produits structurés

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | La réplication conditionnelle fournit désormais un coût et un P&L, mais ces nombres ne permettaient pas encore de situer le projet face aux pratiques documentées. |
| **Problème** | Le P&L réel des desks n'est pas public et ne peut pas être comparé directement à notre erreur de réplication. |
| **Méthode** | Séparation entre benchmark technique interne, trois niveaux de prix et benchmark public de l'écart prix d'émission–valeur estimée. |
| **Modifications** | Ajout d'un module reproductible, de deux graphiques, d'une section dédiée dans le notebook et de tests économiques. |
| **Résultats** | Le notebook mesure maintenant l'amélioration de risque par rapport au non-couvert et à `calls_puts`, puis situe le coussin commercial dans un échantillon public clairement délimité. |

## 1. Pourquoi deux benchmarks sont nécessaires

Une réduction de risque et une marge de prix ne répondent pas à la même
question :

- le **benchmark technique** mesure si la réplication réduit le RMSE et
  l'Expected Shortfall 97,5 % ;
- le **benchmark économique** mesure l'écart entre le prix facturé et la valeur
  théorique du passif.

Les publications des émetteurs ne donnent pas le P&L de couverture réalisé par
leurs desks. Elles donnent en revanche une valeur initiale estimée, souvent
inférieure au prix d'émission. Présenter cet écart comme un bénéfice de trading
serait incorrect : il agrège notamment distribution, structuration, coûts de
couverture et profits projetés.

## 2. Les trois prix

Pour une stratégie donnée, le notebook construit :

```text
prix théorique = valeur Monte-Carlo du passif autocall

prix minimal de couverture
    = prime utilisée dans la simulation - P&L terminal moyen

prix commercial indicatif
    = prix minimal de couverture + marge cible explicite
```

Le prix minimal annule uniquement le **P&L moyen estimé**. Il ne garantit ni un
P&L positif sur chaque trajectoire ni la couverture des queues de distribution.
La marge commerciale vaut 1 % du nominal par défaut dans le notebook ; c'est
une hypothèse modifiable, pas une observation de marché.

## 3. Mesure de l'amélioration technique

Pour chaque famille, pénalité et profil :

```text
amélioration vs non-couvert = 1 - risque résiduel / risque brut

amélioration vs calls_puts = 1 - risque résiduel candidat
                                  / risque résiduel calls_puts comparable
```

Les comparaisons `full` / `calls_puts` sont appariées sur la pénalité et le
profil. Une valeur positive indique une réduction du risque ; une valeur
négative indique une détérioration. Les deux critères publiés sont le RMSE et
l'ES 97,5 %, car une amélioration moyenne peut masquer une queue plus mauvaise.

## 4. Échantillon public

Le module contient quatre exemples documentaires SEC récents : JPMorgan,
Barclays, Morgan Stanley et Goldman Sachs. Pour les fourchettes de valeur, le
graphe conserve une borne basse et une borne haute de l'écart plutôt que de
masquer l'incertitude derrière un seul point.

Sources :

- [JPMorgan — Auto Callable Notes](https://www.sec.gov/Archives/edgar/data/19617/000121390025028272/ea0236912-01_424b2.htm)
- [Barclays — Auto-Callable Notes](https://www.sec.gov/Archives/edgar/data/312070/000191870425019389/form424b2.htm)
- [Morgan Stanley — Jump Notes with Auto-Callable Feature](https://www.sec.gov/Archives/edgar/data/895421/000183988226023540/ms15872_424b2-15430.htm)
- [Goldman Sachs — Autocallable Contingent Coupon Notes](https://www.sec.gov/Archives/edgar/data/0000886982/000095017025052435/amznco11_auto_prelim.htm)

Cet échantillon est petit, non aléatoire et composé de structures différentes.
Il fournit un **ordre de grandeur public**, pas une moyenne du secteur.

## 5. Lecture des résultats

Le notebook produit deux graphiques :

1. réduction du RMSE et de l'ES 97,5 % par rapport à l'autocall non couvert ;
2. comparaison du coussin commercial indicatif aux écarts publics observés.

Il faut conclure séparément :

- « notre méthode réduit le risque de X % » à partir du premier graphique ;
- « notre coussin de prix vaut Y % et se situe à tel niveau de l'échantillon »
  à partir du second.

On ne doit pas conclure « notre desk gagne plus ou moins que JPMorgan » : la
donnée publique nécessaire à cette affirmation n'existe pas.

## 6. Fichiers et validation

- `replication/industry_benchmark.py` : calculs et données documentaires ;
- `notebooks/autocall_research.ipynb` : tables, explications et graphiques ;
- `tests/test_industry_benchmark.py` : ordre des prix, calculs relatifs et
  garde-fous d'interprétation.

