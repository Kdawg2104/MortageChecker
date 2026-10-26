import time

import numpy as np
import pytest

from engine.projection import NEVER
from engine.scenarios import Household, run_scenario
from engine.simulation import (
    CASH_RATE_FLOOR,
    HISTORY_PATH,
    History,
    SimulationSettings,
    bootstrap_indices,
    job_loss_multiplier,
    load_history,
    months_out_of_work,
    run_simulation,
    simulate_economy,
)

HOUSEHOLD = Household(
    incomes=(110_000, 75_000),
    has_help=(False, True),
    annual_rate=6.2,
    monthly_expenses=4_760,
    other_debts=200,
    loan=650_000,
    term_years=30,
    starting_savings=30_000,
)


def synthetic_history(n: int = 60, seed: int = 1) -> History:
    """A small made-up history, so these tests don't depend on the downloaded data."""
    rng = np.random.default_rng(seed)
    months = np.array([f"{2000 + i // 12}-{i % 12 + 1:02d}" for i in range(n)])
    return History(
        months=months,
        cash_rate_change=rng.choice([-0.25, 0.0, 0.0, 0.25], size=n),
        cpi_growth=rng.normal(0.002, 0.002, size=n),
        wage_growth=rng.normal(0.003, 0.001, size=n),
    )


def flat_history(n: int = 60) -> History:
    months = np.array([f"{2000 + i // 12}-{i % 12 + 1:02d}" for i in range(n)])
    zeros = np.zeros(n)
    return History(months, zeros, zeros, zeros)


def test_blocks_are_consecutive_months():
    idx = bootstrap_indices(60, n_sims=200, months=36, block_length=12, rng=np.random.default_rng(0))
    assert idx.shape == (200, 36)
    within_block = np.diff(idx.reshape(200, 3, 12), axis=-1)
    assert (within_block == 1).all()
    assert idx.min() >= 0 and idx.max() < 60


def test_horizon_not_a_multiple_of_block():
    idx = bootstrap_indices(60, n_sims=5, months=30, block_length=12, rng=np.random.default_rng(0))
    assert idx.shape == (5, 30)


def test_series_are_sampled_from_the_same_months():
    history = synthetic_history()
    paths = simulate_economy(history, 100, 24, 4.0, 6.0, 12, np.random.default_rng(3))
    assert paths.cpi_growth == pytest.approx(history.cpi_growth[paths.indices])
    assert paths.wage_growth == pytest.approx(history.wage_growth[paths.indices])


def test_same_seed_same_result_different_seed_different():
    history = synthetic_history()
    a = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=300, seed=7), history)
    b = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=300, seed=7), history)
    c = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=300, seed=8), history)
    assert np.array_equal(a.projection.savings, b.projection.savings)
    assert not np.array_equal(a.projection.savings, c.projection.savings)


def test_cash_rate_never_below_floor():
    falling = History(np.array([f"2000-{m:02d}" for m in range(1, 13)]), np.full(12, -1.0), np.zeros(12), np.zeros(12))
    paths = simulate_economy(falling, 50, 60, 4.0, 6.0, 12, np.random.default_rng(0))
    assert paths.cash_rate.min() == pytest.approx(CASH_RATE_FLOOR)


def test_mortgage_rate_keeps_the_lender_margin():
    paths = simulate_economy(synthetic_history(), 200, 60, 4.0, 6.2, 12, np.random.default_rng(0))
    above_floor = paths.cash_rate > CASH_RATE_FLOOR
    assert (paths.mortgage_rate - paths.cash_rate)[above_floor] == pytest.approx(2.2)


def test_flat_history_matches_phase_2_projection():
    result = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=20, horizon_years=5), flat_history())
    base = run_scenario(HOUSEHOLD, (), 60)
    for path in range(20):
        assert result.projection.savings[path] == pytest.approx(base.savings)


def test_no_job_losses_when_chance_is_zero():
    working = job_loss_multiplier(np.random.default_rng(0), 100, 2, 120, 0.0, 3)
    assert (working == 1).all()


def test_one_job_loss_lasts_exactly_duration():
    starts = np.zeros((1, 1, 24), dtype=bool)
    starts[0, 0, 5] = True
    out = months_out_of_work(starts, duration=3)
    assert out[0, 0].nonzero()[0].tolist() == [5, 6, 7]


def test_job_loss_rate_roughly_matches_annual_chance():
    working = job_loss_multiplier(np.random.default_rng(0), 20_000, 1, 12, 0.03, 1)
    lost_a_job = (working == 0).any(axis=-1).mean()
    assert lost_a_job == pytest.approx(0.03, abs=0.005)


def test_job_loss_raises_risk():
    history = synthetic_history()
    calm = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=500), history)
    risky = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=500, include_job_loss=True, job_loss_chance=0.2), history)
    assert risky.chance_of_stress >= calm.chance_of_stress
    assert float(risky.projection.lowest_savings.mean()) < float(calm.projection.lowest_savings.mean())


def test_summaries_are_sensible():
    result = run_simulation(HOUSEHOLD, 4.0, SimulationSettings(n_sims=500, include_job_loss=True), synthetic_history())
    for chance in (result.chance_of_stress, result.chance_of_severe_stress, result.chance_savings_run_out):
        assert 0 <= chance <= 1
    assert result.chance_of_severe_stress <= result.chance_of_stress
    for bands in (result.savings_bands, result.rate_bands, result.repayment_bands):
        stacked = np.stack([bands[p] for p in (5, 25, 50, 75, 95)])
        assert (np.diff(stacked, axis=0) >= -1e-9).all()
    assert result.worst_summary["lowest_savings"] <= float(np.median(result.projection.lowest_savings))
    assert len(result.worst_paths) == 25


def test_median_run_out_month_only_counts_paths_that_run_out():
    broke = Household((60_000,), (False,), 6.2, 4_500, 0, 600_000, 30, 5_000)
    result = run_simulation(broke, 4.0, SimulationSettings(n_sims=200), synthetic_history())
    assert result.chance_savings_run_out == 1.0
    months = result.projection.first_negative_savings_month
    assert (months != NEVER).all()
    assert result.median_months_until_run_out == float(np.median(months))


def test_real_history_file_loads():
    history = load_history(HISTORY_PATH)
    assert len(history) > 300
    assert history.months[0] <= "1997-10"
    for series in (history.cash_rate_change, history.cpi_growth, history.wage_growth):
        assert np.isfinite(series).all()
    # consecutive months, no gaps
    years, months = np.array([m.split("-") for m in history.months], dtype=int).T
    assert (np.diff(years * 12 + months) == 1).all()


def test_full_size_run_is_fast():
    start = time.perf_counter()
    run_simulation(HOUSEHOLD, 4.6, SimulationSettings(n_sims=5_000, horizon_years=10, include_job_loss=True))
    assert time.perf_counter() - start < 5
