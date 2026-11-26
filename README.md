# FlowForge

**Automated ETL pipelines with DataPilot, a schema-aware natural-language SQL agent**

FlowForge is the ETL platform; **DataPilot** is its natural-language data agent (the SQL assistant). DataPilot takes a plain-English question, ranks the scanned catalog tables by relevance, puts only those schemas and their foreign keys in the LLM prompt (OpenRouter), validates the draft with SQLGlot, checks it with `EXPLAIN` on the live database, and sends any rejection back to the model to fix (up to 3 drafts). Approved SQL can be previewed with bounded results or used as the Extract step of a scheduled pipeline.

FlowForge moves data from PostgreSQL, MySQL, or Amazon Redshift into Google Sheets. Build a pipeline on a visual canvas, extract a table or the result of a read-only SQL query, apply Pandas transformations, and run it on demand or on a schedule. A local SQL assistant can propose queries from database metadata for review before they are used.

## Public portfolio deployment

The public Render deployment uses **the same React Flow editor, FastAPI execution engine, saved pipeline/version models, and APScheduler run queue** as the private application. `Dockerfile.public` builds the UI and serves it from FastAPI. `scripts/serve_public.py` applies Alembic migrations, initializes synthetic data, and starts the service.

Choose **Run the sample pipeline** to open a limited sandbox session. Preview or edit the `orders` SQL, adjust a structured transform, run the graph, save a copy, and download server-written CSV from the destination panel. The dashboard and runtime logs read actual persisted job results. The **Run sample scheduled job** control enqueues the same pinned pipeline version used by the scheduler.

This is a shared synthetic sandbox. External database connections, arbitrary expressions, cross joins, and AI SQL generation are disabled in this public mode. Read-only SQLite authorization, query time/row limits, concurrency limits, and bounded saved state keep it suitable for anonymous exploration. The private deployment below retains real database and Sheets adapters.

**Daily hosted job:** `.github/workflows/scheduled-demo.yml` runs daily at 03:30 UTC (09:00 IST), wakes the free web service, enqueues the saved job, checks the actual result, and retains its CSV and run evidence as a GitHub Actions artifact. It can also be dispatched manually. GitHub schedules may be delayed.

**Hosting limits:** Render Free sleeps when idle, has ephemeral storage, and does not provide a continuously running scheduler. Jobs execute while the process is awake; demo state may reset on restart/redeploy. Use a persistent application database and an always-on scheduler/worker for durable production automation. No user credentials or private datasets are included.

Local public build:

```bash
cd UI
npm ci
VITE_PUBLIC_DEMO=true npm run build
cd ..
python -m pip install -r requirements.txt
PYTHONPATH=. python scripts/serve_public.py
```

## Run it locally with Docker (one command)

```bash
cp .env.example .env      # set LOCAL_ADMIN_PASSWORD (12+ chars) and OPENROUTER_API_KEY
docker compose --profile mysql up -d --build   # drop --profile mysql for PostgreSQL only
```

Open **http://localhost:8001** and sign in as `admin` with your `LOCAL_ADMIN_PASSWORD`. On first start the `bootstrap` service:

- seeds a demo retail database (200 customers, 1,500 orders, 3,833 order lines) in its own Postgres container,
- creates a read-only role for it,
- registers it as the **Demo retail (PostgreSQL)** connection, and scans its catalog.

In the editor, choose **Create guided pipeline**, pick that connection, ask the SQL assistant a question, then load to a Google Sheet. Without Sheets credentials, use `csv://my_report` as the destination; the files land in `./output/`. Add `--profile mysql` (and uncomment `DEMO_MYSQL_ADMIN_URL`) to also test a MySQL source, or `--profile ollama` to use a local model.

## Evaluation

| Suite | What it measures | Command |
| --- | --- | --- |
| Guardrails (layer 1, AST policy) | 40 write/DDL attacks (DROP, DELETE, UPDATE, INSERT, MERGE, TRUNCATE, ALTER, CREATE, GRANT, COPY, `SELECT INTO`, stacked statements, data-modifying CTEs, `EXPLAIN ANALYZE`, Redshift `UNLOAD`, ...) plus 26 side-effect/exfiltration attacks (locks, sleeps, file reads, `dblink`, session changes, system catalogs). Each is run through both entry points (manual Extract SQL and DataPilot output) in the PostgreSQL, MySQL and Redshift dialects. The 60 gold analytics queries are checked for false positives. Gated in CI. | `python -m eval.run_eval guardrails` |
| Read-only role (layer 2, live DB) | The same 40 write/DDL statements sent directly to the demo database through the connection's read-only role, skipping the AST policy. Each runs in a rolled-back transaction. | `docker compose exec api python -m eval.run_eval readonly` |
| ETL end-to-end (live) | For PostgreSQL and MySQL: a saved pipeline (Extract -> Pandas transform -> append Load) is queued like a scheduled run and processed by the worker container. Full load, then incremental load of only the new rows (primary-key checkpoint on PostgreSQL, timestamp on MySQL), then a no-op run; a broken pipeline must be logged with its error and a retry; a runaway query must be cancelled server-side by the statement timeout. | `docker compose exec api python -m scripts.e2e_check` |
| NL-to-SQL execution accuracy | 60 business questions through the real DataPilot pipeline (catalog context, LLM, guardrails, `EXPLAIN`, self-correction). Correct means the accepted SQL returns the same result set as hand-written gold SQL, order-insensitive. | `docker compose exec api python -m eval.run_eval accuracy` |

| Result | Value |
| --- | --- |
| Write/DDL attacks blocked by the AST policy | **40/40 (100%)** in PostgreSQL, MySQL and Redshift dialects |
| Side-effect/exfiltration attacks blocked | **26/26** in all three dialects |
| False positives on the 60 gold analytics queries | **0** in all three dialects |
| Live read-only role refusing write/DDL | **40/40** on PostgreSQL and on MySQL |
| ETL end-to-end | Full load 1,500 rows -> incremental 5 rows -> 0 rows on both sources; failed run logged with retry; runaway query cancelled at the 3 s timeout with nothing left running on the server |
| Execution accuracy (60 questions, PostgreSQL, `nvidia/nemotron-3-ultra-550b-a55b:free`) | **57/60 = 95%** (p50 5.1 s, p95 19.7 s); failures and their SQL in `eval/results/accuracy-demo-retail-postgresql-nvidia-nemotron-3-ultra-550b-a55b-free.json` |

Results are written to `eval/results/`. The accuracy report also records the model, the drafts allowed, accuracy on the first draft, questions recovered by self-correction, p50/p95 latency, and every failure with its SQL.

## Features

- **Database sources:** Connect to PostgreSQL, MySQL, and Amazon Redshift. Save encrypted connection profiles and scan table, column, primary-key, and relationship metadata.
- **Flexible extraction:** Select a scanned table or enter a custom SQL query. Optionally require named columns in the result before loading.
- **Incremental schedules:** Extract rows after an integer primary-key or unique timestamp checkpoint. Checkpoints are scoped to each schedule and Extract node.
- **Transformations:** Use the visual pipeline editor to filter, join, group, pivot, and reshape data with Pandas.
- **Google Sheets output:** Write to one or more tabs in overwrite or append mode. Transient Sheets API errors are retried, and append mode checks the existing header.
- **DataPilot SQL assistant:** Describe the data you need in plain English. The assistant ranks catalog tables by relevance, sends only that schema context to the model (OpenRouter by default, or local Ollama/SQLCoder), and checks every draft with SQLGlot guardrails and `EXPLAIN`. Rejections and database errors go back to the model, which corrects itself (up to 3 drafts). Previews apply a row limit and report truncation exactly.
- **SQL guardrails:** One read-only statement; no writes, DDL, locks, `SELECT INTO`, `COPY`, or session changes; no `pg_*`/advisory-lock/`dblink`/sequence functions; no system catalogs or database-qualified references; assistant queries limited to approved catalog tables. The demo connects through a read-only database role as a second layer.
- **Scheduling and visibility:** APScheduler enqueues runs, workers execute them, and the application records status, row counts, duration, retries, and errors.
- **Access control:** Database-backed login, admin and user roles, encrypted saved passwords, and immutable pipeline versions pinned to schedules.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, React Flow |
| API and workers | Python, FastAPI, Pandas, SQLAlchemy, APScheduler |
| Source databases | PostgreSQL, MySQL, Amazon Redshift |
| Application database | PostgreSQL in Docker; SQLite supported for local development |
| Destination | Google Sheets API via `gspread` |
| SQL assistant | OpenRouter (any OpenAI-compatible LLM) or Ollama/SQLCoder, SQLGlot guardrails, EXPLAIN-based self-correction |
| Deployment | Docker Compose, Caddy, Alembic |

## Architecture

```mermaid
flowchart LR
    user[User] --> web[React and Caddy]
    web --> api[FastAPI]
    api --> appdb[(Application database)]
    api --> catalog[Metadata catalog and SQL assistant]
    catalog --> model[LLM: OpenRouter or local Ollama]
    scheduler[APScheduler] --> appdb
    appdb --> worker[ETL worker]
    worker --> source[(PostgreSQL / MySQL / Redshift)]
    worker --> transform[Pandas transforms]
    transform --> sheets[Google Sheets]
```

The API handles authentication, connection ownership, pipeline definitions, previews, and SQL approval. The scheduler queues a pinned pipeline version; a worker claims the run, performs the extract and load, and records the outcome. See [Architecture](docs/ARCHITECTURE.md) for trust boundaries and delivery semantics.

## Using your own databases and Google Sheets

The Docker stack above is the full application; the demo databases are just pre-registered sources.

1. **SQL assistant model.** Create a key at openrouter.ai and set `OPENROUTER_API_KEY` in `.env`. `LLM_MODEL` takes any OpenRouter model ID. Free models (IDs ending in `:free`) work, but OpenRouter limits them to about 20 requests per minute and 50 per day for accounts without purchased credit; the assistant waits and retries on rate limits. Set `SQL_ASSISTANT_PROVIDER=ollama` (with `--profile ollama`) for a local model instead.
2. **Google Sheets.** In a Google Cloud project, enable the **Google Sheets API** and **Google Drive API**, create a service account, and save its JSON key as `credentials/Sheet_Service.json`. Share each destination spreadsheet with the service account's email as **Editor**. Without credentials, use `csv://<name>` as the destination; files are written to `./output/`.
3. **Source databases.** Add a Credential node for PostgreSQL, MySQL or Amazon Redshift and save it. Connect with a read-only database account; the SQL guardrails are the first layer, the account's permissions the second.
4. **Users.** `docker compose exec api python -m scripts.create_user <login> --role user` creates more accounts.

Secrets (`.env`, `credentials/`) are gitignored. Keep `PASSWORD_PEPPER` and `APP_SECRET_KEY` stable: changing them invalidates passwords and saved connection credentials.

## Local development

Requires Python 3.11+, Node.js 18+, and npm. This example uses SQLite for application state; PostgreSQL is recommended for a multi-process deployment.

```bash
cp .env.example .env
```

For local development, set these values in `.env`:

```dotenv
DATABASE_URL=sqlite:///app.db
APP_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
OLLAMA_BASE_URL=http://127.0.0.1:11434
RUN_EMBEDDED_SCHEDULER=true
```

Also replace `PASSWORD_PEPPER` and `APP_SECRET_KEY` with stable secrets. Then install dependencies, create the database schema and first user, and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
touch app.db
python -m alembic upgrade head
python -m scripts.create_user admin --display-name "Administrator" --role admin
python -m uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd UI
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Set `OPENROUTER_API_KEY` for the SQL assistant, or `SQL_ASSISTANT_PROVIDER=heuristic` to work without a model.

## Build a pipeline

1. Add a **Credential** node, enter a PostgreSQL, MySQL, or Redshift connection, and check it. Save the connection securely to enable the metadata catalog and SQL assistant.
2. Add an **Extract** node. Select a scanned table or enter a read-only SQL query. Set **Expected Columns** if the load should stop when required columns are absent.
3. Connect any **Transform** nodes, then add a **Sink** node with a Google Sheet URL or ID, tab names, and a write mode.
4. Preview nodes, run the pipeline, and save it. Saved pipelines can be reopened from their URLs.
5. Open **Pipelines** to create a one-time or recurring schedule. Scheduled runs use the saved, pinned pipeline version.

### Incremental extraction

Choose **Integer primary key** or **Unique timestamp** in the Extract node, enter the checkpoint column, and set every Sink node to **Append rows**. Save the pipeline and create a schedule. The first scheduled run reads the full result; later runs select rows with checkpoint values greater than the last successfully loaded value. Previews do not advance checkpoints, and direct interactive runs of incremental pipelines are rejected.

The checkpoint column must be present, non-null, and increasing. Integer primary keys and timestamps that are unique within each batch are supported. Rows arriving later with a checkpoint at or below the saved value are skipped. Avoid overlapping runs of the same incremental schedule.

Google Sheets and the application database cannot commit together. If a worker stops after writing to Sheets but before saving its checkpoint, a retry may append duplicate rows. Use a stable key and downstream deduplication when duplicates are unacceptable.

### DataPilot SQL assistant

With a saved connection, scan its schema in the Extract node, describe the data you need, and generate a candidate query. Review the SQL and its bounded preview before selecting **Use this SQL**. The assistant validates the SQL structure and referenced tables; its preview uses `EXPLAIN` and a result limit. Use a read-only source database account as the final permission boundary.

## Configuration

The template is [.env.example](.env.example). Common settings are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL for application state; Compose overrides this with its PostgreSQL service URL. |
| `PASSWORD_PEPPER` | Stable secret for password hashes. Changing it invalidates existing passwords. |
| `APP_SECRET_KEY` | Stable secret for encrypted connection passwords. Changing it prevents decryption of saved credentials. |
| `POSTGRES_PASSWORD` | Password for the Compose PostgreSQL service. |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Service-account JSON path, relative to the project root. |
| `GOOGLE_SHEETS_MAX_RETRIES` | Additional attempts for transient Sheets API errors; default `3`. |
| `SQL_ASSISTANT_PROVIDER` | `openrouter` (default), `ollama`, or `heuristic` (no model, simple fallback). |
| `OPENROUTER_API_KEY`, `LLM_MODEL` | OpenRouter key and model ID, e.g. `nvidia/nemotron-3-ultra-550b-a55b:free`. |
| `SQL_ASSISTANT_MAX_ATTEMPTS` | Drafts allowed per question, including self-corrections; default `3`. |
| `SQL_ASSISTANT_SCHEMA_TABLE_LIMIT` | Most-relevant tables whose schema is put in the prompt; default `12`. |
| `OLLAMA_BASE_URL`, `OLLAMA_SQL_MODEL` | Local model endpoint and model name. |
| `SOURCE_DB_QUERY_TIMEOUT_SECONDS` | Server-side statement timeout for every source query (PostgreSQL `statement_timeout`, MySQL `max_execution_time`, Redshift `statement_timeout`). |
| `PREVIEW_SQL_LIMIT` | Maximum rows requested for an Extract preview. |
| `ALLOW_UNSAFE_SQL` | Keep `false` to enforce read-only manual Extract queries. |
| `RUN_EMBEDDED_SCHEDULER` | `true` for local single-process use; Compose sets `false` and runs separate services. |
| `APP_CORS_ORIGINS` | Allowed browser origins when the frontend runs separately from the API. |

`VITE_*` settings are read when the frontend is built. Operating-system or deployment environment variables take precedence over `.env`.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
cd UI && npm ci && npm run build
```

The unit tests cover SQL guardrails (every attack in `eval/adversarial.json` in three dialects), credentials, pipeline behavior, incremental checkpoints, LLM retry handling, and the Sheets append header check.

CI runs three jobs: backend tests plus the guardrail eval, the frontend tests and build, and an **integration** job that starts the whole Docker stack with PostgreSQL and MySQL sources and runs the live read-only and ETL end-to-end suites (see [Evaluation](#evaluation)). The LLM accuracy eval needs an API key, so it is run manually.

## Project layout

```text
api/          FastAPI routes, pipeline execution, authentication, scheduler, worker
src/          Configuration, Pandas transformations, Google Sheets loader
UI/           React/Vite frontend and Caddy configuration
migrations/   Alembic application database migrations
tests/        Backend tests
eval/         Guardrail, read-only, and NL-to-SQL accuracy suites and their saved results
scripts/      Local bootstrap, demo data, end-to-end check, user management
docs/         Architecture notes
```
