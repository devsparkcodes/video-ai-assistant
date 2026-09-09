# Video AI Assistant — FastAPI API Design

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. API Principles

- RESTful.
- Small endpoint surface.
- Pydantic request/response models.
- Application errors normalized.
- No Gemini SDK types exposed directly.
- No API key in requests.
- Session ID is the main resource identifier.

Base path:

```text
/api/v1
```

## 2. Health Check

### `GET /api/v1/health`

Purpose: service health.

Response:

```json
{
  "status": "ok"
}
```

Status:

- `200 OK`

## 3. Create Session

### `POST /api/v1/sessions`

For uploaded videos.

Request: multipart form data.

Fields:

```text
file: UploadFile
```

Response:

```json
{
  "session_id": "uuid",
  "status": "ready",
  "source_type": "upload"
}
```

Status codes:

- `201 Created`
- `400 Bad Request` invalid input
- `413 Content Too Large`
- `415 Unsupported Media Type`
- `502 Bad Gateway` Gemini upload failure
- `503 Service Unavailable` temporary upstream problem

## 4. Create Session from YouTube URL

### `POST /api/v1/sessions/url`

Request:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Response:

```json
{
  "session_id": "uuid",
  "status": "ready",
  "source_type": "youtube"
}
```

Status:

- `201 Created`
- `400 Bad Request`
- `422 Unprocessable Entity`

## 5. Ask a Question

### `POST /api/v1/sessions/{session_id}/questions`

Request:

```json
{
  "question": "What are the main points discussed in the video?"
}
```

Response:

```json
{
  "message_id": "uuid",
  "answer": "The main points are...",
  "model": "gemini-3.8-flash",
  "timestamps": [],
  "created_at": "2026-09-08T12:00:00Z"
}
```

`timestamps` may remain empty when Gemini does not return timestamp information.

Status:

- `200 OK`
- `404 Not Found`
- `409 Conflict` session not ready/expired
- `422 Unprocessable Entity`
- `429 Too Many Requests` if the application's own API rate limit is exceeded
- `502 Bad Gateway` Gemini upstream failure
- `503 Service Unavailable` all eligible models unavailable

## 6. Get Session

### `GET /api/v1/sessions/{session_id}`

Response:

```json
{
  "session_id": "uuid",
  "status": "ready",
  "source_type": "upload",
  "active_model": "gemini-3.8-flash",
  "created_at": "2026-09-08T12:00:00Z"
}
```

Do not return secrets or raw Gemini credentials.

## 7. Get Conversation

### `GET /api/v1/sessions/{session_id}/messages`

Response:

```json
{
  "session_id": "uuid",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "What happens first?",
      "created_at": "2026-09-08T12:01:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "First...",
      "created_at": "2026-09-08T12:01:04Z"
    }
  ]
}
```

## 8. Delete Session

### `DELETE /api/v1/sessions/{session_id}`

Deletes local application data.

Response:

```json
{
  "deleted": true
}
```

Status:

- `204 No Content` is also acceptable.

Gemini resource deletion must not be assumed from this endpoint.

## 9. Pydantic Schemas

Conceptual:

```python
class YouTubeSessionCreate(BaseModel):
    url: AnyHttpUrl

class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

class TimestampRef(BaseModel):
    start_seconds: float
    label: str | None = None

class AnswerResponse(BaseModel):
    message_id: UUID
    answer: str
    model: str
    timestamps: list[TimestampRef]
    created_at: datetime
```

Exact limits are configuration decisions and should be centralized.

## 10. Error Schema

Use one stable application error format:

```json
{
  "error": {
    "code": "VIDEO_EXPIRED",
    "message": "This video session has expired. Please upload the video again.",
    "retryable": false
  }
}
```

Do not expose raw Gemini exception strings when they reveal internal details.

## 11. No Unnecessary Endpoints

Do not add separate endpoints for:

- Gemini model selection;
- frame retrieval;
- transcription;
- embeddings;
- vector search;
- token counting;
- FFmpeg jobs.

These are not MVP responsibilities.
