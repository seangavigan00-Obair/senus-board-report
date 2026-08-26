"""
The canonical financial vocabulary and the shape of an extraction.

Two design decisions drive this file.

1. A CLOSED metric vocabulary. The model is not allowed to invent line-item
   names. "Turnover", "Revenue" and "Group Revenue" all map to `turnover`, which
   is what lets ADF-era statements and Senus-era statements sit in one series.
   Anything the model cannot map is reported as unmapped rather than guessed.

2. Every fact carries its own provenance. A value without a document, a page and
   the text it was read from is not usable in a board report - nobody can check
   it. Provenance travels with the fact from extraction all the way to the UI.

Sign convention: costs, expenses, liabilities and outflows are NEGATIVE; income,
assets and inflows are POSITIVE. Published statements are inconsistent about
this - some print "Cost of sales 64,861" and some "(188,541)" - so the model is
asked to normalise, and the reconciliation layer then checks that the normalised
figures actually articulate.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Metric(str, Enum):
    """Canonical chart of accounts. Closed set - see module docstring."""

    # Profit and loss
    TURNOVER = "turnover"
    COST_OF_SALES = "cost_of_sales"
    GROSS_PROFIT = "gross_profit"
    DISTRIBUTION_COSTS = "distribution_costs"
    ADMINISTRATIVE_EXPENSES = "administrative_expenses"
    OTHER_OPERATING_INCOME = "other_operating_income"
    OPERATING_PROFIT = "operating_profit"
    OTHER_GAINS_AND_LOSSES = "other_gains_and_losses"
    INTEREST_PAYABLE = "interest_payable"
    PROFIT_BEFORE_TAX = "profit_before_tax"
    TAX = "tax"
    PROFIT_AFTER_TAX = "profit_after_tax"

    # Balance sheet
    GOODWILL = "goodwill"
    DEVELOPMENT_COSTS = "development_costs"
    TANGIBLE_ASSETS = "tangible_assets"
    DEBTORS = "debtors"
    CASH_AND_CASH_EQUIVALENTS = "cash_and_cash_equivalents"
    CREDITORS_WITHIN_ONE_YEAR = "creditors_within_one_year"
    CONTINGENT_CONSIDERATION = "contingent_consideration"
    CREDITORS_AFTER_ONE_YEAR = "creditors_after_one_year"
    NET_ASSETS = "net_assets"
    SHARE_CAPITAL = "share_capital"
    SHARE_PREMIUM = "share_premium"
    RETAINED_EARNINGS = "retained_earnings"

    # Cash flow
    DEPRECIATION = "depreciation"
    CASH_FLOW_FROM_OPERATIONS = "cash_flow_from_operations"
    CASH_FLOW_FROM_INVESTING = "cash_flow_from_investing"
    CASH_FLOW_FROM_FINANCING = "cash_flow_from_financing"
    SHARE_ISSUANCE_PROCEEDS = "share_issuance_proceeds"
    LOAN_REPAYMENT = "loan_repayment"

    # Operating KPIs
    CUSTOMER_ACCOUNTS = "customer_accounts"
    ENTERPRISE_CUSTOMERS = "enterprise_customers"
    ACV_ENTERPRISE_SOIL = "acv_enterprise_soil"
    ACV_ENTERPRISE_TERRAIN = "acv_enterprise_terrain"
    ACV_ENTERPRISE_ERA = "acv_enterprise_era"
    REVENUE_SHARE_IRELAND_PCT = "revenue_share_ireland_pct"
    REVENUE_SHARE_UK_PCT = "revenue_share_uk_pct"
    REVENUE_SHARE_ENTERPRISE_PCT = "revenue_share_enterprise_pct"
    ANNUALISED_COST_REDUCTION = "annualised_cost_reduction"


StatementType = Literal[
    "profit_and_loss", "balance_sheet", "cash_flow", "kpi", "narrative", "none"
]

# Irish statutory accounts present the group AND the parent company separately,
# with genuinely different figures. In the ADF FY2025 accounts the consolidated
# loss is 590,256 and the company-only loss is 593,571; consolidated tangible
# assets are 48,788 against 48,579 for the company. A board report covers the
# group, so mixing the two silently would be a material error. Recording the
# scope on every fact is what stops that happening.
EntityScope = Literal["consolidated", "company", "not_stated"]

# Period ids the extractor is allowed to use. Anything else is a mapping failure,
# not a new period - the period registry is owned by the golden set.
PERIOD_IDS = ["FY2023", "FY2024", "FY2025", "HY2025", "HY2026", "FY2026"]


class ExtractedFact(BaseModel):
    metric: Metric = Field(description="Canonical metric from the closed vocabulary.")
    period: str = Field(description=f"One of: {', '.join(PERIOD_IDS)}")
    value: float = Field(
        description="Value in euro, sign-normalised: costs, liabilities and "
                    "outflows negative; income, assets and inflows positive. "
                    "Percentages are the number itself, e.g. 78.0 for 78%."
    )
    label_as_printed: str = Field(
        description="The line-item label exactly as it appears in the document."
    )
    value_as_printed: str = Field(
        description="The figure exactly as printed, including brackets, commas "
                    "or a dash for nil. Never reformatted."
    )
    statement: StatementType
    entity_scope: EntityScope = Field(
        description="Whether this figure is the GROUP position ('consolidated') "
                    "or the parent company alone ('company'). Irish statutory "
                    "accounts print both, with different numbers. Read the "
                    "statement heading: 'CONSOLIDATED ...' means consolidated, "
                    "'COMPANY ...' means company. Use 'not_stated' only where "
                    "the document has no group/company distinction at all."
    )
    is_approximate: bool = Field(
        description="True when the source hedges the figure - 'almost', "
                    "'approximately', 'in excess of', 'more than'."
    )
    note: str | None = Field(
        default=None,
        description="Anything a reviewer would need to know: a hedge, an "
                    "inconsistency with another figure on the page, an "
                    "unusual presentation. Null when there is nothing to say.",
    )


class PageExtraction(BaseModel):
    """Everything of financial substance on one page."""

    statement_type: StatementType = Field(
        description="The dominant statement on this page, or 'none' if the page "
                    "carries no financial figures at all."
    )
    page_title: str | None = Field(
        default=None, description="Heading as printed, e.g. 'CONSOLIDATED BALANCE SHEET'."
    )
    facts: list[ExtractedFact]
    unmapped_line_items: list[str] = Field(
        default_factory=list,
        description="Labels carrying figures that do not map to the canonical "
                    "vocabulary. Report them rather than forcing a bad match.",
    )
    legibility_concerns: list[str] = Field(
        default_factory=list,
        description="Figures that were hard to read on a scan, identified by "
                    "line-item label. Empty when the page was fully legible.",
    )


class Provenance(BaseModel):
    """Where a fact came from. Attached after extraction, never model-supplied."""

    document: str
    page: int
    extraction_path: Literal["native_text", "vision"]
    model: str
    extracted_at: str


class StoredFact(BaseModel):
    """An extracted fact joined to its provenance - what lands in the database."""

    fact: ExtractedFact
    provenance: Provenance
