"""Aggregate costing feasibility for the under-25 exemption (ticket 008, DEC-002).

Encodes the 008 conclusion: aggregate revenue is NOT estimable from the verified
public aggregates. No figures are produced or fabricated here. The
:class:`AggregateEstimator` protocol is the seam for a future grouped-data
estimator once an adequate joint cross-tabulation is obtained.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from eco_model.contracts import ValueKind
from eco_model.tax.policy import Scenario

NOT_ESTIMABLE = "not_estimable_from_public_aggregates"
FEASIBILITY_NOTE = "docs/research/nz-tax-cost-data-feasibility.md"


@dataclass(frozen=True)
class SourceInspected:
    name: str
    url: str
    limitation: str


@dataclass(frozen=True)
class CrossTabSpec:
    """The privacy-safe aggregate needed before a defensible estimate is possible."""

    dimensions: tuple[str, ...]
    measures: tuple[str, ...]
    metadata: tuple[str, ...]


@dataclass(frozen=True)
class GroupedCell:
    """One cell of a future joint cross-tab (input to an AggregateEstimator)."""

    tax_year: int
    age_group: str
    paye_band: tuple[Decimal, Decimal | None]
    other_income_band: tuple[Decimal, Decimal | None]
    count: int
    total_paye: Decimal
    total_other_income: Decimal
    suppressed: bool = False


@dataclass(frozen=True)
class AggregateEstimate:
    point: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    kind: ValueKind
    assumptions: tuple[str, ...]


@runtime_checkable
class AggregateEstimator(Protocol):
    def estimate(self, cells: tuple[GroupedCell, ...], scenario: Scenario, tax_year: int) -> AggregateEstimate: ...


@dataclass(frozen=True)
class AggregateAssessment:
    status: str
    reasons: tuple[str, ...]
    missing_cross_tab: CrossTabSpec
    sources: tuple[SourceInspected, ...]
    estimate: AggregateEstimate | None = None
    reference: str = FEASIBILITY_NOTE


_REASONS = (
    "Public tables give separate marginals (wage/salary by income band; taxable income and tax by band; "
    "age-specific median weekly wages) but no verified joint distribution of age x qualifying PAYE "
    "earnings x other taxable income x tax liability.",
    "The tax schedule is nonlinear, so the exemption's cost cannot be computed from medians, overall "
    "band totals or separate age totals.",
    "Combining marginals requires an independence assumption between age, qualifying wages and other "
    "income that the sources give no empirical basis for.",
    "Sources differ in unit and period (annual administrative tax-year records vs June-quarter survey "
    "pay-period snapshots vs household income), with no public linking key.",
    "Without compatible joint constraints, informative data-only bounds are not identified; any range "
    "would be an assumption-conditional sensitivity, not an uncertainty interval.",
    "IRD XLSX workbooks could not be inspected at worksheet level, so undocumented cross-tabs remain "
    "unverified.",
)

_MISSING = CrossTabSpec(
    dimensions=(
        "tax year (year ending 31 March)",
        "age: single years 15-24 (or the finest safe bands preserving the age-25 boundary), plus 25+ control",
        "PAYE salary/wage income band (aligned to the tax year's schedule thresholds)",
        "other taxable income band (taxable income excluding qualifying PAYE salary/wages)",
    ),
    measures=(
        "count of individuals / tax units per cell",
        "total annual qualifying PAYE salary/wages per cell",
        "total other taxable income per cell",
        "ideally baseline income tax and relevant credit / student-loan / benefit categories",
    ),
    metadata=(
        "suppression flags",
        "administrative coverage and definition notes",
        "revision / vintage metadata",
    ),
)

_SOURCES = (
    SourceInspected(
        "IRD wage and salary statistics datasets",
        "https://www.ird.govt.nz/about-us/tax-statistics/revenue-refunds/wage-salary-distributions/"
        "wage-and-salary-statistics-datasets",
        "Counts and totals by income band; no documented age cross-tab; workbook not inspected.",
    ),
    SourceInspected(
        "IRD tax-on-taxable-income datasets",
        "https://www.ird.govt.nz/about-us/tax-statistics/revenue-refunds/income-distribution/"
        "tax-on-taxable-income-datasets",
        "Taxable income and tax by band; age dimension documented for PIE income only.",
    ),
    SourceInspected(
        "IRD individual taxable-income distribution",
        "https://www.ird.govt.nz/about-us/tax-statistics/revenue-refunds/income-distribution",
        "Taxable income is not qualifying employment income; no joint age x source table.",
    ),
    SourceInspected(
        "Stats NZ: admin data as substitute for HLFS income variables",
        "https://www.stats.govt.nz/assets/Research/Evaluating-the-use-of-admin-data-as-a-substitute-for-"
        "Household-Labour-Force-Survey-income-variables/evaluating-the-use-of-admin-data-as-a-substitute-"
        "for-household-labour-force-survey-income-variables.pdf",
        "Median weekly wages by age band only; cannot recover a distribution.",
    ),
    SourceInspected(
        "Stats NZ Labour Market Statistics (Income) DataInfo+",
        "https://datainfoplus.stats.govt.nz/item/example.org/8d1f8525-746e-43cd-ad82-81a96f46225f/11",
        "Survey pay-period snapshot; not an annual tax-unit file; suppression and imputation.",
    ),
    SourceInspected(
        "Stats NZ HILS 2024/25 DataInfo+",
        "https://datainfoplus.stats.govt.nz/item/nz.govt.stats/9cd757c6-5e41-43e5-aa24-734c73a32989",
        "Public outputs are selected aggregates; linked IDI records are restricted; quality notice applies.",
    ),
    SourceInspected(
        "IRD OIA response: income tax by age groups under 21",
        "https://www.ird.govt.nz/-/media/project/ir/home/documents/oia-responses/march-2025/"
        "income-tax-collected-from-age-groups-under-21.pdf",
        "One-off, under-21 only, no qualifying-income split, no population denominators.",
    ),
)


def aggregate_feasibility() -> AggregateAssessment:
    """Return the 008 assessment: aggregate cost not estimable; no estimate attached."""
    return AggregateAssessment(
        status=NOT_ESTIMABLE,
        reasons=_REASONS,
        missing_cross_tab=_MISSING,
        sources=_SOURCES,
    )


def render_assessment(assessment: AggregateAssessment) -> str:
    lines = [
        "# Aggregate revenue cost: feasibility",
        "",
        f"**Status:** `{assessment.status}` (see `{assessment.reference}`). No estimate is reported.",
        "",
        "## Reasons",
        *[f"- {r}" for r in assessment.reasons],
        "",
        "## Missing cross-tabulation",
        "Dimensions:",
        *[f"- {d}" for d in assessment.missing_cross_tab.dimensions],
        "Measures:",
        *[f"- {m}" for m in assessment.missing_cross_tab.measures],
        "Metadata:",
        *[f"- {m}" for m in assessment.missing_cross_tab.metadata],
        "",
        "## Sources inspected",
        *[f"- [{s.name}]({s.url}): {s.limitation}" for s in assessment.sources],
    ]
    return "\n".join(lines) + "\n"
