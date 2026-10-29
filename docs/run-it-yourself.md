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
make run          # API on :8000 and the frontend on :3000 together
make dev          # API only, http://localhost:8000  (docs at /docs)
make up           # the API in Docker
```

Nothing calls the model until you ask: the homepage explains the app and offers
four example questions plus a free-text box. A live run takes roughly 15–40
seconds; questions stopped at pre-flight finish in a second or two. Each run gets
its own URL (`/?run=<id>`), so a refresh or a shared link replays it from the
store.

If the API restarts while a run is in flight, that run can never finish. On
startup the API marks such runs `failed` ("interrupted by a server restart") and
returns any review left mid-decision to `pending`, so the UI shows an error
instead of spinning. This assumes **one API process** owns the run store; do not
run several workers against the same `runs.db`.

## Choose who you are asking as

The app has no sign-in, so the homepage asks **"Who are you asking as?"** and
offers a handful of synthetic patients. They are picked at runtime from the record
store by what each record can show off, ranked by how much history it has, so they
stay correct when the data is rebuilt:

| Persona | Chosen as | Good for |
|---|---|---|
| A full record | The richest history in the data | Asking about labs, medications and conditions |
| A hidden critical value | The patient the build planted a critical potassium on | The safety override |
| Basic health literacy | The richest *other* basic-literacy patient with an A1c | The easier reading target (grade 6) and its measured grade |
| Spanish-speaking patient | The richest Spanish-language patient with an A1c | The stated-limitation reply |
| A visit note with a planted instruction | The patient the build planted an injected note on | Showing a note is treated as data, not obeyed |

The two patients tied to planted data are whoever the data build planted the fact
on, so their histories are not chosen for size; the cards show each record's size so
you can see that. A role the data cannot fill is skipped, and a small store is
topped up with its richest patients, so the list is never empty.

The choice lives in the URL (`?patient=…`), so a shared link keeps who it was asked
as, and every run and every held review shows its patient. The four example
questions ask as the persona whose record they need.

!!! warning "A demo selector, not authentication"
    Choosing a patient on the page is not the same as being that patient. The API
    only answers as these personas (`NAVIGATOR_DEMO_PATIENTS_ONLY`), which keeps a
    caller from reading arbitrary records, but it does not know who you are. Real
    use needs sign-in: the server would learn the patient from the session instead
    of from the request, and `GET /personas` and the picker would go away.

## Follow-up questions

An answer is not the end of the conversation. Under a finished answer there is an
**Ask a follow-up** box, so you can say *"what about the one before that?"* or *"is
that normal?"* and be understood. The earlier questions fold away above, each with its
status, and **Start a new conversation** begins again.

How it works, and why it is still safe:

- **A follow-up is an ordinary run.** It goes through the same graph, the same
  pre-flight gate, scoped tools and post-flight checks as any question. Nothing is
  skipped because it is "only" a follow-up, and a held draft goes to the clinician queue
  as usual.
- **One extra step, only when needed.** A new first step, `contextualize`, rewrites a
  message that depends on the earlier turns into a standalone question (*"Is that one
  normal?"* becomes *"Is my A1c result of 2.4% on August 5, 2026, normal?"*). A first
  question has no history, so it skips this step and costs nothing extra. The rewrite is
  shown in the run ("Understood as…") so you can see how you were understood.
- **A rewrite cannot lower the safety decision.** The deterministic red-flag screen
  reads both your own words and the rewrite, the classifier is shown both, and language
  is detected on what you typed. A symptom mentioned inside a follow-up still reaches
  emergency guidance. If the rewrite fails, the run carries on with exactly what you
  typed.
- **The patient never changes mid-conversation.** A follow-up stays with the patient
  the conversation began with; ask as someone else by starting a new conversation.
- **Only the latest answer can be followed up**, and only once it has finished, so a
  thread cannot fork. Answers held for a clinician are noted to the rewriter as "held",
  never quoted.
- **Conversations are capped** (`NAVIGATOR_MAX_CONVERSATION_TURNS`, default 8) and the
  rewriter sees only the most recent turns (`NAVIGATOR_CONVERSATION_CONTEXT_TURNS`,
  default 3), which bounds cost.

Behind the scenes a conversation is a chain of runs (`conversation_id` and `turn` on
each), and `GET /conversations/{id}/thread` lists a conversation's turns. Databases
created before follow-ups existed are upgraded in place on the next start.

## Demo the clinician review queue

Held answers only appear when post-flight refuses to publish a draft, which a
well-behaved model rarely produces, so the queue is usually empty. To demonstrate
the clinician's part, load four sample items:

```bash
make seed-reviews
```

Refresh `/reviews` and you will find four drafts, each held for a different
reason: one tells the patient what to do about their treatment, one contradicts
the patient's actual A1c, one makes a clinical claim with no evidence behind it,
and one is a safe "I don't have that, ask your care team" reply to a general
question (*"What is the bad cholesterol?"*) that post-flight held because its
only claim had nothing to cite. Approve, edit or decline each: a decision really resumes the paused run, and
you can open "See how this draft was produced" to follow it.

The drafts are **scripted**, not model output (it needs no API key and costs
nothing), but they run through the real graph, the real post-flight checks and the
real checkpoint store, and the text is built from the patient's real A1c result.
Running it twice is safe (cases already seeded are skipped); add `--again` to
create fresh copies after you have decided the first set:

```bash
uv run python -m navigator.api.demo_seed --again
```

On a deployed server, run it inside the API container:

```bash
docker compose -f compose.prod.yaml exec navigator-api python -m navigator.api.demo_seed
```

## Inspect the graph in LangGraph Studio

```bash
uv sync --extra dev   # installs the langgraph CLI
make studio           # local server on http://127.0.0.1:2024
```

`make studio` starts `langgraph dev` on the real navigator graph (the same
construction the API uses, from `src/navigator/studio.py`, registered in
`langgraph.json`). Open the Studio URL it prints
(`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`), pick the
`navigator` graph, and you can see all thirteen nodes, step through a run, inspect
the state after each node, and edit state and replay.

Studio starts a run from a state, not a question. Give it these three fields:

```json
{
  "question": "What is an A1c test?",
  "patient_id": "<a patient id from your record store>",
  "run_id": "studio-1"
}
```

Get a patient id with:

```bash
uv run python -c "from pathlib import Path; from navigator.store import RecordStore; print(RecordStore(Path('data/records.db')).patient_ids()[0])"
```

Things to know:

- It needs the data built (`make data`) and `NAVIGATOR_OPENAI_API_KEY` in `.env`,
  because it runs the real model.
- Studio supplies its own in-memory persistence, so the `enqueue_review`
  interrupt pauses and resumes inside Studio (resume with
  `{"action": "approve"}`), but nothing is written to `runs.db` or the review
  queue, and nothing shows up in the web app.
- The local server needs no key. The Studio page itself is hosted by LangChain
  and asks you to sign in to LangSmith in the browser.
- It is a development tool. Do not run it on a server.

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
| `NAVIGATOR_WRITE_RATE_LIMIT_PER_MINUTE` | `10` | Per client IP, per route, on routes that start or resume a model run (`POST /conversations`, `POST /reviews/{id}/decision`) |
| `NAVIGATOR_READ_RATE_LIMIT_PER_MINUTE` | `120` | Per client IP, per route, on reads and the event stream. One page view makes several of these |
| `NAVIGATOR_DEMO_PATIENTS_ONLY` | `true` | The API only answers as a demonstration persona (see below). Set `false` to allow any patient id in the store, for evals or development |
| `NAVIGATOR_DEMO_PATIENT_ID` | *(empty)* | The patient used when a request names none, and always allowed. Empty means the first persona |
| `NAVIGATOR_MAX_CONVERSATION_TURNS` | `8` | Questions allowed in one conversation; a further follow-up is refused with a clear message |
| `NAVIGATOR_CONVERSATION_CONTEXT_TURNS` | `3` | How many of the most recent turns the rewriter is shown |
| `NAVIGATOR_FRONTEND_ORIGINS` | `["http://localhost:3000"]` | CORS allow-list; set it to the public frontend origin in production. In development (`NAVIGATOR_ENVIRONMENT=development`, the default) any `localhost` port is also accepted, so `next dev` moving to :3001 keeps working; production trusts only this list |
| `NAVIGATOR_RUN_STORE_PATH` / `NAVIGATOR_CHECKPOINT_DB_PATH` | `data/runs.db` / `data/checkpoints.db` | Point these at throwaway files to try things without touching your run history |

There is no setting that points this application at a real record system.

## Deploy

See **[Deploy to a server](deploy.md)** for the full walkthrough: server and DNS
prerequisites, getting the data onto the machine, `.env`, the reverse proxy,
protecting the clinician review queue, updating, backups and troubleshooting.

The two points that bite most often:

- `WEB_PUBLIC_API_URL` and `WEB_PUBLIC_DOCS_URL` are baked into the web image at
  **build time**; changing them requires `docker compose -f compose.prod.yaml up -d --build`.
- There is no login. Put basic auth at the proxy in front of `/reviews` and
  `/api/reviews`, or anyone can decide a held answer.
