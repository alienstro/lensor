"""Risk score: a sum of points for facts that the extraction found (UI spec section 4)."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from lensor.extract.schema import RiskLevel


class HasClause(Protocol):
    clause_type: str
    found: bool


@dataclass(frozen=True)
class RiskRule:
    clause_type: str
    when_found: bool
    points: int
    text: str


RISK_RULES: tuple[RiskRule, ...] = (
    RiskRule("Uncapped Liability", True, 30, "No limit on what you could owe for some claims"),
    RiskRule("Cap on Liability", False, 15, "No general limit on what you could owe"),
    RiskRule("Renewal Term", True, 15, "The contract renews by itself"),
    RiskRule("Non-Compete", True, 15, "Limits work with competitors"),
    RiskRule("Change of Control", True, 15, "Rules apply if a company is sold"),
    RiskRule(
        "Termination for Convenience", True, 10, "A party can end the contract without a reason"
    ),
)

HIGH_FROM = 60
MEDIUM_FROM = 30


@dataclass(frozen=True)
class RiskReason:
    clause_type: str
    points: int
    text: str


def risk_reasons(clauses: Iterable[HasClause]) -> list[RiskReason]:
    found = {c.clause_type for c in clauses if c.found}
    return [
        RiskReason(rule.clause_type, rule.points, rule.text)
        for rule in RISK_RULES
        if (rule.clause_type in found) == rule.when_found
    ]


def risk_score(clauses: Iterable[HasClause]) -> int:
    return sum(reason.points for reason in risk_reasons(clauses))


def risk_level_for(score: int) -> RiskLevel:
    if score >= HIGH_FROM:
        return "high"
    if score >= MEDIUM_FROM:
        return "medium"
    return "low"
