"""Result types for the individual static calculator and their markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from eco_model.tax.person import IncomeItem
from eco_model.tax.rules import Provenance

NOT_MODELLED: tuple[str, ...] = (
    "Income transfers, main-benefit abatement and other transfers (existing rules unchanged, not computed)",
    "Working for Families tax credits (family scheme income) and their abatement",
    "Independent Earner Tax Credit (IETC) and all other tax credits/rebates: the result is "
    "income-tax-schedule-only",
    "PAYE withholding timing, secondary tax codes and end-of-year square-ups (annual liability only)",
    "Self-employed ACC levies (invoiced by ACC under separate liable-income rules)",
    "Student-loan pay-period, secondary-income and other-income rules (annual approximation used)",
    "Employer KiwiSaver contributions, ESCT and government contributions",
    "Losses, deductions and non-resident/schedular rules",
    "Labour-supply, wage, hours, take-up or other behaviour responses",
    "macro, GDP, financing (borrowing cost) and general-equilibrium effects",
)

SCOPE = (
    "Static, income-tax-schedule-only calculation. Only the line items listed are represented; "
    "the net change is the change in these items and is NOT a full disposable-income change."
)


@dataclass(frozen=True)
class LineItem:
    """An annual amount deducted from or paid by the person (positive = paid)."""

    name: str
    baseline: Decimal
    policy: Decimal
    note: str

    @property
    def change(self) -> Decimal:
        return self.policy - self.baseline


@dataclass(frozen=True)
class IndividualResult:
    tax_year: int
    tax_year_label: str
    scenario_name: str
    financing: str
    ruleset_is_assumed: bool
    provenance: tuple[tuple[str, Provenance], ...]
    taxable_income: Decimal
    exempt_income: Decimal
    exempt_payments: tuple[IncomeItem, ...]
    lines: tuple[LineItem, ...]
    not_modelled: tuple[str, ...] = NOT_MODELLED
    scope: str = SCOPE

    @property
    def policy_taxable_income(self) -> Decimal:
        return self.taxable_income - self.exempt_income

    @property
    def net_change(self) -> Decimal:
        """Gain to the person across represented line items (baseline minus policy)."""
        return sum((line.baseline - line.policy for line in self.lines), Decimal(0))


def explain(result: IndividualResult) -> str:
    """Render ``result`` as a markdown explanation."""
    out = [
        f"# Under-25 exemption: individual static result, tax year {result.tax_year_label}",
        "",
        f"- Scenario: `{result.scenario_name}` (financing assumption: {result.financing}; not modelled)",
        f"- Taxable income (baseline): ${result.taxable_income:,.2f}",
        f"- Exempt income under policy: ${result.exempt_income:,.2f} "
        f"({len(result.exempt_payments)} exempt payment(s))",
        f"- Taxable income (policy): ${result.policy_taxable_income:,.2f}",
        "",
        "| Line item | Baseline | Policy | Change (policy - baseline) | Note |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for line in result.lines:
        out.append(f"| {line.name} | {line.baseline:.2f} | {line.policy:.2f} | {line.change:.2f} | {line.note} |")
    out += [
        "",
        f"**Net change in represented items (gain to person): ${result.net_change:,.2f}**",
        "",
        f"> {result.scope}",
        "",
    ]
    if result.ruleset_is_assumed:
        out += [
            "> **Warning: this tax year uses ASSUMED parameters** (not officially published). "
            "See provenance below.",
            "",
        ]
    out += ["## Parameter provenance", "", "| Parameter | Kind | Provenance | Source | Verified |", "| --- | --- | --- | --- | --- |"]
    for name, prov in result.provenance:
        out.append(f"| {name} | {prov.kind.value} | {prov.provenance} | {prov.source_url} | {prov.verified_on} |")
    out += ["", "## Not modelled", ""]
    out += [f"- {item}" for item in result.not_modelled]
    out += [
        "",
        "Rounding: each line item is computed exactly in decimal and rounded once to cents (half-up).",
    ]
    return "\n".join(out) + "\n"
