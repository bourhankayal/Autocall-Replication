"""Regenerate the French and English multi-seed stability figures.

The script reads the frozen REPORT export. It does not recalibrate a policy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.text import Text


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "output" / "hyperparameters" / "latest" / "tables" / "selected_stability_details.csv"
sys.path.insert(0, str(ROOT / "src"))

from autocall_replication.replication.hyperparameter_study import plot_seed_robustness  # noqa: E402


TRANSLATIONS = {
    "Full (avec binaires)": "Full (with digitals)",
    "Compromis": "Compromise",
    "Parcimonie": "Parsimony",
    "RMSE de validation (% du nominal)": "Validation RMSE (% of notional)",
    "Boîte : 25e–75e percentile": "Box: 25th–75th percentile",
    "Moustaches : limite à 1,5 × IQR": "Whiskers: 1.5 × IQR limit",
    "Trait orange : médiane": "Orange line: median",
    "Triangle vert : moyenne": "Green triangle: mean",
    "Point bleu : recalibration": "Blue point: recalibration",
    "Croix grise : non convergé, résultat provisoire":
        "Grey cross: non-converged, provisional result",
}


def save(figure: plt.Figure, language: str) -> None:
    output = ROOT / "overleaf" / "figures" / language / "multi_seed_stability.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight")
    plt.close(figure)


def translate(figure: plt.Figure) -> None:
    figure.canvas.draw()
    replacements = sorted(TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True)
    for artist in figure.findobj(match=Text):
        value = artist.get_text()
        for source, target in replacements:
            value = value.replace(source, target)
        artist.set_text(value)
    for axis in figure.axes[:2]:
        labels = []
        for label in axis.get_yticklabels():
            value = label.get_text()
            value = value.replace("Compromis", "Compromise")
            value = value.replace("Parcimonie", "Parsimony")
            labels.append(value)
        axis.set_yticks(axis.get_yticks())
        axis.set_yticklabels(labels)


def main() -> None:
    details = pd.read_csv(TABLE)
    save(plot_seed_robustness(details, nominal=100.0), "fr")
    english = plot_seed_robustness(details, nominal=100.0)
    translate(english)
    save(english, "en")
    print("French and English multi-seed stability figures regenerated.")


if __name__ == "__main__":
    main()
