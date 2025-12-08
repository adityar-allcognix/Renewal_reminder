"""
Renewal Reminders Backend - Main Application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.api import (
    policies, customers, reminders, chat, analytics, health, auth,
    test_reminders, customer_public, document_upload, test_token, email_sms
)
from app.database import init_db

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Renewal Reminders Backend")
    await init_db()
    
    # Initialize scheduler if enabled
    if settings.SCHEDULER_ENABLED:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Renewal Reminders Backend")


app = FastAPI(
    title="Renewal Reminders API",
    description="AI-powered renewal reminder and retention outreach system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(policies.router, prefix="/api/policies", tags=["Policies"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(reminders.router, prefix="/api/reminders", tags=["Reminders"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(test_reminders.router, prefix="/api/test", tags=["Test Reminders"])
app.include_router(customer_public.router, prefix="/api/public", tags=["Public"])
app.include_router(document_upload.router, prefix="/api/public", tags=["Document Upload"])
app.include_router(test_token.router, prefix="/api/test-token", tags=["Test Token"])
app.include_router(email_sms.router, prefix="/api", tags=["Email & SMS"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Renewal Reminders API",
        "version": "1.0.0",
        "status": "running"
    }
