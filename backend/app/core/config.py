from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Gemini API
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    GEMINI_MODELS: str = Field(
        default="gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite",
        description="Comma-separated list of Gemini models in priority order"
    )
    GEMINI_TIMEOUT_SECONDS: int = Field(default=120, description="Request timeout in seconds")
    GEMINI_MAX_FALLBACK_ATTEMPTS: int = Field(default=4, description="Maximum fallback attempts")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./video_ai_assistant.db",
        description="Database connection URL"
    )
    
    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = Field(default=500, description="Maximum upload size in MB")
    
    # CORS
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173",
        description="Comma-separated list of allowed CORS origins"
    )
    
    @property
    def gemini_models_list(self) -> List[str]:
        """Parse comma-separated model list into a list."""
        return [m.strip() for m in self.GEMINI_MODELS.split(",") if m.strip()]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


settings = Settings()
