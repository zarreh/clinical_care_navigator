# Run it yourself

Everything here runs from a clean clone. No account, no course data, and no real
patient data is involved at any point.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Docker (optional, for `make up`)
- An OpenAI API key, for the phases that make model calls

## Setup

```bash
git clone <repo>
cd clinical_care_navigator
uv sync --extra dev
cp .env.example .env       # add NAVIGATOR_OPENAI_API_KEY
```

## Build the data

```bash
make data
```

This generates the synthetic Synthea population, builds the record store,
renders the clinical notes, fetches the public-domain education content, and
generates the safety policy tables. It writes nothing outside `data/`, and
`data/` is gitignored.

The build **fails loudly** rather than coercing: an education row with an
unresolvable citation, or a reference-range row with no cited source, stops the
build.

## Run

```bash
make dev          # http://localhost:8000  (docs at /docs)
make up           # the same thing in Docker
```

## Check

```bash
make check        # ruff, mypy --strict, import-linter, pytest
make eval         # layer 1 canonical regression set
make docs         # this site, locally
```

## Configuration worth knowing about

| Setting | Default | Effect |
|---|---|---|
| `NAVIGATOR_AUTONOMY_LEVEL` | `L2_balanced` | Moves the inform/recommend boundary. Never moves the escalation boundary |
| `NAVIGATOR_MAX_TOOL_CALLS` | `12` | Per-run ceiling; breach ends the run conservatively |
| `NAVIGATOR_CITATION_COVERAGE_FLOOR` | `1.0` | Below this, the run repairs once before publishing |

There is no setting that points this application at a real record system.
