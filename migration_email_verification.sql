-- Run ONCE on an EXISTING database (created before email verification was added).
-- Fresh installs using the new schema.sql do NOT need this file.
USE resume_analyzer;

ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0 AFTER role;

-- Existing users registered before this feature: mark them as verified so they aren't locked out.
UPDATE users SET email_verified = 1;
