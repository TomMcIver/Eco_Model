"""Versioned NZ individual tax rule sets keyed by income-tax year.

A tax year is identified by the calendar year in which it ENDS (31 March):
``2027`` is the 2026/27 year, 1 April 2026 - 31 March 2027.

Every parameter carries a :class:`Provenance` naming the official page it was
verified against and the verification date. Values for a year that has not been
officially published are never invented: :func:`carry_forward_assumption` builds
them from the latest verified year, labels them ``ValueKind.ESTIMATED`` with
``provenance="assumed carry-forward of <year>"``, and :func:`get_ruleset` only
returns such a rule set when the caller passes ``allow_assumed=True``.

Rounding: liabilities are computed exactly with :class:`decimal.Decimal` on the
dollar-and-cent amounts supplied, then rounded once to cents, ROUND_HALF_UP.
This is a modelling convention, not a reproduction of IRD's assessment rounding.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Mapping

from eco_model.contracts import ValueKind

CENT = Decimal("0.01")
VERIFIED_ON = date(2026, 10, 29)
OFFICIAL = "official"

URL_INCOME_TAX = (
    "https://www.ird.govt.nz/income-tax/income-tax-for-individuals/"
    "tax-codes-and-tax-rates-for-individuals/tax-rates-for-individuals"
)
URL_ACC = "https://www.ird.govt.nz/acclevy"
URL_SL_WAGES = "https://www.ird.govt.nz/repaying-my-student-loan-when-i-earn-salary-or-wages"
URL_SL_STATS = (
    "https://www.ird.govt.nz/about-us/tax-statistics/statistics-on-the-student-loan-scheme/"
    "statistics-on-student-loan-repayments"
)
URL_SL_REGULATION = "https://www.legislation.govt.nz/regulation/public/2023/0295/latest/whole.html"


class UnknownTaxYearError(ValueError):
    """No verified or assumable rules exist for the requested tax year."""


class AssumedRulesetError(ValueError):
    """The requested year needs assumed parameters and the caller did not opt in."""


def round_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def tax_year_label(tax_year: int) -> str:
    return f"{tax_year - 1}/{str(tax_year)[-2:]}"


def tax_year_bounds(tax_year: int) -> tuple[date, date]:
    return date(tax_year - 1, 4, 1), date(tax_year, 3, 31)


@dataclass(frozen=True)
class Provenance:
    source_url: str
    verified_on: date
    kind: ValueKind = ValueKind.OBSERVED
    provenance: str = OFFICIAL
    note: str = ""


@dataclass(frozen=True)
class Bracket:
    lower: Decimal
    upper: Decimal | None  # None = no upper limit
    rate: Decimal


@dataclass(frozen=True)
class TaxSchedule:
    brackets: tuple[Bracket, ...]
    source: Provenance

    def __post_init__(self) -> None:
        if not self.brackets or self.brackets[0].lower != 0 or self.brackets[-1].upper is not None:
            raise ValueError("schedule must start at 0 and end unbounded")
        for prev, nxt in zip(self.brackets, self.brackets[1:]):
            if prev.upper != nxt.lower:
                raise ValueError("schedule brackets must be contiguous")


@dataclass(frozen=True)
class AccLevy:
    rate: Decimal  # earners' levy rate incl. GST, as a fraction
    max_liable_earnings: Decimal
    source: Provenance


@dataclass(frozen=True)
class StudentLoanRules:
    rate: Decimal
    annual_threshold: Decimal
    rate_source: Provenance
    threshold_source: Provenance


@dataclass(frozen=True)
class RuleSet:
    tax_year: int
    schedule: TaxSchedule
    acc: AccLevy
    student_loan: StudentLoanRules

    @property
    def label(self) -> str:
        return tax_year_label(self.tax_year)

    @property
    def start(self) -> date:
        return tax_year_bounds(self.tax_year)[0]

    @property
    def end(self) -> date:
        return tax_year_bounds(self.tax_year)[1]

    def provenances(self) -> dict[str, Provenance]:
        return {
            "income_tax_schedule": self.schedule.source,
            "acc_rate": self.acc.source,
            "acc_max_liable_earnings": self.acc.source,
            "student_loan_rate": self.student_loan.rate_source,
            "student_loan_threshold": self.student_loan.threshold_source,
        }

    @property
    def is_assumed(self) -> bool:
        return any(p.kind is not ValueKind.OBSERVED for p in self.provenances().values())


def income_tax(taxable_income: Decimal, schedule: TaxSchedule) -> Decimal:
    """Annual income tax on ``taxable_income`` under a marginal schedule, rounded to cents."""
    if taxable_income < 0:
        raise ValueError("taxable income must be non-negative")
    total = Decimal(0)
    for band in schedule.brackets:
        if taxable_income <= band.lower:
            break
        top = taxable_income if band.upper is None else min(taxable_income, band.upper)
        total += (top - band.lower) * band.rate
    return round_cents(total)


# --- Official parameters (verified 29 Oct 2026) -------------------------------------


def _schedule(rows: tuple[tuple[str, str | None, str], ...], note: str) -> TaxSchedule:
    brackets = tuple(
        Bracket(Decimal(lo), None if hi is None else Decimal(hi), Decimal(rate)) for lo, hi, rate in rows
    )
    return TaxSchedule(brackets, Provenance(URL_INCOME_TAX, VERIFIED_ON, note=note))


_SCHEDULE_FROM_2025_04 = _schedule(
    (
        ("0", "15600", "0.105"),
        ("15600", "53500", "0.175"),
        ("53500", "78100", "0.30"),
        ("78100", "180000", "0.33"),
        ("180000", None, "0.39"),
    ),
    "IRD 'Income tax rates from 1 April 2025'",
)

# 2024/25 annual composite rates (threshold changes on 31 July 2024), as published by IRD.
_SCHEDULE_2024_25 = _schedule(
    (
        ("0", "14000", "0.105"),
        ("14000", "15600", "0.1282"),
        ("15600", "48000", "0.175"),
        ("48000", "53500", "0.2164"),
        ("53500", "70000", "0.30"),
        ("70000", "78100", "0.3099"),
        ("78100", "180000", "0.33"),
        ("180000", None, "0.39"),
    ),
    "IRD 'Income tax rates from 1 April 2024 to 31 March 2025' (annual composite rates)",
)

SCHEDULES: Mapping[int, TaxSchedule] = {
    2025: _SCHEDULE_2024_25,
    2026: _SCHEDULE_FROM_2025_04,
    2027: _SCHEDULE_FROM_2025_04,
}


def _acc(rate: str, cap: str, period: str) -> AccLevy:
    note = f"IRD earners' levy {period}; rate includes GST"
    return AccLevy(Decimal(rate), Decimal(cap), Provenance(URL_ACC, VERIFIED_ON, note=note))


ACC_LEVIES: Mapping[int, AccLevy] = {
    2025: _acc("0.0160", "142283", "1 Apr 2024 - 31 Mar 2025"),
    2026: _acc("0.0167", "152790", "1 Apr 2025 - 31 Mar 2026"),
    2027: _acc("0.0175", "156641", "1 Apr 2026 - 31 Mar 2027"),
    2028: _acc("0.0183", "160244", "1 Apr 2027 - 31 Mar 2028"),
}

_SL_RATE = Provenance(
    URL_SL_WAGES, VERIFIED_ON, note="12% of every dollar over the repayment threshold (IRD; also IRD SL statistics)"
)


def _sl(threshold_url: str, note: str) -> StudentLoanRules:
    return StudentLoanRules(
        Decimal("0.12"), Decimal("24128"), _SL_RATE, Provenance(threshold_url, VERIFIED_ON, note=note)
    )


STUDENT_LOANS: Mapping[int, StudentLoanRules] = {
    2025: _sl(URL_SL_REGULATION, "SL 2023/295: $24,128 for 2024-25 and subsequent tax years; IRD stats table"),
    2026: _sl(URL_SL_WAGES, "IRD: 'For the 2026 tax year the annual repayment threshold is $24,128'"),
    2027: _sl(URL_SL_REGULATION, "SL 2023/295 in force at verification: 2024-25 and subsequent tax years"),
}


def verified_tax_years() -> tuple[int, ...]:
    """Tax years for which every parameter is officially verified."""
    return tuple(sorted(set(SCHEDULES) & set(ACC_LEVIES) & set(STUDENT_LOANS)))


def _assumed(source: Provenance, base_year: int) -> Provenance:
    return replace(
        source,
        kind=ValueKind.ESTIMATED,
        provenance=f"assumed carry-forward of {tax_year_label(base_year)}",
        note=f"Not published for this year; value carried forward. Original: {source.note}",
    )


def _latest_at_or_before(table: Mapping[int, object], tax_year: int) -> int:
    years = [y for y in table if y <= tax_year]
    if not years:
        raise UnknownTaxYearError(f"no rules at or before tax year {tax_year_label(tax_year)}")
    return max(years)


def carry_forward_assumption(tax_year: int) -> RuleSet:
    """Build an ASSUMED rule set for an unpublished year.

    Each component uses the officially published value for ``tax_year`` when one
    exists; otherwise the latest earlier verified value, relabelled as estimated.
    """
    if tax_year in verified_tax_years():
        raise ValueError(f"{tax_year_label(tax_year)} is fully verified; no assumption needed")
    sched_year = _latest_at_or_before(SCHEDULES, tax_year)
    acc_year = _latest_at_or_before(ACC_LEVIES, tax_year)
    sl_year = _latest_at_or_before(STUDENT_LOANS, tax_year)

    schedule = SCHEDULES[sched_year]
    if sched_year != tax_year:
        schedule = replace(schedule, source=_assumed(schedule.source, sched_year))
    acc = ACC_LEVIES[acc_year]
    if acc_year != tax_year:
        acc = replace(acc, source=_assumed(acc.source, acc_year))
    loan = STUDENT_LOANS[sl_year]
    if sl_year != tax_year:
        loan = replace(
            loan,
            rate_source=_assumed(loan.rate_source, sl_year),
            threshold_source=_assumed(loan.threshold_source, sl_year),
        )
    return RuleSet(tax_year, schedule, acc, loan)


def get_ruleset(tax_year: int, allow_assumed: bool = False) -> RuleSet:
    """Return rules for ``tax_year`` (year ending 31 March).

    Raises :class:`AssumedRulesetError` if any parameter would be assumed and the
    caller has not opted in, and :class:`UnknownTaxYearError` for years before the
    earliest verified year.
    """
    if tax_year in verified_tax_years():
        return RuleSet(tax_year, SCHEDULES[tax_year], ACC_LEVIES[tax_year], STUDENT_LOANS[tax_year])
    if tax_year < min(verified_tax_years()):
        raise UnknownTaxYearError(f"no verified rules for tax year {tax_year_label(tax_year)}")
    if not allow_assumed:
        raise AssumedRulesetError(
            f"Rules for {tax_year_label(tax_year)} are not fully published; pass allow_assumed=True "
            f"(CLI: --allow-assumed) to use an assumed carry-forward of the latest verified year."
        )
    return carry_forward_assumption(tax_year)
