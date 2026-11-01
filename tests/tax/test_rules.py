from datetime import date
from decimal import Decimal

import pytest

from eco_model.contracts import ValueKind
from eco_model.tax.rules import (
    AssumedRulesetError,
    UnknownTaxYearError,
    carry_forward_assumption,
    get_ruleset,
    income_tax,
    tax_year_label,
    verified_tax_years,
)

D = Decimal


@pytest.mark.parametrize(
    ("income", "expected"),
    [
        # Hand-computed for 2026/27: 10.5% to 15,600; 17.5% to 53,500; 30% to 78,100;
        # 33% to 180,000; 39% above.
        (D("0"), D("0.00")),
        (D("15600"), D("1638.00")),  # 15,600 x 0.105
        (D("15601"), D("1638.18")),  # + 1 x 0.175 = 1638.175 -> half-up
        (D("53500"), D("8270.50")),  # 1638 + 37,900 x 0.175
        (D("78100"), D("15650.50")),  # 8270.50 + 24,600 x 0.30
        (D("180000"), D("49277.50")),  # 15650.50 + 101,900 x 0.33
        (D("200000"), D("57077.50")),  # 49277.50 + 20,000 x 0.39
        (D("52000"), D("8008.00")),  # 1638 + 36,400 x 0.175
    ],
)
def test_progressive_tax_2026_27_at_bracket_boundaries(income, expected):
    # Arrange
    rules = get_ruleset(2027)
    # Act
    tax = income_tax(income, rules.schedule)
    # Assert
    assert tax == expected


def test_2024_25_composite_schedule_matches_hand_computation():
    # Arrange: 14,000 x .105 + 1,600 x .1282 + 32,400 x .175 + 5,500 x .2164 = 8,535.32
    rules = get_ruleset(2025)
    # Act
    tax = income_tax(D("53500"), rules.schedule)
    # Assert
    assert tax == D("8535.32")


def test_verified_years_have_official_provenance_and_urls():
    for year in verified_tax_years():
        rules = get_ruleset(year)
        assert not rules.is_assumed
        for name, prov in rules.provenances().items():
            assert prov.kind is ValueKind.OBSERVED, name
            assert prov.source_url.startswith("https://"), name
            assert prov.verified_on == date(2026, 10, 29)


def test_verified_years_include_2025_26_and_2026_27():
    assert {2026, 2027} <= set(verified_tax_years())


def test_acc_parameters_2026_27():
    rules = get_ruleset(2027)
    assert rules.acc.rate == D("0.0175")
    assert rules.acc.max_liable_earnings == D("156641")


def test_student_loan_parameters_2025_26():
    rules = get_ruleset(2026)
    assert rules.student_loan.rate == D("0.12")
    assert rules.student_loan.annual_threshold == D("24128")


def test_policy_start_year_requires_opt_in():
    with pytest.raises(AssumedRulesetError):
        get_ruleset(2028)


def test_assumed_ruleset_is_labelled_and_keeps_official_acc():
    # Act
    rules = get_ruleset(2028, allow_assumed=True)
    provs = rules.provenances()
    # Assert
    assert rules.is_assumed
    assert provs["income_tax_schedule"].kind is ValueKind.ESTIMATED
    assert provs["income_tax_schedule"].provenance == "assumed carry-forward of 2026/27"
    assert provs["student_loan_threshold"].kind is ValueKind.ESTIMATED
    # ACC 2027/28 is officially published by IRD, so it is not assumed.
    assert provs["acc_rate"].kind is ValueKind.OBSERVED
    assert rules.acc.rate == D("0.0183")
    assert rules.acc.max_liable_earnings == D("160244")
    assert rules.schedule.brackets == get_ruleset(2027).schedule.brackets


def test_carry_forward_assumption_direct_call():
    rules = carry_forward_assumption(2029)
    assert rules.tax_year == 2029
    assert rules.provenances()["acc_rate"].provenance == "assumed carry-forward of 2027/28"


def test_carry_forward_rejects_years_with_full_official_rules():
    with pytest.raises(ValueError):
        carry_forward_assumption(2027)


def test_unknown_early_year_raises():
    with pytest.raises(UnknownTaxYearError):
        get_ruleset(2010)


def test_tax_year_label_and_dates():
    rules = get_ruleset(2027)
    assert tax_year_label(2027) == "2026/27"
    assert rules.start == date(2026, 4, 1)
    assert rules.end == date(2027, 3, 31)


def test_negative_income_rejected():
    with pytest.raises(ValueError):
        income_tax(D("-1"), get_ruleset(2027).schedule)
