import numpy as np
import pandas as pd
from scipy.optimize import root_scalar
from IPython.display import display


# ============================================================
# 1) Frequencies omega_n
# ============================================================

def omega0():
    """
    Positive root of coth(w) = w, i.e. 1/tanh(w) - w = 0.
    """
    f = lambda w: 1.0 / np.tanh(w) - w
    sol = root_scalar(f, bracket=[1e-10, 10.0], method="brentq")
    return sol.root


def omega_even(n):
    """
    For even n >= 2, omega_n is the unique root of cot(w) = -w
    on ((n-1)pi/2, npi/2).
    """
    a = (n - 1) * np.pi / 2 + 1e-10
    b = n * np.pi / 2 - 1e-10
    f = lambda w: 1.0 / np.tan(w) + w
    sol = root_scalar(f, bracket=[a, b], method="brentq")
    return sol.root


def omega_n(n):
    """
    omega_0 solves coth(w)=w
    omega_n = n*pi/2 for odd n
    omega_n solves cot(w) = -w for even n>=2
    """
    if n == 0:
        return omega0()
    if n % 2 == 1:
        return n * np.pi / 2
    return omega_even(n)


# ============================================================
# 2) Eigenvalues lambda_n
# ============================================================

def lambda_n(n):
    """
    Eigenvalues of the straddle kernel on [0,1]:
    lambda_n =  1/(2 omega_0^2) for n=0
    lambda_n = -1/(2 omega_n^2)  for n>=1
    """
    w = omega_n(n)
    if n == 0:
        return 1.0 / (2.0 * w**2)
    return -1.0 / (2.0 * w**2)


# ============================================================
# 3) Coefficients c_n from the spectral decomposition
# ============================================================

def c_n(n):
    """
    Coefficients in the kernel expansion:
    |x-y| = sum_n c_n phi_n(x) phi_n(y)
    """
    w = omega_n(n)
    if n == 0:
        return 1.0 / (w * np.cosh(w))**2
    if n % 2 == 1:
        return -4.0 / (n * np.pi)**2
    return -1.0 / (w * np.cos(w))**2


# ============================================================
# 4) Eigenfunctions on [0,1]
# ============================================================

def phi_n(n, x):
    """
    Orthonormal eigenfunctions of the straddle kernel on [0,1].
    x can be a scalar or a numpy array.
    """
    x = np.asarray(x)

    if n == 0:
        w = omega_n(0)
        return np.sqrt(2.0) / np.cosh(w) * np.cosh(w * (1.0 - 2.0 * x))

    if n % 2 == 1:
        return np.sqrt(2.0) * np.cos(n * np.pi * x)

    w = omega_n(n)
    return np.sqrt(2.0) / np.cos(w) * np.cos(w * (1.0 - 2.0 * x))


# ============================================================
# 5) Truncation error
# ============================================================

def build_spectral_table(N=20, tail_terms=10000):
    """
    Builds a dataframe with:
    n, lambda_n (x10^-3), omega_n, c_n, error_norm_L2

    error_norm_L2 is approximated by:
    sqrt(sum_{k=n+1}^∞ lambda_k^2)
    using a large finite tail.
    """
    lambdas = np.array([lambda_n(k) for k in range(tail_terms)], dtype=float)

    rows = []
    for n in range(N):
        err_l2 = np.sqrt(np.sum(lambdas[n + 1:] ** 2))

        rows.append({
            "n": n,
            "lambda_n (x10^-3)": lambda_n(n) * 1e3,
            "omega_n": omega_n(n),
            "c_n": c_n(n),
            "error_norm_L2": round(err_l2, 6),
        })

    return pd.DataFrame(rows)


# ============================================================
# 6) Display
# ============================================================

table = build_spectral_table(N=20, tail_terms=20000)

styled_table = (
    table.style
    .hide(axis="index")
    .format({
        "lambda_n (x10^-3)": "{:.6f}",
        "omega_n": "{:.9f}",
        "c_n": "{:.9f}",
        "error_norm_L2": "{:.6f}",
    })
    .set_properties(**{"text-align": "right"})
    .set_table_styles([
        {"selector": "th", "props": [("text-align", "center"), ("font-weight", "bold")]},
        {"selector": "table", "props": [("border-collapse", "collapse"), ("width", "100%")]},
        {"selector": "td, th", "props": [("padding", "6px 10px")]},
    ])
)

print(table.to_string(index=False))