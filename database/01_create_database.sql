-- ============================================================================
-- 01_create_database.sql
-- Creates the application database and a dedicated, least-privilege DB user.
--
-- Run this as a MySQL root/admin user:
--   mysql -u root -p < database/01_create_database.sql
--
-- Safe to re-run (IF NOT EXISTS everywhere) -- and safe to skip entirely if
-- you're using docker-compose, since the mysql:8.0 image already creates the
-- database/user from MYSQL_DATABASE / MYSQL_USER / MYSQL_PASSWORD before any
-- file in this folder runs (see docker-compose.yml).
--
-- CHANGE THE PASSWORD BELOW before running against anything but a local dev
-- instance -- it must match DATABASE_URL in your .env.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS solar_layout
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'solar_user'@'%' IDENTIFIED BY 'CHANGE_ME';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
    ON solar_layout.* TO 'solar_user'@'%';

FLUSH PRIVILEGES;
