import json

import pytest

from engine.costs import (
    FHBAS_CONCESSION_LIMIT,
    FHBAS_EXEMPT_LIMIT,
    NSW_LRS_MORTGAGE_FEE,
    NSW_LRS_TRANSFER_FEE,
    NSW_PREMIUM_THRESHOLD,
    SCHEME_PRICE_CAPS,
)
from engine.loan import APRA_SERVICEABILITY_BUFFER
from engine.market import REQUIRED_FIELDS, load_snapshot
from engine.tax import HELP_THRESHOLD, TAX_BRACKETS


@pytest.fixture(scope="module")
def snapshot():
    return load_snapshot()


def test_snapshot_loads(snapshot):
    assert snapshot.last_updated
    assert len(snapshot.figures) > 0


def test_every_figure_has_source_and_date(snapshot):
    for figure in snapshot.figures:
        assert figure.source.strip(), f"{figure.id} has no source"
        assert figure.as_at.strip(), f"{figure.id} has no as_at date"
        assert figure.url.startswith("https://"), f"{figure.id} has no https source link"


def test_ids_are_unique(snapshot):
    ids = [figure.id for figure in snapshot.figures]
    assert len(ids) == len(set(ids))


def test_pages_can_find_the_figures_they_use(snapshot):
    for figure_id in ("cash_rate", "avg_variable_rate_new", "median_national", "cpi_annual", "apra_buffer"):
        snapshot.get(figure_id)


def test_unknown_id_raises(snapshot):
    with pytest.raises(KeyError):
        snapshot.get("not_a_real_figure")


def test_missing_field_is_rejected(tmp_path):
    bad = {"last_updated": "today", "figures": [{"id": "x", "name": "X", "value": 1}]}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="missing"):
        load_snapshot(path)


def test_required_fields_include_source_and_date():
    assert "source" in REQUIRED_FIELDS and "as_at" in REQUIRED_FIELDS


# The engine keeps its own constants for calculations. These tests make sure the
# displayed figures and the figures used in the maths never drift apart.
def test_apra_buffer_matches_engine(snapshot):
    assert snapshot.get("apra_buffer").value == APRA_SERVICEABILITY_BUFFER


def test_help_threshold_matches_engine(snapshot):
    assert snapshot.get("help_threshold").value == HELP_THRESHOLD


def test_tax_brackets_match_engine(snapshot):
    json_brackets = [(b["over"], b["rate"] / 100) for b in snapshot.get("tax_brackets").value]
    assert json_brackets == list(TAX_BRACKETS)


def test_buying_cost_figures_match_engine(snapshot):
    assert snapshot.get("nsw_fhbas_exempt_limit").value == FHBAS_EXEMPT_LIMIT
    assert snapshot.get("nsw_fhbas_concession_limit").value == FHBAS_CONCESSION_LIMIT
    assert snapshot.get("nsw_premium_threshold").value == NSW_PREMIUM_THRESHOLD
    assert snapshot.get("scheme_cap_sydney").value == SCHEME_PRICE_CAPS["Sydney or NSW regional centre"]
    assert snapshot.get("scheme_cap_rest_nsw").value == SCHEME_PRICE_CAPS["Rest of NSW"]
    assert snapshot.get("nsw_lrs_transfer_fee").value == NSW_LRS_TRANSFER_FEE
    assert snapshot.get("nsw_lrs_mortgage_fee").value == NSW_LRS_MORTGAGE_FEE
