# Video AI Assistant — Model Router

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Purpose

The model router exists for **reliability and maintainability**, not quota circumvention.

It keeps model selection in one place and allows the application to recover when a configured eligible model is temporarily unavailable.

## 2. Default Model Configuration

Recommended initial order:

```text
1. gemini-3.8-flash
2. gemini-3.7-flash
3. gemini-3.6-flash
4. gemini-3.5-flash-lite
```

This list is configuration, not permanent architecture.

Only models currently documented by Google as supporting agentic video understanding may be placed in this list. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

Example configuration:

```env
GEMINI_MODELS=gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite
GEMINI_MAX_FALLBACK_ATTEMPTS=4
GEMINI_TIMEOUT_SECONDS=120
```

## 3. Routing Algorithm

```text
request
  |
  v
load configured models
  |
  v
for each model in priority order:
    attempt request
    |
    +-- success --> return answer
    |
    +-- retryable --> record failure and continue
    |
    +-- non-retryable --> return mapped error
    |
all exhausted
  |
  v
return service-unavailable/quota error
```

## 4. Error Classification

### Retry/fallback candidates

Fallback may occur for:

- temporary `429 RESOURCE_EXHAUSTED`;
- transient 5xx server errors;
- documented temporary service-unavailable conditions;
- model-specific temporary unavailability;
- `model_not_found` for a configured model that is no longer available, in which case the router may skip that model and try the next configured eligible model;
- timeout where the underlying request may reasonably be retried.

The router should avoid immediate repeated retries that amplify load.

### Do NOT fallback

Do not blindly fallback for:

- invalid API key;
- permission denied caused by project configuration;
- malformed video input;
- unsupported video format;
- invalid URL;
- a configuration error affecting the entire request or router; a single `model_not_found` should instead be treated as a per-model fallback condition;
- safety/content rejection;
- invalid request schema;
- missing required resource caused by application state.

Changing models does not fix these conditions in a reliable way.

Google documents machine-readable Interactions API error codes including `authentication` (401), `permission_denied` (403), `model_not_found` (404), `rate_limit_exceeded` (429), and `content_blocked`. The router should classify these codes rather than relying on exception text. [API errors](https://ai.google.dev/gemini-api/docs/api-errors)

## 5. Rate-Limit Behavior

A `429` means one or more rate/quota/spend limits may have been exceeded.

Because Gemini limits are project-scoped, switching from Model A to Model B does not guarantee additional project capacity. The router may try another eligible model only as a reliability mechanism where the model-specific limit makes that meaningful.

The router must never claim that fallback creates new quota.

[Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 6. Daily Quota Exhaustion

If the project has exhausted an applicable RPD quota:

- do not rotate API keys;
- do not rotate Google accounts;
- do not attempt quota bypass;
- do not perform endless retries.

If another configured model legitimately remains available because its applicable model-specific limit is still available, it may be attempted according to normal routing policy. A project-wide quota exhaustion must be treated as terminal for that request; switching models is not a bypass.

Google states that RPD quotas reset at midnight Pacific Time. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 7. Authentication Failure

A `401 authentication` error caused by a missing/invalid/expired API key, or a `403 permission_denied` error caused by project/key permissions, is not a model-selection problem.

The router should stop and report an operator/configuration error.

Do not expose the credential value to the user.

## 8. Invalid Request

If the request is malformed or unsupported, stop.

Examples:

- unsupported MIME type;
- invalid YouTube URL;
- unsupported processing parameter;
- expired/missing Gemini file reference.

Trying every model would add latency without fixing the request.

## 9. Retry Policy

For retryable transient failures:

- maximum one short retry per model by default;
- then move to the next configured model;
- use exponential backoff with jitter where appropriate;
- respect `Retry-After` if the SDK/API exposes it;
- never busy-loop.

The retry count must be configurable.

## 10. Maximum Attempts

Default:

```text
maximum model attempts = number of configured models
maximum retry per model = 1
```

A future production deployment may tune this based on measured latency and quota behavior.

## 11. Sticky Model

After a successful answer, the session should retain the successful model as its `active_model`.

Follow-up questions should use that model first.

If it fails with a retryable condition, the router can fall through to the remaining eligible models.

## 12. Model Switch and Conversation State

Do not assume a Gemini `previous_interaction_id` can be transferred across model changes.

For a same-model follow-up:

```text
active_model + previous_interaction_id
```

For a model-switch fallback:

```text
new_model
+ video reference/input
+ application-managed conversation context
```

This keeps the application independent of undocumented cross-model state behavior.

## 13. Logging

For every attempt log:

```text
request_id
session_id
model
attempt_number
result: success | retryable_failure | non_retryable_failure
error_category
latency_ms
```

Never log:

- API keys;
- authorization headers;
- raw video bytes;
- unnecessary user-sensitive content.

## 14. Router Interface

Conceptual Python interface:

```python
class ModelRouter(Protocol):
    async def answer(
        self,
        *,
        session: VideoSession,
        question: str,
    ) -> GeminiAnswer:
        ...
```

The router should depend on an abstract Gemini service rather than directly on the SDK.

## 15. Router Tests

At minimum:

1. Model A succeeds.
2. Model A returns 429; Model B succeeds.
3. Model A returns 500; Model B succeeds.
4. Model A returns 403; no fallback.
5. Model A returns invalid-request error; no fallback.
6. All models fail.
7. Retry count is respected.
8. Active model updates after fallback success.
9. Conversation state is preserved correctly during same-model continuation.
10. Model switch creates a safe fresh interaction path.
