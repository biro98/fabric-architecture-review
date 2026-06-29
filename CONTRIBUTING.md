# Contributing

Thank you for your interest in contributing to the **Fabric Architecture Review Accelerator**! This project welcomes contributions and suggestions.

## Ground rules

By submitting a contribution you certify that you have the right to do so and that your
contribution may be distributed under the project's [MIT License](LICENSE). Please be
respectful and constructive — this project follows its [Code of Conduct](CODE_OF_CONDUCT.md).

## How to contribute

1. **Open an issue first** for anything beyond a trivial fix, so we can align on the approach.
2. **Fork** the repository and create a topic branch from `main`.
3. Make your change with clear, focused commits.
4. **Run the pipeline locally** against the sample data in `output/` (or your own tenant) to confirm nothing regresses.
5. Open a **pull request** describing the change and the motivation.

## The data-safety contract (mandatory)

This accelerator's core promise is that **it never reads customer business data** — only
metadata, configuration, inventory, and metrics. Any contribution is automatically
rejected if it:

- Issues `EVALUATE` / `SELECT` against tables that contain customer data (the only DAX
  permitted targets the Microsoft-published Capacity Metrics App, gated behind a flag),
- Downloads OneLake file contents,
- Reads notebook cell **outputs**,
- Enables Scanner API scopes that return PII (`getArtifactUsers`, `datasetSchema`,
  `datasetExpressions`, `datasourceDetails`),
- Persists raw API payloads outside the gitignored `output/raw/` folder.

Every collector module must carry a `# DATA SAFETY:` comment documenting exactly what it
reads. See [docs/data-safety.md](docs/data-safety.md) for the full allow / deny list.

## Adding a rule, collector, or analyzer

See the **[Extending the framework](README.md#-extending-the-framework)** section of the
README for the end-to-end pattern (collector → analyzer → checklist → thresholds). Key
points:

- Numeric pass/fail boundaries belong in [config/thresholds.yaml](config/thresholds.yaml),
  resolved via `analyzers._common.threshold()` — do not hard-code magic numbers.
- Rule metadata (id, dimension, severity, description, Learn URL) belongs in
  [config/review-checklist.yaml](config/review-checklist.yaml).
- Findings are dicts with `rule_id`, `dimension`, `severity`, `status`
  (`pass`/`fail`/`info`), `title`, `evidence`, `recommendation`.

## Code style

- Python 3.11+, standard library + the dependencies in `requirements.txt`.
- Keep collectors metadata-only and resilient: degrade gracefully (emit an `info`
  finding) when a permission or input is missing rather than crashing the run.
