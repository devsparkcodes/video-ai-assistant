"""Tests for Gemini Service Adapter.

Tests use mocked Gemini calls and do not require a real API key.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

from app.services.gemini_service import (
    GeminiService,
    GeminiAnswer,
    GeminiError,
    GeminiErrorCategory,
)


class MockInteraction:
    """Mock Gemini interaction response."""
    
    def __init__(
        self,
        text: str = "Test response",
        interaction_id: str = "test-interaction-123",
        model: str = "gemini-3.8-flash",
    ):
        self.output_text = text
        self.id = interaction_id
        self.model = model
        self.status = "completed"
        self.created = "2026-09-09T12:00:00Z"


class MockFile:
    """Mock Gemini file response."""
    
    def __init__(
        self,
        uri: str = "gs://test-bucket/test-video.mp4",
        name: str = "files/test-video",
        mime_type: str = "video/mp4",
        state: str = "ACTIVE",
    ):
        self.uri = uri
        self.name = name
        self.mime_type = mime_type
        self.state = Mock(name=state)


class TestGeminiServiceInitialization:
    """Test Gemini service initialization."""
    
    def test_initialization_with_api_key(self):
        """Test service initialization with provided API key."""
        service = GeminiService(api_key="test-api-key")
        assert service._api_key == "test-api-key"
    
    @patch('app.services.gemini_service.settings')
    def test_initialization_with_environment_variable(self, mock_settings):
        """Test service initialization with environment variable."""
        mock_settings.GEMINI_API_KEY = "env-api-key"
        mock_settings.gemini_models_list = ["gemini-3.8-flash"]
        
        service = GeminiService()
        assert service._api_key == "env-api-key"
    
    def test_initialization_without_api_key_raises_error(self):
        """Test that initialization fails without API key."""
        with patch('app.services.gemini_service.settings') as mock_settings:
            mock_settings.GEMINI_API_KEY = ""
            
            with pytest.raises(ValueError, match="Gemini API key is required"):
                GeminiService()


class TestGeminiServiceCreateInteraction:
    """Test Gemini service create_interaction method."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_create_interaction_with_video(self, mock_client_class):
        """Test creating interaction with video input."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        # Create service and interaction
        service = GeminiService(api_key="test-api-key")
        answer = service.create_interaction(
            question="What is this video about?",
            video_uri="gs://test-bucket/test.mp4",
            video_mime_type="video/mp4",
        )
        
        # Verify
        assert isinstance(answer, GeminiAnswer)
        assert answer.text == "Test response"
        assert answer.interaction_id == "test-interaction-123"
        assert answer.model == "gemini-3.8-flash"
        
        # Verify correct SDK call
        mock_client.interactions.create.assert_called_once()
        call_args = mock_client.interactions.create.call_args
        assert call_args.kwargs['model'] == "gemini-3.8-flash"
        
        # Verify input structure
        input_content = call_args.kwargs['input']
        assert len(input_content) == 2
        assert input_content[0]['type'] == 'video'
        assert input_content[0]['uri'] == 'gs://test-bucket/test.mp4'
        assert input_content[0]['processing'] == 'agentic'
        assert input_content[1]['type'] == 'text'
        assert input_content[1]['text'] == 'What is this video about?'
    
    @patch('app.services.gemini_service.genai.Client')
    def test_create_interaction_without_video(self, mock_client_class):
        """Test creating interaction without video input."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        # Create service and interaction
        service = GeminiService(api_key="test-api-key")
        answer = service.create_interaction(
            question="Hello, how are you?",
        )
        
        # Verify
        assert isinstance(answer, GeminiAnswer)
        assert answer.text == "Test response"
        
        # Verify input structure (text only)
        call_args = mock_client.interactions.create.call_args
        input_content = call_args.kwargs['input']
        assert len(input_content) == 1
        assert input_content[0]['type'] == 'text'
        assert input_content[0]['text'] == 'Hello, how are you?'
    
    @patch('app.services.gemini_service.genai.Client')
    def test_create_interaction_with_previous_interaction_id(self, mock_client_class):
        """Test creating interaction with previous interaction ID."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        # Create service and interaction
        service = GeminiService(api_key="test-api-key")
        answer = service.create_interaction(
            question="What happened next?",
            previous_interaction_id="previous-interaction-123",
        )
        
        # Verify
        call_args = mock_client.interactions.create.call_args
        assert call_args.kwargs['previous_interaction_id'] == "previous-interaction-123"
    
    @patch('app.services.gemini_service.genai.Client')
    def test_create_interaction_with_custom_model(self, mock_client_class):
        """Test creating interaction with custom model."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        # Create service and interaction
        service = GeminiService(api_key="test-api-key")
        answer = service.create_interaction(
            question="Test question",
            model="gemini-3.7-flash",
        )
        
        # Verify
        call_args = mock_client.interactions.create.call_args
        assert call_args.kwargs['model'] == "gemini-3.7-flash"


class TestGeminiServiceErrorHandling:
    """Test Gemini service error handling."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_authentication_error(self, mock_client_class):
        """Test authentication error normalization."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.side_effect = Exception("authentication failed 401")
        
        # Create service and attempt interaction
        service = GeminiService(api_key="test-api-key")
        
        with pytest.raises(GeminiError) as exc_info:
            service.create_interaction(
                question="Test question",
                video_uri="gs://test-bucket/test.mp4",
            )
        
        # Verify error
        assert exc_info.value.category == GeminiErrorCategory.AUTHENTICATION
        assert exc_info.value.retryable is False
        assert "authentication" in exc_info.value.message.lower()
    
    @patch('app.services.gemini_service.genai.Client')
    def test_rate_limit_error(self, mock_client_class):
        """Test rate limit error normalization."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.side_effect = Exception("rate limit exceeded 429")
        
        # Create service and attempt interaction
        service = GeminiService(api_key="test-api-key")
        
        with pytest.raises(GeminiError) as exc_info:
            service.create_interaction(
                question="Test question",
                video_uri="gs://test-bucket/test.mp4",
            )
        
        # Verify error
        assert exc_info.value.category == GeminiErrorCategory.RATE_LIMITED
        assert exc_info.value.retryable is True
    
    @patch('app.services.gemini_service.genai.Client')
    def test_model_not_found_error(self, mock_client_class):
        """Test model not found error normalization."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.side_effect = Exception("model_not_found 404")
        
        # Create service and attempt interaction
        service = GeminiService(api_key="test-api-key")
        
        with pytest.raises(GeminiError) as exc_info:
            service.create_interaction(
                question="Test question",
                video_uri="gs://test-bucket/test.mp4",
            )
        
        # Verify error
        assert exc_info.value.category == GeminiErrorCategory.MODEL_NOT_FOUND
        # Phase 5 approved decision 1: model-not-found means the configured
        # model is unavailable and must be skipped for the next eligible model.
        assert exc_info.value.retryable is True
    
    @patch('app.services.gemini_service.genai.Client')
    def test_content_blocked_error(self, mock_client_class):
        """Test content blocked error normalization."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.side_effect = Exception("content_blocked safety")
        
        # Create service and attempt interaction
        service = GeminiService(api_key="test-api-key")
        
        with pytest.raises(GeminiError) as exc_info:
            service.create_interaction(
                question="Test question",
                video_uri="gs://test-bucket/test.mp4",
            )
        
        # Verify error
        assert exc_info.value.category == GeminiErrorCategory.CONTENT_BLOCKED
        assert exc_info.value.retryable is False
    
    @patch('app.services.gemini_service.genai.Client')
    def test_timeout_error(self, mock_client_class):
        """Test timeout error normalization."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.side_effect = Exception("timeout")
        
        # Create service and attempt interaction
        service = GeminiService(api_key="test-api-key")
        
        with pytest.raises(GeminiError) as exc_info:
            service.create_interaction(
                question="Test question",
                video_uri="gs://test-bucket/test.mp4",
            )
        
        # Verify error
        assert exc_info.value.category == GeminiErrorCategory.TIMEOUT
        assert exc_info.value.retryable is True
    
    @patch('app.services.gemini_service.genai.Client')
    def test_unknown_error(self, mock_client_class):
        """Test unknown error normalization."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.side_effect = Exception("something unexpected")
        
        # Create service and attempt interaction
        service = GeminiService(api_key="test-api-key")
        
        with pytest.raises(GeminiError) as exc_info:
            service.create_interaction(
                question="Test question",
                video_uri="gs://test-bucket/test.mp4",
            )
        
        # Verify error
        assert exc_info.value.category == GeminiErrorCategory.UNKNOWN
        # Phase 5 approved decision 3: unknown errors receive at most one
        # bounded retry, so they are classified retryable (bounded by the
        # router's attempt budget).
        assert exc_info.value.retryable is True


class TestGeminiServiceFileOperations:
    """Test Gemini service file operations."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_upload_file(self, mock_client_class):
        """Test file upload."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.files.upload.return_value = MockFile()
        
        # Create service and upload file
        service = GeminiService(api_key="test-api-key")
        result = service.upload_file("/path/to/video.mp4")
        
        # Verify
        assert result['uri'] == "gs://test-bucket/test-video.mp4"
        assert result['name'] == "files/test-video"
        assert result['mime_type'] == "video/mp4"
        assert result['state'] == "ACTIVE"
    
    @patch('app.services.gemini_service.genai.Client')
    def test_get_file(self, mock_client_class):
        """Test file retrieval."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.files.get.return_value = MockFile()
        
        # Create service and get file
        service = GeminiService(api_key="test-api-key")
        result = service.get_file("files/test-video")
        
        # Verify
        assert result['uri'] == "gs://test-bucket/test-video.mp4"
        assert result['name'] == "files/test-video"
        assert result['mime_type'] == "video/mp4"
        assert result['state'] == "ACTIVE"


class TestGeminiServiceInputBuilding:
    """Test Gemini service input content building."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_build_input_content_with_agentic(self, mock_client_class):
        """Test input content building with agentic processing."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        service = GeminiService(api_key="test-api-key")
        input_content = service._build_input_content(
            question="Test question",
            video_uri="gs://test-bucket/test.mp4",
            video_mime_type="video/mp4",
            agentic=True,
        )
        
        # Verify
        assert len(input_content) == 2
        assert input_content[0]['processing'] == 'agentic'
    
    @patch('app.services.gemini_service.genai.Client')
    def test_build_input_content_without_agentic(self, mock_client_class):
        """Test input content building without agentic processing."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        service = GeminiService(api_key="test-api-key")
        input_content = service._build_input_content(
            question="Test question",
            video_uri="gs://test-bucket/test.mp4",
            video_mime_type="video/mp4",
            agentic=False,
        )
        
        # Verify
        assert len(input_content) == 2
        assert 'processing' not in input_content[0]


class TestGeminiServiceResponseNormalization:
    """Test Gemini service response normalization."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_normalize_response(self, mock_client_class):
        """Test response normalization."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        service = GeminiService(api_key="test-api-key")
        mock_interaction = MockInteraction()
        
        answer = service._normalize_response(mock_interaction, "gemini-3.8-flash")
        
        # Verify
        assert isinstance(answer, GeminiAnswer)
        assert answer.text == "Test response"
        assert answer.interaction_id == "test-interaction-123"
        assert answer.model == "gemini-3.8-flash"
        assert answer.raw_metadata is not None
        assert answer.raw_metadata['status'] == "completed"


class TestGeminiServiceErrorNormalization:
    """Test Gemini service error normalization."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_normalize_error(self, mock_client_class):
        """Test error normalization."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        service = GeminiService(api_key="test-api-key")
        
        # Test different error types.
        # retryable reflects the Phase 5 approved fallback decision matrix:
        # model_not_found skips to the next model; unknown gets at most one
        # bounded retry.
        test_cases = [
            ("authentication failed", GeminiErrorCategory.AUTHENTICATION, False),
            ("permission denied", GeminiErrorCategory.PERMISSION_DENIED, False),
            ("model_not_found", GeminiErrorCategory.MODEL_NOT_FOUND, True),
            ("rate limit exceeded 429", GeminiErrorCategory.RATE_LIMITED, True),
            ("content blocked", GeminiErrorCategory.CONTENT_BLOCKED, False),
            ("timeout", GeminiErrorCategory.TIMEOUT, True),
            ("invalid request", GeminiErrorCategory.INVALID_REQUEST, False),
            ("network error", GeminiErrorCategory.NETWORK_ERROR, True),
            ("something unexpected", GeminiErrorCategory.UNKNOWN, True),
        ]
        
        for error_msg, expected_category, expected_retryable in test_cases:
            error = Exception(error_msg)
            normalized = service._normalize_error(error)
            
            assert normalized.category == expected_category
            assert normalized.retryable == expected_retryable
            assert normalized.raw_error is error


class TestSDKErrorNormalization:
    """Deterministic classification of machine-readable SDK exceptions.

    Phase 5 decision: classify from structured status/code fields, and never
    treat a resource 404 as model unavailability.
    """

    def _service(self) -> GeminiService:
        return GeminiService(api_key="test-api-key")

    def test_model_404_classified_as_model_not_found(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            404,
            {"status": "MODEL_NOT_FOUND", "message": "Model gemini-x was not found."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.MODEL_NOT_FOUND
        assert normalized.retryable is True

    def test_resource_404_classified_as_not_found(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            404,
            {"status": "NOT_FOUND", "message": "File not found."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.NOT_FOUND
        assert normalized.retryable is False

    def test_404_without_status_defaults_to_resource_not_found(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(404, {"message": "not found"})
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.NOT_FOUND
        assert normalized.retryable is False

    def test_rate_limit_429_structured(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            429,
            {"status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.RATE_LIMITED
        assert normalized.retryable is True

    def test_authentication_401_structured(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            401,
            {"status": "UNAUTHENTICATED", "message": "API key not valid."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.AUTHENTICATION
        assert normalized.retryable is False

    def test_permission_403_structured(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            403,
            {"status": "PERMISSION_DENIED", "message": "Permission denied."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.PERMISSION_DENIED
        assert normalized.retryable is False

    def test_invalid_request_400_structured(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            400,
            {"status": "INVALID_ARGUMENT", "message": "Bad request."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.INVALID_REQUEST
        assert normalized.retryable is False

    def test_content_blocked_status_structured(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ClientError(
            400,
            {"status": "content_blocked", "message": "Blocked by policy."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.CONTENT_BLOCKED
        assert normalized.retryable is False

    def test_server_5xx_classified_as_server_error(self):
        from google.genai import errors as genai_errors

        error = genai_errors.ServerError(
            503,
            {"status": "UNAVAILABLE", "message": "Service unavailable."},
        )
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.SERVER_ERROR
        assert normalized.retryable is True

    def test_http_timeout_classified_as_timeout(self):
        import httpx

        error = httpx.ReadTimeout("The read operation timed out")
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.TIMEOUT
        assert normalized.retryable is True

    def test_connection_error_classified_as_network_error(self):
        import httpx

        error = httpx.ConnectError("Connection refused")
        normalized = self._service()._normalize_error(error)
        assert normalized.category == GeminiErrorCategory.NETWORK_ERROR
        assert normalized.retryable is True

    def test_already_normalized_error_returned_unchanged(self):
        original = GeminiError(
            category=GeminiErrorCategory.CONTENT_BLOCKED,
            message="Content was blocked by safety filters.",
            retryable=False,
        )
        normalized = self._service()._normalize_error(original)
        assert normalized is original


class TestGeminiServiceSDKWiring:
    """Wiring of approved SDK configuration (Phase 5 decisions 7 and 10)."""

    @patch('app.services.gemini_service.genai.Client')
    def test_client_timeout_matches_configured_seconds(
        self, mock_client_class, monkeypatch
    ):
        """GEMINI_TIMEOUT_SECONDS reaches the verified HttpOptions.timeout (ms)."""
        from app.core.config import settings as app_settings

        monkeypatch.setattr(app_settings, "GEMINI_TIMEOUT_SECONDS", 45)

        GeminiService(api_key="test-api-key")

        client_kwargs = mock_client_class.call_args.kwargs
        assert client_kwargs["http_options"].timeout == 45_000

    @patch('app.services.gemini_service.genai.Client')
    def test_interactions_create_enables_store(self, mock_client_class):
        """store=True is sent so previous_interaction_id continuation works."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()

        service = GeminiService(api_key="test-api-key")
        service.create_interaction(
            question="What are the main points?",
            video_uri="gs://test-bucket/test.mp4",
            previous_interaction_id="ix-previous",
        )

        call_kwargs = mock_client.interactions.create.call_args.kwargs
        assert call_kwargs["store"] is True
        assert call_kwargs["previous_interaction_id"] == "ix-previous"
        assert call_kwargs["model"] == "gemini-3.8-flash"


class TestGeminiServiceAgenticVideoProcessing:
    """Test Gemini service agentic video processing."""
    
    @patch('app.services.gemini_service.genai.Client')
    def test_agentic_processing_requested(self, mock_client_class):
        """Test that agentic processing is correctly requested."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        service = GeminiService(api_key="test-api-key")
        service.create_interaction(
            question="What are the main points?",
            video_uri="gs://test-bucket/test.mp4",
            agentic=True,
        )
        
        # Verify agentic processing was requested
        call_args = mock_client.interactions.create.call_args
        input_content = call_args.kwargs['input']
        video_input = input_content[0]
        
        assert video_input['type'] == 'video'
        assert video_input['processing'] == 'agentic'
    
    @patch('app.services.gemini_service.genai.Client')
    def test_youtube_url_support(self, mock_client_class):
        """Test YouTube URL support."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.interactions.create.return_value = MockInteraction()
        
        service = GeminiService(api_key="test-api-key")
        service.create_interaction(
            question="Summarize this video",
            video_uri="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            agentic=True,
        )
        
        # Verify YouTube URL was passed correctly
        call_args = mock_client.interactions.create.call_args
        input_content = call_args.kwargs['input']
        video_input = input_content[0]
        
        assert video_input['type'] == 'video'
        assert video_input['uri'] == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        assert video_input['processing'] == 'agentic'