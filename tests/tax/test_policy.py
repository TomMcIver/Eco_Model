from dataclasses import replace
from datetime import date

import pytest

from eco_model.tax.person import IncomeCategory, IncomeItem, Person
from eco_model.tax.policy import BASE_CASE, Scenario, is_exempt_payment

PAYE = IncomeCategory.PAYE_SALARY_WAGES
PERSON = Person(date_of_birth=date(2003, 9, 15))  # 25th birthday 15 Sep 2028


def test_base_case_matches_spec():
    assert BASE_CASE.start == date(2027, 4, 1)
    assert BASE_CASE.end is None
    assert BASE_CASE.age_limit == 25
    assert BASE_CASE.qualifying_categories == frozenset({PAYE})
    assert BASE_CASE.financing == "borrowing"


def test_payment_day_before_25th_birthday_is_exempt():
    assert is_exempt_payment(PERSON, IncomeItem(PAYE, 100, date(2028, 9, 14)), BASE_CASE)


def test_payment_on_25th_birthday_is_not_exempt():
    assert not is_exempt_payment(PERSON, IncomeItem(PAYE, 100, date(2028, 9, 15)), BASE_CASE)


def test_payment_before_policy_start_is_never_exempt():
    assert not is_exempt_payment(PERSON, IncomeItem(PAYE, 100, date(2027, 3, 31)), BASE_CASE)
    assert is_exempt_payment(PERSON, IncomeItem(PAYE, 100, date(2027, 4, 1)), BASE_CASE)


def test_payment_after_end_date_is_not_exempt():
    scenario = replace(BASE_CASE, end=date(2027, 12, 31))
    assert not is_exempt_payment(PERSON, IncomeItem(PAYE, 100, date(2028, 1, 1)), scenario)


def test_self_employment_excluded_in_base_case_but_included_when_configured():
    item = IncomeItem(IncomeCategory.SELF_EMPLOYMENT_NET, 100, date(2027, 6, 1))
    widened = replace(BASE_CASE, qualifying_categories=frozenset({PAYE, IncomeCategory.SELF_EMPLOYMENT_NET}))
    assert not is_exempt_payment(PERSON, item, BASE_CASE)
    assert is_exempt_payment(PERSON, item, widened)


def test_scenario_validation():
    with pytest.raises(ValueError):
        Scenario(name="bad", start=date(2027, 4, 1), end=date(2027, 1, 1))
    with pytest.raises(ValueError):
        Scenario(name="bad", start=date(2027, 4, 1), age_limit=0)
    with pytest.raises(ValueError):
        Scenario(name="bad", start=date(2027, 4, 1), qualifying_categories=frozenset())
