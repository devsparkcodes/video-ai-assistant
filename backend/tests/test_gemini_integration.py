"""Integration tests for Gemini Service.

These tests require a real Gemini API key and are marked as live tests.
Run with: pytest -m live
"""

import pytest
import os
from app.services.gemini_service import GeminiService, GeminiAnswer


@pytest.mark.live
class TestGeminiIntegration:
    """Live integration tests for Gemini service."""
    
    def test_gemini_service_initialization(self):
        """Test that Gemini service can be initialized with API key."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            pytest.skip("GEMINI_API_KEY environment variable not set")
        
        service = GeminiService(api_key=api_key)
        assert service._api_key == api_key
    
    def test_create_simple_interaction(self):
        """Test creating a simple interaction without video."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            pytest.skip("GEMINI_API_KEY environment variable not set")
        
        service = GeminiService(api_key=api_key)
        
        # Create a simple interaction
        answer = service.create_interaction(
            question="Hello, what is 2+2?",
            agentic=False,  # No video, so agentic doesn't apply
        )
        
        # Verify response
        assert isinstance(answer, GeminiAnswer)
        assert answer.text is not None
        assert len(answer.text) > 0
        assert answer.interaction_id is not None
        assert answer.model == "gemini-3.8-flash"
    
    @pytest.mark.skip(reason="Requires a test video file")
    def test_create_video_interaction(self):
        """Test creating interaction with video input."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            pytest.skip("GEMINI_API_KEY environment variable not set")
        
        # This test would require a test video file
        # For now, it's skipped
        service = GeminiService(api_key=api_key)
        
        # Would need to upload a test video first
        # file_result = service.upload_file("test_video.mp4")
        # answer = service.create_interaction(
        #     question="What is this video about?",
        #     video_uri=file_result['uri'],
        #     video_mime_type=file_result['mime_type'],
        # )
        # assert isinstance(answer, GeminiAnswer)
        # assert answer.text is not None