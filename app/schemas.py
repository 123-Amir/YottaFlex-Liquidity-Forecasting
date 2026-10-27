from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    database: str


class ForecastRequest(BaseModel):
    scenario_code: str = Field(min_length=1, max_length=32)
    simulation_date: date
    horizon_days: int = Field(gt=0, le=366)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    information_cutoff: date | None = None
    threshold: Decimal | None = None


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_code: str
    legal_name: str
    country_code: str
    functional_currency: str


class BankAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_code: str
    bank_name: str
    currency: str
    opening_balance: Decimal
    recorded_closing_balance: Decimal
    entity_code: str


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_code: str
    name: str
    kind: str
    description: str
    assumptions: str


class ForecastRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_code: str
    version: int
    simulation_date: date
    information_cutoff: date
    horizon_days: int
    base_currency: str
    status: str
    scenario_code: str


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_date: date
    opening_balance: Decimal
    expected_inflows: Decimal
    expected_outflows: Decimal
    closing_balance: Decimal
    base_currency: str


class ValidationResponse(BaseModel):
    issue_type: str
    explanation: str


class DatasetSummary(BaseModel):
    counts: dict[str, int]
    currencies: list[str]
    latest_migration: str | None
