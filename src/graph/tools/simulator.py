from __future__ import annotations

import numpy as np
from langchain_core.tools import tool
from .models.sir import fit, rmse, sir_incidence
from .utils import load_incidence_from_csv

@tool
def fit_sir_from_csv(
    population: int,
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
    initial_beta: float = 1.0,
    initial_mu: float = 0.2,
    initial_detection_fraction: float = 0.1,
) -> dict:
    """
    Fit SIR model parameters to incidence data loaded from a (hardcoded) CSV file.

    Args:
    - population: total population size (N) for the SIR model.
    - start_date: optional start date to filter the CSV data (inclusive).
    - end_date: optional end date to filter the CSV data (inclusive).
    - rolling_window: window size for rolling average smoothing of incidence data (default: 7).
    - initial_beta: initial guess for the infection rate parameter beta (default: 1.0).
    - initial_mu: initial guess for the recovery rate parameter mu (default: 0.2).
    - initial_detection_fraction: initial guess for the fraction of infections that are detected (default: 0.1).

    Returns:
        A dictionary containing the fitted parameters (beta, mu, I0, detection_fraction), R0, RMSE of the fit, 
        number of data points used, success flag, optimization message, and the predicted vs observed incidence values.
    """
    if population <= 0:
        raise ValueError("population must be > 0")
    if initial_detection_fraction <= 0:
        raise ValueError("initial_detection_fraction must be > 0")
    
    # harcoded csv path for the moment (check utils, it's harcoded to 'data/Accessi in PS 2022-2026 con FLU - aggiornato al 8-03-2026.csv')
    fit_incidence = load_incidence_from_csv(
        column=0,   # hardcoded column to let llm choose less stuff
        start_date=start_date,
        end_date=end_date,
        rolling_window=rolling_window,
    )

    initial_i0 = max(fit_incidence[0] / initial_detection_fraction, 1e-8)
    initial_guess = np.array(
        [initial_beta, initial_mu, initial_i0, initial_detection_fraction], dtype=float
    )

    optimum = fit(
        sir_incidence,
        rmse,
        fit_incidence,
        initial_guess=initial_guess,
        fixed_args=(population,),
        verbose=False,
    )

    beta, mu, i0, detection_fraction = optimum.x
    predicted_incidence = sir_incidence(optimum.x, (0.0, len(fit_incidence)), population)
    fit_rmse = rmse(optimum.x, (0.0, len(fit_incidence)), sir_incidence, (population,), fit_incidence)

    return {
        "beta": float(beta),
        "mu": float(mu),
        "I0": float(i0),
        "detection_fraction": float(detection_fraction),
        "R0": float(beta / mu) if mu > 0 else None,
        "rmse": float(fit_rmse),
        "n_points": int(len(fit_incidence)),
        "success": bool(optimum.success),
        "message": str(optimum.message),
        "predicted_incidence": [float(value) for value in predicted_incidence],
        "observed_incidence": [float(value) for value in fit_incidence],
    }