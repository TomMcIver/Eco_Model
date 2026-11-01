from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from eco_model.tax.calculator import calculate, explain
from eco_model.tax.person import IncomeCategory, IncomeItem, PayFrequency, Person, pay_schedule
from eco_model.tax.policy import BASE_CASE
from eco_model.tax.rules import AssumedRulesetError

D = Decimal
PAYE = IncomeCategory.PAYE_SALARY_WAGES


def _lines(result):
    return {line.name: line for line in result.lines}


def test_turning_25_mid_year_only_pre_birthday_payments_exempt():
    # Arrange: 25th birthday 15 Sep 2027; monthly month-end pay of 5,000.
    person = Person(date_of_birth=date(2002, 9, 15))
    items = pay_schedule(D("60000"), PayFrequency.MONTHLY, 2028)
    # Act
    result = calculate(person, items, 2028, BASE_CASE, allow_assumed=True)
    # Assert: Apr-Aug paid before the birthday -> 5 x 5,000 exempt.
    assert result.exempt_income == D("25000.00")
    assert len(result.exempt_payments) == 5
    tax = _lines(result)["income_tax"]
    assert tax.baseline == D("10220.50")  # 8270.50 + 6,500 x 0.30
    assert tax.policy == D("5033.00")  # 1638 + 19,400 x 0.175
    assert result.net_change == D("5187.50")
    assert result.ruleset_is_assumed


def test_person_aged_30_has_zero_change():
    person = Person(date_of_birth=date(1997, 1, 1))
    items = pay_schedule(D("52000"), PayFrequency.FORTNIGHTLY, 2028)
    result = calculate(person, items, 2028, BASE_CASE, allow_assumed=True)
    assert result.exempt_income == D("0")
    assert result.net_change == D("0")


def test_payments_before_1_april_2027_never_exempt():
    person = Person(date_of_birth=date(2006, 1, 1))  # aged 20-21 in 2026/27
    items = pay_schedule(D("52000"), PayFrequency.WEEKLY, 2027)
    result = calculate(person, items, 2027, BASE_CASE)
    assert result.exempt_income == D("0")
    assert _lines(result)["income_tax"].baseline == D("8008.00")
    assert result.net_change == D("0")


def test_policy_start_inside_tax_year_splits_payments():
    person = Person(date_of_birth=date(2006, 1, 1))
    scenario = replace(BASE_CASE, start=date(2026, 10, 1))
    items = pay_schedule(D("12000"), PayFrequency.MONTHLY, 2027)
    result = calculate(person, items, 2027, scenario)
    assert result.exempt_income == D("6000.00")  # Oct..Mar month-end payments


def test_self_employment_not_exempt_in_base_case_but_exempt_when_included():
    person = Person(date_of_birth=date(2006, 1, 1))
    items = (IncomeItem(IncomeCategory.SELF_EMPLOYMENT_NET, D("30000"), date(2027, 6, 30)),)
    widened = replace(
        BASE_CASE, qualifying_categories=frozenset({PAYE, IncomeCategory.SELF_EMPLOYMENT_NET})
    )
    base = calculate(person, items, 2028, BASE_CASE, allow_assumed=True)
    wide = calculate(person, items, 2028, widened, allow_assumed=True)
    assert base.exempt_income == D("0")
    assert wide.exempt_income == D("30000.00")
    assert wide.net_change == D("4158.00")  # 1638 + 14,400 x 0.175
    # Self-employed ACC levy is invoiced by ACC under separate rules: not modelled here.
    assert _lines(wide)["acc_earners_levy"].baseline == D("0.00")


def test_acc_levy_capped_at_max_liable_earnings():
    person = Person(date_of_birth=date(1990, 1, 1))
    items = (IncomeItem(PAYE, D("200000"), date(2026, 6, 1)),)
    result = calculate(person, items, 2027, BASE_CASE)
    acc = _lines(result)["acc_earners_levy"]
    assert acc.baseline == D("2741.22")  # 156,641 x 1.75%
    assert acc.policy == acc.baseline


def test_acc_below_cap_and_student_loan_and_kiwisaver_unchanged_by_policy():
    person = Person(date_of_birth=date(2006, 1, 1), has_student_loan=True, kiwisaver_rate=D("0.03"))
    items = (IncomeItem(PAYE, D("52000"), date(2027, 6, 1)),)
    result = calculate(person, items, 2028, BASE_CASE, allow_assumed=True)
    lines = _lines(result)
    assert lines["acc_earners_levy"].baseline == D("951.60")  # 52,000 x 1.83%
    # Exempt income stays in student-loan repayment income: only income tax is exempted.
    assert lines["student_loan_repayment"].baseline == D("3344.64")  # 12% x (52,000 - 24,128)
    assert lines["student_loan_repayment"].policy == D("3344.64")
    assert lines["kiwisaver_employee"].baseline == D("1560.00")
    assert lines["kiwisaver_employee"].policy == D("1560.00")
    assert lines["income_tax"].policy == D("0.00")
    assert result.net_change == D("8008.00")


def test_no_student_loan_line_is_zero():
    person = Person(date_of_birth=date(1990, 1, 1))
    items = (IncomeItem(PAYE, D("52000"), date(2026, 6, 1)),)
    lines = _lines(calculate(person, items, 2027, BASE_CASE))
    assert lines["student_loan_repayment"].baseline == D("0.00")
    assert lines["kiwisaver_employee"].baseline == D("0.00")


def test_other_taxable_income_is_taxed_but_not_exempt():
    person = Person(date_of_birth=date(2006, 1, 1))
    items = (
        IncomeItem(PAYE, D("10000"), date(2027, 6, 1)),
        IncomeItem(IncomeCategory.OTHER_TAXABLE, D("20000"), date(2027, 6, 1)),
    )
    result = calculate(person, items, 2028, BASE_CASE, allow_assumed=True)
    assert result.taxable_income == D("30000.00")
    assert _lines(result)["income_tax"].policy == D("2408.00")  # 1638 + 4,400 x 0.175
    assert result.policy_taxable_income == D("20000.00")


def test_assumed_ruleset_requires_opt_in():
    person = Person(date_of_birth=date(2006, 1, 1))
    items = (IncomeItem(PAYE, D("1000"), date(2027, 6, 1)),)
    with pytest.raises(AssumedRulesetError):
        calculate(person, items, 2028, BASE_CASE)


def test_item_outside_tax_year_rejected():
    person = Person(date_of_birth=date(2006, 1, 1))
    items = (IncomeItem(PAYE, D("1000"), date(2027, 4, 1)),)
    with pytest.raises(ValueError):
        calculate(person, items, 2027, BASE_CASE)


def test_not_modelled_list_and_explain_markdown():
    person = Person(date_of_birth=date(2006, 1, 1))
    items = (IncomeItem(PAYE, D("52000"), date(2027, 6, 1)),)
    result = calculate(person, items, 2028, BASE_CASE, allow_assumed=True)
    joined = " ".join(result.not_modelled)
    for word in ("Working for Families", "Independent Earner Tax Credit", "transfers", "behaviour", "macro"):
        assert word in joined
    text = explain(result)
    assert text.startswith("# ")
    assert "| income_tax |" in text
    assert "assumed carry-forward of 2026/27" in text
    assert "Not modelled" in text
    assert "borrowing" in text
    assert "income-tax-schedule-only" in text
