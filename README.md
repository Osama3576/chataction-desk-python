# ChatAction Desk

ChatAction Desk is a Python desktop automation tool for turning business chat traffic into a structured review workflow.

## What this build demonstrates

- PySide6 desktop product UI
- FastAPI backend
- Meta WhatsApp and Twilio webhook handling
- AI-assisted action detection with Google Gemini
- Review queue -> tasks workflow
- Local SQLite persistence
- Dashboard, tasks, conversations, contacts, analytics, and AI extraction settings

## AI extraction flow

1. A chat message reaches the backend through a webhook or a manual test event.
2. The backend stores the message and recent conversation context.
3. Gemini analyzes the latest message and returns a structured JSON decision.
4. If Gemini detects an actionable item with enough confidence, a review item is added to the dashboard and review queue.
5. Confirmed items move into Tasks.

## Backend setup

1. Open `backend/.env`
2. Set your Google AI Studio key:

```env
GEMINI_API_KEY=your_real_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
```

3. Install dependencies:

```bash
pip install -r backend/requirements.txt
```

4. Run the API:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

## Desktop setup

```bash
pip install -r desktop/requirements.txt
cd desktop
python main.py
```
