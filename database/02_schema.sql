-- ============================================================================
-- 02_schema.sql
-- Full table schema for the Solar Layout Backend, matching app/db/models.py
-- (SQLAlchemy ORM) field-for-field. This is the same schema Alembic's
-- alembic/versions/0001_initial.py produces -- this file exists as a plain,
-- reviewable SQL sheet for DBAs / manual setup / MySQL Workbench import.
--
-- Run:
--   mysql -u solar_user -p solar_layout < database/02_schema.sql
--
-- If you run this file directly (instead of `alembic upgrade head`), tell
-- Alembic the DB is already at this revision so it doesn't try to create
-- these tables again later:
--   alembic stamp 0001_initial
-- ============================================================================

USE solar_layout;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- users
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    email           VARCHAR(255)    NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_admin        BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ix_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- projects
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    uuid        VARCHAR(36)     NOT NULL,
    user_id     INT             NOT NULL,
    name        VARCHAR(255)    NOT NULL,
    status      ENUM('DRAFT','INPUTS_READY','CALCULATING','GENERATING','COMPLETED','FAILED')
                    NOT NULL DEFAULT 'DRAFT',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ix_projects_uuid (uuid),
    KEY ix_projects_user_id (user_id),
    CONSTRAINT fk_projects_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- project_inputs -- one row per project; JSON blobs mirror config.json's
-- module / table / layout / electrical / service_road / dxf sections 1:1.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_inputs (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    project_id              INT     NOT NULL,
    module_config           JSON    NOT NULL,
    table_config            JSON    NOT NULL,
    layout_config           JSON    NOT NULL,
    electrical_config       JSON    NOT NULL,
    service_road_config     JSON    NOT NULL,
    dxf_config              JSON    NOT NULL,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ix_project_inputs_project_id (project_id),
    CONSTRAINT fk_project_inputs_project
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- project_files -- uploaded CSVs (boundary/control-room/inverter-room/
-- private-area) AND generated outputs (DXF/DWG) share this table, keyed by
-- file_type; download endpoints resolve strictly via this table's uuid.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_files (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    uuid                VARCHAR(36)     NOT NULL,
    project_id          INT             NOT NULL,
    file_type           ENUM('BOUNDARY','CONTROL_ROOM','INVERTER_ROOM','PRIVATE_AREA','DXF','DWG')
                            NOT NULL,
    original_filename   VARCHAR(255)    NOT NULL,
    stored_filename     VARCHAR(255)    NOT NULL,
    storage_path        VARCHAR(1024)   NOT NULL,
    mime_type           VARCHAR(127)    NOT NULL,
    file_size           INT             NOT NULL,
    checksum            VARCHAR(64)     NOT NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ix_project_files_uuid (uuid),
    KEY ix_project_files_project_id (project_id),
    CONSTRAINT fk_project_files_project
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- calculation_results -- one row per calculation preview AND per completed
-- generation job; theoretical_result / actual_result are kept as SEPARATE
-- JSON columns on purpose (never merged -- see spec "actual vs theoretical").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calculation_results (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    project_id          INT     NOT NULL,
    theoretical_result  JSON    NULL,
    actual_result       JSON    NULL,
    grouping_result     JSON    NULL,
    capacity_result     JSON    NULL,
    warnings            JSON    NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_calculation_results_project_id (project_id),
    CONSTRAINT fk_calculation_results_project
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- jobs -- one row per async generation run (QUEUED -> RUNNING -> COMPLETED/FAILED)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    uuid            VARCHAR(36)     NOT NULL,
    project_id      INT             NOT NULL,
    status          ENUM('QUEUED','RUNNING','COMPLETED','FAILED') NOT NULL DEFAULT 'QUEUED',
    progress        INT             NOT NULL DEFAULT 0,
    result          JSON            NULL,
    error_message   TEXT            NULL,
    started_at      DATETIME        NULL,
    completed_at    DATETIME        NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ix_jobs_uuid (uuid),
    KEY ix_jobs_project_id (project_id),
    CONSTRAINT fk_jobs_project
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- audit_logs -- append-only action trail; FKs are ON DELETE SET NULL so the
-- audit trail survives deletion of the user/project/job it refers to.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NULL,
    project_id  INT NULL,
    job_id      INT NULL,
    action      ENUM(
                    'PROJECT_CREATED',
                    'FILE_UPLOADED',
                    'INPUT_UPDATED',
                    'CALCULATION_STARTED',
                    'CALCULATION_COMPLETED',
                    'LAYOUT_GENERATION_STARTED',
                    'LAYOUT_GENERATION_COMPLETED',
                    'LAYOUT_GENERATION_FAILED',
                    'FILE_DOWNLOADED'
                ) NOT NULL,
    details     JSON NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_audit_logs_user_id (user_id),
    KEY ix_audit_logs_project_id (project_id),
    KEY ix_audit_logs_job_id (job_id),
    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_logs_project
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_logs_job
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- alembic_version -- lets `alembic upgrade`/`downgrade` work normally
-- afterwards even though this file (not alembic) created the tables.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    PRIMARY KEY (version_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO alembic_version (version_num)
    SELECT '0001_initial' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM alembic_version);

SET FOREIGN_KEY_CHECKS = 1;
