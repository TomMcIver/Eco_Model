"""Exact static individual calculator for the under-25 PAYE exemption.

Annual income tax is recomputed under the tax year's schedule on taxable income
minus exempt income. ACC earners' levy, student-loan repayment and KiwiSaver
employee contributions are separate line items and are held unchanged: the
policy exempts income tax only, so exempt income remains ACC-liable earnings and
student-loan repayment income.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from eco_model.tax.person import IncomeCategory, IncomeItem, Person
from eco_model.tax.policy import Scenario, is_exempt_payment
from eco_model.tax.result import IndividualResult, LineItem, explain
from eco_model.tax.rules import RuleSet, get_ruleset, income_tax, round_cents

__all__ = ["calculate", "explain"]


def _sum(items: Iterable[IncomeItem]) -> Decimal:
    return sum((i.amount for i in items), Decimal(0))


def _validate_items(items: tuple[IncomeItem, ...], rules: RuleSet) -> None:
    for item in items:
        if not rules.start <= item.paid_on <= rules.end:
            raise ValueError(
                f"income paid on {item.paid_on} is outside tax year {rules.label} ({rules.start} to {rules.end})"
            )


def _acc_levy(paye_wages: Decimal, rules: RuleSet) -> Decimal:
    return round_cents(min(paye_wages, rules.acc.max_liable_earnings) * rules.acc.rate)


def _student_loan(person: Person, repayment_income: Decimal, rules: RuleSet) -> Decimal:
    if not person.has_student_loan:
        return Decimal("0.00")
    excess = max(Decimal(0), repayment_income - rules.student_loan.annual_threshold)
    return round_cents(excess * rules.student_loan.rate)


def _kiwisaver(person: Person, paye_wages: Decimal) -> Decimal:
    if person.kiwisaver_rate is None:
        return Decimal("0.00")
    return round_cents(paye_wages * person.kiwisaver_rate)


def _unchanged(name: str, amount: Decimal, note: str) -> LineItem:
    return LineItem(name, amount, amount, note)


def calculate(
    person: Person,
    items: Iterable[IncomeItem],
    tax_year: int,
    scenario: Scenario,
    allow_assumed: bool = False,
) -> IndividualResult:
    """Baseline vs policy line items for one person's income in ``tax_year`` (year ending 31 March)."""
    rules = get_ruleset(tax_year, allow_assumed=allow_assumed)
    all_items = tuple(items)
    _validate_items(all_items, rules)

    exempt = tuple(i for i in all_items if is_exempt_payment(person, i, scenario))
    taxable = _sum(all_items)
    exempt_income = _sum(exempt)
    paye_wages = _sum(i for i in all_items if i.category is IncomeCategory.PAYE_SALARY_WAGES)

    lines = (
        LineItem(
            "income_tax",
            income_tax(taxable, rules.schedule),
            income_tax(taxable - exempt_income, rules.schedule),
            "annual liability on taxable income minus exempt income",
        ),
        _unchanged("acc_earners_levy", _acc_levy(paye_wages, rules), "PAYE earnings up to max liable earnings; unchanged"),
        _unchanged(
            "student_loan_repayment",
            _student_loan(person, taxable, rules),
            "annual approx.; exempt income stays in repayment income; unchanged",
        ),
        _unchanged("kiwisaver_employee", _kiwisaver(person, paye_wages), "employee rate x PAYE wages; unchanged"),
    )
    return IndividualResult(
        tax_year=tax_year,
        tax_year_label=rules.label,
        scenario_name=scenario.name,
        financing=scenario.financing,
        ruleset_is_assumed=rules.is_assumed,
        provenance=tuple(rules.provenances().items()),
        taxable_income=round_cents(taxable),
        exempt_income=round_cents(exempt_income),
        exempt_payments=exempt,
        lines=lines,
    )
