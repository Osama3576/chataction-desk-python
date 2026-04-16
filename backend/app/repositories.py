import json
from datetime import datetime

from .config import GEMINI_API_KEY
from .database import db, DEFAULT_AI_SETTINGS


def upsert_contact_and_conversation(channel: str, external_id: str, name: str, timestamp: str):
    with db() as conn:
        contact = conn.execute("SELECT * FROM contacts WHERE external_id = ?", (external_id,)).fetchone()
        if contact is None:
            conn.execute(
                "INSERT INTO contacts (external_id, name, channel, last_activity) VALUES (?, ?, ?, ?)",
                (external_id, name, channel, timestamp),
            )
            contact = conn.execute("SELECT * FROM contacts WHERE external_id = ?", (external_id,)).fetchone()
        else:
            conn.execute(
                "UPDATE contacts SET name = ?, channel = ?, last_activity = ? WHERE id = ?",
                (name, channel, timestamp, contact["id"]),
            )
            contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact["id"],)).fetchone()

        title = f"{name} · {channel.title()}"
        conversation = conn.execute(
            "SELECT * FROM conversations WHERE contact_id = ? AND channel = ?",
            (contact["id"], channel),
        ).fetchone()
        if conversation is None:
            conn.execute(
                "INSERT INTO conversations (contact_id, title, channel, last_message_at) VALUES (?, ?, ?, ?)",
                (contact["id"], title, channel, timestamp),
            )
            conversation = conn.execute(
                "SELECT * FROM conversations WHERE contact_id = ? AND channel = ?",
                (contact["id"], channel),
            ).fetchone()
        else:
            conn.execute("UPDATE conversations SET last_message_at = ? WHERE id = ?", (timestamp, conversation["id"]))
            conversation = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation["id"],)).fetchone()
        return dict(contact), dict(conversation)


def create_message(conversation_id: int, provider_message_id: str | None, body: str, message_time: str, raw_payload: dict | None):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, provider_message_id, sender_label, body, message_time, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, provider_message_id, "Contact", body, message_time, json.dumps(raw_payload or {})),
        )
        row = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row)


def list_recent_messages(conversation_id: int, limit: int = 6):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, sender_label, body, message_time
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]


def get_ai_settings():
    with db() as conn:
        row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", ("ai_settings",)).fetchone()
        if row is None:
            return DEFAULT_AI_SETTINGS | {"api_key_configured": bool(GEMINI_API_KEY)}
        settings = DEFAULT_AI_SETTINGS | json.loads(row["value_json"])
        settings["api_key_configured"] = bool(GEMINI_API_KEY)
        return settings


def update_ai_settings(payload: dict):
    current = get_ai_settings()
    merged = {
        **DEFAULT_AI_SETTINGS,
        **{k: v for k, v in current.items() if k in DEFAULT_AI_SETTINGS},
        **payload,
    }
    now = datetime.utcnow().isoformat()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            ("ai_settings", json.dumps({k: merged[k] for k in DEFAULT_AI_SETTINGS}), now),
        )
    merged["api_key_configured"] = bool(GEMINI_API_KEY)
    return merged


def create_review_item(item: dict):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO review_items (
                conversation_id, message_id, item_type, title, summary, source_preview,
                due_date, confidence_label, confidence_score, priority, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["conversation_id"], item["message_id"], item["item_type"], item["title"],
                item["summary"], item["source_preview"], item.get("due_date"),
                item["confidence_label"], item["confidence_score"], item.get("priority", "Medium"),
                "Pending Review", item.get("notes", "")
            ),
        )
        row = conn.execute("SELECT * FROM review_items ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row)


def list_review_items(*, pending_only: bool = False):
    query = """
        SELECT r.*, c.title AS conversation_title, ct.name AS contact_name, ct.external_id AS contact_external_id
        FROM review_items r
        JOIN conversations c ON c.id = r.conversation_id
        JOIN contacts ct ON ct.id = c.contact_id
    """
    params = ()
    if pending_only:
        query += " WHERE r.status = ?"
        params = ("Pending Review",)
    query += " ORDER BY r.id DESC"

    with db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def confirm_review_item(review_item_id: int, title: str | None, due_date: str | None, priority: str | None, notes: str | None, item_type: str | None):
    with db() as conn:
        review = conn.execute(
            """
            SELECT r.*, c.contact_id AS linked_contact_id
            FROM review_items r
            JOIN conversations c ON c.id = r.conversation_id
            WHERE r.id = ?
            """,
            (review_item_id,),
        ).fetchone()
        if review is None:
            return None
        final_title = title or review["title"]
        final_due = due_date if due_date is not None else review["due_date"]
        final_priority = priority or review["priority"]
        final_notes = notes if notes is not None else review["notes"]
        final_type = item_type or review["item_type"]
        updated_review = conn.execute(
            """
            UPDATE review_items
            SET status = 'Confirmed', reviewed_at = CURRENT_TIMESTAMP, title = ?, due_date = ?, priority = ?, notes = ?, item_type = ?
            WHERE id = ? AND status = 'Pending Review'
            """,
            (final_title, final_due, final_priority, final_notes, final_type, review_item_id),
        )
        if updated_review.rowcount == 0:
            existing_task = conn.execute(
                "SELECT * FROM tasks WHERE review_item_id = ? ORDER BY id DESC LIMIT 1",
                (review_item_id,),
            ).fetchone()
            return dict(existing_task) if existing_task is not None else None

        conn.execute(
            """
            INSERT INTO tasks (
                review_item_id, conversation_id, contact_id, item_type, title, description,
                due_date, priority, status, source_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
            """,
            (
                review_item_id, review["conversation_id"], review["linked_contact_id"], final_type,
                final_title, review["summary"] + (f"\n\nNotes: {final_notes}" if final_notes else ""),
                final_due, final_priority, review["source_preview"]
            ),
        )
        task = conn.execute("SELECT * FROM tasks WHERE review_item_id = ? ORDER BY id DESC LIMIT 1", (review_item_id,)).fetchone()
        return dict(task)


def reject_review_item(review_item_id: int):
    with db() as conn:
        conn.execute("UPDATE review_items SET status = 'Rejected', reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (review_item_id,))


def list_tasks():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT t.*, ct.name AS contact_name, c.title AS conversation_title
            FROM tasks t
            JOIN contacts ct ON ct.id = t.contact_id
            JOIN conversations c ON c.id = t.conversation_id
            ORDER BY t.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_task_status(task_id: int, new_status: str):
    completed_at = datetime.utcnow().isoformat() if new_status == "Completed" else None
    with db() as conn:
        conn.execute("UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?", (new_status, completed_at, task_id))


def archive_task(task_id: int):
    with db() as conn:
        conn.execute("UPDATE tasks SET status = 'Archived', archived_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))


def delete_task(task_id: int):
    with db() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0


def list_conversations():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, ct.name AS contact_name, ct.external_id AS contact_external_id,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,
                   (SELECT COUNT(*) FROM review_items r WHERE r.conversation_id = c.id AND r.status != 'Rejected') AS action_count
            FROM conversations c
            JOIN contacts ct ON ct.id = c.contact_id
            ORDER BY c.last_message_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conversation_id: int):
    with db() as conn:
        conversation = conn.execute(
            """
            SELECT c.*, ct.name AS contact_name, ct.external_id AS contact_external_id
            FROM conversations c
            JOIN contacts ct ON ct.id = c.contact_id
            WHERE c.id = ?
            """,
            (conversation_id,),
        ).fetchone()
        if not conversation:
            return None
        messages = conn.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC", (conversation_id,)).fetchall()
        review_items = conn.execute("SELECT * FROM review_items WHERE conversation_id = ? ORDER BY id DESC", (conversation_id,)).fetchall()
        tasks = conn.execute("SELECT * FROM tasks WHERE conversation_id = ? ORDER BY id DESC", (conversation_id,)).fetchall()
        return {
            "conversation": dict(conversation),
            "messages": [dict(m) for m in messages],
            "review_items": [dict(r) for r in review_items],
            "tasks": [dict(t) for t in tasks],
        }


def list_contacts():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                ct.*,
                COUNT(DISTINCT c.id) AS conversations_count,
                COALESCE(SUM(CASE WHEN t.status IN ('Pending', 'In Progress') THEN 1 ELSE 0 END), 0) AS active_tasks,
                COALESCE(SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed_tasks,
                COALESCE(SUM(CASE WHEN r.status = 'Pending Review' THEN 1 ELSE 0 END), 0) AS pending_reviews
            FROM contacts ct
            LEFT JOIN conversations c ON c.contact_id = ct.id
            LEFT JOIN tasks t ON t.contact_id = ct.id
            LEFT JOIN review_items r ON r.conversation_id = c.id
            GROUP BY ct.id
            ORDER BY ct.last_activity DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def dashboard_summary():
    with db() as conn:
        summary = {
            "total_conversations": conn.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"],
            "total_messages": conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"],
            "review_pending": conn.execute("SELECT COUNT(*) AS c FROM review_items WHERE status = 'Pending Review'").fetchone()["c"],
            "review_rejected": conn.execute("SELECT COUNT(*) AS c FROM review_items WHERE status = 'Rejected'").fetchone()["c"],
            "review_confirmed": conn.execute("SELECT COUNT(*) AS c FROM review_items WHERE status = 'Confirmed'").fetchone()["c"],
            "tasks_active": conn.execute("SELECT COUNT(*) AS c FROM tasks WHERE status IN ('Pending', 'In Progress')").fetchone()["c"],
            "tasks_completed": conn.execute("SELECT COUNT(*) AS c FROM tasks WHERE status = 'Completed'").fetchone()["c"],
            "overdue_count": conn.execute("SELECT COUNT(*) AS c FROM tasks WHERE due_date IS NOT NULL AND status != 'Completed' AND due_date < date('now')").fetchone()["c"],
        }
        confidence = conn.execute("SELECT confidence_label, COUNT(*) AS total FROM review_items GROUP BY confidence_label").fetchall()
        by_type = conn.execute("SELECT item_type, COUNT(*) AS total FROM review_items GROUP BY item_type").fetchall()
        recent_review = conn.execute("SELECT id, item_type, title, confidence_label, source_preview, status, created_at FROM review_items ORDER BY id DESC LIMIT 8").fetchall()
        recent_conversations = conn.execute(
            "SELECT c.id, c.title, c.last_message_at, ct.name AS contact_name FROM conversations c JOIN contacts ct ON ct.id = c.contact_id ORDER BY c.last_message_at DESC LIMIT 6"
        ).fetchall()
        return {
            "summary": summary,
            "confidence_breakdown": [dict(r) for r in confidence],
            "type_breakdown": [dict(r) for r in by_type],
            "recent_review": [dict(r) for r in recent_review],
            "recent_conversations": [dict(r) for r in recent_conversations],
        }


def analytics_summary():
    with db() as conn:
        return {
            "actions_by_type": [dict(r) for r in conn.execute("SELECT item_type AS label, COUNT(*) AS total FROM review_items GROUP BY item_type").fetchall()],
            "confidence_distribution": [dict(r) for r in conn.execute("SELECT confidence_label AS label, COUNT(*) AS total FROM review_items GROUP BY confidence_label").fetchall()],
            "task_status_distribution": [dict(r) for r in conn.execute("SELECT status AS label, COUNT(*) AS total FROM tasks GROUP BY status").fetchall()],
            "contact_load": [dict(r) for r in conn.execute("SELECT ct.name AS label, COUNT(t.id) AS total FROM contacts ct LEFT JOIN tasks t ON t.contact_id = ct.id GROUP BY ct.id ORDER BY total DESC LIMIT 8").fetchall()]
        }


def export_tasks():
    return list_tasks()
