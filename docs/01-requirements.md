# Video AI Assistant — Requirements

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Functional Requirements

### FR-01 — Video Upload

The system shall allow a user to select and upload a supported video file.

The backend shall validate:

- file presence;
- MIME type;
- configured application upload limit;
- basic file integrity.

The application shall reject unsupported input before making a Gemini request.

The MVP shall use the Gemini File API as the normal upload path for videos that are large enough or reused across requests. Google's current Video Understanding documentation lists the File API input maximum as **20 GB on paid tier / 2 GB on free tier**. The separate Files API page currently describes **up to 20 GB of project storage and a 2 GB per-file maximum**. Because Google's pages currently present these limits differently, implementation must use the current Video Understanding limit for the actual service tier and re-check both official pages before production deployment. Do not hard-code an input limit that contradicts the current API documentation. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) [Files API](https://ai.google.dev/gemini-api/docs/files)

### FR-02 — Video URL Input

The MVP shall accept public YouTube URLs.

The backend shall:

- validate URL syntax;
- verify that the URL is a supported YouTube URL;
- reject unsupported/private/restricted URLs with a clear message.

The application shall not claim that arbitrary direct video URLs are supported unless the current official Gemini video documentation explicitly supports the required workflow.

### FR-03 — Video Session Creation

Creating a video session shall produce an application-level `session_id`.

A session shall contain enough metadata to associate:

- the source;
- Gemini file/URI information when applicable;
- the active model;
- conversation messages;
- Gemini interaction state when used.

### FR-04 — Ask a Question

A user shall be able to submit a natural-language question against the current video session.

The backend shall send the question to Gemini using agentic video processing on an eligible configured model.

### FR-05 — Follow-Up Questions

The user shall be able to ask additional questions without re-uploading the video.

For same-model continuation, the backend may use Gemini Interactions API `previous_interaction_id`.

If the model changes because of fallback, the application shall not assume that a previous interaction ID can safely preserve state across models. The fallback path shall use application-managed conversation context and the video input to create a new interaction.

This distinction is deliberate: the official documentation confirms `previous_interaction_id` for continuing conversation state but does not make cross-model fallback semantics a project guarantee. [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

### FR-06 — Conversation History

The application shall show the current session's user and assistant messages.

The local database shall store application-visible messages. Gemini remains responsible for its own server-side interaction state when that feature is used.

### FR-07 — Agentic Video Processing

The system shall request agentic video processing rather than implementing its own video analysis pipeline.

For the Interactions API, the video input shall use `processing: "agentic"`.

Google's current documentation lists Gemini 3.8 Flash, 3.7 Flash, 3.6 Flash, and 3.5 Flash-Lite as supporting agentic video understanding. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

### FR-08 — Timestamp References

When Gemini provides timestamp information, the backend shall preserve it and the frontend shall render it clearly.

The application shall not fabricate timestamps.

If Gemini does not provide a timestamp, the UI shall not imply that an exact timestamp was calculated by the application.

### FR-09 — Model Fallback

The model router shall attempt eligible configured models in priority order.

Fallback shall occur only for configured retryable/model-availability conditions.

The router shall not create additional Google accounts or API keys.

### FR-10 — User-Friendly Status

The frontend shall show meaningful states such as:

- Uploading video
- Preparing video
- Ready for questions
- Analyzing video
- Answer ready
- Temporary service problem
- Quota temporarily unavailable
- Unsupported input
- Session expired

The UI shall not expose raw stack traces or API keys.

### FR-11 — Session Deletion

The backend should expose session deletion for local application data.

Gemini interaction/file deletion shall only be performed when the corresponding official API operation and lifecycle semantics are known and intentionally implemented.

## 2. Deployment Eligibility Requirement

The current Gemini API Additional Terms state that API users must be 18 or older and that API Clients must not be directed to or likely accessed by individuals under 18. They also state that Gemini API/AI Studio use is for developers building with Google AI models for professional or business purposes, not consumer use. Therefore, the MVP may be developed locally without authentication, but **public deployment is blocked until the deployment's audience/access controls are demonstrably compatible with the current terms**. The application must not be marketed or deployed as a general consumer/minor-facing service while using the Gemini Developer API. [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)

## 3. Non-Functional Requirements

### NFR-01 — Simplicity

The MVP shall remain understandable by a student/developer.

### NFR-02 — Reliability

Transient Gemini failures should be handled through controlled retries/fallback.

### NFR-03 — Security

The Gemini API key must never be sent to the frontend.

### NFR-04 — Maintainability

Gemini SDK calls must be isolated behind a service abstraction.

### NFR-05 — Testability

Gemini calls shall be mockable.

### NFR-06 — Performance

The application shall avoid unnecessary re-uploading of videos.

### NFR-07 — Observability

Backend logs shall record:

- request/session ID;
- model attempted;
- result category;
- duration;
- fallback event.

Logs must not contain API keys or raw sensitive video content.

### NFR-08 — Configuration

Models, timeouts, retry counts, and upload limits shall be configurable through environment/configuration rather than scattered literals.

## 4. MVP

Version 1 must contain:

1. FastAPI backend.
2. Simple web frontend.
3. Video file upload.
4. Public YouTube URL input.
5. Video session creation.
6. Gemini File API integration for uploads.
7. Gemini Interactions API integration.
8. Agentic video processing.
9. Question answering.
10. Follow-up questions.
11. Application conversation history.
12. Configurable model router.
13. Clear error handling.
14. SQLite persistence.
15. Automated tests with mocked Gemini calls.
16. Server-side API key management.
17. A documented deployment-eligibility check against the current Gemini API Additional Terms before any public release.

## 5. Explicitly Out of Scope

- User authentication.
- Payments.
- Subscriptions.
- Multi-tenant organization management.
- Multiple Google API keys/accounts.
- Quota bypass.
- FFmpeg frame extraction.
- Whisper transcription.
- Custom embeddings.
- Vector DB.
- RAG.
- Custom visual retrieval.
- Custom speech/video alignment.
- Microservices.
- Kubernetes.
- Complex background-job infrastructure unless required by measured Gemini interaction latency.
- Arbitrary direct video URL ingestion unless officially validated for the chosen API path.
- Custom model training.

## 6. Acceptance Criteria

The MVP is acceptable when a developer can demonstrate:

- a supported video upload creates a session;
- a YouTube URL creates a session;
- a question returns a Gemini answer;
- a follow-up works without re-uploading the video;
- timestamp information is displayed when returned;
- a retryable model failure causes controlled fallback;
- a non-retryable invalid request does not cause pointless fallback;
- all configured models failing produces a useful final error;
- no Gemini secret reaches the browser;
- unit/API tests run without live Gemini access.
