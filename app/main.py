from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import webhook

# ==========================================================
# DATABASE INIT (safe if empty — no models defined yet)
# ==========================================================
Base.metadata.create_all(bind=engine)

# ==========================================================
# APP INITIALIZATION
# ==========================================================
app = FastAPI(
    title="AgriAgent API",
    version="1.0.0",
    description=(
        "AgriAgent — AI-powered WhatsApp assistant for smallholder farmers. "
        "Provides text, image, and WhatsApp webhook endpoints."
    ),
)

# ==========================================================
# GLOBAL CORS MIDDLEWARE (for Flutter app & admin panel)
# ==========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # you can restrict to your frontend URL later
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# BASIC HEALTH CHECK ENDPOINT (used by Render and debugging)
# ==========================================================
@app.get("/")
def root():
    """
    Health check route for Render or uptime checks.
    """
    return {"status": "ok", "service": "AgriAgent API"}

# ==========================================================
# INCLUDE ALL ROUTES (webhook + app JSON endpoints)
# ==========================================================
app.include_router(webhook.router)

# ==========================================================
# OPTIONAL DEV-ONLY ROOT INFO (visible in interactive docs)
# ==========================================================
@app.get("/info")
def info():
    return {
        "name": "AgriAgent API",
        "version": "1.0.0",
        "routes": ["/", "/check", "/message", "/identify", "/webhook"],
        "description": "All systems operational ✅",
    }
