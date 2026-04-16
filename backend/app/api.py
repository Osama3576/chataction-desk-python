from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .config import APP_NAME, META_VERIFY_TOKEN
from .database import init_db
from .models import AISettingsPayload, IncomingMessage, ReviewDecisionPayload
from .providers import normalize_meta_whatsapp, normalize_twilio_whatsapp
from .services import build_csv_for_tasks, build_json, process_incoming_message
from . import repositories


def create_app():
    init_db()
    app = FastAPI(title=APP_NAME)

    @app.get("/health")
    def health():
        ai_settings = repositories.get_ai_settings()
        return {
            "ok": True,
            "service": APP_NAME,
            "ai_provider": ai_settings.get("provider", "google_gemini"),
            "ai_enabled": ai_settings.get("enabled", True),
            "ai_model": ai_settings.get("model"),
            "gemini_key_configured": ai_settings.get("api_key_configured", False),
        }

    @app.get("/api/dashboard")
    def dashboard():
        return repositories.dashboard_summary()

    @app.get("/api/review-items")
    def review_items():
        return repositories.list_review_items(pending_only=True)

    @app.post("/api/review-items/{review_item_id}/confirm")
    def confirm_review_item(review_item_id: int, payload: ReviewDecisionPayload):
        task = repositories.confirm_review_item(
            review_item_id, payload.title, payload.due_date, payload.priority, payload.notes, payload.type
        )
        if not task:
            raise HTTPException(status_code=404, detail="Review item not found")
        return task

    @app.post("/api/review-items/{review_item_id}/reject")
    def reject_review_item(review_item_id: int):
        repositories.reject_review_item(review_item_id)
        return {"ok": True}

    @app.get("/api/tasks")
    def tasks():
        return repositories.list_tasks()

    @app.post("/api/tasks/{task_id}/complete")
    def complete_task(task_id: int):
        repositories.update_task_status(task_id, "Completed")
        return {"ok": True}

    @app.post("/api/tasks/{task_id}/reopen")
    def reopen_task(task_id: int):
        repositories.update_task_status(task_id, "Pending")
        return {"ok": True}

    @app.post("/api/tasks/{task_id}/archive")
    def archive_task(task_id: int):
        repositories.archive_task(task_id)
        return {"ok": True}

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int):
        deleted = repositories.delete_task(task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"ok": True}

    @app.get("/api/conversations")
    def conversations():
        return repositories.list_conversations()

    @app.get("/api/conversations/{conversation_id}")
    def conversation_detail(conversation_id: int):
        data = repositories.get_conversation(conversation_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return data

    @app.get("/api/contacts")
    def contacts():
        return repositories.list_contacts()

    @app.get("/api/analytics")
    def analytics():
        return repositories.analytics_summary()

    @app.get("/api/ai-settings")
    def ai_settings():
        return repositories.get_ai_settings()

    @app.post("/api/ai-settings/update")
    def update_ai_settings(payload: AISettingsPayload):
        return repositories.update_ai_settings(payload.model_dump())

    @app.get("/api/export/tasks.csv")
    def export_tasks_csv():
        csv_text = build_csv_for_tasks()
        return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=tasks_export.csv"})

    @app.get("/api/export/tasks.json")
    def export_tasks_json():
        return Response(content=build_json(repositories.list_tasks()), media_type="application/json", headers={"Content-Disposition": "attachment; filename=tasks_export.json"})

    @app.get("/api/export/review-items.json")
    def export_review_json():
        return Response(content=build_json(repositories.list_review_items()), media_type="application/json", headers={"Content-Disposition": "attachment; filename=review_items_export.json"})

    @app.post("/api/simulate-message")
    async def simulate_message(payload: IncomingMessage):
        return process_incoming_message(payload)

    @app.get("/webhooks/meta/whatsapp")
    async def verify_meta_webhook(
        hub_mode: str = Query(alias="hub.mode"),
        hub_verify_token: str = Query(alias="hub.verify_token"),
        hub_challenge: str = Query(alias="hub.challenge"),
    ):
        if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
            return PlainTextResponse(hub_challenge)
        raise HTTPException(status_code=403, detail="Invalid verify token")

    @app.post("/webhooks/meta/whatsapp")
    async def meta_webhook(request: Request):
        payload = await request.json()
        messages = normalize_meta_whatsapp(payload)
        for message in messages:
            process_incoming_message(message)
        return JSONResponse({"received": len(messages)})

    @app.post("/webhooks/twilio/whatsapp")
    async def twilio_whatsapp_webhook(request: Request):
        form = await request.form()
        messages = normalize_twilio_whatsapp(dict(form))
        for message in messages:
            process_incoming_message(message)
        return PlainTextResponse("OK")

    return app
