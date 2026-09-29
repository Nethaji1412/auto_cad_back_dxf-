# Database setup (raw SQL)

This folder is a plain, reviewable SQL alternative to `alembic upgrade
head` — useful for DBA review, manual setup, or importing into MySQL
Workbench. Every statement here was written to match `app/db/models.py`
field-for-field, and has been run and verified against a real MySQL-
compatible server (MariaDB 10.11) end-to-end, including foreign-key
cascades and the actual FastAPI app connecting and writing through it.

| File | Purpose |
|---|---|
| `01_create_database.sql` | Creates the `solar_layout` database + a `solar_user` app user with least-privilege grants |
| `02_schema.sql` | Creates all 7 application tables + `alembic_version`, with the same FKs/indexes/enums as `alembic/versions/0001_initial.py` |
| `03_seed_admin_optional.sql` | *Optional.* One ready-to-login admin user (`admin@example.com` / `ChangeMe123!`) |
| `99_drop_all.sql` | *Destructive.* Drops every table, for local reset only |

## Option A — manual / bare-metal MySQL

```bash
mysql -u root -p < database/01_create_database.sql
mysql -u solar_user -p solar_layout < database/02_schema.sql
mysql -u solar_user -p solar_layout < database/03_seed_admin_optional.sql   # optional
```

Then point `.env`'s `DATABASE_URL` at it:
```
DATABASE_URL=mysql+pymysql://solar_user:CHANGE_ME@localhost:3306/solar_layout
```
(matching whatever password you set in `01_create_database.sql`).

Because `02_schema.sql` also stamps `alembic_version = 0001_initial`, running
`alembic upgrade head` afterwards is a safe no-op — Alembic and this SQL
sheet won't fight each other or try to create the tables twice.

## Option B — Docker (automatic)

`docker-compose.yml` mounts this folder into the MySQL container's
`/docker-entrypoint-initdb.d/`, which MySQL executes automatically, in
filename order, the **first time** the container starts with an empty data
volume:

```bash
docker compose up --build
```

No manual step needed — `01_`, `02_`, and `03_` (seed) all run
automatically. If you don't want the seed admin user in Docker, either
delete `03_seed_admin_optional.sql` or just remove that admin row
afterwards.

> This only runs on a **fresh** volume. If you've already started the stack
> once, `docker compose down -v` first (this deletes all data) to force
> re-initialization, or apply the SQL manually via `docker compose exec db
> mysql -u root -p < database/02_schema.sql`.

## Verifying it worked

```bash
mysql -u solar_user -p solar_layout -e "SHOW TABLES;"
```
should list: `alembic_version, audit_logs, calculation_results, jobs,
project_files, project_inputs, projects, users`.

## Resetting

```bash
mysql -u root -p < database/99_drop_all.sql
mysql -u root -p < database/02_schema.sql
```
