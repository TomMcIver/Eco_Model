"""Live checks against stats.govt.nz (run with `pytest -m network`)."""

from __future__ import annotations

import pandas as pd
import pytest

from eco_model.contracts import RAW_SERIES
from eco_model.data.snapshots import default_session
from eco_model.data.statsnz_catalog import STATSNZ_SERIES, rank_links, release_url
from eco_model.data.statsnz_parse import parse_release_page

pytestmark = pytest.mark.network


@pytest.mark.parametrize("series_id", RAW_SERIES)
def test_june_2026_release_pages_have_1045_date_and_usable_links(series_id):
    # Arrange
    spec = STATSNZ_SERIES[series_id]
    # Act
    response = default_session().get(release_url(spec, pd.Period("2026Q2", freq="Q")), timeout=60)
    page = parse_release_page(response.content)
    # Assert
    assert response.status_code == 200
    assert page.published_local.endswith("10:45:00")
    assert rank_links(spec, list(page.links))
