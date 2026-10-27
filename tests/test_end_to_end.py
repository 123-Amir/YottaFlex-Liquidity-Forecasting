from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.calculations import reconcile_accounts
from app.generator import GeneratorConfig, generate
from app.models.base import Base
from app.models.entities import ForecastPosition, ForecastRun
from app.scenarios import execute_forecast
from app.validation import detect_anomalies


def test_clean_starter_end_to_end_workflow() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        report = generate(session, GeneratorConfig.starter(), reset=True)
        run = execute_forecast(
            session,
            "BASE",
            simulation_date=date(2026, 1, 1),
            horizon_days=10,
        )
        reconciliation = reconcile_accounts(session)

        assert report["validation"]["reconciliation_failures"] == []
        assert run.status == "completed"
        assert session.scalar(
            select(ForecastPosition).where(ForecastPosition.forecast_run_id == run.id).limit(1)
        )
        assert reconciliation.failures == ()
        assert detect_anomalies(session, date(2026, 1, 1)) == []
        assert session.scalar(select(ForecastRun).where(ForecastRun.id == run.id)) is not None
