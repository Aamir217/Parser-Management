from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


AllowedTransformation = Literal[
    "identity",
    "trim",
    "upper",
    "lower",
    "parse_date",
    "parse_decimal",
]


class LlmColumnMapping(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    source: str = Field(
        min_length=1,
        max_length=255,
        description=(
            "Normalized source column name "
            "from the workbook schema."
        ),
    )

    target: str = Field(
        min_length=1,
        max_length=255,
        description=(
            "Proposed normalized target field."
        ),
    )

    transform: AllowedTransformation = Field(
        description=(
            "One transformation from the "
            "provided deterministic allowlist."
        ),
    )

    required: bool = Field(
        description=(
            "Whether a missing or empty value "
            "should block parser execution."
        ),
    )

    rationale: str = Field(
        min_length=1,
        max_length=1000,
        description=(
            "Short reason for this mapping."
        ),
    )


class LlmParserProposalResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    parser_name_suggestion: str = Field(
        min_length=1,
        max_length=255,
    )

    source_sheet: str = Field(
        min_length=1,
        max_length=255,
    )

    header_row: int = Field(
        ge=1,
        le=100,
    )

    mappings: list[LlmColumnMapping] = Field(
        min_length=1,
        max_length=200,
    )

    assumptions: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    review_requirements: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in structural mapping only."
        ),
    )

    risk_level: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    proposal_notes: str = Field(
        min_length=1,
        max_length=2000,
    )
