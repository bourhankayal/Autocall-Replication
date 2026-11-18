# Overleaf Report

The historical `rapport_autocall.tex` file is the V0. The new
`rapport_autocall_v1.tex` is a separate, complete research-report draft; the V0
is intentionally preserved. `V1_HANDOFF.md` lists the remaining notebook work,
the displays still worth creating and the exact vector-PDF files to upload.

Both TeX files are self-contained and can be imported directly into an Overleaf
project. The `figures/` directory is intended for validated vector-PDF exports.

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
