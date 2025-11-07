from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import webhook

# Create database tables (safe to run even if none exist yet)
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="AgriAgent API",
    version="1.0.0",
    description="AI-powered assistant for smallholder farmers via WhatsApp"
)

# Enable CORS (so the Flutter admin UI or other frontends can call it)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict this later
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint (Render uses this for / health probe)
@app.get("/")
def healthcheck():
    return {"status": "ok", "service": "AgriAgent API"}

# Include the WhatsApp webhook routes
app.include_router(webhook.router)
