"""
Application Configuration
"""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "renewal-reminders"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "your-super-secret-key"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://renewals_user:renewals_pass@localhost:5432/renewals_db"
    SYNC_DATABASE_URL: str = "postgresql://renewals_user:renewals_pass@localhost:5432/renewals_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # AI Model Configuration
    # Supports: OpenAI, GitHub Models, or any OpenAI-compatible API
    OPENAI_API_KEY: str = ""  # Your OpenAI API key (sk-...)
    GITHUB_TOKEN: str = ""    # Or GitHub token for GitHub Models
    AI_MODEL_ID: str = "gpt-4o-mini"  # Model to use
    AI_MODEL: str = "gpt-4o-mini"
    AI_MODEL_ENDPOINT: str = "https://api.openai.com/v1"  # OpenAI default
    
    @property
    def ai_api_key(self) -> str:
        """Get the API key - prefers OPENAI_API_KEY, falls back to GITHUB_TOKEN."""
        return self.OPENAI_API_KEY or self.GITHUB_TOKEN
    
    # Embedding Model
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Communication - SendGrid
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "renewals@yourcompany.com"
    SENDGRID_FROM_NAME: str = "Renewal Reminders"
    
    # Communication - Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    
    # Frontend URL (for generating links)
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Scheduler
    SCHEDULER_ENABLED: bool = True
    REMINDER_CHECK_INTERVAL_MINUTES: int = 60
    REMINDER_WINDOWS: str = "30,15,7,1"
    
    # Security
    JWT_SECRET_KEY: str = "your-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    
    # CORS - stored as comma-separated string in .env
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    
    # RAG Configuration
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K_RESULTS: int = 5
    VECTOR_DIMENSION: int = 384
    POLICY_DOCUMENTS_PATH: str = "../policy_documents"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    @property
    def reminder_window_days(self) -> List[int]:
        """Parse reminder windows into list of integers."""
        return [int(d.strip()) for d in self.REMINDER_WINDOWS.split(",")]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
