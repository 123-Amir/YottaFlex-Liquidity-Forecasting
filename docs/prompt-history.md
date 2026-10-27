# Prompt history

This project was developed in explicit phases so that each completed phase
could be reviewed before the next phase started.

## Phase 2 — database foundation

- Implement SQLAlchemy entities and relationships.
- Configure PostgreSQL and Alembic migrations.
- Add a local Docker Compose PostgreSQL service.
- Verify the schema against a fresh database.

## Phase 3 — deterministic data generation

- Implement starter and full-scale synthetic data generation.
- Use a stable seed, business identifiers, and logical checksums.
- Verify repeatability, foreign keys, source links, and reconciliation.
- Generate the reviewed full dataset only after starter-mode review.

## Phase 4 — financial calculations

- Implement effective-dated FX selection and explicit missing-rate errors.
- Calculate daily account balances and consolidated forecast positions.
- Use Decimal arithmetic and explicit monetary rounding.
- Verify all accounts and currencies, not only one legal entity.

## Phase 5 — scenarios and immutable runs

- Add scenario adjustments, information cutoffs, assumptions snapshots,
  source summaries, and versioned forecast runs.
- Preserve completed runs and reject in-place recalculation.
- Verify scenario isolation and traceability.

## Phase 6 — validation

- Add five controlled anomaly cases and operational detectors.
- Keep ground truth separate from detector inputs.
- Export ground truth as JSON and CSV.
- Measure precision, recall, and F1 on the isolated synthetic review sample.

## Phase 7 — API and dashboard

- Add typed FastAPI contracts and read-oriented API routes.
- Add explicit forecast execution and OpenAPI documentation.
- Add a lightweight browser dashboard.
- Verify live PostgreSQL endpoint responses.

## Phase 8 — acceptance and performance

- Add end-to-end, API-validation, scenario-isolation, and clean-data tests.
- Verify migration drift, compilation, and static checks.
- Measure full-scale generation and 72-day forecast execution in isolation.

## Phase 9 — documentation and handoff

- Document reproducibility, AI assistance, limitations, and public-repository
  safety requirements.
- Add safe synthetic sample exports for reviewers.
- Do not alter the reviewed PostgreSQL dataset.

The prompts above are concise summaries of the implementation requests. They
are not intended to reproduce private conversation content or credentials.
