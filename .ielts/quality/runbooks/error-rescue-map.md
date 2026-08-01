# Error and Rescue Map (W1)

| Codepath | Exception Class | Rescue Action | Retry Policy | Operator Sees |
| --- | --- | --- | --- | --- |
| replay-runner | TimeoutError | mark run failed, emit recommendation | retry 1x with backoff | timeout in run report |
| replay-runner | JSONDecodeError | reject malformed output, log payload hash | none | malformed-output warning |
| gate-evaluator | ValueError (threshold parse) | block gate, fallback to report-only | none | threshold-parse-error |
| trigger-router | DuplicateRunError | dedupe by run key | none | duplicate-run-skipped |
| snapshot-loader | StaleSnapshotError | abort run, require re-run | none | stale-snapshot-warning |
