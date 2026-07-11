# Contributing

Thank you for improving RanD.

## Development setup

Run these commands from research-runtime:

    uv sync --all-groups
    uv run ruff check .
    uv run mypy src tests
    uv run pytest

Changes to artifacts must update the Draft 2020-12 schema, validator, fixtures,
and legacy compatibility tests together. Changes to live delivery must retain
the two-part confirmation gate and use tracker-bridge as the external sync
history authority.

## Pull requests

Keep the release sequence separated:

1. locking, atomic artifact commit, and CLI status;
2. artifact contract and external boundaries;
3. tracker-bridge outbound issue support;
4. RanD live transport and pinned tracker version;
5. governance, CI, and release evidence.

Do not commit credentials, generated live issues, local SQLite databases,
runtime state, or run artifacts.