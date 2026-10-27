from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.calculations import MissingFXRateError, effective_fx_rate, quantize_money
from app.models.base import Base
from app.models.entities import CurrencyRate


def test_decimal_rounding_and_effective_rate_selection() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add_all(
            [
                CurrencyRate(currency="EUR", base_currency="USD", rate_date=date(2026, 1, 1), rate=Decimal("1.10")),
                CurrencyRate(currency="EUR", base_currency="USD", rate_date=date(2026, 1, 5), rate=Decimal("1.20")),
            ]
        )
        session.commit()
        rate, rate_date = effective_fx_rate(session, "EUR", "USD", date(2026, 1, 6))
        assert rate == Decimal("1.20")
        assert rate_date == date(2026, 1, 5)
        assert quantize_money(Decimal("1.005")) == Decimal("1.01")


def test_missing_fx_rate_is_explicit() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session, pytest.raises(MissingFXRateError):
        effective_fx_rate(session, "JPY", "USD", date(2026, 1, 1))
