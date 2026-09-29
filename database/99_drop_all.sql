-- ============================================================================
-- 99_drop_all.sql  (DESTRUCTIVE -- for local dev/reset only)
-- Drops every table this project owns, in FK-safe order.
-- Run: mysql -u solar_user -p solar_layout < database/99_drop_all.sql
-- ============================================================================

USE solar_layout;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS calculation_results;
DROP TABLE IF EXISTS project_files;
DROP TABLE IF EXISTS project_inputs;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS alembic_version;

SET FOREIGN_KEY_CHECKS = 1;
