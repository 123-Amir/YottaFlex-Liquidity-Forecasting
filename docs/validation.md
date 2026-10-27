# Phase 6 validation and anomaly evaluation

## Controlled anomaly cases

The review harness creates valid baseline data first, then injects exactly five
labelled cases in a separate review database:

1. `reconciliation_mismatch`: recorded closing balance differs from opening
   balance plus signed ledger movements.
2. `missing_fx_rate`: a required currency/date rate is removed.
3. `duplicate_cash_flow`: a second forecast record references the same source
   receivable.
4. `cutoff_lookahead`: an actual is recorded after the information cutoff.
5. `mixed_currency_aggregation`: multiple source currencies are present and
   must not be summed without conversion.

The labels are represented only by `AnomalyCase` values and exported to
`ground_truth.json` and `ground_truth.csv`. Detectors query operational records
without reading those labels. Ground truth is used only after detection for
evaluation.

## Metrics

For issue-type evaluation:

```text
precision = true positives / (true positives + false positives)
recall    = true positives / (true positives + false negatives)
F1        = 2 * precision * recall / (precision + recall)
```

An empty denominator returns `0.0`. This Phase 6 result uses a five-case
synthetic review sample, not production data and not predictive performance.
Forecast error metrics and actual-versus-forecast evaluation require actual
outcomes and remain later work.
