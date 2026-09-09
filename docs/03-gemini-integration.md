# Video AI Assistant — Gemini Integration

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Official SDK

Use Google's official Python SDK:

```text
google-genai
```

The backend owns the SDK client.

Do not expose the SDK or API key to the browser.

## 2. Authentication

Use a server-side environment variable:

```env
GEMINI_API_KEY=your_key_here
```

The frontend never receives this value.

The official Gemini API supports API-key authentication for the Gemini Developer API. Use the SDK's standard authentication mechanism rather than implementing custom credential transport.

## 3. Recommended API

Use the **Gemini Interactions API** for the MVP.

Google currently describes the Interactions API as the recommended interface for new projects and documents server-side conversation state through `previous_interaction_id`. [Interactions API overview](https://ai.google.dev/gemini-api/docs/interactions-overview)

Generate Content remains supported, but Google currently labels the original Generate Content API as legacy while recommending Interactions for new projects. The project therefore uses Interactions only for its primary Gemini integration; the Generate Content API is referenced only where Google's legacy documentation is useful for comparison or migration.

## 4. Agentic Video Processing

Agentic processing is requested on the video input.

Current documented Interactions API pattern:

```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input=[
        {
            "type": "video",
            "uri": "VIDEO_URI",
            "processing": "agentic",
        },
        {
            "type": "text",
            "text": "What are the three main points discussed in this video?",
        },
    ],
)

print(interaction.output_text)
```

The exact SDK object shapes should be checked against the installed `google-genai` version at implementation time. The `processing: "agentic"` behavior is documented by Google. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

## 5. Current Eligible Agentic Models

As of this documentation verification:

| Model | ID | Agentic video |
|---|---|---|
| Gemini 3.8 Flash | `gemini-3.8-flash` | Supported |
| Gemini 3.7 Flash | `gemini-3.7-flash` | Supported |
| Gemini 3.6 Flash | `gemini-3.6-flash` | Supported |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | Supported |

Google's current video-understanding documentation is the authority for this list. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

### Recommended default

Use:

```text
gemini-3.8-flash
```

as the preferred model. Google currently describes Gemini 3.8 Flash as its most intelligent Flash model, and the current video-understanding documentation lists it as supporting agentic video understanding. [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)

The fallback models should remain configurable.

## 6. Video Input

### Uploaded video

Use the Gemini File API for normal uploaded videos.

```python
video_file = client.files.upload(
    file=local_path,
)
```

Then reference the returned URI in the interaction.

Google recommends the File API for large/reusable media. Standard File API uploads are temporary and currently stored for 48 hours. [File API](https://ai.google.dev/gemini-api/docs/files)

### Small inline inputs

Inline data exists, but the application should not make it the default upload path.

Google currently documents inline video input as suitable for payloads under 100 MB; the File API is recommended for larger or reused media. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) [File input methods](https://ai.google.dev/gemini-api/docs/file-input-methods)

### YouTube

Public YouTube URLs are a documented video input method:

```python
{
    "type": "video",
    "uri": "https://www.youtube.com/watch?v=...",
    "processing": "agentic",
}
```

The project should validate that the URL is a supported public YouTube URL before creating a session. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

### Direct arbitrary video URLs

Do not implement arbitrary direct video URLs in the MVP based only on generic URL-context functionality. Google's URL Context documentation explicitly treats YouTube separately and does not mean every public URL is a supported video input. [URL context](https://ai.google.dev/gemini-api/docs/url-context)

If direct video URLs are added later, verify the exact current Gemini API documentation first.

## 7. Conversation State

For same-model follow-ups:

```python
next_interaction = client.interactions.create(
    model=session.active_model,
    previous_interaction_id=session.previous_interaction_id,
    input="What happened immediately after that?",
)
```

The exact SDK syntax must be verified against the installed SDK.

`previous_interaction_id` lets the server retrieve prior conversation history without resending the full chat history. [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

### Important fallback rule

Do not treat `previous_interaction_id` as a guaranteed cross-model state-transfer mechanism.

When the router changes models:

1. preserve the application's conversation history;
2. create a fresh interaction on the fallback model;
3. provide the video input again as required;
4. provide the relevant prior conversation context;
5. save the new interaction ID;
6. make the fallback model the active model for subsequent turns if successful.

This is intentionally conservative because the official documentation does not establish cross-model interaction IDs as the application's routing contract.

## 8. Response Handling

The Gemini adapter shall normalize responses into an internal structure:

```python
class GeminiAnswer:
    text: str
    interaction_id: str | None
    model: str
    raw_metadata: dict | None
```

Timestamp extraction should be conservative.

If the model returns timestamp references as structured output in a future verified API capability, the adapter may normalize them. Until then, do not invent a timestamp parser that assumes an undocumented response schema.

## 9. Errors

Relevant HTTP/API conditions include:

The current Interactions API error reference uses machine-readable error codes including:

- `authentication` / HTTP 401 — missing, invalid, or expired API key;
- `permission_denied` / HTTP 403 — the key does not have permission for the resource;
- `invalid_request` / HTTP 400 — malformed or invalid request;
- `parameter_unknown` / HTTP 400 — unsupported parameter;
- `model_not_found` / HTTP 404 — model ID is unavailable;
- `not_found` / HTTP 404 — referenced resource is unavailable;
- `rate_limit_exceeded` / HTTP 429 — per-minute/per-second request or token limit exceeded;
- `content_blocked` — policy/safety block.

The adapter must classify errors from the documented error code/status, not from free-form exception text. [API errors](https://ai.google.dev/gemini-api/docs/api-errors)

## 10. Rate Limits

Google documents:

- RPM — requests per minute;
- TPM — input tokens per minute;
- RPD — requests per day;
- spend-based limits on applicable paid tiers.

Limits are applied **per project, not per API key**.

RPD quotas reset at **midnight Pacific Time**.

Exact limits vary by model and usage tier and are visible in Google AI Studio. The application must not hard-code a universal RPM/RPD number. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 11. Quota/Fallback Policy

Fallback may improve reliability when one eligible model temporarily fails.

Fallback must never be used to:

- rotate Google accounts;
- rotate API keys;
- evade project limits;
- evade policy controls;
- create artificial quota capacity.

If all eligible models are unavailable, return a clear error.

## 12. Pricing

Pricing changes over time.

As of the verification date, Gemini 3.8 Flash has introductory standard pricing of $0.75 per 1M input tokens and $3.75 per 1M output tokens through December 31, 2026, with higher standard pricing scheduled afterward according to Google's current pricing page.

The project must not hard-code prices into application behavior.

Use the official pricing page for current values. [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)

## 13. Free vs Paid Data Handling

Google's current terms distinguish Free and Paid Services. The current terms state that for Paid Services Google does not use prompts/responses to improve products and processes them under the applicable data processing terms. Free-tier behavior and data handling are different.

The application must not promise a stronger privacy guarantee than Google's current terms.

Users should be informed appropriately if the deployment uses free-tier services.

Sources:
- [Gemini API Terms](https://ai.google.dev/gemini-api/terms)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)

## 14. Terms and Eligibility

The current Gemini API Additional Terms are a deployment requirement, not merely a legal footnote. They currently state:

- API users must be 18 or older.
- API Clients must not be directed to or likely accessed by individuals under 18.
- Gemini API/AI Studio use is for developers building with Google AI models for professional or business purposes, not consumer use.
- Applications must not bypass Google's safety protections or attempt to reverse engineer/replicate provider technology.

Therefore, a general public consumer/minor-facing deployment is **not an approved MVP deployment target under the current Gemini Developer API terms**. The project may be developed and tested locally, but the deployment plan must establish an eligible professional/business audience and access policy before release. Re-check the current terms immediately before deployment. [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)

## 15. Long-Running Requests

Agentic video processing can take longer than short text requests, especially for long or complex videos. Google's current guidance recommends streaming for long/complex requests and documents background execution through the Interactions API. The MVP may start with a synchronous interaction path, but the implementation must use a sufficiently long upstream timeout and must surface a clear timeout/error state. If measured requests regularly exceed the synchronous connection budget, adopt streaming or background execution as the first performance improvement rather than adding a custom video-processing pipeline. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

## 16. API Change Policy

Gemini-specific behavior is volatile.

Whenever a developer changes:

- model IDs;
- processing parameters;
- interaction state handling;
- video input format;
- File API behavior;
- error classification;
- pricing assumptions;

the developer must re-check Google's official documentation and update this document first if the documented contract changes.
