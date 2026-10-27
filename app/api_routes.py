from collections.abc import Generator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.calculations import reconcile_accounts
from app.models.entities import (
    BankAccount,
    CashFlowForecast,
    CurrencyRate,
    ForecastPosition,
    ForecastRun,
    LedgerEntry,
    LegalEntity,
    LiquidityScenario,
)
from app.scenarios import execute_forecast
from app.schemas import (
    BankAccountResponse,
    DatasetSummary,
    EntityResponse,
    ForecastRequest,
    ForecastRunResponse,
    HealthResponse,
    PositionResponse,
    ScenarioResponse,
    ValidationResponse,
)
from app.validation import detect_anomalies

# FastAPI dependency declarations use callable defaults by design.
# ruff: noqa: B008
router = APIRouter()


def get_db() -> Generator[Session, None, None]:
    from app.db import SessionLocal

    with SessionLocal() as session:
        yield session


@router.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_db)) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(status_code=503, detail="database unavailable") from error
    return HealthResponse(status="ok", database="ready")


@router.get("/summary", response_model=DatasetSummary)
def summary(session: Session = Depends(get_db)) -> DatasetSummary:
    models = {
        "legal_entities": LegalEntity,
        "bank_accounts": BankAccount,
        "cash_flow_forecasts": CashFlowForecast,
        "currency_rates": CurrencyRate,
        "liquidity_scenarios": LiquidityScenario,
        "forecast_runs": ForecastRun,
        "forecast_positions": ForecastPosition,
    }
    counts = {
        name: session.scalar(select(func.count()).select_from(model)) or 0
        for name, model in models.items()
    }
    currencies = list(
        session.scalars(select(CurrencyRate.currency).distinct().order_by(CurrencyRate.currency))
    )
    migration = session.scalar(text("SELECT version_num FROM alembic_version"))
    return DatasetSummary(counts=counts, currencies=currencies, latest_migration=migration)


@router.get("/entities", response_model=list[EntityResponse])
def entities(session: Session = Depends(get_db)) -> list[LegalEntity]:
    return list(session.scalars(select(LegalEntity).order_by(LegalEntity.entity_code).limit(500)))


@router.get("/accounts", response_model=list[BankAccountResponse])
def accounts(session: Session = Depends(get_db)) -> list[BankAccountResponse]:
    rows = session.execute(
        select(BankAccount, LegalEntity.entity_code)
        .join(LegalEntity)
        .order_by(BankAccount.account_code)
        .limit(500)
    )
    return [
        BankAccountResponse.model_validate(
            {
                **account.__dict__,
                "entity_code": entity_code,
            }
        )
        for account, entity_code in rows
    ]


@router.get("/scenarios", response_model=list[ScenarioResponse])
def scenarios(session: Session = Depends(get_db)) -> list[LiquidityScenario]:
    return list(session.scalars(select(LiquidityScenario).order_by(LiquidityScenario.scenario_code)))


@router.get("/rates")
def rates(session: Session = Depends(get_db), limit: int = Query(default=500, gt=0, le=5000)) -> list[dict]:
    return [
        {
            "currency": rate.currency,
            "base_currency": rate.base_currency,
            "rate_date": rate.rate_date,
            "rate": rate.rate,
        }
        for rate in session.scalars(
            select(CurrencyRate).order_by(CurrencyRate.rate_date, CurrencyRate.currency).limit(limit)
        )
    ]


@router.get("/ledger-entries")
def ledger_entries(
    session: Session = Depends(get_db), limit: int = Query(default=500, gt=0, le=5000)
) -> list[dict]:
    return [
        {
            "entry_code": entry.entry_code,
            "posted_on": entry.posted_on,
            "amount": entry.amount,
            "currency": entry.currency,
            "bank_account_id": entry.bank_account_id,
        }
        for entry in session.scalars(
            select(LedgerEntry).order_by(LedgerEntry.posted_on, LedgerEntry.entry_code).limit(limit)
        )
    ]


@router.get("/cash-flows")
def cash_flows(
    session: Session = Depends(get_db), limit: int = Query(default=500, gt=0, le=5000)
) -> list[dict]:
    return [
        {
            "forecast_code": flow.forecast_code,
            "source_type": str(flow.source_type),
            "expected_date": flow.expected_date,
            "amount": flow.amount,
            "currency": flow.currency,
            "legal_entity_id": flow.legal_entity_id,
            "bank_account_id": flow.bank_account_id,
            "receivable_id": flow.receivable_id,
            "payable_id": flow.payable_id,
        }
        for flow in session.scalars(
            select(CashFlowForecast)
            .order_by(CashFlowForecast.expected_date, CashFlowForecast.forecast_code)
            .limit(limit)
        )
    ]


@router.post("/forecast-runs", response_model=ForecastRunResponse, status_code=201)
def create_forecast(request: ForecastRequest, session: Session = Depends(get_db)) -> ForecastRun:
    try:
        run = execute_forecast(
            session,
            request.scenario_code,
            simulation_date=request.simulation_date,
            horizon_days=request.horizon_days,
            base_currency=request.base_currency,
            information_cutoff=request.information_cutoff,
            threshold=request.threshold,
        )
        return {
            "run_code": run.run_code,
            "version": run.version,
            "simulation_date": run.simulation_date,
            "information_cutoff": run.information_cutoff,
            "horizon_days": run.horizon_days,
            "base_currency": run.base_currency,
            "status": str(run.status),
            "scenario_code": run.scenario.scenario_code,
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/forecast-runs", response_model=list[ForecastRunResponse])
def forecast_runs(session: Session = Depends(get_db)) -> list[ForecastRunResponse]:
    runs = session.scalars(
        select(ForecastRun).order_by(ForecastRun.simulation_date.desc(), ForecastRun.version.desc())
    ).all()
    return [
        ForecastRunResponse(
            run_code=run.run_code,
            version=run.version,
            simulation_date=run.simulation_date,
            information_cutoff=run.information_cutoff,
            horizon_days=run.horizon_days,
            base_currency=run.base_currency,
            status=str(run.status),
            scenario_code=run.scenario.scenario_code,
        )
        for run in runs
    ]


@router.get("/forecast-runs/{run_code}/positions", response_model=list[PositionResponse])
def positions(run_code: str, session: Session = Depends(get_db)) -> list[ForecastPosition]:
    run = session.scalar(select(ForecastRun).where(ForecastRun.run_code == run_code))
    if run is None:
        raise HTTPException(status_code=404, detail="forecast run not found")
    return list(
        session.scalars(
            select(ForecastPosition)
            .where(ForecastPosition.forecast_run_id == run.id)
            .order_by(ForecastPosition.position_date)
        )
    )


@router.get("/validation", response_model=list[ValidationResponse])
def validation(
    cutoff: date = Query(default=date(2026, 1, 1)),
    session: Session = Depends(get_db),
) -> list[ValidationResponse]:
    return [
        ValidationResponse(issue_type=item.issue_type, explanation=item.explanation)
        for item in detect_anomalies(session, cutoff)
    ]


@router.get("/reconciliation")
def reconciliation(session: Session = Depends(get_db)) -> dict[str, object]:
    result = reconcile_accounts(session)
    return {"checked_accounts": result.checked_accounts, "failures": list(result.failures)}
