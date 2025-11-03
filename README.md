<<<<<<< HEAD
# AgriAgent MVP

This repository contains a working MVP for an AI Agent to support smallholder farmers via WhatsApp.

Contents:
- `app/` : FastAPI backend (webhook, agent, DB)
- `frontend/` : Simple React admin UI (view messages, send alerts)
- Docker + docker-compose for local deployment
- `DEPLOY.md` : deployment guide (AWS / Render / Railway suggestions)

To run locally:
1. Copy `.env.example` to `.env` and fill keys (OpenAI, Twilio, OpenWeather).
2. Build & run:
   - `docker compose up --build`
   or for dev:
   - create virtualenv, `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --port 8000`
3. Expose webhook with ngrok and configure Twilio sandbox webhook to `https://<ngrok-id>.ngrok.io/webhook`

=======
# agricagent-api
AgricAgent FastAPI backend
>>>>>>> 42989f5774e08513efe6fd9e6113629cf1ab61cf
