"""Under-25 exemption scenarios and the per-payment eligibility rule (ticket 007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from eco_model.tax.person import IncomeCategory, IncomeItem, Person

BORROWING = "borrowing"


@dataclass(frozen=True)
class Scenario:
    """A static exemption scenario.

    ``financing`` is a label only: the static calculator does not model how the
    revenue change is financed.
    """

    name: str
    start: date
    end: date | None = None  # inclusive; None = no scheduled end
    age_limit: int = 25
    qualifying_categories: frozenset[IncomeCategory] = field(
        default_factory=lambda: frozenset({IncomeCategory.PAYE_SALARY_WAGES})
    )
    financing: str = BORROWING

    def __post_init__(self) -> None:
        if self.end is not None and self.end < self.start:
            raise ValueError("scenario end must not precede its start")
        if self.age_limit <= 0:
            raise ValueError("age_limit must be positive")
        if not self.qualifying_categories:
            raise ValueError("at least one qualifying income category is required")


BASE_CASE = Scenario(name="base_case_under25_paye_exemption", start=date(2027, 4, 1))


def is_exempt_payment(person: Person, item: IncomeItem, scenario: Scenario) -> bool:
    """True if ``item`` is exempt: a qualifying category, paid while the policy is in
    force, and paid strictly before the person's ``age_limit`` birthday."""
    if item.category not in scenario.qualifying_categories:
        return False
    if item.paid_on < scenario.start:
        return False
    if scenario.end is not None and item.paid_on > scenario.end:
        return False
    return item.paid_on < person.birthday(scenario.age_limit)
