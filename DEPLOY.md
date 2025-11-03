# Deployment Guide — AgriAgent MVP

This guide lists quick steps to deploy to common platforms.

## 1) Render (fastest)
- Create a new Web Service on Render.
- Connect GitHub repo and select the repo.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Add environment variables in the Render dashboard (OPENAI_API_KEY, TWILIO_*, OPENWEATHER_API_KEY, ADMIN_SECRET).
- Set health checks to `/`.

## 2) Railway
- Similar steps: add a Python service, set env vars.
- Railway gives automatic Postgres if you want to switch from SQLite.

## 3) AWS ECS / Fargate
- Build Docker image, push to ECR.
- Create an ECS service on Fargate using the image.
- Add secrets in Secrets Manager (OPENAI_API_KEY etc.)
- Attach ALB with TLS.

## 4) Domain + TLS
- Use Cloudflare or provider to point domain to your hosting.
- Ensure webhook URL is HTTPS before configuring Twilio.

## Notes on scaling
- Replace SQLite with Postgres for concurrent writes.
- Move OpenAI calls behind a rate-limiter / queue.
- Monitor Twilio & OpenAI costs.

