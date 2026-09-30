from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


def resolve_max_model_attempts(max_attempts, model_count: int) -> int:
    """Compute the total upstream model-call budget (Phase 5 decision 4).

    Single source of the approved formula, shared by Settings.max_model_attempts
    and ModelRouter: budget = min(GEMINI_MAX_FALLBACK_ATTEMPTS, number of
    configured models), clamped to at least one call.

    Args:
        max_attempts: Configured attempt cap (GEMINI_MAX_FALLBACK_ATTEMPTS).
        model_count: Number of eligible configured models.

    Returns:
        Total call budget including the initial call.
    """
    try:
        attempts = int(max_attempts)
    except (TypeError, ValueError):
        attempts = 1
    if not model_count:
        return max(1, attempts)
    return max(1, min(attempts, model_count))


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
    GEMINI_MAX_RETRIES_PER_MODEL: int = Field(
        default=1,
        description="Maximum same-model retries per model before falling back to the next model",
    )
    CONVERSATION_CONTEXT_MAX_MESSAGES: int = Field(
        default=20,
        description=(
            "Maximum number of most-recent persisted messages included in the "
            "application-managed conversation context rebuilt on a model switch"
        ),
    )
    
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
    def max_model_attempts(self) -> int:
        """Total upstream model-call budget, including the initial call.

        Decision (Phase 5 Checkpoint A): budget = min(GEMINI_MAX_FALLBACK_ATTEMPTS,
        number of configured models), clamped to at least one call. The formula
        lives in resolve_max_model_attempts() so ModelRouter stays in sync.
        """
        return resolve_max_model_attempts(
            self.GEMINI_MAX_FALLBACK_ATTEMPTS,
            len(self.gemini_models_list),
        )
    
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
