from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.calculations import calculate_run_positions
from app.generator import GeneratorConfig, generate
from app.models.base import Base
from app.models.entities import ForecastPosition, ForecastRunSourceSummary
from app.scenarios import execute_forecast


def test_scenarios_are_versioned_traceable_and_different() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        generate(session, GeneratorConfig.starter(), reset=True)
        base = execute_forecast(
            session, "BASE", simulation_date=date(2026, 1, 1), horizon_days=10
        )
        delayed = execute_forecast(
            session, "DELAYED-RECEIPTS", simulation_date=date(2026, 1, 1), horizon_days=10
        )
        stress = execute_forecast(
            session, "STRESS", simulation_date=date(2026, 1, 1), horizon_days=10
        )
        base_closing = {
            position.position_date: position.closing_balance
            for position in session.scalars(
                select(ForecastPosition).where(ForecastPosition.forecast_run_id == base.id)
            )
        }
        delayed_closing = {
            position.position_date: position.closing_balance
            for position in session.scalars(
                select(ForecastPosition).where(ForecastPosition.forecast_run_id == delayed.id)
            )
        }
        stress_closing = {
            position.position_date: position.closing_balance
            for position in session.scalars(
                select(ForecastPosition).where(ForecastPosition.forecast_run_id == stress.id)
            )
        }
        assert base.version == 2
        assert delayed.version == stress.version == 2
        assert str(base.status) == str(delayed.status) == "completed"
        assert any(base_closing[day] != delayed_closing[day] for day in base_closing)
        assert any(base_closing[day] != stress_closing[day] for day in base_closing)
        assert len(session.scalars(select(ForecastRunSourceSummary)).all()) == 12

        try:
            calculate_run_positions(session, base)
        except ValueError as error:
            assert "immutable" in str(error)
        else:
            raise AssertionError("Expected completed forecast run to be immutable")
