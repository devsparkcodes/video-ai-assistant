"""Video validation utilities for upload and URL validation."""

import re
from typing import Tuple, Optional
from urllib.parse import urlparse

from app.core.config import settings


# Supported video MIME types based on current Gemini documentation
SUPPORTED_MIME_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/avi",
    "video/x-flv",
    "video/mpg",
    "video/webm",
    "video/wmv",
    "video/3gpp",
}

# Supported file extensions for validation
SUPPORTED_EXTENSIONS = {
    ".mp4", ".mpeg", ".mov", ".avi", ".flv", 
    ".mpg", ".webm", ".wmv", ".3gp"
}

# YouTube URL patterns
YOUTUBE_PATTERNS = [
    r"^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]{11}(?:&[\w-=]*)?$",
    r"^https?://youtu\.be/[\w-]{11}(?:\?[\w-=]*)?$",
    r"^https?://(?:www\.)?youtube\.com/embed/[\w-]{11}(?:\?[\w-=]*)?$",
    r"^https?://(?:www\.)?youtube\.com/v/[\w-]{11}(?:\?[\w-=]*)?$",
]

# YouTube host patterns
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
}


def validate_video_file(
    filename: str,
    content_type: str,
    file_size: int
) -> Tuple[bool, Optional[str]]:
    """Validate uploaded video file.
    
    Args:
        filename: Original filename
        content_type: MIME type from upload
        file_size: File size in bytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if file is empty
    if file_size == 0:
        return False, "Empty file. Please upload a valid video."
    
    # Check file size against configured limit
    max_size = settings.max_upload_size_bytes
    if file_size > max_size:
        return False, f"File is too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB."
    
    # Validate MIME type
    if content_type not in SUPPORTED_MIME_TYPES:
        return False, f"Unsupported video format. Supported formats: {', '.join(sorted(SUPPORTED_MIME_TYPES))}"
    
    # Validate file extension
    file_ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if file_ext not in SUPPORTED_EXTENSIONS:
        return False, f"Unsupported file extension. Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    
    return True, None


def validate_youtube_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate YouTube URL.
    
    Args:
        url: YouTube URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not url.strip():
        return False, "URL is required."
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format."
    
    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return False, "Invalid URL scheme. Must be http or https."
    
    # Check host
    hostname = parsed.hostname or ""
    if hostname.lower() not in YOUTUBE_HOSTS:
        return False, "Invalid YouTube URL. Only public YouTube videos are supported."
    
    # Check URL pattern
    for pattern in YOUTUBE_PATTERNS:
        if re.match(pattern, url, re.IGNORECASE):
            return True, None
    
    return False, "Invalid YouTube URL format. Please provide a valid public YouTube video URL."


def get_youtube_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL.
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID if valid, None otherwise
    """
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([\w-]{11})",
        r"(?:embed/)([\w-]{11})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None