# YottaFlex Liquidity Forecasting

An explainable, locally runnable liquidity forecasting platform built with
Python, FastAPI, SQLAlchemy, PostgreSQL, Alembic, and Docker.

The project models short-term cash positions across multiple legal entities,
bank accounts, currencies, receivables, payables, ledger movements, FX rates,
scenarios, and forecast runs. The emphasis is on financial correctness,
traceability, deterministic data, and operational validation—not just producing
a forecast number.

## Why this project stands out

- **Reproducible:** fixed-seed synthetic data produces stable row counts and
  logical-record checksums.
- **Explainable:** every forecast run stores its scenario, assumptions,
  information cutoff, source summaries, and daily positions.
- **Financially disciplined:** money uses `Decimal` arithmetic, explicit
  rounding, effective-dated FX selection, and reconciliation checks.
- **Scenario-aware:** BASE, DELAYED-RECEIPTS, and STRESS runs are versioned and
  immutable after completion.
- **Failure-aware:** missing FX rates, duplicate cash flows, cutoff leakage,
  mixed currencies, and reconciliation mismatches are detected explicitly.
- **Reviewable:** the project includes migrations, tests, API contracts,
  documentation, sample exports, and a clean local setup.

## Verified dataset scale

The full synthetic dataset contains:

| Dataset | Records |
|---|---:|
| Legal entities | 30 |
| Bank accounts | 150 |
| Ledger entries | 100,000 |
| Receivables | 10,000 |
| Payables | 10,000 |
| Forecast cash flows | 20,000 |
| FX rates | 365 |
| Currencies | 5 |
| Scenarios | 3 |

The reviewed full-dataset checksum is:

```text
41dad9684ed0d88d532e8b53fcda1a005c2f90cf37f77061b836c06455b2bae0
```

## Architecture

```text
PostgreSQL
    |
SQLAlchemy models + Alembic migrations
    |
Deterministic generator
    |
Financial calculation and scenario services
    |
Validation and anomaly detection
    |
FastAPI API + lightweight browser dashboard
```

Important modules:

- [app/models/entities.py](app/models/entities.py) — domain entities and
  relationships.
- [app/generator.py](app/generator.py) — starter/full-scale deterministic
  synthetic data generation.
- [app/calculations.py](app/calculations.py) — balances, FX conversion,
  reconciliation, and forecast positions.
- [app/scenarios.py](app/scenarios.py) — immutable, versioned scenario runs.
- [app/validation.py](app/validation.py) — controlled anomaly review and
  precision/recall/F1 evaluation.
- [app/api_routes.py](app/api_routes.py) — typed FastAPI endpoints.
- [app/main.py](app/main.py) — application entry point and dashboard.

## Run it locally

### Requirements

- Python 3.12+
- Docker Desktop with the Linux engine
- PostgreSQL 16 through Docker Compose

### 1. Install and start PostgreSQL

```powershell
Copy-Item .env.example .env
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
```

### 2. Generate a safe starter dataset

```powershell
python -m app.generator --starter --seed 20261022 --reset
```

The command prints counts, a deterministic checksum, and validation results.
Running it twice with the same seed produces the same result.

`--reset` replaces generated records, so use it only with a disposable local
database.

### 3. Start the application

```powershell
python -m uvicorn app.main:app --reload
```

Open:

- Dashboard: <http://127.0.0.1:8000/>
- OpenAPI documentation: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/api/health>

## API capabilities

The API provides:

- dataset summary and health checks;
- legal entities, bank accounts, ledger entries, cash flows, and FX rates;
- available liquidity scenarios;
- forecast-run execution and version history;
- daily forecast positions;
- validation findings;
- account reconciliation results.

Forecast execution is explicit through `POST /api/forecast-runs`. Destructive
generation and anomaly-injection operations are intentionally not exposed as
public API routes.

## Financial calculation approach

- Monetary values use PostgreSQL `NUMERIC` columns and Python `Decimal`.
- Monetary outputs use explicit `ROUND_HALF_UP` quantization.
- FX selection uses the latest rate with `rate_date <= calculation_date`.
- Missing rates raise `MissingFXRateError`; they do not silently fall back.
- Account reconciliation checks:

  ```text
  recorded closing balance =
  opening balance + signed ledger movements
  ```

- Forecast positions consolidate all accounts into the configured base
  currency.
- Completed forecast runs cannot be recalculated in place.

Detailed formulas and assumptions are documented in
[docs/calculations.md](docs/calculations.md).

## Scenario modeling

| Scenario | Documented assumption |
|---|---|
| BASE | Expected receipt and payment dates |
| DELAYED-RECEIPTS | Eligible receivables shift by five calendar days |
| STRESS | Receivables shift by five days and adverse FX is applied |

Each scenario run stores:

- scenario code and version;
- assumptions snapshot;
- information cutoff;
- source record counts and checksums;
- daily positions;
- completion status.

## Validation and controlled anomalies

The isolated review harness covers five negative scenarios:

1. opening balance and ledger movements do not reconcile;
2. a required FX rate is missing;
3. a cash flow is counted twice;
4. an actual is recorded after the information cutoff;
5. a currency is mixed without conversion.

Ground truth is kept separate from operational detector inputs. The synthetic
five-case review achieved:

```text
True positives: 5
False positives: 0
False negatives: 0
Precision: 1.0
Recall: 1.0
F1: 1.0
```

This result measures the controlled review sample only; it is not a claim of
production predictive performance. See
[docs/validation.md](docs/validation.md).

## Testing and acceptance evidence

Current checks:

```powershell
pytest -q
ruff check app migrations tests
python -m compileall -q app migrations tests
alembic check
```

Latest result:

```text
11 passed
Ruff passed
Compilation passed
No new Alembic upgrade operations detected
```

An isolated full-scale benchmark completed with:

```text
Generation: 83.284 seconds
72-day forecast: 18.936 seconds
Foreign-key failures: 0
Reconciliation failures: 0
All forecast sources linked: True
```

## Documentation and sample exports

- [docs/data-model.md](docs/data-model.md) — entity relationships and schema.
- [docs/calculations.md](docs/calculations.md) — calculation rules and
  rounding.
- [docs/validation.md](docs/validation.md) — anomaly definitions and metrics.
- [docs/reproducibility.md](docs/reproducibility.md) — clean setup and
  handoff procedure.
- [docs/prompt-history.md](docs/prompt-history.md) — phased development
  summary.
- [docs/ai-use-disclosure.md](docs/ai-use-disclosure.md) — transparent AI-use
  disclosure.
- [docs/public-repository-checklist.md](docs/public-repository-checklist.md) —
  publication safety review.
- [sample_exports/summary.json](sample_exports/summary.json) and
  [sample_exports/positions.csv](sample_exports/positions.csv) — synthetic
  reviewer examples.
