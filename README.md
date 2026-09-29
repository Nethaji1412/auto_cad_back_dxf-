# Solar Layout Backend

A FastAPI service layer around the existing Solar PV Layout Generator
engineering pipeline. **This backend does not reimplement any engineering
logic** — capacity sizing, geometry, packing, grouping, and DXF/DWG
generation all live, unmodified, in `existing_pipeline/`, byte-for-byte
identical to the uploaded source (verified with `diff`).

## Status: fully wired to the real pipeline, verified end-to-end

Every file in `existing_pipeline/` is now the real, original implementation
— `pipeline.py`, `calculation_engine.py`, `geometry.py`, `packing.py`, and
`dxf_writer.py` were supplied after an earlier round where they were
placeholder stubs; this build integrates the real versions.

**What "verified" means here, concretely:**
- The real `core/pipeline.py` was run standalone via `reference/main.py`
  (a faithful reproduction of the original CLI entry point) against a
  synthetic boundary/control-room/inverter-room CSV set, and produced a
  real ~830KB DXF with the exact same 26-layer structure (`BOUNDARY`,
  `PV_TABLES`, `TITLE_BLOCK`, `LIGHTNING_ARRESTER`, `GROUP_BOUNDARY`, …) as
  the two sample DXF outputs provided alongside the source files.
- The full FastAPI flow (`register → login → create project → save inputs
  → upload CSV → generate → poll job → download`) was run against a live
  MySQL-compatible server (not SQLite), producing a real, downloadable DXF
  and correct `project_files`/`jobs` rows.
- `pytest tests/` (34 tests) passes on a clean `pip install -r
  requirements.txt`, including a genuine end-to-end generation test that
  opens the produced DXF with `ezdxf` and checks its layers and entity
  counts, not just that the HTTP call succeeded.

## Three real bugs this integration caught and fixed

Reading the actual pipeline source (rather than the brief's paraphrase of
it) surfaced problems that would only have shown up at generation time:

1. **`calculatePlant()`, not `grouping.py`'s `compute_*_grouping()`, is
   what `pipeline.py` actually calls** for string/inverter/SCB sizing.
   `app/services/calculation_service.py` was rewritten to mirror
   `pipeline.py`'s exact capacity-resolution dispatch and call
   `calculatePlant()` directly, so `POST /calculate` previews now equal
   what `POST /generate` will actually build (both verified against the
   same regression numbers: 7 inverters, 4 SCBs/inverter, 329 theoretical
   tables for the reference 7 MW / 1.2 DC:AC config).
2. **`input.exclusions`** in the real pipeline is a path to one generic
   polygon/circle-exclusion JSON file — not a list of CSV paths, which is
   what an earlier version of the adapter had guessed and would have
   crashed `load_json()` on a real run. Removed; every CSV-based exclusion
   (control room / inverter room / private area) already reaches the
   pipeline through the dedicated list keys.
3. **Optional-field nulls vs. absent keys**: Pydantic's `model_dump()`
   serializes an unset `Optional` field as an explicit `null`, but
   `pipeline.py` reads several config values via `config.get(key,
   default)` — which only falls back to `default` when the key is
   *missing*, not when it's present-and-null. Left alone, an unset
   `arrester_radius_m`/`arrester_clearance_m`/`tables_per_group_columns`
   would have sent an explicit `null` through and crashed the pipeline's
   `float(None)`/`int(None)` casts. `app/pipeline/adapter.py`'s
   `_strip_none()` normalizes this at the config-construction boundary.

A fourth, packaging-only fix: `pipeline.py` imports `pandas` (for the
title-block plant-details table), which was never listed in the original
`requirements.txt`. Added here — a dependency-declaration fix, not a
behavior change.

## Why the `core` aliasing works

The real `core/pipeline.py` imports its siblings absolutely — `from
core.geometry import GeometryEngine`, `from core.offset import
OffsetEngine`, `from core.dxf_writer import DXFWriter`, `from
core.calculation_engine import calculatePlant, generateTableGrouping`, etc.
Renaming the directory to `existing_pipeline/` (to match the requested
backend layout) would break every one of those imports — and editing the
pipeline's own import lines is explicitly out of scope.

`app/pipeline/adapter.py` resolves this without touching a single line of
pipeline code: at import time it registers `existing_pipeline` into
`sys.modules["core"]`, **and** pre-registers every one of its submodules
under `core.<name>` too, pointing at the exact same module objects. This
matters for correctness, not just cosmetics — without the submodule-level
aliasing, code reached via `core.pipeline` doing `from core.exceptions
import X` would trigger a *second*, independent import of `exceptions.py`,
producing a distinct class object that an `except` elsewhere would
silently fail to catch. (This exact bug was caught by an earlier version of
`tests/test_generation.py` before the real files arrived, and the fix —
pre-registering every submodule, not just the top-level package — is why
`from core.geometry import GeometryEngine` etc. now resolve correctly.)

## Project layout

```
backend/
├── app/
│   ├── main.py                 FastAPI app, CORS, security headers, routers
│   ├── api/
│   │   ├── deps.py             DB session, current user, project ownership
│   │   └── routes/             auth, projects, inputs, calculations, layouts, files
│   ├── core/                   config, JWT/password hashing, logging, errors, rate limiting
│   ├── db/                     SQLAlchemy models + repositories
│   ├── schemas/                Pydantic request/response models (extra="forbid")
│   ├── services/                orchestration -- routes never contain business logic
│   │   └── calculation_service.py   mirrors pipeline.py's capacity-resolution
│   │                                 dispatch, then calls the real calculatePlant()
│   └── pipeline/
│       └── adapter.py          the ONLY module allowed to call run_pipeline();
│                                also home to _strip_none() (see bug #3 above)
├── existing_pipeline/           the real, unmodified engineering pipeline
│   ├── capacity.py  csv_loader.py  grouping.py  offset.py  dwg_export.py
│   ├── geometry.py  packing.py  calculation_engine.py  dxf_writer.py
│   └── pipeline.py              run_pipeline() -- full orchestration incl.
│                                 the AutoCAD-style right-of-boundary title block
├── reference/                    standalone CLI reproduction for regression
│   ├── main.py  config.json  core/ (symlink-equivalent copy of existing_pipeline)
│   └── streamlit_app.py         original Streamlit UI, for reference only
├── alembic/                      DB migrations (initial schema hand-authored to
│                                 match app/db/models.py -- autogenerate needs a live
│                                 MySQL connection; run `alembic revision
│                                 --autogenerate` yourself against a real DB to
│                                 verify/extend it)
├── database/                     plain .sql sheets: create DB/user, full schema,
│                                 optional seed admin (see database/README.md)
├── tests/
├── uploads/ outputs/
├── requirements.txt  .env.example  Dockerfile  docker-compose.yml
```

## Running locally

```bash
cp .env.example .env        # edit JWT_SECRET_KEY, DATABASE_URL, etc.
pip install -r requirements.txt
alembic upgrade head        # requires a running MySQL matching DATABASE_URL
uvicorn app.main:app --reload
```

Prefer plain SQL over Alembic for initial setup? See **`database/`** — a
reviewable `.sql` sheet (create DB + user, full schema, optional seed admin)
that's been run and verified against a real MySQL-compatible server,
including FK cascades and the live app writing through it. `docker compose
up` runs it automatically on a fresh volume; see `database/README.md` for
the manual (`mysql -u root -p < database/02_schema.sql`) path too.

Or with Docker (brings up MySQL + Redis + the API):

```bash
docker compose up --build
```

Swagger UI: `http://localhost:8000/docs` · ReDoc: `/redoc`

### Quick local smoke test without MySQL

For local iteration only (not what docker-compose uses in production), you
can point `DATABASE_URL` in `.env` at SQLite:

```
DATABASE_URL=sqlite:///./dev.db
```

then `python -c "from app.db.database import Base, engine; import app.db.models; Base.metadata.create_all(bind=engine)"`.
Real generation (DXF/DWG output) works identically under SQLite — it's
only used here for speed, not because generation needs MySQL specifically.

## Running the tests

```bash
pytest tests/ -v
```

34 tests covering: auth (register/login/invalid password/bad token),
project ownership (cross-user 403, 404 on unknown project), CSV validation
(missing columns, non-numeric coordinates, <3 points, disallowed
extensions), the real `capacity.py` formulas and the real
`calculation_engine.calculatePlant()` (asserted against the literal
reference-CLI regression numbers — no alternate math), the real
`csv_loader.py`/`offset.py` geometry helpers, and a genuine end-to-end
generation test that runs the real pipeline, opens the resulting DXF with
`ezdxf`, and checks its layer set and entity counts.

## Regression testing against the original pipeline (spec §45)

`reference/` is a standalone, runnable reproduction of the original CLI
(`main.py` + `core/` + `config.json`) kept outside the FastAPI app
specifically for this: run the same config/CSVs through **both**

1. `cd reference && python main.py config.json` (the original CLI path), and
2. the API (`POST /inputs` with the equivalent payload, upload the same
   CSVs, `POST /generate`, poll `GET /jobs/{id}`)

and diff `table_count`, `module_count`, `actual_dc_mwp`, `land_area_acres`,
the grouping breakdown, and the DXF layer/entity structure. This was done
during development (see "Status" above); `tests/test_generation.py::
test_generate_produces_real_dxf_end_to_end` codifies the same checks as an
automated regression test.

## Security notes

- Passwords hashed with bcrypt (via passlib); JWTs signed with
  `JWT_SECRET_KEY` (HS256, configurable).
- Every project-scoped route resolves the project by UUID and checks
  `project.user_id == current_user.id` (or admin) — never trusts the URL
  alone.
- Uploads: extension allow-list (`.csv` only) + explicit forbidden-extension
  reject, soft MIME check, streamed size cap, UUID-based storage filenames
  (the original filename never touches a filesystem path), SHA-256
  checksums, and real structural CSV validation via `csv_loader.py`.
- Downloads are resolved strictly through the `project_files` DB table,
  scoped to the authenticated, ownership-checked project — there is no
  path-parameter-based file endpoint anywhere.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`) on every response; CORS origins come from
  `CORS_ORIGINS`, never `*`.
- In-memory sliding-window rate limiter on `/auth/login`, `/auth/register`,
  `/generate`, and file uploads (`app/core/rate_limit.py`) — isolated
  behind one function so it can be swapped for a Redis-backed
  implementation (the docker-compose stack already ships Redis for this)
  without touching any route.
- Structured logging never emits `password`/`token`/`secret`/etc. fields
  (`app/core/logging.py`'s redacting filter); unhandled exceptions are
  logged server-side and returned to clients as a generic `INTERNAL_ERROR`
  with no stack trace.

## Async generation

The first implementation uses FastAPI `BackgroundTasks`
(`layout_service.background_runner`), intentionally structured so a
Celery/RQ worker can replace it later: swap the one call to
`background_runner(job.id, project.id)` in `app/api/routes/layouts.py` for
`execute_generation_job.delay(job.id, project.id)`, and nothing else in the
codebase changes. Real generation on a modestly-sized site (a few hundred
tables) takes low single-digit seconds in this environment; larger sites
with the `rtree` package installed (optional; falls back gracefully to a
linear scan without it — see the `rtree package not installed` warnings in
logs) will be faster.

## DWG export

Unchanged, real behavior from `dwg_export.py`: if the free ODA File
Converter is installed and `ODA_FILE_CONVERTER_PATH` (or
`oda_file_converter_path` in the project's dxf config) points at it, a real
`.dwg` is produced alongside the `.dxf` and both appear under
`GET /outputs`. Without it, generation still succeeds — `dwg_path` is
`null` and `dwg_export_message` explains why, exactly as
`streamlit_app.py`'s own UI messaging describes it. Note that the real
`run_pipeline()` does not currently raise on `dxf.require_dwg=true` when
DWG export fails (that flag is accepted and stored, but not enforced
anywhere in the supplied `pipeline.py`) — this backend does not add
enforcement that doesn't exist in the original code.
