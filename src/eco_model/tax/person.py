"""People, dated income items, and regular pay-schedule generation."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from eco_model.tax.rules import CENT, round_cents, tax_year_bounds


class IncomeCategory(str, Enum):
    PAYE_SALARY_WAGES = "paye_salary_wages"
    SELF_EMPLOYMENT_NET = "self_employment_net"
    OTHER_TAXABLE = "other_taxable"  # interest, dividends, rents, etc.


class PayFrequency(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    # str() first so floats such as 100.1 become 100.10, not a binary expansion.
    return round_cents(Decimal(str(value)))


@dataclass(frozen=True)
class Person:
    date_of_birth: date
    has_student_loan: bool = False
    kiwisaver_rate: Decimal | None = None  # employee contribution rate as a fraction, e.g. 0.03

    def __post_init__(self) -> None:
        if self.kiwisaver_rate is not None:
            rate = Decimal(str(self.kiwisaver_rate))
            if not Decimal(0) < rate <= Decimal(1):
                raise ValueError("kiwisaver_rate must be a fraction in (0, 1]")
            object.__setattr__(self, "kiwisaver_rate", rate)

    def birthday(self, age: int) -> date:
        """Date the person attains ``age``. Convention: a 29 Feb birthday falls on 1 Mar in common years."""
        year = self.date_of_birth.year + age
        if self.date_of_birth.month == 2 and self.date_of_birth.day == 29 and not calendar.isleap(year):
            return date(year, 3, 1)
        return self.date_of_birth.replace(year=year)


@dataclass(frozen=True)
class IncomeItem:
    """One payment (or annual amount) of taxable income, dated by when it was paid."""

    category: IncomeCategory
    amount: Decimal
    paid_on: date

    def __post_init__(self) -> None:
        amount = _to_decimal(self.amount)
        if amount < 0:
            raise ValueError("income amounts must be non-negative (losses are not modelled)")
        object.__setattr__(self, "amount", amount)


def _monthly_dates(start: date, end: date, day: int) -> list[date]:
    dates: list[date] = []
    year, month = start.year, start.month
    while True:
        last = calendar.monthrange(year, month)[1]
        current = date(year, month, min(day, last))
        if current > end:
            return dates
        if current >= start:
            dates.append(current)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def _pay_dates(frequency: PayFrequency, start: date, end: date, first: date | None) -> list[date]:
    if frequency is PayFrequency.MONTHLY:
        return _monthly_dates(first or start, end, (first.day if first else 31))
    step = 7 if frequency is PayFrequency.WEEKLY else 14
    current = first or start + timedelta(days=step - 1)
    dates = []
    while current <= end:
        dates.append(current)
        current += timedelta(days=step)
    return dates


def pay_schedule(
    annual_amount: Decimal | int | float | str,
    frequency: PayFrequency,
    tax_year: int,
    first_pay_date: date | None = None,
) -> tuple[IncomeItem, ...]:
    """Split ``annual_amount`` of PAYE salary/wages into equal payments within ``tax_year``.

    Defaults: weekly/fortnightly pay on the last day of each period counted from
    1 April; monthly pay on the last day of each month. Each payment is the
    amount divided by the number of paydays, rounded to cents; the rounding
    remainder is added to the final payment so the total is exact.
    """
    start, end = tax_year_bounds(tax_year)
    if first_pay_date is not None and not start <= first_pay_date <= end:
        raise ValueError("first_pay_date must fall inside the tax year")
    total = _to_decimal(annual_amount)
    dates = _pay_dates(frequency, start, end, first_pay_date)
    each = (total / len(dates)).quantize(CENT, rounding="ROUND_DOWN")
    amounts = [each] * (len(dates) - 1) + [total - each * (len(dates) - 1)]
    return tuple(IncomeItem(IncomeCategory.PAYE_SALARY_WAGES, a, d) for a, d in zip(amounts, dates))
