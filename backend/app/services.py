import csv
import io
import json

from . import repositories
from .extraction import classify_message_with_ai


def process_incoming_message(incoming):
    contact, conversation = repositories.upsert_contact_and_conversation(
        channel=incoming.channel,
        external_id=incoming.contact_id,
        name=incoming.contact_name,
        timestamp=incoming.timestamp.isoformat(),
    )
    message = repositories.create_message(
        conversation_id=conversation["id"],
        provider_message_id=incoming.provider_message_id,
        body=incoming.message_text,
        message_time=incoming.timestamp.isoformat(),
        raw_payload=incoming.raw_payload,
    )

    ai_settings = repositories.get_ai_settings()
    recent_messages = repositories.list_recent_messages(
        conversation_id=conversation["id"],
        limit=int(ai_settings.get("context_messages", 6)),
    )
    detections = classify_message_with_ai(
        incoming.message_text,
        contact["name"],
        incoming.timestamp,
        recent_messages,
        ai_settings,
    )

    created = []
    for detection in detections:
        detection["conversation_id"] = conversation["id"]
        detection["message_id"] = message["id"]
        created.append(repositories.create_review_item(detection))
    return {"contact": contact, "conversation": conversation, "message": message, "detections": created}


def build_csv_for_tasks():
    tasks = repositories.export_tasks()
    buffer = io.StringIO()
    fieldnames = ["id", "item_type", "title", "description", "due_date", "priority", "status", "contact_name", "conversation_title", "created_at", "completed_at"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in tasks:
        writer.writerow({key: row.get(key) for key in fieldnames})
    return buffer.getvalue()


def build_json(data):
    return json.dumps(data, indent=2)
