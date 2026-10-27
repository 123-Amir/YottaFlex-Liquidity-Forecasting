# Reproducibility and handoff

## Requirements

- Python 3.12+
- Docker Desktop with the Linux engine
- PostgreSQL 16 through Docker Compose

## Clean local setup

```powershell
Copy-Item .env.example .env
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
python -m app.generator --starter --seed 20261022 --reset
```

The starter generator prints counts, a logical-record checksum, and validation
results. Running it twice with the same seed must produce the same counts and
checksum.

## Full dataset

Only run the full generator against a disposable local database:

```powershell
python -m app.generator --seed 20261022 --reset
```

The reviewed full-scale checksum is:

```text
41dad9684ed0d88d532e8b53fcda1a005c2f90cf37f77061b836c06455b2bae0
```

## Verification commands

```powershell
alembic check
ruff check app migrations tests
python -m compileall -q app migrations tests
pytest -q
```

Start the application with:

```powershell
python -m uvicorn app.main:app --reload
```

The dashboard is available at `http://127.0.0.1:8000/` and OpenAPI at
`http://127.0.0.1:8000/docs`.

## Isolation rules

The generator's `--reset` option replaces local records. Never use it against a
shared or production database. Phase review and benchmark runs should use a
separate database or an in-memory test database.
