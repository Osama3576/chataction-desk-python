from datetime import datetime
from .models import IncomingMessage

def normalize_meta_whatsapp(payload: dict) -> list[IncomingMessage]:
    items = []
    entries = payload.get("entry", [])
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = value.get("contacts", [])
            messages = value.get("messages", [])
            name = contacts[0].get("profile", {}).get("name", "Unknown Contact") if contacts else "Unknown Contact"
            contact_id = contacts[0].get("wa_id", "unknown-meta") if contacts else "unknown-meta"
            for msg in messages:
                msg_type = msg.get("type")
                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg_type == "button":
                    text = msg.get("button", {}).get("text", "")
                else:
                    text = f"[Unsupported message type: {msg_type}]"
                items.append(
                    IncomingMessage(
                        channel="meta_whatsapp",
                        provider_message_id=msg.get("id"),
                        contact_name=name,
                        contact_id=contact_id,
                        message_text=text,
                        timestamp=datetime.fromtimestamp(int(msg.get("timestamp", datetime.utcnow().timestamp()))),
                        raw_payload=msg,
                    )
                )
    return items

def normalize_twilio_whatsapp(form_data: dict) -> list[IncomingMessage]:
    from_number = form_data.get("From", "unknown-twilio").replace("whatsapp:", "")
    profile_name = form_data.get("ProfileName", from_number)
    body = form_data.get("Body", "")
    message_sid = form_data.get("MessageSid")
    return [
        IncomingMessage(
            channel="twilio_whatsapp",
            provider_message_id=message_sid,
            contact_name=profile_name,
            contact_id=from_number,
            message_text=body,
            timestamp=datetime.utcnow(),
            raw_payload=form_data,
        )
    ]
