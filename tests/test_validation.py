from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.generator import GeneratorConfig, generate
from app.models.base import Base
from app.validation import detect_anomalies, evaluate, export_ground_truth, inject_anomalies


def test_anomaly_ground_truth_is_separate_and_detected(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        generate(session, GeneratorConfig.starter(), reset=True)
        truth = inject_anomalies(session, date(2026, 1, 1))
        session.commit()
        detections = detect_anomalies(session, date(2026, 1, 1))
        metrics = evaluate(truth, detections)
        export_ground_truth(truth, tmp_path / "ground_truth.json")

    assert len(truth) == 5
    assert metrics["recall"] == 1.0
    assert metrics["precision"] == 1.0
    assert (tmp_path / "ground_truth.json").exists()
    assert (tmp_path / "ground_truth.csv").exists()
