"""Deterministic synthetic data generation for the Phase 3 baseline dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AccountStatus,
    ActualCashFlow,
    BankAccount,
    CashFlowForecast,
    CashFlowStatus,
    CashFlowType,
    CurrencyRate,
    DailyAccountBalance,
    ForecastPosition,
    ForecastRun,
    ForecastRunSourceSummary,
    ForecastRunStatus,
    LedgerEntry,
    LegalEntity,
    LiquidityScenario,
    Payable,
    Receivable,
    ScenarioCashFlowAdjustment,
    ScenarioKind,
)

CURRENCIES = ("USD", "EUR", "GBP", "INR", "JPY")
COUNTRIES = ("US", "DE", "GB", "IN", "JP")
RATE_TO_USD = {"USD": Decimal("1.00000000"), "EUR": Decimal("1.08000000"),
               "GBP": Decimal("1.27000000"), "INR": Decimal("0.01200000"),
               "JPY": Decimal("0.00670000")}


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 20261022
    simulation_start: date = date(2026, 1, 1)
    forecast_horizon: int = 72
    entities: int = 30
    accounts: int = 150
    ledger_entries: int = 100_000
    forecast_items: int = 20_000

    @classmethod
    def starter(cls, seed: int = 20261022) -> GeneratorConfig:
        return cls(seed=seed, entities=3, accounts=6, ledger_entries=24, forecast_items=18)


def _date_for(index: int, start: date, horizon: int) -> date:
    return start + timedelta(days=index % horizon)


def _money(value: int) -> Decimal:
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"))


def _delete_existing(session: Session) -> None:
    for model in (
        ScenarioCashFlowAdjustment,
        ForecastPosition,
        DailyAccountBalance,
        ForecastRunSourceSummary,
        ActualCashFlow,
        ForecastRun,
        CashFlowForecast,
        Receivable,
        Payable,
        CurrencyRate,
        LedgerEntry,
        BankAccount,
        LiquidityScenario,
        LegalEntity,
    ):
        session.execute(delete(model))


def _record_payload(record: Any) -> dict[str, Any]:
    excluded = {"id", "created_at", "updated_at"}
    return {
        column.name: str(getattr(record, column.name))
        for column in record.__table__.columns
        if column.name not in excluded and not column.name.endswith("_id")
    }


def _checksum(records: list[Any]) -> str:
    payload = "\n".join(
        json.dumps(_record_payload(record), sort_keys=True, separators=(",", ":"))
        for record in records
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate(session: Session, config: GeneratorConfig, reset: bool = False) -> dict[str, Any]:
    """Generate one deterministic baseline and return counts/checksums/validation results."""
    if reset:
        _delete_existing(session)

    rng = random.Random(config.seed)
    entities: list[LegalEntity] = []
    accounts: list[BankAccount] = []
    ledger: list[LedgerEntry] = []
    receivables: list[Receivable] = []
    payables: list[Payable] = []
    cash_flows: list[CashFlowForecast] = []
    rates: list[CurrencyRate] = []

    for index in range(config.entities):
        entity = LegalEntity(
            entity_code=f"ENT-{index + 1:06d}",
            legal_name=f"YottaFlex Entity {index + 1:03d}",
            country_code=COUNTRIES[index % len(COUNTRIES)],
            functional_currency=CURRENCIES[index % len(CURRENCIES)],
        )
        entities.append(entity)
    session.add_all(entities)
    session.flush()

    for index in range(config.accounts):
        entity = entities[index % len(entities)]
        opening = _money(rng.randint(100_000, 2_000_000))
        account = BankAccount(
            account_code=f"BANKACC-{entity.entity_code}-{index + 1:03d}",
            bank_name=f"Demo Bank {(index % 4) + 1}",
            account_number_last4=f"{index + 1:04d}",
            currency=CURRENCIES[index % len(CURRENCIES)],
            opening_balance=opening,
            recorded_closing_balance=opening,
            status=AccountStatus.ACTIVE,
            legal_entity=entity,
        )
        accounts.append(account)
    session.add_all(accounts)
    session.flush()

    for index in range(config.ledger_entries):
        account = accounts[index % len(accounts)]
        amount = _money(rng.randint(100, 25_000))
        if index % 2:
            amount = -amount
        entry = LedgerEntry(
            entry_code=f"LED-{config.simulation_start.year}-{index + 1:08d}",
            posted_on=_date_for(index, config.simulation_start, config.forecast_horizon),
            amount=amount,
            currency=account.currency,
            description=f"Generated ledger movement {index + 1:06d}",
            legal_entity_id=account.legal_entity_id,
            bank_account=account,
        )
        ledger.append(entry)
    session.add_all(ledger)
    session.flush()
    for account in accounts:
        account.recorded_closing_balance = account.opening_balance + sum(
            entry.amount for entry in ledger if entry.bank_account_id == account.id
        )

    incoming_count = config.forecast_items // 2
    for index in range(config.forecast_items):
        account = accounts[index % len(accounts)]
        expected_date = _date_for(index + 1, config.simulation_start, config.forecast_horizon)
        amount = _money(rng.randint(500, 100_000))
        if index < incoming_count:
            source = Receivable(
                receivable_code=f"REC-{config.simulation_start.year}-{index + 1:08d}",
                customer_name=f"Customer {(index % 50) + 1:03d}",
                expected_date=expected_date,
                amount=amount,
                currency=account.currency,
                status=CashFlowStatus.SCHEDULED,
                legal_entity_id=account.legal_entity_id,
            )
            receivables.append(source)
            session.add(source)
            session.flush()
            flow = CashFlowForecast(
                forecast_code=f"CF-{config.simulation_start.year}-{index + 1:08d}",
                source_type=CashFlowType.RECEIVABLE,
                expected_date=expected_date,
                amount=amount,
                currency=account.currency,
                description=f"Forecast receipt {source.receivable_code}",
                legal_entity_id=account.legal_entity_id,
                bank_account_id=account.id,
                receivable_id=source.id,
            )
        else:
            source = Payable(
                payable_code=f"PAY-{config.simulation_start.year}-{index - incoming_count + 1:08d}",
                supplier_name=f"Supplier {(index % 50) + 1:03d}",
                expected_date=expected_date,
                amount=amount,
                currency=account.currency,
                status=CashFlowStatus.SCHEDULED,
                legal_entity_id=account.legal_entity_id,
            )
            payables.append(source)
            session.add(source)
            session.flush()
            flow = CashFlowForecast(
                forecast_code=f"CF-{config.simulation_start.year}-{index + 1:08d}",
                source_type=CashFlowType.PAYABLE,
                expected_date=expected_date,
                amount=amount,
                currency=account.currency,
                description=f"Forecast payment {source.payable_code}",
                legal_entity_id=account.legal_entity_id,
                bank_account_id=account.id,
                payable_id=source.id,
            )
        cash_flows.append(flow)
        session.add(flow)
    session.flush()

    rate_days = config.forecast_horizon + 1
    for day_index in range(rate_days):
        rate_date = config.simulation_start + timedelta(days=day_index)
        for currency in CURRENCIES:
            rates.append(
                CurrencyRate(
                    currency=currency,
                    base_currency="USD",
                    rate_date=rate_date,
                    rate=RATE_TO_USD[currency],
                )
            )
    session.add_all(rates)

    scenarios = [
        LiquidityScenario(
            scenario_code="BASE",
            name="Base",
            kind=ScenarioKind.BASE,
            description="Expected receipt and payment dates.",
            assumptions="No date or amount adjustments.",
        ),
        LiquidityScenario(
            scenario_code="DELAYED-RECEIPTS",
            name="Delayed receipts",
            kind=ScenarioKind.DELAYED_RECEIPTS,
            description="Eligible incoming flows are delayed by five days.",
            assumptions="Receivables are shifted five calendar days.",
        ),
        LiquidityScenario(
            scenario_code="STRESS",
            name="Stress",
            kind=ScenarioKind.STRESS,
            description="Receipts are delayed and FX is adverse.",
            assumptions="Receivables are shifted five days; adverse FX is documented for Phase 4.",
        ),
    ]
    session.add_all(scenarios)
    session.flush()
    for scenario in scenarios[1:]:
        for flow in cash_flows:
            if flow.source_type == CashFlowType.RECEIVABLE:
                session.add(
                    ScenarioCashFlowAdjustment(
                        scenario_id=scenario.id,
                        cash_flow_id=flow.id,
                        date_shift_days=5,
                        amount_multiplier=Decimal("1.0000"),
                        fx_multiplier=Decimal("0.9500") if scenario.kind == ScenarioKind.STRESS else Decimal("1.0000"),
                        rationale="Documented delayed-receipt assumption.",
                    )
                )
    for index, scenario in enumerate(scenarios):
        session.add(
            ForecastRun(
                run_code=f"FCAST-{config.simulation_start}-{index + 1:03d}",
                version=1,
                simulation_date=config.simulation_start,
                horizon_days=config.forecast_horizon,
                status=ForecastRunStatus.COMPLETED,
                base_currency="USD",
                information_cutoff=config.simulation_start,
                assumptions_snapshot=scenario.assumptions,
                source_reference="phase3-generator-baseline",
                legal_entity_id=entities[0].id,
                scenario_id=scenario.id,
            )
        )
    session.commit()

    table_records = [*entities, *accounts, *ledger, *receivables, *payables, *cash_flows, *rates, *scenarios]
    reconciliation_failures = []
    for account in accounts:
        calculated = account.opening_balance + sum(
            entry.amount for entry in ledger if entry.bank_account_id == account.id
        )
        if calculated != account.recorded_closing_balance:
            reconciliation_failures.append(account.account_code)
    foreign_key_failures = session.scalar(
        select(func.count()).select_from(CashFlowForecast).where(
            (CashFlowForecast.legal_entity_id.is_(None))
            | (CashFlowForecast.bank_account_id.is_(None))
        )
    )
    counts = {
        "legal_entities": session.scalar(select(func.count()).select_from(LegalEntity)),
        "bank_accounts": session.scalar(select(func.count()).select_from(BankAccount)),
        "ledger_entries": session.scalar(select(func.count()).select_from(LedgerEntry)),
        "receivables": session.scalar(select(func.count()).select_from(Receivable)),
        "payables": session.scalar(select(func.count()).select_from(Payable)),
        "cash_flow_forecasts": session.scalar(select(func.count()).select_from(CashFlowForecast)),
        "currency_rates": session.scalar(select(func.count()).select_from(CurrencyRate)),
        "liquidity_scenarios": session.scalar(select(func.count()).select_from(LiquidityScenario)),
        "forecast_runs": session.scalar(select(func.count()).select_from(ForecastRun)),
    }
    return {
        "config": {**asdict(config), "simulation_start": config.simulation_start.isoformat()},
        "counts": counts,
        "checksum": _checksum(table_records),
        "validation": {
            "foreign_key_failures": foreign_key_failures or 0,
            "reconciliation_failures": reconciliation_failures,
            "all_forecast_sources_linked": all(
                (flow.receivable_id is not None) if flow.source_type == CashFlowType.RECEIVABLE
                else (flow.payable_id is not None)
                for flow in cash_flows
            ),
        },
    }


def main() -> None:
    from app.db import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--starter", action="store_true", help="Use the small review dataset.")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--simulation-start", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--forecast-horizon", type=int, default=72)
    parser.add_argument("--reset", action="store_true", help="Replace existing generated records.")
    args = parser.parse_args()
    config = GeneratorConfig.starter(args.seed) if args.starter else GeneratorConfig(seed=args.seed)
    config = replace(
        config,
        simulation_start=args.simulation_start,
        forecast_horizon=args.forecast_horizon,
    )
    with SessionLocal() as session:
        print(json.dumps(generate(session, config, reset=args.reset), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
