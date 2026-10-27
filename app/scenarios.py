"""Immutable, versioned scenario forecast execution."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.calculations import calculate_run_positions
from app.models.entities import (
    BankAccount,
    CashFlowForecast,
    ForecastRun,
    ForecastRunSourceSummary,
    ForecastRunStatus,
    LedgerEntry,
    LegalEntity,
    LiquidityScenario,
)


def _checksum(values: list[str]) -> str:
    payload = json.dumps(sorted(values), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def execute_forecast(
    session: Session,
    scenario_code: str,
    *,
    simulation_date: date,
    horizon_days: int,
    base_currency: str = "USD",
    information_cutoff: date | None = None,
    threshold: Decimal | None = None,
) -> ForecastRun:
    """Create and complete a new immutable run for a documented scenario."""
    scenario = session.scalar(
        select(LiquidityScenario).where(LiquidityScenario.scenario_code == scenario_code)
    )
    if scenario is None:
        raise ValueError(f"Unknown liquidity scenario: {scenario_code}")
    entity = session.scalar(select(LegalEntity).order_by(LegalEntity.id).limit(1))
    if entity is None:
        raise ValueError("Cannot execute a forecast without a legal entity")
    previous_version = session.scalar(
        select(func.max(ForecastRun.version)).where(
            ForecastRun.scenario_id == scenario.id,
            ForecastRun.simulation_date == simulation_date,
        )
    )
    version = (previous_version or 0) + 1
    run = ForecastRun(
        run_code=f"FCAST-{simulation_date}-{scenario.scenario_code}-{version:03d}",
        version=version,
        simulation_date=simulation_date,
        horizon_days=horizon_days,
        status=ForecastRunStatus.RUNNING,
        base_currency=base_currency,
        information_cutoff=information_cutoff or simulation_date,
        assumptions_snapshot=json.dumps(
            {
                "scenario_code": scenario.scenario_code,
                "description": scenario.description,
                "assumptions": scenario.assumptions,
                "threshold": str(threshold) if threshold is not None else None,
            },
            sort_keys=True,
        ),
        source_reference="phase5-source-summaries",
        legal_entity_id=entity.id,
        scenario_id=scenario.id,
    )
    session.add(run)
    session.flush()

    source_groups = {
        "legal_entities": session.scalars(select(LegalEntity)).all(),
        "bank_accounts": session.scalars(select(BankAccount)).all(),
        "ledger_entries": session.scalars(select(LedgerEntry)).all(),
        "cash_flow_forecasts": session.scalars(select(CashFlowForecast)).all(),
    }
    for kind, records in source_groups.items():
        codes = [
            str(getattr(record, "entity_code", None)
                or getattr(record, "account_code", None)
                or getattr(record, "entry_code", None)
                or getattr(record, "forecast_code", None))
            for record in records
        ]
        session.add(
            ForecastRunSourceSummary(
                source_kind=kind,
                record_count=len(records),
                source_checksum=_checksum(codes),
                source_version="baseline-v1",
                forecast_run_id=run.id,
            )
        )
    try:
        calculate_run_positions(session, run, scenario=scenario, threshold=threshold)
        run.status = ForecastRunStatus.COMPLETED
        session.commit()
    except Exception:
        run.status = ForecastRunStatus.FAILED
        session.commit()
        raise
    return run
