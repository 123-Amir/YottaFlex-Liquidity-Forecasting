from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.generator import CURRENCIES, GeneratorConfig, generate
from app.models.base import Base


def test_starter_generation_is_deterministic_and_reconciles() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        first = generate(session, GeneratorConfig.starter(), reset=True)
        second = generate(session, GeneratorConfig.starter(), reset=True)

    assert first["counts"] == second["counts"]
    assert first["checksum"] == second["checksum"]
    assert first["validation"] == {
        "foreign_key_failures": 0,
        "reconciliation_failures": [],
        "all_forecast_sources_linked": True,
    }


def test_full_scale_targets_and_currency_requirements_are_configured() -> None:
    config = GeneratorConfig()

    assert (config.entities, config.accounts) == (30, 150)
    assert (config.ledger_entries, config.forecast_items) == (100_000, 20_000)
    assert config.seed == 20261022
    assert len(CURRENCIES) == 5
    assert "USD" in CURRENCIES
