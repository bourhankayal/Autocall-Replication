"""Régénère les figures françaises dont certains libellés étaient restés en anglais.

Le script lit uniquement les tableaux CSV figés du calcul d'hyperparamètres.
Il ne relance aucune calibration ni simulation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "hyperparameters" / "latest"
TABLES = RUN / "tables"
OUTPUT = ROOT / "overleaf" / "figures" / "fr"
sys.path.insert(0, str(ROOT / "src"))

from autocall_replication.replication.hyperparameter_study import plot_regularization_grid  # noqa: E402


FAMILLES = {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"}
PENALITES = {"l0": "L0", "l1": "L1", "l2": "L2", "elastic_net": "Elastic Net"}


def table(nom: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / nom)


def sauvegarder(figure: plt.Figure, nom: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT / f"{nom}.pdf", bbox_inches="tight")
    figure.savefig(OUTPUT / f"{nom}.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def chemins_alpha() -> None:
    donnees = table("alpha_grid.csv")
    profils = table("alpha_profiles.csv")
    figure = plot_regularization_grid(
        donnees.loc[donnees["penalty"].ne("elastic_net")],
        profils,
        nominal=100.0,
        title="Méthode B — chemins d’alpha L0, L1 et L2 (Elastic Net : carte conjointe ci-dessus)",
    )
    sauvegarder(figure, "alpha_grid")


def audit_l0() -> None:
    donnees = table("l0_initialization_audit.csv")
    figure, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    for famille, groupe in donnees.groupby("family", sort=False):
        ordonne = groupe.sort_values("alpha_relative", ascending=False)
        axes[0].plot(
            ordonne["alpha_relative"],
            ordonne["warm_cold_support_jaccard"],
            marker="o",
            label=FAMILLES[famille],
        )
        axes[1].plot(
            ordonne["alpha_relative"],
            ordonne["n_distinct_supports"],
            marker="o",
            label=FAMILLES[famille],
        )
    for axe in axes:
        axe.set_xscale("log")
        axe.invert_xaxis()
        axe.set_xlabel("Alpha L0 relatif (fort → faible)")
        axe.grid(alpha=0.25)
        axe.legend()
    axes[0].set_title("Accord entre démarrage chaud et démarrage froid")
    axes[0].set_ylabel("Similarité de Jaccard des supports")
    axes[1].set_title("Multiplicité des solutions locales observées")
    axes[1].set_ylabel("Nombre de supports distincts")
    figure.suptitle("L0 — dépendance à l’initialisation")
    figure.tight_layout()
    sauvegarder(figure, "l0_initialization_audit")


def carte_filtres() -> None:
    donnees = table("regularization_filter_flow.csv")
    ordre_etapes = list(dict.fromkeys(donnees["stage"]))
    ordre_lignes = list(dict.fromkeys(zip(donnees["family"], donnees["penalty"])))
    pivot = donnees.pivot(index=["family", "penalty"], columns="stage", values="remaining")
    pivot = pivot.reindex(index=pd.MultiIndex.from_tuples(ordre_lignes), columns=ordre_etapes)
    valeurs = pivot.to_numpy(dtype=float)
    figure, axe = plt.subplots(figsize=(13, 5.8))
    image = axe.imshow(
        valeurs,
        aspect="auto",
        cmap="YlGn",
        vmin=0,
        vmax=max(1.0, float(np.nanmax(valeurs))),
    )
    axe.set_xticks(range(len(ordre_etapes)), ordre_etapes, rotation=35, ha="right")
    axe.set_yticks(
        range(len(ordre_lignes)),
        [f"{FAMILLES[famille]} / {PENALITES[penalite]}" for famille, penalite in ordre_lignes],
    )
    seuil = np.nanmax(valeurs) * 0.55
    for ligne in range(valeurs.shape[0]):
        for colonne in range(valeurs.shape[1]):
            if np.isfinite(valeurs[ligne, colonne]):
                axe.text(
                    colonne,
                    ligne,
                    f"{int(valeurs[ligne, colonne])}",
                    ha="center",
                    va="center",
                    color="white" if valeurs[ligne, colonne] > seuil else "black",
                    fontsize=9,
                )
    axe.set_title("Nombre de solutions restantes après chaque filtre")
    figure.colorbar(image, ax=axe, label="Solutions restantes")
    figure.tight_layout()
    sauvegarder(figure, "regularization_filter_map")


def libelle_politique(cle: str) -> str:
    penalite, objectif, profil = str(cle).split("|")
    objectifs = {"constrained_es": "ES contrainte", "penalized_es": "ES pénalisée"}
    profils = {
        "compromise": "compromis",
        "rmse_priority": "priorité RMSE",
        "es_priority": "priorité ES",
    }
    return f"{PENALITES[penalite]} | {objectifs[objectif]} | {profils[profil]}"


def precision_importance_sampling() -> None:
    resume = table("importance_sampling_grid.csv").sort_values(["candidate_index", "family"])
    descriptions = {
        ligne.candidate_index: str(ligne.mixture_description).replace(" — ", "\n").replace(" ; ", "\n")
        for ligne in resume.drop_duplicates("candidate_index").itertuples()
    }
    politiques = table("importance_sampling_policy_summary.csv")
    for famille, groupe in politiques.loc[politiques["candidate_index"].ge(0)].groupby("family", sort=False):
        matrice = groupe.pivot(
            index="policy_key", columns="candidate_index", values="precision_ratio_to_mc"
        ).sort_index()
        figure, axe = plt.subplots(figsize=(11, max(6.0, 0.35 * len(matrice) + 2.5)))
        valeurs = matrice.to_numpy(dtype=float)
        image = axe.imshow(
            valeurs,
            aspect="auto",
            cmap="RdYlGn_r",
            vmin=0,
            vmax=max(2.0, float(np.nanmax(valeurs))),
        )
        axe.set_yticks(np.arange(len(matrice)), [libelle_politique(cle) for cle in matrice.index], fontsize=8)
        retenu = resume.loc[
            resume["family"].eq(famille) & resume["recommended"].astype(bool), "candidate_index"
        ]
        choix = int(retenu.iloc[0]) if len(retenu) else -999
        axe.set_xticks(
            np.arange(len(matrice.columns)),
            [
                descriptions[int(valeur)] + ("\n★ retenu" if int(valeur) == choix else "")
                for valeur in matrice.columns
            ],
            fontsize=8,
        )
        axe.set_title(f"{FAMILLES[famille]} — précision IS/MC par portefeuille d’ES figé")
        axe.set_xlabel("Mélange d’importance sampling testé · déplacement : part simulée")
        figure.colorbar(
            image,
            ax=axe,
            label="Écart-type IS / écart-type MC (plus faible = plus précis)",
        )
        figure.tight_layout()
        sauvegarder(figure, f"importance_policy_precision_{famille}")


def main() -> None:
    plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 180, "font.size": 10})
    chemins_alpha()
    audit_l0()
    carte_filtres()
    precision_importance_sampling()
    print(f"Figures françaises mises à jour dans {OUTPUT}")


if __name__ == "__main__":
    main()
