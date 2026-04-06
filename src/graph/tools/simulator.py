from __future__ import annotations
from typing import TypedDict
from langchain_core.tools import tool
from langgraph.types import Command
from typing_extensions import Annotated, Literal, NotRequired
from datetime import datetime, timezone
from langchain_core.messages import ToolMessage
from langchain.tools import ToolRuntime
import json
from .models.sir import fit
from .utils import load_incidence_from_csv

DEFAULT_SIR_PARAMETERS = {
    "initial_beta": 1.0,
    "initial_mu": 0.2,
    "initial_detection_fraction": 0.1,
}

DEFAULT_SEIR_PARAMETERS = {
    "initial_beta": 1.0,
    "initial_gamma": 0.2,
    "initial_mu": 0.2,
    "initial_detection_fraction": 0.1,
}

DEFAULT_GAMMASIR_PARAMETERS = {
    "initial_beta": 1.0,
    "initial_infectious_period": 5.0,
    "initial_infectious_std": 3.0,
    "initial_detection_fraction": 0.1,
}

# model-specific parameter schemas for type safety and validation
class SIRParameters(TypedDict, total=False):
    initial_beta: NotRequired[float]
    initial_mu: NotRequired[float]
    initial_detection_fraction: NotRequired[float]

class SEIRParameters(TypedDict, total=False):
    initial_beta: NotRequired[float]
    initial_gamma: NotRequired[float]
    initial_mu: NotRequired[float]
    initial_detection_fraction: NotRequired[float]

# TODO: sistema questi parametri per il GAMMASIR, e controlla SEIR 
class GammaSIRParameters(TypedDict, total=False):
    initial_beta: NotRequired[float]
    initial_infectious_period: NotRequired[float]
    initial_infectious_std: NotRequired[float]
    initial_detection_fraction: NotRequired[float]

def _merge_with_defaults(defaults: dict[str, float], overrides: dict[str, float] | None) -> dict[str, float]:
    """
    Merge user-provided parameter overrides with model defaults.
    User overrides take precedence, but any missing fields are filled from defaults.
    In this way the agent can provide only a subset of parameters and rely on defaults for the rest.
    """
    merged = defaults.copy()
    if overrides:
        merged.update(overrides)
    return merged

def _get_model_spec(
    model: Literal["SIR", "SEIR", "GAMMASIR"],
    metric_name: Literal["rmse"],
    fit_incidence,
    model_parameters: SIRParameters | SEIRParameters | GammaSIRParameters | None,
):
    """
    Build a model-specific fitting specification used by `_fit_model_from_csv`.

    This helper centralizes all model-dependent pieces of the fitting pipeline so
    the public tools can stay thin and consistent.

    Args:
        model: Epidemiologic model identifier. Supported values are
            "SIR", "SEIR", and "GAMMASIR".
        metric_name: Optimization metric name. Currently only "rmse" is
            supported.
        fit_incidence: Preprocessed incidence series used for fitting.
            The first element is also used to derive an initial condition
            (I0 or E0/I0 depending on model).
        model_parameters: Optional per-model initial-guess overrides.
            Missing fields are filled from model defaults.

    Returns:
        dict: A model specification with these required keys:
            - incidence_fn: callable used by the optimizer to generate incidence.
            - metric_fn: objective callable (RMSE).
            - fixed_args: extra positional args passed to incidence_fn.
            - initial_guess: ordered parameter vector for optimization.
            - result_fields: tuple of names aligned 1:1 with optimum.x order.
            - derived_fields: callable(values)->dict for derived outputs (e.g., R0).

    Notes:
        - `result_fields` exists to map optimizer output vectors to stable,
          explicit names in the final JSON response.
        - `derived_fields` is separated so model-specific derived quantities
          (like R0 definitions) are defined in one place.
        - `initial_detection_fraction` must be > 0 for all models because it is
          used to derive initial conditions from observed incidence.

    Model parameter semantics:
        SIR:
            initial_beta, initial_mu, initial_detection_fraction
        SEIR:
            initial_beta, initial_gamma, initial_mu, initial_detection_fraction
        GAMMASIR:
            initial_beta, initial_infectious_period, initial_infectious_std,
            initial_detection_fraction
    """
    if metric_name != "rmse":
        raise ValueError(f"Unsupported metric: {metric_name}")

    from .models.models import gammasir_incidence, seir_incidence, sir_incidence
    from .models.sir import rmse

    if model == "SIR":
        params = _merge_with_defaults(DEFAULT_SIR_PARAMETERS, model_parameters)
        detection_fraction = params["initial_detection_fraction"]
        if detection_fraction <= 0:
            raise ValueError("initial_detection_fraction must be > 0")

        return {
            "incidence_fn": sir_incidence,
            "metric_fn": rmse,
            "fixed_args": (),
            "initial_guess": [
                params["initial_beta"],
                params["initial_mu"],
                fit_incidence[0] / detection_fraction,
                detection_fraction,
            ],
            "result_fields": ("beta", "mu", "I0", "detection_fraction"),
            "derived_fields": lambda values: {
                "R0": float(values[0] / values[1]) if values[1] > 0 else None,
            },
        }

    if model == "SEIR":
        params = _merge_with_defaults(DEFAULT_SEIR_PARAMETERS, model_parameters)
        detection_fraction = params["initial_detection_fraction"]
        if detection_fraction <= 0:
            raise ValueError("initial_detection_fraction must be > 0")

        return {
            "incidence_fn": seir_incidence,
            "metric_fn": rmse,
            "fixed_args": (),
            "initial_guess": [
                params["initial_beta"],
                params["initial_gamma"],
                params["initial_mu"],
                fit_incidence[0] / detection_fraction,
                fit_incidence[0] / detection_fraction,
                detection_fraction,
            ],
            "result_fields": ("beta", "gamma", "mu", "E0", "I0", "detection_fraction"),
            "derived_fields": lambda values: {
                "R0": float(values[0] / values[2]) if values[2] > 0 else None,
            },
        }

    params = _merge_with_defaults(DEFAULT_GAMMASIR_PARAMETERS, model_parameters)
    detection_fraction = params["initial_detection_fraction"]
    if detection_fraction <= 0:
        raise ValueError("initial_detection_fraction must be > 0")

    return {
        "incidence_fn": gammasir_incidence,
        "metric_fn": rmse,
        "fixed_args": (1 / 24.0,),
        "initial_guess": [
            params["initial_beta"],
            params["initial_infectious_period"],
            params["initial_infectious_std"],
            fit_incidence[0] / detection_fraction,
            detection_fraction,
        ],
        "result_fields": ("beta", "infectious_period", "infectious_std", "I0", "detection_fraction"),
        "derived_fields": lambda values: {
            "R0": float(values[0] * values[1]),
        },
    }

def _fit_model_from_csv(
    runtime: ToolRuntime,
    model: Literal["SIR", "SEIR", "GAMMASIR"],
    model_parameters: SIRParameters | SEIRParameters | GammaSIRParameters | None,
    csv_path: str,
    metric: Literal["rmse"] = "rmse",
    population: int = 800000,
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
) -> Command:
    """
    Shared fitting pipeline for all model-specific public tools.

    This is the core orchestrator that ties together data loading, model specification,
    optimization, and result formatting. All three public tools (fit_sir_from_csv,
    fit_seir_from_csv, fit_gammasir_from_csv) delegate to this single implementation
    to avoid code duplication.

    Args:
        runtime: Tool runtime context (used for message routing and call tracking).
        model: Model identifier ("SIR", "SEIR", or "GAMMASIR"). Determines which
            model spec and parameter schema will be used.
        model_parameters: Optional per-model initial guesses. Missing fields are
            filled from model defaults via _get_model_spec.
        csv_path: Path to CSV file with datetime index and "incidence" column.
        metric: Metric name for optimization. NOTE: Currently only "rmse" is supported.
        population: Total population (N) used in model dynamics.
        start_date: Optional date filter (inclusive). If provided, incidence data
            before this date is excluded.
        end_date: Optional date filter (inclusive). If provided, incidence data
            after this date is excluded.
        rolling_window: Window size for rolling average smoothing (default: 7 days).

    Returns:
        Command: Result command with two updates:
            - "messages": ToolMessage with JSON-serialized result_dict.
            - "simulations": list containing result_dict for state propagation.

    Result dict schema:
        - timestamp: ISO 8601 UTC timestamp of fitting.
        - model: Fitted model identifier.
        - csv_path: Input CSV path (for provenance tracking).
        - <model-specific fields>: e.g., beta, mu, I0, detection_fraction (SIR).
        - <derived fields>: e.g., R0 (from result_fields & derived_fields spec).
        - rmse: Optimizer metric value.
        - n_points: Number of data points used in fitting.
        - success: Boolean success flag from scipy.optimize.minimize.
        - message: Optimizer message string.
        - predicted_incidence: Fitted model incidence values.
        - observed_incidence: Preprocessed input incidence values.

    Workflow:
        1. Load and preprocess incidence data via load_incidence_from_csv.
        2. Fetch model spec (functions, parameters, result schema) via _get_model_spec.
        3. Run scipy optimizer with the incidence function and metric.
        4. Unpack optimizer result and compute derived quantities (e.g., R0).
        5. Return Command with results routed to state.
    """
    if population <= 0:
        raise ValueError("population must be > 0")
    if rolling_window <= 0:
        raise ValueError("rolling_window must be > 0")

    fit_incidence = load_incidence_from_csv(
        csv_path=csv_path,
        start_date=start_date,
        end_date=end_date,
        rolling_window=rolling_window,
    )

    spec = _get_model_spec(model, metric, fit_incidence, model_parameters)
    incidence_fn = spec["incidence_fn"]
    metric_fn = spec["metric_fn"]
    initial_guess = spec["initial_guess"]
    fixed_args = (population, *spec["fixed_args"])

    optimum = fit(
        incidence_fn,
        metric_fn,
        fit_incidence,
        initial_guess=initial_guess,
        fixed_args=fixed_args,
        verbose=False,
    )

    predicted_incidence = incidence_fn(optimum.x, (0.0, len(fit_incidence)), *fixed_args)
    fit_metric = metric_fn(optimum.x, (0.0, len(fit_incidence)), incidence_fn, fixed_args, fit_incidence)

    fitted_values = [float(value) for value in optimum.x]
    result_dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "csv_path": csv_path,
        **dict(zip(spec["result_fields"], fitted_values)),
        **spec["derived_fields"](fitted_values),
        "rmse": float(fit_metric),
        "n_points": int(len(fit_incidence)),
        "success": bool(optimum.success),
        "message": str(optimum.message),
        "predicted_incidence": [float(value) for value in predicted_incidence],
        "observed_incidence": [float(value) for value in fit_incidence],
    }

    return Command(
        update={
            "messages": [ToolMessage(content=json.dumps(result_dict), tool_call_id=runtime.tool_call_id)],
            "simulations": [result_dict],
        }
    )

@tool
def fit_sir_from_csv(
    runtime: ToolRuntime,
    csv_path: Annotated[str, "Path to the CSV file containing incidence data."],
    model_parameters: SIRParameters | None = None,
    metric: Annotated[Literal["rmse"], "The metric function to use for fitting."] = "rmse",
    population: Annotated[int, "Total population size (N) for the model."] = 800000,
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
) -> Command:
    """
    Fit SIR model parameters to incidence data loaded from a CSV file.

    Args:
    - model_parameters: Initial guesses for the SIR parameters.
    - csv_path: Path to the CSV file containing incidence data.
    - metric: The metric function to use for fitting (default: "rmse").
    - population: Total population size (N) for the model.
    - start_date: Optional start date to filter the CSV data (inclusive).
    - end_date: Optional end date to filter the CSV data (inclusive).
    - rolling_window: Window size for rolling average smoothing of incidence data (default: 7).
    """
    return _fit_model_from_csv(
        runtime=runtime,
        model="SIR",
        model_parameters=model_parameters,
        csv_path=csv_path,
        metric=metric,
        population=population,
        start_date=start_date,
        end_date=end_date,
        rolling_window=rolling_window,
    )

@tool
def fit_seir_from_csv(
    runtime: ToolRuntime,
    csv_path: Annotated[str, "Path to the CSV file containing incidence data."],
    model_parameters: SEIRParameters | None = None,
    metric: Annotated[Literal["rmse"], "The metric function to use for fitting."] = "rmse",
    population: Annotated[int, "Total population size (N) for the model."] = 800000,
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
) -> Command:
    """
    Fit SEIR model parameters to incidence data loaded from a CSV file.

    Args:
    - model_parameters: Initial guesses for the SEIR parameters.
    - csv_path: Path to the CSV file containing incidence data.
    - metric: The metric function to use for fitting (default: "rmse").
    - population: Total population size (N) for the model.
    - start_date: Optional start date to filter the CSV data (inclusive).
    - end_date: Optional end date to filter the CSV data (inclusive).
    - rolling_window: Window size for rolling average smoothing of incidence data (default: 7).
    """
    return _fit_model_from_csv(
        runtime=runtime,
        model="SEIR",
        model_parameters=model_parameters,
        csv_path=csv_path,
        metric=metric,
        population=population,
        start_date=start_date,
        end_date=end_date,
        rolling_window=rolling_window,
    )

@tool
def fit_gammasir_from_csv(
    runtime: ToolRuntime,
    csv_path: Annotated[str, "Path to the CSV file containing incidence data."],
    model_parameters: GammaSIRParameters | None = None,
    metric: Annotated[Literal["rmse"], "The metric function to use for fitting."] = "rmse",
    population: Annotated[int, "Total population size (N) for the model."] = 800000,
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
) -> Command:
    """
    Fit Gamma-SIR model parameters to incidence data loaded from a CSV file.

    Args:
    - model_parameters: Initial guesses for the Gamma-SIR parameters.
    - csv_path: Path to the CSV file containing incidence data.
    - metric: The metric function to use for fitting (default: "rmse").
    - population: Total population size (N) for the model.
    - start_date: Optional start date to filter the CSV data (inclusive).
    - end_date: Optional end date to filter the CSV data (inclusive).
    - rolling_window: Window size for rolling average smoothing of incidence data (default: 7).
    """
    return _fit_model_from_csv(
        runtime=runtime,
        model="GAMMASIR",
        model_parameters=model_parameters,
        csv_path=csv_path,
        metric=metric,
        population=population,
        start_date=start_date,
        end_date=end_date,
        rolling_window=rolling_window,
    )
