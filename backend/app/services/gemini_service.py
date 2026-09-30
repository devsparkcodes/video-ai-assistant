"""Gemini Service Adapter.

A narrow adapter around the official google-genai SDK for Gemini interactions.
Follows the architecture documented in docs/02-architecture.md and docs/03-gemini-integration.md.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

import httpx
from google import genai
from google.genai import types, errors as genai_errors

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
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"
    SERVICE_UNAVAILABLE = "service_unavailable"


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
        
        # Verified against installed google-genai (2.23.0): genai.Client accepts
        # http_options=types.HttpOptions(timeout=<milliseconds>).
        self._client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=self._timeout_milliseconds()),
        )
        self._default_model = settings.gemini_models_list[0] if settings.gemini_models_list else "gemini-3.8-flash"

    @staticmethod
    def _timeout_milliseconds() -> int:
        """Resolve the configured upstream timeout in milliseconds.

        GEMINI_TIMEOUT_SECONDS is verified SDK-supported configuration
        (HttpOptions.timeout is documented in milliseconds).
        """
        try:
            seconds = int(settings.GEMINI_TIMEOUT_SECONDS)
        except (TypeError, ValueError):
            seconds = 120
        return max(1, seconds) * 1000
    
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
            
            # Create interaction.
            # store=True is verified as a supported parameter of the installed
            # SDK (CreateModelInteractionParam.store) and is required because the
            # application relies on previous_interaction_id for same-model
            # continuation (docs/06-conversation-system.md, docs/11-security.md).
            interaction = self._client.interactions.create(
                model=model_id,
                input=input_content,
                previous_interaction_id=previous_interaction_id,
                store=True,
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
    
    # Ordered machine-readable status tokens → (category, retryable).
    # Checked before HTTP codes so that a structured status always wins
    # (docs/03-gemini-integration.md §9: classify from error codes, not text).
    _STATUS_RULES: List[Any] = [
        ("model_not_found", GeminiErrorCategory.MODEL_NOT_FOUND, True),
        ("content_blocked", GeminiErrorCategory.CONTENT_BLOCKED, False),
        ("unauthenticated", GeminiErrorCategory.AUTHENTICATION, False),
        ("authentication", GeminiErrorCategory.AUTHENTICATION, False),
        ("permission_denied", GeminiErrorCategory.PERMISSION_DENIED, False),
        ("resource_exhausted", GeminiErrorCategory.RATE_LIMITED, True),
        ("rate_limit_exceeded", GeminiErrorCategory.RATE_LIMITED, True),
        ("invalid_argument", GeminiErrorCategory.INVALID_REQUEST, False),
        ("parameter_unknown", GeminiErrorCategory.INVALID_REQUEST, False),
        ("failed_precondition", GeminiErrorCategory.INVALID_REQUEST, False),
        ("invalid_request", GeminiErrorCategory.INVALID_REQUEST, False),
        ("not_found", GeminiErrorCategory.NOT_FOUND, False),
        ("deadline_exceeded", GeminiErrorCategory.TIMEOUT, True),
        ("timeout", GeminiErrorCategory.TIMEOUT, True),
        ("unavailable", GeminiErrorCategory.SERVER_ERROR, True),
        ("internal", GeminiErrorCategory.SERVER_ERROR, True),
        ("network", GeminiErrorCategory.NETWORK_ERROR, True),
    ]

    @classmethod
    def _structured_tokens(cls, error: Any) -> List[str]:
        """Extract machine-readable status tokens from an SDK APIError.

        Only structured fields are inspected (status/reason codes), never
        free-form message text, per docs/03 and docs/04 §4.
        """
        tokens: List[str] = []

        def _add(value: Any) -> None:
            if isinstance(value, str) and value.strip():
                tokens.append(value.strip().lower())

        _add(getattr(error, "status", None))

        details = getattr(error, "details", None)
        if isinstance(details, dict):
            for key in ("status", "reason", "type"):
                _add(details.get(key))
            nested = details.get("error")
            if isinstance(nested, dict):
                for key in ("status", "reason"):
                    _add(nested.get(key))
        elif isinstance(details, list):
            for item in details:
                if isinstance(item, dict):
                    for key in ("status", "reason"):
                        _add(item.get(key))
        return tokens

    @classmethod
    def _classify_api_error(cls, error: Exception) -> GeminiError:
        """Classify an SDK APIError from its structured status/code fields."""
        code = getattr(error, "code", None)
        tokens = cls._structured_tokens(error)

        # 1) Structured status tokens (most specific first; "model_not_found"
        #    must be matched before the generic "not_found" rule).
        for token in tokens:
            for match, category, retryable in cls._STATUS_RULES:
                if token == match:
                    return GeminiError(
                        category=category,
                        message=cls._message_for(category),
                        retryable=retryable,
                        raw_error=error,
                    )

        # 2) HTTP status codes when no structured token matched.
        if isinstance(error, genai_errors.ServerError) or (
            isinstance(code, int) and 500 <= code < 600
        ):
            category = GeminiErrorCategory.SERVER_ERROR
            retryable = True
        elif code == 401:
            category = GeminiErrorCategory.AUTHENTICATION
            retryable = False
        elif code == 403:
            category = GeminiErrorCategory.PERMISSION_DENIED
            retryable = False
        elif code == 429:
            category = GeminiErrorCategory.RATE_LIMITED
            retryable = True
        elif code == 408:
            category = GeminiErrorCategory.TIMEOUT
            retryable = True
        elif code == 400:
            category = GeminiErrorCategory.INVALID_REQUEST
            retryable = False
        elif code == 404:
            # A 404 without a model_not_found status is a resource error:
            # never rotate models for it (Phase 5 decision 2).
            category = GeminiErrorCategory.NOT_FOUND
            retryable = False
        else:
            category = GeminiErrorCategory.UNKNOWN
            retryable = True

        return GeminiError(
            category=category,
            message=cls._message_for(category),
            retryable=retryable,
            raw_error=error,
        )

    @staticmethod
    def _message_for(category: GeminiErrorCategory) -> str:
        """User-safe message for a normalized category."""
        return {
            GeminiErrorCategory.AUTHENTICATION: (
                "Authentication failed. Please check your API key configuration."
            ),
            GeminiErrorCategory.PERMISSION_DENIED: (
                "Permission denied. Your API key does not have access to this resource."
            ),
            GeminiErrorCategory.INVALID_REQUEST: (
                "Invalid request. Please check your input."
            ),
            GeminiErrorCategory.MODEL_NOT_FOUND: (
                "Model not found. The requested model is not available."
            ),
            GeminiErrorCategory.NOT_FOUND: (
                "The requested resource was not found. The video session may have expired."
            ),
            GeminiErrorCategory.RATE_LIMITED: (
                "Rate limit exceeded. Please try again later."
            ),
            GeminiErrorCategory.CONTENT_BLOCKED: (
                "Content was blocked by safety filters."
            ),
            GeminiErrorCategory.TIMEOUT: "Request timed out. Please try again.",
            GeminiErrorCategory.NETWORK_ERROR: (
                "Network error. Please check your connection."
            ),
            GeminiErrorCategory.SERVER_ERROR: (
                "The video service is temporarily unavailable. Please try again."
            ),
            GeminiErrorCategory.SERVICE_UNAVAILABLE: (
                "All supported models are temporarily unavailable. Please try again later."
            ),
            GeminiErrorCategory.UNKNOWN: (
                "An unexpected error occurred. Please try again."
            ),
        }.get(category, "An unexpected error occurred. Please try again.")

    def _normalize_error(self, error: Exception) -> GeminiError:
        """Normalize a Gemini error to the internal error structure.
        
        Classification order:
        1. Already-normalized GeminiError is returned unchanged.
        2. SDK APIError subclasses are classified from machine-readable
           status/code fields (docs/03 §9, docs/04 §4).
        3. Transport exceptions (timeouts, connection failures) are classified
           from their exception type.
        4. A conservative text fallback handles non-SDK exceptions that do not
           carry structured fields.
        
        Args:
            error: Raw Gemini error.
            
        Returns:
            Normalized Gemini error.
        """
        if isinstance(error, GeminiError):
            return error

        # Structured SDK errors (google-genai errors.APIError and subclasses).
        if isinstance(error, genai_errors.APIError):
            return self._classify_api_error(error)

        # Transport-level errors from the underlying HTTP client.
        if isinstance(error, (httpx.TimeoutException, TimeoutError)):
            return GeminiError(
                category=GeminiErrorCategory.TIMEOUT,
                message=self._message_for(GeminiErrorCategory.TIMEOUT),
                retryable=True,
                raw_error=error,
            )
        if isinstance(error, (httpx.TransportError, ConnectionError)):
            return GeminiError(
                category=GeminiErrorCategory.NETWORK_ERROR,
                message=self._message_for(GeminiErrorCategory.NETWORK_ERROR),
                retryable=True,
                raw_error=error,
            )

        # Text fallback for plain exceptions without structured fields.
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
        elif "model_not_found" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.MODEL_NOT_FOUND,
                message="Model not found. The requested model is not available.",
                retryable=True,
                raw_error=error,
            )
        elif "rate_limit" in error_str or "429" in error_str or "resource_exhausted" in error_str:
            return GeminiError(
                category=GeminiErrorCategory.RATE_LIMITED,
                message="Rate limit exceeded. Please try again later.",
                retryable=True,
                raw_error=error,
            )
        elif "content_blocked" in error_str or "content blocked" in error_str or "safety" in error_str:
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
        elif (
            "invalid_request" in error_str
            or "invalid request" in error_str
            or "bad_request" in error_str
            or "400" in error_str
        ):
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
        elif "404" in error_str:
            # A bare 404 in text is a resource error, not model unavailability.
            return GeminiError(
                category=GeminiErrorCategory.NOT_FOUND,
                message="The requested resource was not found. The video session may have expired.",
                retryable=False,
                raw_error=error,
            )
        else:
            return GeminiError(
                category=GeminiErrorCategory.UNKNOWN,
                message="An unexpected error occurred. Please try again.",
                retryable=True,
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