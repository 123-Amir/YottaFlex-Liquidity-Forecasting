# Phase 4 calculation rules

## Rounding

Financial amounts use `Decimal` arithmetic and are quantized to `0.01` using
`ROUND_HALF_UP` at monetary output boundaries. FX rates retain up to eight
decimal places.

## Account reconciliation

For each bank account:

```text
calculated closing = opening balance + sum(signed ledger movements)
```

The calculated value must equal `recorded_closing_balance`. A mismatch is
reported as a reconciliation failure; it is never silently corrected.

## Effective-dated FX

For a source currency and reporting currency on a calculation date, the
selected rate is the latest rate whose `rate_date` is less than or equal to
that date. Same-currency conversions use rate `1.00000000`. A missing
cross-currency rate raises an explicit `MissingFXRateError`.

Every daily account balance retains:

- source currency and source amount
- selected FX rate and effective rate date
- reporting/base currency and converted amount

## Daily positions

For each forecast day:

```text
closing liquidity =
    opening liquidity
    + eligible converted inflows
    - eligible converted outflows
```

Baseline eligibility uses scheduled forecast items whose expected date equals
the calculation date. Scenario execution applies only the adjustments attached
to that scenario:

- **BASE** leaves dates, amounts, and FX unchanged.
- **DELAYED-RECEIPTS** shifts eligible receivables by five calendar days.
- **STRESS** shifts those receivables by five days and applies the documented
  `0.9500` FX multiplier to the adjusted incoming flows.

`DailyAccountBalance` stores account-level ledger balances and conversion
evidence. `ForecastPosition` stores the consolidated reporting-currency
position for each forecast run and date.

## Immutable scenario runs

Every execution creates a new `ForecastRun` version. Completed runs cannot be
recalculated in place. Each run stores its scenario assumptions snapshot,
information cutoff, reporting currency, and source-reference marker. The
`ForecastRunSourceSummary` rows record counts, stable checksums, and source
version for legal entities, bank accounts, ledger entries, and forecast cash
flows. Individual cash-flow records retain their receivable/payable and bank
account foreign keys for detailed traceability.
