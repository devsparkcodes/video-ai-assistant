from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import create_db_and_tables
from app.api.v1.router import router as v1_router
from app.schemas.error import ErrorResponse, ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    create_db_and_tables()
    yield
    # Shutdown


app = FastAPI(
    title="Video AI Assistant",
    description="A web application for asking natural-language questions about videos using Gemini",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 router
app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            retryable=False
        )
    )
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )
