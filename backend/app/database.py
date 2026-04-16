import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH, DEFAULT_GEMINI_MODEL


DEFAULT_AI_SETTINGS = {
    "enabled": True,
    "provider": "google_gemini",
    "model": DEFAULT_GEMINI_MODEL,
    "confidence_threshold": 0.58,
    "context_messages": 6,
    "system_instruction": (
        "You analyze business chat messages and decide whether the latest message contains an actionable item. "
        "Support English, Roman Urdu, and mixed language. Classify only the latest message using nearby context for clarity. "
        "Treat direct requests, orders, commitments, delivery asks, approvals, follow-ups, and deadline-driven asks as actionable. "
        "If nothing actionable exists, return has_action=false. Keep due_date in YYYY-MM-DD format when it is clearly implied."
    ),
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT NOT NULL,
                channel TEXT NOT NULL,
                last_activity TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                channel TEXT NOT NULL,
                last_message_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(contact_id) REFERENCES contacts(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                provider_message_id TEXT,
                sender_label TEXT NOT NULL,
                body TEXT NOT NULL,
                message_time TEXT NOT NULL,
                raw_payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS review_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_preview TEXT NOT NULL,
                due_date TEXT,
                confidence_label TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending Review',
                priority TEXT NOT NULL DEFAULT 'Medium',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id),
                FOREIGN KEY(message_id) REFERENCES messages(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_item_id INTEGER,
                conversation_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'Medium',
                status TEXT NOT NULL DEFAULT 'Pending',
                source_preview TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                archived_at TEXT,
                FOREIGN KEY(review_item_id) REFERENCES review_items(id),
                FOREIGN KEY(conversation_id) REFERENCES conversations(id),
                FOREIGN KEY(contact_id) REFERENCES contacts(id)
            );

            CREATE TABLE IF NOT EXISTS rules (
                key TEXT PRIMARY KEY,
                values_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        existing = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", ("ai_settings",)).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO app_settings (key, value_json) VALUES (?, ?)",
                ("ai_settings", json.dumps(DEFAULT_AI_SETTINGS)),
            )
