"""Command-line entry for the static under-25 tax calculator.

Example::

    main_tax(["--dob", "2004-06-15", "--salary", "52000", "--pay-frequency", "fortnightly",
              "--tax-year", "2028", "--allow-assumed"])
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Sequence

from eco_model.tax.aggregate import aggregate_feasibility, render_assessment
from eco_model.tax.calculator import calculate, explain
from eco_model.tax.person import IncomeCategory, IncomeItem, PayFrequency, Person, pay_schedule
from eco_model.tax.policy import BASE_CASE
from eco_model.tax.rules import tax_year_bounds


def _decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from exc


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eco-model tax", description="Static under-25 PAYE tax exemption calculator")
    p.add_argument("--dob", type=date.fromisoformat, help="date of birth, YYYY-MM-DD")
    p.add_argument("--salary", type=_decimal, default=Decimal(0), help="annual PAYE salary/wages")
    p.add_argument("--pay-frequency", choices=[f.value for f in PayFrequency], default="fortnightly")
    p.add_argument("--tax-year", type=int, help="tax year ending 31 March, e.g. 2028 = 2027/28")
    p.add_argument("--allow-assumed", action="store_true", help="opt in to assumed carry-forward rules")
    p.add_argument("--student-loan", action="store_true")
    p.add_argument("--kiwisaver-rate", type=_decimal, default=None, help="employee rate as fraction, e.g. 0.03")
    p.add_argument("--self-employment", type=_decimal, default=Decimal(0), help="annual net self-employment income")
    p.add_argument("--other-income", type=_decimal, default=Decimal(0), help="annual other taxable income")
    p.add_argument("--include-self-employment", action="store_true", help="scenario: exempt self-employment too")
    p.add_argument("--aggregate", action="store_true", help="print aggregate-costing feasibility and exit")
    return p


def _items(args: argparse.Namespace) -> tuple[IncomeItem, ...]:
    year_end = tax_year_bounds(args.tax_year)[1]
    items = pay_schedule(args.salary, PayFrequency(args.pay_frequency), args.tax_year) if args.salary else ()
    extra = (
        (IncomeCategory.SELF_EMPLOYMENT_NET, args.self_employment),
        (IncomeCategory.OTHER_TAXABLE, args.other_income),
    )
    # Annual non-PAYE amounts are dated at the tax-year end (one annual amount).
    return items + tuple(IncomeItem(cat, amt, year_end) for cat, amt in extra if amt)


def main_tax(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.aggregate:
        sys.stdout.write(render_assessment(aggregate_feasibility()))
        return 0
    if args.dob is None or args.tax_year is None:
        sys.stderr.write("error: --dob and --tax-year are required\n")
        return 2
    scenario = BASE_CASE
    if args.include_self_employment:
        scenario = replace(
            BASE_CASE,
            name="under25_paye_and_self_employment",
            qualifying_categories=BASE_CASE.qualifying_categories | {IncomeCategory.SELF_EMPLOYMENT_NET},
        )
    try:
        person = Person(args.dob, has_student_loan=args.student_loan, kiwisaver_rate=args.kiwisaver_rate)
        result = calculate(person, _items(args), args.tax_year, scenario, allow_assumed=args.allow_assumed)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    sys.stdout.write(explain(result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main_tax())
