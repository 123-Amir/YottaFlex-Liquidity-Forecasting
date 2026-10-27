"""Phase 4 daily balances, FX conversion, liquidity positions, and reconciliation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import (
    BankAccount,
    CashFlowForecast,
    CurrencyRate,
    DailyAccountBalance,
    ForecastPosition,
    ForecastRun,
    LedgerEntry,
    LiquidityScenario,
)

MONEY_QUANTUM = Decimal("0.01")


class MissingFXRateError(ValueError):
    """Raised when a source currency cannot be converted on a calculation date."""


@dataclass(frozen=True)
class ReconciliationResult:
    checked_accounts: int
    failures: tuple[str, ...]


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def effective_fx_rate(
    session: Session, currency: str, base_currency: str, as_of: date
) -> tuple[Decimal, date]:
    if currency == base_currency:
        return Decimal("1.00000000"), as_of
    rate = session.scalar(
        select(CurrencyRate)
        .where(
            CurrencyRate.currency == currency,
            CurrencyRate.base_currency == base_currency,
            CurrencyRate.rate_date <= as_of,
        )
        .order_by(CurrencyRate.rate_date.desc())
        .limit(1)
    )
    if rate is None:
        raise MissingFXRateError(
            f"No FX rate for {currency}/{base_currency} effective on or before {as_of}"
        )
    return rate.rate, rate.rate_date


def reconcile_accounts(session: Session) -> ReconciliationResult:
    failures: list[str] = []
    accounts = session.scalars(select(BankAccount).order_by(BankAccount.id)).all()
    for account in accounts:
        movement_total = sum(
            (
                entry.amount
                for entry in session.scalars(
                    select(LedgerEntry).where(LedgerEntry.bank_account_id == account.id)
                )
            ),
            Decimal("0.00"),
        )
        calculated = quantize_money(account.opening_balance + movement_total)
        if calculated != account.recorded_closing_balance:
            failures.append(account.account_code)
    return ReconciliationResult(len(accounts), tuple(failures))


def calculate_run_positions(
    session: Session,
    run: ForecastRun,
    *,
    threshold: Decimal | None = None,
    scenario: LiquidityScenario | None = None,
) -> list[ForecastPosition]:
    """Calculate baseline daily positions using expected-date cash-flow eligibility."""
    accounts = session.scalars(select(BankAccount).order_by(BankAccount.id)).all()
    if not accounts:
        raise ValueError(f"Forecast run {run.run_code} has no bank accounts")

    start = run.simulation_date
    dates = [start + timedelta(days=index) for index in range(run.horizon_days)]
    if run.status == "completed" and session.scalar(
        select(ForecastPosition.id).where(ForecastPosition.forecast_run_id == run.id).limit(1)
    ):
        raise ValueError(f"Completed forecast run {run.run_code} is immutable")
    session.execute(delete(ForecastPosition).where(ForecastPosition.forecast_run_id == run.id))
    session.execute(
        delete(DailyAccountBalance).where(
            DailyAccountBalance.position_date.between(start, dates[-1]),
        )
    )

    all_entries = session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.bank_account_id.in_([account.id for account in accounts]),
            LedgerEntry.posted_on <= dates[-1],
        )
    ).all()
    movements_by_account_date: dict[tuple[int, date], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for entry in all_entries:
        movements_by_account_date[(entry.bank_account_id, entry.posted_on)] += entry.amount
    opening_by_account: dict[int, Decimal] = {}
    cumulative_by_account_date: dict[tuple[int, date], Decimal] = {}
    for account in accounts:
        opening_by_account[account.id] = account.opening_balance + sum(
            (
                amount
                for (account_id, movement_date), amount in movements_by_account_date.items()
                if account_id == account.id and movement_date < start
            ),
            Decimal("0.00"),
        )
        cumulative = Decimal("0.00")
        for position_date in dates:
            cumulative += movements_by_account_date[(account.id, position_date)]
            cumulative_by_account_date[(account.id, position_date)] = cumulative
    flows = session.scalars(
        select(CashFlowForecast).where(
            CashFlowForecast.expected_date.between(start, dates[-1]),
        )
    ).all()
    adjustments = {}
    if scenario is not None:
        adjustments = {
            adjustment.cash_flow_id: adjustment
            for adjustment in scenario.adjustments
        }
    flow_totals_by_date: dict[date, tuple[Decimal, Decimal]] = defaultdict(
        lambda: (Decimal("0.00"), Decimal("0.00"))
    )
    for flow in flows:
        adjustment = adjustments.get(flow.id)
        flow_date = flow.expected_date
        amount = flow.amount
        if adjustment is not None:
            flow_date += timedelta(days=adjustment.date_shift_days)
            amount = quantize_money(amount * adjustment.amount_multiplier)
        if flow_date < start or flow_date > dates[-1]:
            continue
        rate, _ = effective_fx_rate(session, flow.currency, run.base_currency, flow_date)
        if adjustment is not None:
            rate *= adjustment.fx_multiplier
        converted = quantize_money(amount * rate)
        inflow, outflow = flow_totals_by_date[flow_date]
        if str(flow.source_type) == "receivable":
            flow_totals_by_date[flow_date] = (inflow + converted, outflow)
        else:
            flow_totals_by_date[flow_date] = (inflow, outflow + converted)
    positions: list[ForecastPosition] = []
    opening_total = Decimal("0.00")
    for account in accounts:
        opening = opening_by_account[account.id]
        rate, _ = effective_fx_rate(session, account.currency, run.base_currency, start)
        opening_total += opening * rate
    for position_date in dates:
        inflows = Decimal("0.00")
        outflows = Decimal("0.00")
        for account in accounts:
            movements = movements_by_account_date[(account.id, position_date)]
            closing = quantize_money(
                opening_by_account[account.id] + cumulative_by_account_date[(account.id, position_date)]
            )
            rate, rate_date = effective_fx_rate(
                session, account.currency, run.base_currency, position_date
            )
            session.add(
                DailyAccountBalance(
                    position_date=position_date,
                    opening_balance=quantize_money(opening),
                    ledger_movements=quantize_money(movements),
                    closing_balance=closing,
                    source_currency=account.currency,
                    source_amount=closing,
                    fx_rate=rate,
                    fx_rate_date=rate_date,
                    base_currency=run.base_currency,
                    base_amount=quantize_money(closing * rate),
                    legal_entity_id=account.legal_entity_id,
                    bank_account_id=account.id,
                )
            )
        inflows, outflows = flow_totals_by_date[position_date]
        closing_total = quantize_money(opening_total + inflows - outflows)
        positions.append(
            ForecastPosition(
                position_date=position_date,
                opening_balance=quantize_money(opening_total),
                expected_inflows=quantize_money(inflows),
                expected_outflows=quantize_money(outflows),
                closing_balance=closing_total,
                base_currency=run.base_currency,
                forecast_run_id=run.id,
            )
        )
        opening_total = closing_total
    session.add_all(positions)
    session.commit()
    return positions
