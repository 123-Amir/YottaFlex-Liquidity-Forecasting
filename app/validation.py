"""Controlled anomaly injection, detection, ground truth, and evaluation."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ActualCashFlow,
    BankAccount,
    CashFlowForecast,
    CashFlowType,
    CurrencyRate,
    LedgerEntry,
)


@dataclass(frozen=True)
class AnomalyCase:
    anomaly_id: str
    issue_type: str
    expected_decision: str
    record_reference: str


@dataclass(frozen=True)
class Detection:
    anomaly_id: str
    issue_type: str
    explanation: str


def inject_anomalies(session: Session, cutoff: date) -> list[AnomalyCase]:
    """Create five labelled anomalies in a review database only."""
    account = session.scalar(select(BankAccount).order_by(BankAccount.id).limit(1))
    ledger = session.scalar(
        select(LedgerEntry).where(LedgerEntry.bank_account_id == account.id).limit(1)
    )
    flow = session.scalar(
        select(CashFlowForecast)
        .where(CashFlowForecast.currency != "USD")
        .order_by(CashFlowForecast.id)
        .limit(1)
    )
    rate = session.scalar(
        select(CurrencyRate).where(
            CurrencyRate.currency == flow.currency,
            CurrencyRate.rate_date == flow.expected_date,
        )
    )
    if not all((account, ledger, flow, rate)):
        raise ValueError("Anomaly injection requires baseline accounts, ledger, flows, and rates")

    account.recorded_closing_balance += Decimal("1.00")
    duplicate = CashFlowForecast(
        forecast_code=f"{flow.forecast_code}-DUP",
        source_type=flow.source_type,
        expected_date=flow.expected_date,
        amount=flow.amount,
        currency="USD" if flow.currency != "USD" else "EUR",
        description="Controlled duplicate of an existing source flow",
        legal_entity_id=flow.legal_entity_id,
        bank_account_id=flow.bank_account_id,
        receivable_id=flow.receivable_id,
        payable_id=flow.payable_id,
    )
    session.add(duplicate)
    session.add(
        ActualCashFlow(
            actual_code="ACT-LOOKAHEAD-000001",
            occurred_on=cutoff,
            recorded_at=cutoff.replace(day=min(cutoff.day + 1, 28)),
            amount=flow.amount,
            currency=flow.currency,
            source_type=CashFlowType.RECEIVABLE,
            cash_flow_id=flow.id,
            legal_entity_id=flow.legal_entity_id,
        )
    )
    session.delete(rate)
    session.flush()
    return [
        AnomalyCase("ANOM-001", "reconciliation_mismatch", "reject_account", account.account_code),
        AnomalyCase("ANOM-002", "missing_fx_rate", "raise_exception", f"{rate.currency}/{rate.base_currency}"),
        AnomalyCase("ANOM-003", "duplicate_cash_flow", "count_once", flow.forecast_code),
        AnomalyCase("ANOM-004", "cutoff_lookahead", "exclude_actual", "ACT-LOOKAHEAD-000001"),
        AnomalyCase("ANOM-005", "mixed_currency_aggregation", "reject_unconverted_sum", flow.forecast_code),
    ]


def detect_anomalies(session: Session, cutoff: date) -> list[Detection]:
    detections: list[Detection] = []
    for account in session.scalars(select(BankAccount)):
        movement_total = session.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.bank_account_id == account.id
            )
        )
        if account.opening_balance + movement_total != account.recorded_closing_balance:
            detections.append(Detection("ANOM-001", "reconciliation_mismatch", account.account_code))
    duplicate_sources = session.execute(
        select(CashFlowForecast.receivable_id, func.count(CashFlowForecast.id))
        .where(CashFlowForecast.receivable_id.is_not(None))
        .group_by(CashFlowForecast.receivable_id)
        .having(func.count(CashFlowForecast.id) > 1)
    ).all()
    if duplicate_sources:
        detections.append(Detection("ANOM-003", "duplicate_cash_flow", "shared receivable source"))
    required_rates = session.execute(
        select(CashFlowForecast.currency, CashFlowForecast.expected_date)
        .where(CashFlowForecast.currency != "USD")
        .distinct()
    ).all()
    missing_rates = [
        (currency, rate_date)
        for currency, rate_date in required_rates
        if session.scalar(
            select(CurrencyRate.id).where(
                CurrencyRate.currency == currency,
                CurrencyRate.base_currency == "USD",
                CurrencyRate.rate_date == rate_date,
            )
        )
        is None
    ]
    if missing_rates:
        detections.append(Detection("ANOM-002", "missing_fx_rate", str(missing_rates[0])))
    lookahead = session.scalar(
        select(func.count()).select_from(ActualCashFlow).where(
            ActualCashFlow.occurred_on <= cutoff,
            ActualCashFlow.recorded_at > cutoff,
        )
    )
    if lookahead:
        detections.append(Detection("ANOM-004", "cutoff_lookahead", "actual recorded after cutoff"))
    mixed_currency_flow = session.scalar(
        select(CashFlowForecast.forecast_code)
        .join(BankAccount, CashFlowForecast.bank_account_id == BankAccount.id)
        .where(CashFlowForecast.currency != BankAccount.currency)
        .limit(1)
    )
    if mixed_currency_flow:
        detections.append(
            Detection(
                "ANOM-005",
                "mixed_currency_aggregation",
                f"cash flow {mixed_currency_flow} differs from its account currency without an explicit aggregation conversion",
            )
        )
    return detections


def evaluate(ground_truth: list[AnomalyCase], detections: list[Detection]) -> dict[str, object]:
    expected = {case.issue_type for case in ground_truth}
    found = {detection.issue_type for detection in detections}
    true_positive = len(expected & found)
    false_positive = len(found - expected)
    false_negative = len(expected - found)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "by_issue_type": {
            issue_type: issue_type in found for issue_type in sorted(expected)
        },
    }


def export_ground_truth(cases: list[AnomalyCase], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(case) for case in cases], indent=2), encoding="utf-8")
    with path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=asdict(cases[0]).keys())
        writer.writeheader()
        writer.writerows(asdict(case) for case in cases)
