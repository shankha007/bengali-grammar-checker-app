"""Phase 1 persistence: SQLite for local dev, same schema shape as the Postgres
16 target (spec §4).

Two invariants hold across every table that touches identity:

1. `device_id` is NOT NULL and is the working key today.
2. `user_id` exists and is NULLABLE, unused, and indexed - so that
   `upgrade_anonymous_to_account` is an UPDATE, not a migration.

Privacy (spec §10): no document text is stored by default. `documents.body` is
only written when `explicit_save` is set by the caller.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
    device_id        TEXT PRIMARY KEY,
    user_id          TEXT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at     TEXT NOT NULL DEFAULT (datetime('now')),
    recovery_hash    TEXT NULL UNIQUE,
    wordlist_version INTEGER NOT NULL DEFAULT 1,
    locale           TEXT NOT NULL DEFAULT 'bn'
);
CREATE INDEX IF NOT EXISTS ix_devices_user ON devices(user_id);

-- Reserved for Phase 5. Created now so the FK direction is settled.
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    device_id    TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    user_id      TEXT NULL,
    title        TEXT NOT NULL DEFAULT '',
    -- NULL unless the user explicitly asked us to keep it.
    body         TEXT NULL,
    word_count   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_documents_device ON documents(device_id);
CREATE INDEX IF NOT EXISTS ix_documents_user ON documents(user_id);

-- Aggregate counts only: which error classes this device hits, never the text.
CREATE TABLE IF NOT EXISTS error_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    user_id      TEXT NULL,
    error_class  TEXT NOT NULL,
    stage        INTEGER NOT NULL,
    accepted     INTEGER NOT NULL DEFAULT 0,
    occurred_on  TEXT NOT NULL DEFAULT (date('now'))
);
CREATE INDEX IF NOT EXISTS ix_error_events_device_day
    ON error_events(device_id, occurred_on);

CREATE TABLE IF NOT EXISTS streaks (
    device_id      TEXT PRIMARY KEY REFERENCES devices(device_id) ON DELETE CASCADE,
    user_id        TEXT NULL,
    current_days   INTEGER NOT NULL DEFAULT 0,
    longest_days   INTEGER NOT NULL DEFAULT 0,
    freeze_tokens  INTEGER NOT NULL DEFAULT 0,
    last_active_on TEXT NULL
);

-- Spec §2: hard-code everyone to free_unlimited via one flag, but keep the
-- plumbing so pricing later is a config change rather than a schema change.
CREATE TABLE IF NOT EXISTS entitlements (
    device_id  TEXT PRIMARY KEY REFERENCES devices(device_id) ON DELETE CASCADE,
    user_id    TEXT NULL,
    tier       TEXT NOT NULL DEFAULT 'free_unlimited',
    granted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# The single flag from spec §2. Everything reads entitlements through this.
FORCE_TIER: str | None = "free_unlimited"


@dataclass(frozen=True, slots=True)
class DeviceRow:
    device_id: str
    user_id: str | None
    recovery_hash: str | None


def connect(path: str | Path = "bhashasetu.db") -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: str | Path = "bhashasetu.db") -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_device(
    conn: sqlite3.Connection, device_id: str, *, locale: str = "bn"
) -> DeviceRow:
    conn.execute(
        "INSERT INTO devices(device_id, locale) VALUES(?, ?) "
        "ON CONFLICT(device_id) DO UPDATE SET last_seen_at = datetime('now')",
        (device_id, locale),
    )
    conn.execute(
        "INSERT OR IGNORE INTO entitlements(device_id, tier) VALUES(?, ?)",
        (device_id, FORCE_TIER or "free"),
    )
    conn.execute("INSERT OR IGNORE INTO streaks(device_id) VALUES(?)", (device_id,))
    row = conn.execute(
        "SELECT device_id, user_id, recovery_hash FROM devices WHERE device_id = ?",
        (device_id,),
    ).fetchone()
    return DeviceRow(row["device_id"], row["user_id"], row["recovery_hash"])


def attach_recovery(
    conn: sqlite3.Connection, device_id: str, secret_hash: str, version: int = 1
) -> None:
    conn.execute(
        "UPDATE devices SET recovery_hash = ?, wordlist_version = ? WHERE device_id = ?",
        (secret_hash, version, device_id),
    )


def device_for_recovery_hash(
    conn: sqlite3.Connection, secret_hash: str
) -> str | None:
    row = conn.execute(
        "SELECT device_id FROM devices WHERE recovery_hash = ?", (secret_hash,)
    ).fetchone()
    return row["device_id"] if row else None


def tier_for(conn: sqlite3.Connection, device_id: str) -> str:
    if FORCE_TIER is not None:
        return FORCE_TIER
    row = conn.execute(
        "SELECT tier FROM entitlements WHERE device_id = ?", (device_id,)
    ).fetchone()
    return row["tier"] if row else "free"


_IDENTITY_TABLES = ("devices", "documents", "error_events", "streaks", "entitlements")


def upgrade_anonymous_to_account(
    conn: sqlite3.Connection, device_id: str, user_id: str
) -> int:
    """Bind every row owned by `device_id` to `user_id`.

    Written in Phase 1 on purpose (spec §5). Idempotent, and refuses to steal a
    device already claimed by a different user. Returns rows touched.
    """
    existing = conn.execute(
        "SELECT user_id FROM devices WHERE device_id = ?", (device_id,)
    ).fetchone()
    if existing is None:
        raise KeyError(f"unknown device {device_id}")
    if existing["user_id"] not in (None, user_id):
        raise PermissionError(
            f"device {device_id} already belongs to user {existing['user_id']}"
        )

    conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
    touched = 0
    for table in _IDENTITY_TABLES:
        cur = conn.execute(
            f"UPDATE {table} SET user_id = ? WHERE device_id = ? AND user_id IS NULL",  # noqa: S608
            (user_id, device_id),
        )
        touched += cur.rowcount
    return touched
