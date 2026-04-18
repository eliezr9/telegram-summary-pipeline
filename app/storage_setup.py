import sqlite3
from pathlib import Path

DB_PATH = Path("data/messages.db")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    chat_name TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    message_date TEXT NOT NULL,
    window_end TEXT NOT NULL,
    text TEXT NOT NULL,
    is_ad_candidate INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    UNIQUE(chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_chat_window
ON raw_messages(chat_id, window_end);

CREATE INDEX IF NOT EXISTS idx_raw_messages_processed
ON raw_messages(processed);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    chat_name TEXT NOT NULL,
    window_end TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(chat_id, window_end)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status
ON jobs(status);
"""


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"Database initialized at: {DB_PATH.resolve()}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
