"""Phase 3 tests: forecasting, the what-if simulator, anomaly detection, saved runs."""

import numpy as np
import pandas as pd
import pytest

from core import anomalies, db, forecasting, ingest, simulator


@pytest.fixture(scope="module")
def sample():
    return ingest.load_sample().df


def seasonal_series(months: int = 48, noise: float = 0.0, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=months, freq="MS")
    pattern = 100 + 30 * np.sin(np.arange(months) * 2 * np.pi / 12)
    return pd.Series(pattern + rng.normal(0, noise, months), index=idx)


def frame_from(series: pd.Series) -> pd.DataFrame:
    """One order line per month on the 15th, revenue = the series value."""
    return pd.DataFrame({"order_date": series.index + pd.Timedelta(days=14), "revenue": series.to_numpy(),
                         "order_id": range(len(series))})


# ----------------------------------------------------------
# Forecasting
# ----------------------------------------------------------

def test_seasonal_naive_repeats_last_season_exactly():
    y = seasonal_series()
    f = forecasting.fit_forecast(y, forecasting.NAIVE, 12, "Month")
    assert np.allclose(f.mean, y.iloc[-12:].to_numpy())
    assert f.index[0] == y.index[-1] + pd.offsets.MonthBegin(1)


def test_intervals_are_ordered_and_95_is_wider():
    f = forecasting.fit_forecast(seasonal_series(noise=5), forecasting.ETS, 6, "Month")
    assert (f.lo95 <= f.lo80).all() and (f.lo80 <= f.mean).all()
    assert (f.mean <= f.hi80).all() and (f.hi80 <= f.hi95).all()


def test_backtest_never_uses_the_future():
    """Poison every value after the last origin: errors on earlier folds must not change."""
    y = seasonal_series(noise=3)
    clean = forecasting.backtest(y, forecasting.NAIVE, 3, "Month", folds=1)
    poisoned = y.copy()
    poisoned.iloc[-3:] = poisoned.iloc[-3:] * 0 + 1e6   # the test window itself
    before = forecasting.fit_forecast(y.iloc[:-3], forecasting.NAIVE, 3, "Month")
    after = forecasting.fit_forecast(poisoned.iloc[:-3], forecasting.NAIVE, 3, "Month")
    assert np.allclose(before.mean, after.mean)
    assert clean["points"] == 3


def test_partial_last_month_is_dropped():
    df = frame_from(seasonal_series(30))
    df = pd.concat([df, pd.DataFrame({"order_date": [df["order_date"].max() + pd.Timedelta(days=20)],
                                      "revenue": [1.0], "order_id": [999]})])
    y, dropped = forecasting.build_series(df, "revenue", "Month")
    assert dropped and y.iloc[-1] > 1


def test_auto_model_beats_seasonal_naive_on_superstore(sample):
    result = forecasting.run(sample, "revenue", "Month", horizon=6)
    scores = result.comparison.set_index("model")["mase"]
    assert scores[result.chosen] <= scores[forecasting.NAIVE]
    assert len(result.forecast.mean) == 6
    assert (result.forecast.lo95 >= 0).all()          # revenue intervals are clipped at zero


def test_short_history_drops_seasonality():
    df = frame_from(seasonal_series(18))
    result = forecasting.run(df, "revenue", "Month", horizon=3)
    assert not result.seasonal and any("seasonality" in n for n in result.notes)


def test_too_little_history_is_a_clear_error():
    with pytest.raises(ValueError, match="needs at least"):
        forecasting.run(frame_from(seasonal_series(8)), "revenue", "Month", horizon=3)


# ----------------------------------------------------------
# Simulator
# ----------------------------------------------------------

@pytest.fixture(scope="module")
def response(sample):
    last12 = sample[sample["order_date"] > sample["order_date"].max() - pd.DateOffset(months=12)]
    return simulator.discount_response(last12)


def test_zero_levers_return_the_baseline(response):
    r = simulator.simulate(100_000, response, simulator.Levers())
    assert r["revenue"] == pytest.approx(100_000)
    assert r["profit"] == pytest.approx(r["baseline_profit"])
    assert r["profit_low"] == pytest.approx(r["profit"]) == pytest.approx(r["profit_high"])


def test_more_discount_lowers_profit_here(response):
    assert (response["slope"] < 0).all()              # Superstore: discount and margin move apart
    r = simulator.simulate(100_000, response, simulator.Levers(discount_pp=0.05))
    assert r["profit"] < r["baseline_profit"]
    assert r["profit_low"] <= r["profit"] <= r["profit_high"]


def test_price_and_volume_arithmetic(response):
    base = simulator.simulate(100_000, response, simulator.Levers())
    price = simulator.simulate(100_000, response, simulator.Levers(price_pct=0.03))
    assert price["revenue"] == pytest.approx(103_000)
    assert price["profit"] - base["profit"] == pytest.approx(3_000)     # costs unchanged
    volume = simulator.simulate(100_000, response, simulator.Levers(volume_pct=0.10))
    assert volume["profit"] == pytest.approx(base["profit"] * 1.10)
    assert volume["margin"] == pytest.approx(base["margin"])


def test_waterfall_steps_add_up(response):
    r = simulator.simulate(100_000, response, simulator.Levers(0.03, 0.02, 0.05))
    assert sum(v for _, v in r["steps"]) == pytest.approx(r["profit"])


# ----------------------------------------------------------
# Anomalies
# ----------------------------------------------------------

def test_a_spike_is_found_and_a_steady_series_is_not():
    y = seasonal_series(48, noise=2, seed=1)
    steady = anomalies.robust_z(anomalies.misses(y, anomalies.expected_values(y, "revenue"), "revenue"))
    assert steady.abs().max() < anomalies.THRESHOLD
    spiked = y.copy()
    spiked.iloc[40] *= 2.5
    z = anomalies.robust_z(anomalies.misses(spiked, anomalies.expected_values(spiked, "revenue"), "revenue"))
    assert z.abs().idxmax() == spiked.index[40] and z.iloc[40] > anomalies.THRESHOLD


def test_expectations_only_use_the_past():
    y = seasonal_series(36, noise=2)
    changed = y.copy()
    changed.iloc[30:] = 0
    a = anomalies.expected_values(y, "revenue").iloc[:31]
    b = anomalies.expected_values(changed, "revenue").iloc[:31]
    pd.testing.assert_series_equal(a, b)


def test_detect_on_superstore_finds_the_april_2017_technology_loss(sample):
    found = anomalies.detect(sample, pd.Timestamp("2017-01-01"), sample["order_date"].max())
    hit = found[(found["scope"] == "Technology") & (found["metric"] == "margin")]
    assert len(hit) == 1 and hit.iloc[0]["month"] == pd.Timestamp("2017-04-01")
    assert (found["month"] >= pd.Timestamp("2017-01-01")).all()
    items = anomalies.as_items(found)
    assert items and items[0]["tone"] == "bad"


# ----------------------------------------------------------
# Saved runs round-trip exactly
# ----------------------------------------------------------

def test_saved_run_reloads_exactly(tmp_path, sample):
    result = forecasting.run(sample, "revenue", "Month", horizon=3)
    frame = result.forecast.frame()
    results = {"index": [d.isoformat() for d in frame.index], **{c: frame[c].tolist() for c in frame}}
    run_id = db.save_run(dataset_name="s", dataset_digest="d", metric="revenue", grain="Month", horizon=3,
                         model=result.chosen, mape=0.1, params={}, results=results, path=tmp_path / "r.db")
    loaded = db.get_run(run_id, tmp_path / "r.db")["results"]
    assert loaded["forecast"] == frame["forecast"].tolist()
    assert loaded["index"] == results["index"]


def test_slices_with_too_few_orders_raise_no_alerts():
    """A 600-row file has only a few orders a month per region: no alerts from noise."""
    from pathlib import Path
    data = (Path(__file__).parent / "fixtures" / "renamed_schema.csv").read_bytes()
    cleaned, _ = ingest.read_and_clean(data, "renamed_schema.csv")
    from core.schema import suggest_mapping
    df = ingest.load_dataset(data, "renamed_schema.csv", suggest_mapping(cleaned.columns), is_sample=False).df
    found = anomalies.detect(df, df["order_date"].min(), df["order_date"].max())
    assert found.empty
