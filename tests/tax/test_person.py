from datetime import date
from decimal import Decimal

import pytest

from eco_model.tax.person import (
    IncomeCategory,
    IncomeItem,
    PayFrequency,
    Person,
    pay_schedule,
)


def test_birthday_handles_leap_day_as_1_march():
    person = Person(date_of_birth=date(2004, 2, 29))
    assert person.birthday(25) == date(2029, 3, 1)
    assert person.birthday(20) == date(2024, 2, 29)


def test_income_item_coerces_amount_to_decimal():
    item = IncomeItem(IncomeCategory.PAYE_SALARY_WAGES, 100.1, date(2027, 5, 1))
    assert item.amount == Decimal("100.10")


def test_income_item_rejects_negative_amount():
    with pytest.raises(ValueError):
        IncomeItem(IncomeCategory.OTHER_TAXABLE, -5, date(2027, 5, 1))


def test_person_rejects_bad_kiwisaver_rate():
    with pytest.raises(ValueError):
        Person(date_of_birth=date(2000, 1, 1), kiwisaver_rate=Decimal("1.5"))


@pytest.mark.parametrize(
    ("frequency", "count"),
    [(PayFrequency.WEEKLY, 52), (PayFrequency.FORTNIGHTLY, 26), (PayFrequency.MONTHLY, 12)],
)
def test_pay_schedule_counts_and_sums_exactly(frequency, count):
    # Act
    items = pay_schedule(Decimal("52000"), frequency, 2028)
    # Assert
    assert len(items) == count
    assert sum(i.amount for i in items) == Decimal("52000.00")
    assert all(date(2027, 4, 1) <= i.paid_on <= date(2028, 3, 31) for i in items)
    assert all(i.category is IncomeCategory.PAYE_SALARY_WAGES for i in items)


def test_pay_schedule_remainder_cents_go_to_last_payment():
    items = pay_schedule(Decimal("1000"), PayFrequency.WEEKLY, 2028)
    assert items[0].amount == Decimal("19.23")
    assert sum(i.amount for i in items) == Decimal("1000.00")


def test_monthly_schedule_clamps_to_month_end():
    items = pay_schedule(Decimal("12000"), PayFrequency.MONTHLY, 2028)
    assert items[0].paid_on == date(2027, 4, 30)
    assert items[10].paid_on == date(2028, 2, 29)


def test_pay_schedule_respects_first_pay_date():
    items = pay_schedule(Decimal("26000"), PayFrequency.FORTNIGHTLY, 2028, first_pay_date=date(2027, 4, 1))
    assert items[0].paid_on == date(2027, 4, 1)
    assert len(items) == 27


def test_pay_schedule_rejects_first_pay_date_outside_year():
    with pytest.raises(ValueError):
        pay_schedule(Decimal("1"), PayFrequency.WEEKLY, 2028, first_pay_date=date(2026, 1, 1))
