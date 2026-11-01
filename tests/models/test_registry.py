from eco_model.models import registry
from eco_model.models.ensemble import ENSEMBLE_MEMBERS


def test_default_forecasters_names_and_order():
    names = [f.name for f in registry.default_forecasters()]
    assert names == ["persistence", "historical_mean", "ar", "var3"]
    assert set(ENSEMBLE_MEMBERS) <= set(names)


def test_default_forecasters_returns_fresh_instances():
    assert registry.default_forecasters()[2] is not registry.default_forecasters()[2]
