"""Monte Carlo simulation of interest rates, inflation and wages from Australian history.

Instead of testing one guess ("what if rates rise 2%?"), we build thousands of possible
futures by re-sampling real history in 12-month blocks (a "block bootstrap"), then run every
future through the same month-by-month projection as the stress scenarios (projection.py).

Everything is vectorised with numpy: all simulated futures are handled at once.
The history comes from data/processed/history.csv, built by scripts/update_data.py.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from engine.projection import NEVER, ProjectionInputs, ProjectionResult, project
from engine.scenarios import Household, run_scenario

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "history.csv"

# History windows. The Wage Price Index (ABS 6345.0) starts in Sep 1997, so aligned history
# for all three series starts in Oct 1997.
HISTORY_WINDOWS = {
    "Since 1997 (inflation targeting; WPI starts Sep 1997)": "1997-10",
    "Since 2010": "2010-01",
}
DEFAULT_WINDOW = next(iter(HISTORY_WINDOWS))

# Lowest cash rate target the RBA has ever set: 0.10% (Nov 2020 to May 2022, RBA table A2).
CASH_RATE_FLOOR = 0.10

DEFAULT_SIMS = 5_000
HORIZON_CHOICES = (5, 10)          # years
DEFAULT_HORIZON_YEARS = 10
DEFAULT_BLOCK = 12                 # months per sampled block
DEFAULT_SEED = 42

# PLACEHOLDER assumptions (editable in the UI): chance each earner loses their job in a year,
# and how many months they go without income when it happens.
JOB_LOSS_ANNUAL_CHANCE = 0.03
JOB_LOSS_MONTHS = 3

PERCENTILES = (5, 25, 50, 75, 95)
WORST_SHARE = 0.05                 # "worst 5%" of futures, ranked by lowest savings


@dataclass(frozen=True)
class History:
    """Aligned monthly history: each position is the same calendar month in every array."""

    months: np.ndarray             # "YYYY-MM" strings
    cash_rate_change: np.ndarray   # percentage points
    cpi_growth: np.ndarray         # monthly, as a fraction (0.003 = 0.3%)
    wage_growth: np.ndarray        # monthly, as a fraction

    def __len__(self) -> int:
        return len(self.months)

    def since(self, start: str) -> "History":
        """Only the months from `start` ("YYYY-MM") onwards."""
        keep = self.months >= start
        return History(self.months[keep], self.cash_rate_change[keep], self.cpi_growth[keep], self.wage_growth[keep])


def load_history(path: Path = HISTORY_PATH) -> History:
    """Read data/processed/history.csv. The app never downloads data itself."""
    frame = pd.read_csv(path, dtype={"month": str})
    return History(
        months=frame["month"].to_numpy(),
        cash_rate_change=frame["cash_rate_change"].to_numpy(dtype=float),
        cpi_growth=frame["cpi_growth"].to_numpy(dtype=float),
        wage_growth=frame["wage_growth"].to_numpy(dtype=float),
    )


def bootstrap_indices(n_history: int, n_sims: int, months: int, block_length: int, rng: np.random.Generator) -> np.ndarray:
    """Which history month each simulated month copies, shape (n_sims, months).

    Each simulated future is stitched together from random blocks of `block_length`
    CONSECUTIVE historical months. Using the same index for every series keeps their real
    relationship (e.g. rate rises tending to come with high inflation).
    """
    if block_length > n_history:
        raise ValueError("The history window is shorter than one block")
    n_blocks = -(-months // block_length)  # ceiling division
    starts = rng.integers(0, n_history - block_length + 1, size=(n_sims, n_blocks))
    indices = starts[..., None] + np.arange(block_length)
    return indices.reshape(n_sims, -1)[:, :months]


@dataclass(frozen=True)
class EconomyPaths:
    """Simulated monthly paths, each shaped (n_sims, months)."""

    indices: np.ndarray
    cash_rate: np.ndarray
    mortgage_rate: np.ndarray
    cpi_growth: np.ndarray
    wage_growth: np.ndarray
    price_index: np.ndarray        # 1.0 = today's prices
    wage_index: np.ndarray         # 1.0 = today's pay


def simulate_economy(
    history: History,
    n_sims: int,
    months: int,
    cash_rate_now: float,
    mortgage_rate_now: float,
    block_length: int,
    rng: np.random.Generator,
) -> EconomyPaths:
    """Simulated cash rate, mortgage rate, prices and wages for every future at once.

    Cash rate = today's rate + the sampled historical changes, never below CASH_RATE_FLOOR.
    Mortgage rate = cash rate + the lender's margin today (your rate minus the cash rate).
    """
    idx = bootstrap_indices(len(history), n_sims, months, block_length, rng)
    cash = np.maximum(cash_rate_now + np.cumsum(history.cash_rate_change[idx], axis=1), CASH_RATE_FLOOR)
    margin = mortgage_rate_now - cash_rate_now
    cpi = history.cpi_growth[idx]
    wages = history.wage_growth[idx]
    return EconomyPaths(
        indices=idx,
        cash_rate=cash,
        mortgage_rate=np.maximum(cash + margin, 0.0),
        cpi_growth=cpi,
        wage_growth=wages,
        price_index=np.cumprod(1 + cpi, axis=1),
        wage_index=np.cumprod(1 + wages, axis=1),
    )


def months_out_of_work(starts: np.ndarray, duration: int) -> np.ndarray:
    """True in each month within `duration` months of a job loss starting (inclusive)."""
    count = np.cumsum(starts, axis=-1)
    earlier = np.zeros_like(count)
    if duration < count.shape[-1]:
        earlier[..., duration:] = count[..., :-duration]
    return (count - earlier) > 0


def job_loss_multiplier(
    rng: np.random.Generator, n_sims: int, borrowers: int, months: int, annual_chance: float, duration: int
) -> np.ndarray:
    """Random job losses, shape (n_sims, borrowers, months): 1 = working, 0 = no income.

    Each earner independently has `annual_chance` of losing their job in any year, spread
    evenly over months, and goes `duration` months without income each time.
    """
    if annual_chance <= 0 or duration <= 0:
        return np.ones((n_sims, borrowers, months))
    monthly_chance = 1 - (1 - annual_chance) ** (1 / 12)
    starts = rng.random((n_sims, borrowers, months)) < monthly_chance
    return 1.0 - months_out_of_work(starts, duration)


@dataclass(frozen=True)
class SimulationSettings:
    n_sims: int = DEFAULT_SIMS
    horizon_years: int = DEFAULT_HORIZON_YEARS
    window: str = DEFAULT_WINDOW
    block_length: int = DEFAULT_BLOCK
    seed: int = DEFAULT_SEED
    include_job_loss: bool = False
    job_loss_chance: float = JOB_LOSS_ANNUAL_CHANCE
    job_loss_months: int = JOB_LOSS_MONTHS

    @property
    def months(self) -> int:
        return self.horizon_years * 12


@dataclass(frozen=True)
class SimulationResult:
    """Every simulated future, plus the summary measures the Risk Simulator shows."""

    settings: SimulationSettings
    economy: EconomyPaths
    projection: ProjectionResult   # arrays shaped (n_sims, months)
    single_scenario: ProjectionResult  # "nothing changes" projection, for comparison
    history_range: tuple[str, str] = field(default=("", ""))

    # ---- chances (0 to 1) ----
    @property
    def chance_of_stress(self) -> float:
        return float(np.mean(self.projection.first_stress_month != NEVER))

    @property
    def chance_of_severe_stress(self) -> float:
        return float(np.mean(self.projection.first_severe_stress_month != NEVER))

    @property
    def chance_savings_run_out(self) -> float:
        return float(np.mean(self.projection.first_negative_savings_month != NEVER))

    @property
    def median_months_until_run_out(self) -> float | None:
        """Typical month savings run out, among futures where they do."""
        months = self.projection.first_negative_savings_month
        months = months[months != NEVER]
        return float(np.median(months)) if months.size else None

    # ---- percentile bands over time: {percentile: array of months} ----
    @staticmethod
    def bands(values: np.ndarray) -> dict[int, np.ndarray]:
        return dict(zip(PERCENTILES, np.percentile(values, PERCENTILES, axis=0)))

    @property
    def savings_bands(self) -> dict[int, np.ndarray]:
        return self.bands(self.projection.savings)

    @property
    def rate_bands(self) -> dict[int, np.ndarray]:
        return self.bands(self.economy.mortgage_rate)

    @property
    def repayment_bands(self) -> dict[int, np.ndarray]:
        return self.bands(self.projection.repayment)

    # ---- worst 5% of futures, ranked by lowest savings ----
    @property
    def worst_paths(self) -> np.ndarray:
        """Indices of the worst 5% of futures: lowest savings first, ties broken by final savings."""
        n_worst = max(1, int(np.ceil(WORST_SHARE * self.settings.n_sims)))
        order = np.lexsort((self.projection.savings[:, -1], self.projection.lowest_savings))
        return order[:n_worst]

    @property
    def worst_summary(self) -> dict:
        """Average outcome across the worst 5% (a household 'value at risk')."""
        worst = self.worst_paths
        p = self.projection
        ratio = np.where(np.isinf(p.stress_ratio[worst]), np.nan, p.stress_ratio[worst])
        return {
            "lowest_savings": float(np.mean(p.lowest_savings[worst])),
            "final_savings": float(np.mean(p.savings[worst, -1])),
            "peak_stress_ratio": float(np.nanmean(np.nanmax(ratio, axis=1))) if np.isfinite(ratio).any() else float("nan"),
            "peak_mortgage_rate": float(np.mean(self.economy.mortgage_rate[worst].max(axis=1))),
            "share_run_out": float(np.mean(p.first_negative_savings_month[worst] != NEVER)),
        }


def run_simulation(
    household: Household,
    cash_rate_now: float,
    settings: SimulationSettings = SimulationSettings(),
    history: History | None = None,
) -> SimulationResult:
    """Simulate many futures for this household and project each one month by month."""
    history = (history or load_history()).since(HISTORY_WINDOWS.get(settings.window, settings.window))
    rng = np.random.default_rng(settings.seed)
    months = settings.months
    borrowers = len(household.incomes)

    economy = simulate_economy(
        history, settings.n_sims, months, cash_rate_now, household.annual_rate, settings.block_length, rng
    )
    working = (
        job_loss_multiplier(rng, settings.n_sims, borrowers, months, settings.job_loss_chance, settings.job_loss_months)
        if settings.include_job_loss
        else 1.0
    )
    inputs = ProjectionInputs(
        annual_rate=economy.mortgage_rate,
        income_multiplier=economy.wage_index[:, None, :] * working,   # pay grows with wages; 0 when out of work
        expenses=household.monthly_expenses * economy.price_index,    # living costs grow with CPI
        one_off=np.zeros((settings.n_sims, months)),
        base_gross=tuple(household.incomes),
        has_help=tuple(household.has_help),
        other_debts=household.other_debts,
        principal=household.loan,
        term_years=household.term_years,
        starting_savings=household.starting_savings,
        savings_cap=household.savings_cap,
    )
    return SimulationResult(
        settings=settings,
        economy=economy,
        projection=project(inputs),
        single_scenario=run_scenario(household, (), months),
        history_range=(str(history.months[0]), str(history.months[-1])),
    )
