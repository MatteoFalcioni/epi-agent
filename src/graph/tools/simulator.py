from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from langchain_core.tools import tool

from .models.sir import fit, rmse, sir, sir_incidence
from utils import load_incidence_from_csv

@tool
def simulate_sir(beta: float, gamma: float, S0: int, I0: int, R0: int, days: int) -> list:
    """
    Simulate the SIR model given the parameters.

    Args:
        beta (float): Infection rate.
        gamma (float): Recovery rate.
        S0 (int): Initial number of susceptible individuals.
        I0 (int): Initial number of infected individuals.
        R0 (int): Initial number of recovered individuals.
        days (int): Number of days to simulate.

    Returns:
        list: A list of dictionaries containing the daily counts of S, I, and R.
    """
    if days <= 0:
        raise ValueError("days must be > 0")

    n_population = S0 + I0 + R0
    t_span = (0, days)

    sol = solve_ivp(
        sir,
        t_span=t_span,
        y0=np.array([S0, I0, R0], dtype=float),
        args=(beta, gamma, n_population),
        t_eval=np.arange(*t_span, 1.0),
        method="Radau",
    )

    susceptible, infected, recovered = sol.y
    incidence = beta * susceptible * infected / n_population

    return [
        {
            "day": int(day),
            "S": float(s),
            "I": float(i),
            "R": float(r),
            "incidence": float(new_cases),
        }
        for day, s, i, r, new_cases in zip(
            sol.t, susceptible, infected, recovered, incidence, strict=False
        )
    ]


@tool
def fit_sir_from_csv(
    csv_path: str,
    population: int,
    column: str = "0",
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
    initial_beta: float = 1.0,
    initial_mu: float = 0.2,
    initial_detection_fraction: float = 0.1,
) -> dict:
    """
    Fit SIR model parameters to incidence data loaded from a CSV file.

    Returns fitted parameters and model-predicted incidence over the fitting window.
    """
    if population <= 0:
        raise ValueError("population must be > 0")
    if initial_detection_fraction <= 0:
        raise ValueError("initial_detection_fraction must be > 0")

    fit_incidence = load_incidence_from_csv(
        csv_path=csv_path,
        column=column,
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