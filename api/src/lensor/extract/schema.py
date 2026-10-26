from typing import Literal

from pydantic import BaseModel, Field, field_validator

RiskLevel = Literal["low", "medium", "high"]

MAX_QUOTES = 3


class ClauseResult(BaseModel):
    clause_type: str = Field(description="One of the clause type names, exactly as given.")
    found: bool = Field(description="True when the contract has this clause.")
    quotes: list[str] = Field(
        description="Up to 3 passages copied word for word from the contract. Empty if not found."
    )
    summary: str = Field(description="One plain sentence about what the clause says.")
    risk_level: RiskLevel | None = Field(
        description="Risk for the party that reviews the contract. Null if not found."
    )

    @field_validator("quotes")
    @classmethod
    def _limit_quotes(cls, quotes: list[str]) -> list[str]:
        return quotes[:MAX_QUOTES]


class ExtractionResult(BaseModel):
    clauses: list[ClauseResult]
