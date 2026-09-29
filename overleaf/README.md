# Overleaf Report

The `rapport_autocall.tex` file is self-contained and can be imported directly
into an Overleaf project. The `figures/` directory is intended for the manual
addition of validated vector-PDF exports.

The document is compatible with Overleaf's default pdfLaTeX compiler; no
compiler setting needs to be changed.

The report is independent of the notebook and is never generated automatically.
Numerical results should be updated only when a complete execution becomes the
new project reference.

Recommended workflow:

1. run the notebook from a clean kernel;
2. review all tables and figures;
3. replace `output/pdf/resultats_courants.pdf`;
4. update the figures and numerical results in Overleaf;
5. compile and proofread the final report.
