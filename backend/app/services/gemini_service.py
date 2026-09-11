"""Gemini Service Adapter.

A narrow adapter around the official google-genai SDK for Gemini interactions.
Follows the architecture documented in docs/02-architecture.md and docs/03-gemini-integration.md.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

from google import genai
from google.genai import types

from app.core.config import settings


logger = logging.getLogger(__name__)


class GeminiErrorCategory(Enum):
    """Gemini error categories for normalized error handling."""
    AUTHENTICATION = "authentication"
    PERMISSION_DENIED = "permission_denied"
    INVALID_REQUEST = "invalid_request"
    MODEL_NOT_FOUND = "model_not_found"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limit_exceeded"
    CONTENT_BLOCKED = "content_blocked"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class GeminiAnswer:
    """Normalized Gemini response structure."""
    text: str
    interaction_id: Optional[str]
    model: str
    raw_metadata: Optional[Dict[str, Any]] = None


@dataclass
class GeminiError(Exception):
    """Normalized Gemini error structure."""
    category: GeminiErrorCategory
    message: str
    retryable: bool
    raw_error: Optional[Exception] = None
    
    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


class GeminiService:
    """Gemini service adapter for handling interactions with Gemini models."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini service.
        
        Args:
            api_key: Gemini API key. If not provided, uses GEMINI_API_KEY from settings.
            
        Raises:
            ValueError: If no API key is provided and GEMINI_API_KEY is not set.
        """
        self._api_key = api_key or settings.GEMINI_API_KEY
        if not self._api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or provide api_key parameter."
            )
        
        self._client = genai.Client(api_key=self._api_key)
        self._default_model = settings.gemini_models_list[0] if settings.gemini_models_list else "gemini-3.8-flash"
    
    def create_interaction(
        self,
        question: str,
        video_uri: Optional[str] = None,
        video_mime_type: Optional[str] = None,
        model: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        agentic: bool = True,
    ) -> GeminiAnswer:
        """Create a new interaction with Gemini.
        
        Args:
            question: The question to ask about the video.
            video_uri: URI of the video (File API URI or YouTube URL).
            video_mime_type: MIME type of the video (required for File API uploads).
            model: Model ID to use. If not provided, uses the default model.
            previous_interaction_id: ID of previous interaction for conversation continuity.
            agentic: Whether to use agentic processing for video understanding.
            
        Returns:
            Normalized Gemini answer.
            
        Raises:
            GeminiError: If the interaction fails.
        """
        model_id = model or self._default_model
        
        try:
            # Build input content
            input_content = self._build_input_content(
                question=question,
                video_uri=video_uri,
                video_mime_type=video_mime_type,
                agentic=agentic,
            )
            
            # Create interaction
            interaction = self._client.interactions.create(
                model=model_id,
                input=input_content,
                previous_interaction_id=previous_interaction_id,
            )
            
            # Normalize response
            return self._normalize_response(interaction, model_id)
            
        except Exception as e:
            raise self._normalize_error(e)
    
    def _build_input_content(
        self,
        question: str,
        video_uri: Optional[str],
        video_mime_type: Optional[str],
        agentic: bool,
    ) -> List[Dict[str, Any]]:
        """Build input content for the interaction.
        
        Args:
            question: The question to ask.
            video_uri: URI of the video.
            video_mime_type: MIME type of the video.
            agentic: Whether to use agentic processing.
            
        Returns:
            List of input content items.
        """
        input_content = []
        
        # Add video input if provided
        if video_uri:
            video_input = {
                "type": "video",
                "uri": video_uri,
            }
            
            if video_mime_type:
                video_input["mime_type"] = video_mime_type
            
            if agentic:
                video_input["processing"] = "agentic"
            
            input_content.append(video_input)
        
        # Add text question
        input_content.append({
            "type": "text",
            "text": question,
        })
        
        return input_content
    
    def _normalize_response(
        self,
        interaction: Any,
        model: str,
    ) -> GeminiAnswer:
        """Normalize Gemini response to internal structure.
        
        Args:
            interaction: Raw Gemini interaction response.
            model: Model ID used for the interaction.
            
        Returns:
            Normalized Gemini answer.
        """
        # Extract text from interaction
        text = ""
        if hasattr(interaction, 'output_text'):
            text = interaction.output_text
        elif hasattr(interaction, 'output') and hasattr(interaction.output, 'text'):
            text = interaction.output.text
        
        # Extract interaction ID
        interaction_id = None
        if hasattr(interaction, 'id'):
            interaction_id = interaction.id
        
        # Build raw metadata
        raw_metadata = None
        if hasattr(interaction, '__dict__'):
            raw_metadata = {
                "status": getattr(interaction, 'status', None),
                "created": getattr(interaction, 'created', None),
            }
        
        return GeminiAnswer(
            text=text,
            interaction_id=interaction_id,
            model=model,
            raw_metadata=raw_metadata,
        )
    
    def _normalize_error(self, error: Exception) -> GeminiError:
        """Normalize Gemini error to internal error structure.
        
        Args:
            error: Raw Gemini error.
            
        Returns:
            Normalized Gemini error.
        """
        error_str = str(error).lower()
        
        # Classify error based on exception type and message
        if "authentication" in error_str or "api_key" in error_str or "401" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.AUTHENTICATION,
                message="Authentication failed. Please check your API key configuration.",
                retryable=False,
                raw_error=error,
            )
        elif "permission" in error_str or "403" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.PERMISSION_DENIED,
                message="Permission denied. Your API key does not have access to this resource.",
                retryable=False,
                raw_error=error,
            )
        elif "model_not_found" in error_str or "404" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.MODEL_NOT_FOUND,
                message="Model not found. The requested model is not available.",
                retryable=False,
                raw_error=error,
            )
        elif "rate_limit" in error_str or "429" in error_str or "resource_exhausted" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.RATE_LIMITED,
                message="Rate limit exceeded. Please try again later.",
                retryable=True,
                raw_error=error,
            )
        elif "content_blocked" in error_str or "safety" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.CONTENT_BLOCKED,
                message="Content was blocked by safety filters.",
                retryable=False,
                raw_error=error,
            )
        elif "timeout" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.TIMEOUT,
                message="Request timed out. Please try again.",
                retryable=True,
                raw_error=error,
            )
        elif "invalid_request" in error_str or "bad_request" in error_str or "400" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.INVALID_REQUEST,
                message="Invalid request. Please check your input.",
                retryable=False,
                raw_error=error,
            )
        elif "network" in error_str or "connection" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.NETWORK_ERROR,
                message="Network error. Please check your connection.",
                retryable=True,
                raw_error=error,
            )
        else:
            return GeminiError(
                category=GeminiErrorCategory.UNKNOWN,
                message="An unexpected error occurred. Please try again.",
                retryable=False,
                raw_error=error,
            )
    
    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a file to Gemini File API.
        
        Args:
            file_path: Path to the file to upload.
            
        Returns:
            Dictionary with file URI and metadata.
            
        Raises:
            GeminiError: If the upload fails.
        """
        try:
            file = self._client.files.upload(file=file_path)
            return {
                "uri": file.uri,
                "name": file.name,
                "mime_type": file.mime_type,
                "state": file.state.name if file.state else None,
            }
        except Exception as e:
            raise self._normalize_error(e)
    
    def get_file(self, file_name: str) -> Dict[str, Any]:
        """Get file metadata from Gemini File API.
        
        Args:
            file_name: Name of the file to retrieve.
            
        Returns:
            Dictionary with file metadata.
            
        Raises:
            GeminiError: If the retrieval fails.
        """
        try:
            file = self._client.files.get(name=file_name)
            return {
                "uri": file.uri,
                "name": file.name,
                "mime_type": file.mime_type,
                "state": file.state.name if file.state else None,
            }
        except Exception as e:
            raise self._normalize_error(e)