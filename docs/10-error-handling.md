# Video AI Assistant — Error Handling

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Principles

1. Errors are classified centrally.
2. User messages are simple.
3. Backend logs contain diagnostic detail.
4. Secrets are never logged.
5. Fallback is selective.
6. Invalid requests are not repeatedly retried.

## 2. Error Categories

| Category | Example | Fallback? | User behavior |
|---|---|---:|---|
| Invalid input | bad video/URL | No | Correct input |
| Unsupported media | unsupported format | No | Choose supported media |
| Upload failure | network/API upload error | Usually retry once | Retry |
| Rate limit | 429 | Sometimes | Try eligible model / later |
| Daily quota | Project/model RPD exhausted | Only if another model is legitimately still available; never for project-wide exhaustion | Try later |
| Auth/permission | 401 authentication or 403 permission_denied | No | Operator must fix configuration |
| Not found | 404 not_found | No | Recreate/re-upload session |
| Model unavailable | 404 model_not_found | Yes, skip this model | Try next eligible model |
| Timeout | request timeout | Yes, bounded | Retry/fallback |
| Server error | 5xx | Yes, bounded | Retry/fallback |
| Safety rejection | blocked content | No | Explain request cannot be processed |
| Unknown | unexpected | One bounded retry at most | Generic error |

Google's current Interactions API error guide documents machine-readable codes including `authentication` (401), `permission_denied` (403), `not_found`/`model_not_found` (404), `rate_limit_exceeded` (429), and `content_blocked`. [API errors](https://ai.google.dev/gemini-api/docs/api-errors)

## 3. Invalid Video

Backend:

- validate before Gemini;
- return `VIDEO_INVALID`.

Frontend:

> This video could not be processed. Please choose another supported video.

No model fallback.

## 4. Unsupported Format

Return:

```json
{
  "error": {
    "code": "UNSUPPORTED_VIDEO",
    "message": "This video format is not supported.",
    "retryable": false
  }
}
```

## 5. File Too Large

Return HTTP `413`.

Do not upload a file known to exceed the application's configured limit.

The application limit may be lower than Gemini's documented maximum.

## 6. Upload Failure

If the upload fails because of a transient network/provider issue:

- retry once;
- if still failing, return a temporary upload error.

Do not retry indefinitely.

## 7. Rate Limit

Gemini uses `429 RESOURCE_EXHAUSTED` for rate-limit and quota-related conditions.

The router may attempt another configured eligible model only when the failure is plausibly model-specific or otherwise retryable. A project-wide quota exhaustion is terminal for the request.

If all models fail:

> The video service is currently at capacity. Please try again later.

[Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 8. Daily Quota Exhaustion

The application must not attempt to bypass daily quota.

If the relevant quota cannot be served:

> Today's video-processing limit has been reached. Please try again after the quota resets.

Google states that RPD quotas reset at midnight Pacific Time. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 9. Authentication

A credential/configuration failure (`authentication`/401 or relevant `permission_denied`/403) should produce an operator-oriented log and a generic user response:

> The video service is not configured correctly. Please contact the administrator.

Never reveal the API key or provider credential details.

## 10. Timeout

Use a configured request timeout.

On timeout:

1. classify as retryable;
2. retry once or move to the next model;
3. stop after the router's attempt limit.

For long-running interactions, Google recommends streaming for long/complex video requests and also supports background execution through the Interactions API. The MVP may start synchronously, but the implementation must surface a timeout state and should move to streaming/background execution if real-world latency makes synchronous requests unreliable. [Background execution](https://ai.google.dev/gemini-api/docs/background-execution)

## 11. Safety/Content Rejection

Do not bypass a safety rejection by changing models.

Return a neutral message explaining that the request cannot be processed.

Do not expose internal safety classifier details.

## 12. Unknown Error

Log:

```text
request_id
session_id
model
exception type
provider status if available
latency
```

Return:

> Something went wrong while analyzing the video. Please try again.

## 13. Error Mapping

Internal error codes should be stable:

```text
INVALID_VIDEO
UNSUPPORTED_VIDEO
VIDEO_TOO_LARGE
INVALID_YOUTUBE_URL
VIDEO_EXPIRED
SESSION_NOT_FOUND
GEMINI_AUTH_ERROR
GEMINI_RATE_LIMITED
GEMINI_QUOTA_EXHAUSTED
GEMINI_TIMEOUT
GEMINI_UNAVAILABLE
GEMINI_SAFETY_REJECTED
GEMINI_INVALID_REQUEST
INTERNAL_ERROR
```

## 14. Observability

Every request should have a correlation/request ID.

Fallback logs should explicitly record:

```text
fallback_started
from_model
to_model
reason_category
```

Never log API keys or raw video data.
