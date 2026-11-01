from eco_model.tax.aggregate import (
    NOT_ESTIMABLE,
    AggregateEstimator,
    aggregate_feasibility,
)


def test_aggregate_is_not_estimable_without_numbers():
    # Act
    result = aggregate_feasibility()
    # Assert
    assert result.status == NOT_ESTIMABLE == "not_estimable_from_public_aggregates"
    assert result.estimate is None
    assert len(result.reasons) >= 3


def test_missing_cross_tab_specifies_required_dimensions():
    spec = aggregate_feasibility().missing_cross_tab
    dims = " ".join(spec.dimensions).lower()
    assert "tax year" in dims
    assert "15" in dims and "24" in dims
    assert "paye salary/wage income band" in dims
    assert "other taxable income band" in dims
    measures = " ".join(spec.measures).lower()
    assert "count" in measures and "total" in measures


def test_sources_inspected_are_official_urls():
    sources = aggregate_feasibility().sources
    assert len(sources) >= 5
    assert all(s.url.startswith("https://") for s in sources)
    assert any("ird.govt.nz" in s.url for s in sources)
    assert any("stats.govt.nz" in s.url for s in sources)


def test_estimator_protocol_is_runtime_checkable():
    class Dummy:
        def estimate(self, cells, scenario, tax_year):
            raise NotImplementedError

    assert isinstance(Dummy(), AggregateEstimator)
    assert not isinstance(object(), AggregateEstimator)
