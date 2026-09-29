-- ============================================================================
-- 03_seed_admin_optional.sql  (OPTIONAL -- not required for the app to work)
--
-- Creates one initial admin user so you have a way into the system before
-- any real registrations exist:
--     email:    admin@example.com
--     password: ChangeMe123!
--
-- The hash below is a REAL bcrypt hash of that password (generated with the
-- same passlib/bcrypt setup app/core/security.py uses), so this user can
-- log in immediately via POST /api/v1/auth/login.
--
-- CHANGE THE PASSWORD IMMEDIATELY after first login in anything but local
-- dev -- there is no "change password" endpoint yet, so for now either:
--   (a) update password_hash directly with a freshly generated hash, e.g.:
--         python -c "from app.core.security import hash_password; print(hash_password('new-password'))"
--   (b) or just delete this seed row and register normally instead.
-- ============================================================================

USE solar_layout;

INSERT INTO users (email, password_hash, is_active, is_admin)
SELECT 'admin@example.com',
       '$2b$12$39rP6lUzCsNYvfKES48jzOQ1TlavP.d7.2miWcYquXQw0u44Jd3fC',
       TRUE,
       TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'admin@example.com'
);
