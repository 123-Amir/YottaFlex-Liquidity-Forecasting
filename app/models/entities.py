from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

MONEY = Numeric(18, 2)
RATE = Numeric(20, 8)


class AccountStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CashFlowStatus(StrEnum):
    SCHEDULED = "scheduled"
    RECEIVED = "received"
    PAID = "paid"
    CANCELLED = "cancelled"


class CashFlowType(StrEnum):
    RECEIVABLE = "receivable"
    PAYABLE = "payable"


class ScenarioKind(StrEnum):
    BASE = "base"
    DELAYED_RECEIPTS = "delayed_receipts"
    STRESS = "stress"


class ForecastRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LegalEntity(TimestampMixin, Base):
    __tablename__ = "legal_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    functional_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bank_accounts: Mapped[list["BankAccount"]] = relationship(back_populates="legal_entity")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="legal_entity")
    receivables: Mapped[list["Receivable"]] = relationship(back_populates="legal_entity")
    payables: Mapped[list["Payable"]] = relationship(back_populates="legal_entity")
    cash_flows: Mapped[list["CashFlowForecast"]] = relationship(back_populates="legal_entity")
    forecast_runs: Mapped[list["ForecastRun"]] = relationship(back_populates="legal_entity")
    daily_balances: Mapped[list["DailyAccountBalance"]] = relationship(back_populates="legal_entity")


class BankAccount(TimestampMixin, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("legal_entity_id", "account_code"),
        CheckConstraint("opening_balance >= 0", name="opening_balance_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_number_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    recorded_closing_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[AccountStatus] = mapped_column(String(16), default=AccountStatus.ACTIVE, nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="bank_accounts")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="bank_account")
    cash_flows: Mapped[list["CashFlowForecast"]] = relationship(back_populates="bank_account")
    daily_balances: Mapped[list["DailyAccountBalance"]] = relationship(back_populates="bank_account")


class LedgerEntry(TimestampMixin, Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("entry_code"),
        CheckConstraint("amount <> 0", name="amount_non_zero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    posted_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="ledger_entries")
    bank_account: Mapped["BankAccount"] = relationship(back_populates="ledger_entries")


class Receivable(TimestampMixin, Base):
    __tablename__ = "receivables"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    receivable_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[CashFlowStatus] = mapped_column(String(16), default=CashFlowStatus.SCHEDULED, nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="receivables")


class Payable(TimestampMixin, Base):
    __tablename__ = "payables"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payable_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[CashFlowStatus] = mapped_column(String(16), default=CashFlowStatus.SCHEDULED, nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="payables")


class CurrencyRate(TimestampMixin, Base):
    __tablename__ = "currency_rates"
    __table_args__ = (
        UniqueConstraint("currency", "rate_date", "base_currency"),
        CheckConstraint("rate > 0", name="rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)


class LiquidityScenario(TimestampMixin, Base):
    __tablename__ = "liquidity_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[ScenarioKind] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    adjustments: Mapped[list["ScenarioCashFlowAdjustment"]] = relationship(back_populates="scenario")
    forecast_runs: Mapped[list["ForecastRun"]] = relationship(back_populates="scenario")


class CashFlowForecast(TimestampMixin, Base):
    __tablename__ = "cash_flow_forecasts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("source_type IN ('receivable', 'payable')", name="source_type_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    forecast_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_type: Mapped[CashFlowType] = mapped_column(String(16), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)
    bank_account_id: Mapped[int | None] = mapped_column(ForeignKey("bank_accounts.id"))
    receivable_id: Mapped[int | None] = mapped_column(ForeignKey("receivables.id"))
    payable_id: Mapped[int | None] = mapped_column(ForeignKey("payables.id"))

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="cash_flows")
    bank_account: Mapped["BankAccount | None"] = relationship(back_populates="cash_flows")
    receivable: Mapped["Receivable | None"] = relationship()
    payable: Mapped["Payable | None"] = relationship()
    adjustments: Mapped[list["ScenarioCashFlowAdjustment"]] = relationship(back_populates="cash_flow")


class ScenarioCashFlowAdjustment(TimestampMixin, Base):
    __tablename__ = "scenario_cash_flow_adjustments"
    __table_args__ = (UniqueConstraint("scenario_id", "cash_flow_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("liquidity_scenarios.id"), nullable=False)
    cash_flow_id: Mapped[int] = mapped_column(ForeignKey("cash_flow_forecasts.id"), nullable=False)
    date_shift_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=1, nullable=False)
    fx_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=1, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    scenario: Mapped["LiquidityScenario"] = relationship(back_populates="adjustments")
    cash_flow: Mapped["CashFlowForecast"] = relationship(back_populates="adjustments")


class ForecastRun(TimestampMixin, Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (
        UniqueConstraint("run_code"),
        CheckConstraint("horizon_days > 0", name="horizon_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ForecastRunStatus] = mapped_column(String(16), default=ForecastRunStatus.RUNNING, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    information_cutoff: Mapped[date] = mapped_column(Date, nullable=False)
    assumptions_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("liquidity_scenarios.id"), nullable=False)

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="forecast_runs")
    scenario: Mapped["LiquidityScenario"] = relationship(back_populates="forecast_runs")
    positions: Mapped[list["ForecastPosition"]] = relationship(back_populates="forecast_run")
    source_summaries: Mapped[list["ForecastRunSourceSummary"]] = relationship(
        back_populates="forecast_run"
    )


class ForecastPosition(Base):
    __tablename__ = "forecast_positions"
    __table_args__ = (UniqueConstraint("forecast_run_id", "position_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    position_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    expected_inflows: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    expected_outflows: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    forecast_run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id"), nullable=False)

    forecast_run: Mapped["ForecastRun"] = relationship(back_populates="positions")


class ForecastRunSourceSummary(Base):
    __tablename__ = "forecast_run_source_summaries"
    __table_args__ = (UniqueConstraint("forecast_run_id", "source_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[str] = mapped_column(String(64), nullable=False)
    forecast_run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id"), nullable=False)

    forecast_run: Mapped["ForecastRun"] = relationship(back_populates="source_summaries")


class DailyAccountBalance(TimestampMixin, Base):
    __tablename__ = "daily_account_balances"
    __table_args__ = (
        UniqueConstraint("bank_account_id", "position_date"),
        CheckConstraint("fx_rate > 0", name="fx_rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    position_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    ledger_movements: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    source_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    fx_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    legal_entity: Mapped["LegalEntity"] = relationship(back_populates="daily_balances")
    bank_account: Mapped["BankAccount"] = relationship(back_populates="daily_balances")


class ActualCashFlow(TimestampMixin, Base):
    __tablename__ = "actual_cash_flows"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actual_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_at: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_type: Mapped[CashFlowType] = mapped_column(String(16), nullable=False)
    cash_flow_id: Mapped[int | None] = mapped_column(ForeignKey("cash_flow_forecasts.id"))
    legal_entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), nullable=False)

    cash_flow: Mapped["CashFlowForecast | None"] = relationship()
    legal_entity: Mapped["LegalEntity"] = relationship()
