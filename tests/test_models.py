from sqlalchemy import Numeric

from app.models.base import Base
from app.models.entities import (
    BankAccount,
    CashFlowForecast,
    ForecastRun,
    LegalEntity,
    ScenarioCashFlowAdjustment,
)


def test_phase_two_tables_are_registered() -> None:
    expected = {
        "legal_entities",
        "bank_accounts",
        "ledger_entries",
        "receivables",
        "payables",
        "currency_rates",
        "liquidity_scenarios",
        "cash_flow_forecasts",
        "scenario_cash_flow_adjustments",
        "forecast_runs",
        "forecast_positions",
        "daily_account_balances",
        "forecast_run_source_summaries",
        "actual_cash_flows",
    }

    assert set(Base.metadata.tables) == expected


def test_key_relationships_and_financial_precision_are_declared() -> None:
    assert BankAccount.legal_entity.property.back_populates == "bank_accounts"
    assert CashFlowForecast.legal_entity.property.back_populates == "cash_flows"
    assert ForecastRun.scenario.property.back_populates == "forecast_runs"
    assert ScenarioCashFlowAdjustment.cash_flow.property.back_populates == "adjustments"
    assert LegalEntity.__table__.c.id.primary_key
    amount_type = CashFlowForecast.__table__.c.amount.type
    assert isinstance(amount_type, Numeric)
    assert (amount_type.precision, amount_type.scale) == (18, 2)
