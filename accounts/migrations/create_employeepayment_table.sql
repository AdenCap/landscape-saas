-- Run this only if migrate doesn't work (e.g. from project root):
--   sqlite3 db.sqlite3 < accounts/migrations/create_employeepayment_table.sql
-- Or in Django dbshell: paste the statements below.

CREATE TABLE IF NOT EXISTS accounts_employeepayment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount DECIMAL(12, 2) NOT NULL,
    paid_date DATE NOT NULL,
    notes VARCHAR(500) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL,
    business_id INTEGER NOT NULL REFERENCES businesses_business(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE
);

-- Tell Django this migration was applied (so "migrate" doesn't try again):
INSERT OR IGNORE INTO django_migrations (app, name, applied)
VALUES ('accounts', '0006_employeepayment', datetime('now'));
