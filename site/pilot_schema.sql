-- Access codes for downloads (site/worker.js, tools/pilot_access.py). Codes are stored only as SHA-256 hashes; the
-- name behind each code stays on the owner's computer. A download records which code and when -- nothing else.
CREATE TABLE IF NOT EXISTS codes (
  id TEXT PRIMARY KEY,
  hash TEXT UNIQUE NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created TEXT NOT NULL,
  uses INTEGER NOT NULL DEFAULT 0,
  last_used TEXT
);
CREATE TABLE IF NOT EXISTS downloads (
  code_id TEXT NOT NULL,
  at TEXT NOT NULL,
  file TEXT NOT NULL
);
