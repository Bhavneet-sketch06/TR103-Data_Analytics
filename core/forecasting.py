"""
Forecasting: three candidate models, a rolling-origin backtest, and
prediction intervals.

    result = forecasting.run(df, "revenue", "Month", horizon=6)

Models
  * Seasonal naive: next period = same period one season ago. The baseline
    every other model has to beat.
  * Exponential smoothing (ETS): additive error, damped additive trend,
    additive seasonality.
  * SARIMA(1,1,1)(0,1,1,12): monthly only (a 52-week season is too slow and
    unstable to fit interactively).

Nothing here looks at the future: each backtest fold fits only on data
before its origin, and the incomplete last period is dropped so a half
month doesn't read as a collapse.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core import metrics

SEASON = {"Month": 12, "Week": 52}
FREQ = {"Month": "MS", "Week": "W-MON"}
METRICS = {"revenue": "Revenue", "profit": "Profit", "orders": "Orders", "units": "Units sold"}
NON_NEGATIVE = {"revenue", "orders", "units"}

NAIVE, ETS, SARIMA = "Seasonal naive", "Exponential smoothing", "SARIMA"
MODELS = [NAIVE, ETS, SARIMA]
Z80, Z95 = 1.2816, 1.9600


@dataclass
class Forecast:
    model: str
    index: pd.DatetimeIndex
    mean: np.ndarray
    lo80: np.ndarray
    hi80: np.ndarray
    lo95: np.ndarray
    hi95: np.ndarray

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame({"forecast": self.mean, "lo80": self.lo80, "hi80": self.hi80,
                             "lo95": self.lo95, "hi95": self.hi95}, index=self.index)


@dataclass
class Result:
    metric: str
    grain: str
    horizon: int
    series: pd.Series                       # complete periods used for fitting
    forecast: Forecast
    comparison: pd.DataFrame                # backtest scores per model
    chosen: str
    seasonal: bool
    notes: list[str] = field(default_factory=list)


# ----------------------------------------------------------
# Series
# ----------------------------------------------------------

def build_series(df: pd.DataFrame, metric: str, grain: str) -> tuple[pd.Series, bool]:
    """
    Metric per period with every period present (zeros where nothing sold).
    Returns (series, dropped_partial): the last period is dropped when the
    data stops more than a few days before it ends.
    """
    key = "units" if metric == "units" else metric
    y = metrics.kpi_series(df, key, grain).astype(float).fillna(0.0)
    y.index = pd.DatetimeIndex(y.index, freq=FREQ[grain])
    last_day = df["order_date"].max().normalize()
    period_end = y.index[-1] + (pd.offsets.MonthEnd(0) if grain == "Month" else pd.Timedelta(days=6))
    dropped = (period_end - last_day).days > (3 if grain == "Month" else 1)
    if dropped:
        y = y.iloc[:-1]
    return y, dropped


def can_be_seasonal(y: pd.Series, grain: str) -> bool:
    return len(y) >= 2 * SEASON[grain]


def models_for(grain: str) -> list[str]:
    return [NAIVE, ETS] + ([SARIMA] if grain == "Month" else [])


# ----------------------------------------------------------
# Models
# ----------------------------------------------------------

def _future_index(y: pd.Series, h: int) -> pd.DatetimeIndex:
    return pd.date_range(y.index[-1] + y.index.freq, periods=h, freq=y.index.freq)


def _seasonal_naive(y: pd.Series, h: int, m: int) -> Forecast:
    """Repeat the last season. Intervals widen with each full season ahead."""
    m = m if len(y) > m else 1
    values = y.to_numpy()
    mean = np.array([values[len(values) - m + (k % m)] for k in range(h)])
    errors = values[m:] - values[:-m]
    sigma = float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0
    spread = np.array([sigma * math.sqrt(math.ceil((k + 1) / m)) for k in range(h)])
    return Forecast(NAIVE, _future_index(y, h), mean,
                    mean - Z80 * spread, mean + Z80 * spread, mean - Z95 * spread, mean + Z95 * spread)


def _ets(y: pd.Series, h: int, m: int, seasonal: bool) -> Forecast:
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ETSModel(y, error="add", trend="add", damped_trend=True,
                         seasonal="add" if seasonal else None,
                         seasonal_periods=m if seasonal else None).fit(disp=False)
        pred = model.get_prediction(start=len(y), end=len(y) + h - 1)
        f80, f95 = pred.summary_frame(alpha=0.20), pred.summary_frame(alpha=0.05)
    return Forecast(ETS, _future_index(y, h), f80["mean"].to_numpy(),
                    f80["pi_lower"].to_numpy(), f80["pi_upper"].to_numpy(),
                    f95["pi_lower"].to_numpy(), f95["pi_upper"].to_numpy())


def _sarima(y: pd.Series, h: int, m: int, seasonal: bool) -> Forecast:
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = SARIMAX(y, order=(1, 1, 1), seasonal_order=(0, 1, 1, m) if seasonal else (0, 0, 0, 0),
                      enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        pred = fit.get_forecast(h)
        f80, f95 = pred.summary_frame(alpha=0.20), pred.summary_frame(alpha=0.05)
    return Forecast(SARIMA, _future_index(y, h), f80["mean"].to_numpy(),
                    f80["mean_ci_lower"].to_numpy(), f80["mean_ci_upper"].to_numpy(),
                    f95["mean_ci_lower"].to_numpy(), f95["mean_ci_upper"].to_numpy())


def fit_forecast(y: pd.Series, model: str, h: int, grain: str, seasonal: bool | None = None) -> Forecast:
    m = SEASON[grain]
    seasonal = can_be_seasonal(y, grain) if seasonal is None else seasonal
    if model == NAIVE:
        return _seasonal_naive(y, h, m if seasonal else 1)
    if model == ETS:
        return _ets(y, h, m, seasonal)
    if model == SARIMA:
        return _sarima(y, h, m, seasonal)
    raise ValueError(f"Unknown model: {model}")


def _clip(f: Forecast, metric: str) -> Forecast:
    if metric not in NON_NEGATIVE:
        return f
    c = lambda a: np.clip(a, 0, None)  # noqa: E731
    return Forecast(f.model, f.index, c(f.mean), c(f.lo80), c(f.hi80), c(f.lo95), c(f.hi95))


# ----------------------------------------------------------
# Backtest
# ----------------------------------------------------------

def backtest(y: pd.Series, model: str, h: int, grain: str, folds: int = 6,
             seasonal: bool | None = None) -> dict:
    """
    Rolling-origin evaluation. Fold k fits on y[:origin] only and forecasts
    the next h periods; errors from all folds are pooled.

    MASE divides by the in-sample error of the seasonal-naive forecast, so
    < 1 means better than "same as last season". MAPE is only reported when
    every actual is positive (it's meaningless around zero or for losses).
    """
    m = SEASON[grain]
    seasonal = can_be_seasonal(y, grain) if seasonal is None else seasonal
    season = m if seasonal else 1
    values = y.to_numpy()
    scale = float(np.mean(np.abs(values[season:] - values[:-season]))) or 1.0
    min_train = 2 * m if seasonal else max(8, h)
    origins = [o for o in range(len(y) - h - folds + 1, len(y) - h + 1) if o >= min_train]
    actual, predicted = [], []
    for origin in origins:
        train = y.iloc[:origin]
        try:
            f = fit_forecast(train, model, h, grain, seasonal)
        except Exception:
            continue
        actual.extend(values[origin:origin + h])
        predicted.extend(f.mean[: len(values[origin:origin + h])])
    if not actual:
        return {"model": model, "mape": None, "mase": None, "points": 0}
    actual, predicted = np.array(actual), np.array(predicted)
    errors = np.abs(actual - predicted)
    mape = float(np.mean(errors / actual)) if (actual > 0).all() else None
    return {"model": model, "mape": mape, "mase": float(np.mean(errors) / scale), "points": len(actual)}


def compare(y: pd.Series, h: int, grain: str, folds: int = 6, seasonal: bool | None = None) -> pd.DataFrame:
    rows = [backtest(y, model, h, grain, folds, seasonal) for model in models_for(grain)]
    table = pd.DataFrame(rows)
    return table.sort_values("mase", na_position="last").reset_index(drop=True)


# ----------------------------------------------------------
# One call for the page
# ----------------------------------------------------------

def run(df: pd.DataFrame, metric: str, grain: str, horizon: int, model: str = "Auto",
        folds: int = 6) -> Result:
    y, dropped = build_series(df, metric, grain)
    notes = []
    if dropped:
        notes.append(f"The last {grain.lower()} is incomplete, so it's left out of the model.")
    min_points = SEASON[grain] + 2
    if len(y) < min_points:
        raise ValueError(f"Forecasting by {grain.lower()} needs at least {min_points} complete "
                         f"{grain.lower()}s of history; this data has {len(y)}.")
    seasonal = can_be_seasonal(y, grain)
    if not seasonal:
        notes.append(f"Less than two years of history, so seasonality is ignored "
                     f"(it needs {2 * SEASON[grain]} {grain.lower()}s).")
    table = compare(y, horizon, grain, folds, seasonal)
    scored = table.dropna(subset=["mase"])
    chosen = model if model != "Auto" else (scored.iloc[0]["model"] if len(scored) else NAIVE)
    forecast = _clip(fit_forecast(y, chosen, horizon, grain, seasonal), metric)
    table["chosen"] = table["model"] == chosen
    return Result(metric, grain, horizon, y, forecast, table, chosen, seasonal, notes)
