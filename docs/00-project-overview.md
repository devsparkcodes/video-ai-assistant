# Video AI Assistant — Project Overview

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09  
**Primary external authority:** Google Gemini API documentation

## 1. Purpose

Video AI Assistant is a web application that lets a non-technical user upload a video or provide a supported video URL, then ask natural-language questions about that video.

The application delegates video understanding to Google's Gemini API and its **agentic video understanding** capability. The application is an interaction layer, not a replacement video-analysis engine.

Gemini's current video-understanding documentation states that Gemini can answer questions about video content and refer to specific timestamps. Agentic processing dynamically explores a video's timeline instead of requiring the application to extract frames itself. Supported agentic models currently include Gemini 3.8 Flash, 3.7 Flash, 3.6 Flash, and 3.5 Flash-Lite. [Google Video Understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

## 2. Problem

Video analysis is technically difficult for non-technical users. They should not need to understand:

- video frame extraction
- FPS
- speech-to-text pipelines
- embeddings
- vector databases
- RAG
- FFmpeg
- model-specific tokenization
- Gemini request formats

The application hides those details behind a simple upload/URL + chat experience.

## 3. Target Users

The product experience is designed for non-technical **adult users in professional or business contexts** who want to ask questions about existing videos without learning an AI/video-processing API.

This audience restriction is intentional. Google's current Gemini API Additional Terms state that users must be 18 or older and that Gemini API/AI Studio use is for developers building with Google AI models for professional or business purposes, not consumer use. The application must therefore not be positioned as a general consumer/minor-facing product while using the Gemini Developer API. [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)

Examples:

- adult students/professional learners asking questions about lectures
- users reviewing tutorials
- users finding moments in long videos
- users asking for summaries or explanations
- developers testing Gemini video understanding through a simple UI

## 4. Main User Experience

1. Open the application.
2. Upload a video **or provide a public YouTube URL**.
3. The backend creates a video session.
4. The video is made available to Gemini using an appropriate official input method.
5. The user asks a natural-language question.
6. The backend sends the question and video context to Gemini using agentic video processing.
7. The response is shown in the chat.
8. Timestamp references are displayed when Gemini provides them.
9. The user continues asking follow-up questions.

The application should feel like "chat with this video", not like a developer console.

## 5. Core Features

- Local video upload.
- Public YouTube URL input.
- Video/session creation.
- Natural-language questions.
- Follow-up questions.
- Conversation history.
- Agentic video understanding.
- Configurable Gemini model router.
- Automatic fallback for retryable/model-availability failures.
- User-friendly processing and error states.
- Optional timestamp links/labels when the Gemini response identifies a time.
- Server-side Gemini API key handling.

## 6. Non-Goals

The MVP does **not** build:

- a custom video-understanding model
- FFmpeg-based frame extraction
- Whisper-based transcription
- forced audio/video alignment
- a custom embedding pipeline
- a vector database
- a custom RAG pipeline
- a custom visual search engine
- multiple Google accounts/API keys for quota bypass
- microservices
- billing/subscription infrastructure
- user authentication unless later required
- a custom quota-bypass mechanism

Gemini already provides native video understanding, including timeline-aware analysis in agentic mode. Duplicating those capabilities would add complexity without improving the MVP.

## 7. Core Technology

### Backend

- Python
- FastAPI
- Pydantic
- SQLModel or SQLAlchemy
- SQLite for initial development

### Frontend

A simple modern single-page frontend. React + TypeScript + Vite is the recommended default because it is lightweight, common, and suitable for a chat interface.

### AI

- Official Google Gemini API
- Official `google-genai` SDK
- Gemini Interactions API
- Agentic video processing
- Configurable model router

The Interactions API is currently recommended by Google for new projects and supports server-side conversation state through `previous_interaction_id`. [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

## 8. Architectural Principles

1. **Gemini-native first.** If Gemini provides a capability natively, use it.
2. **Thin application layer.** The application coordinates input, sessions, persistence, errors, and UI.
3. **Gemini isolation.** Gemini-specific code stays behind a service/interface.
4. **Configurable routing.** Model IDs and priority are configuration, not scattered constants.
5. **One Google project/API key for MVP.** The router is for reliability, not quota circumvention.
6. **No undocumented behavior.** Google documentation is authoritative.
7. **Small MVP.** Do not add infrastructure until a concrete requirement exists.
8. **Documentation-first development.** This repository's documentation is the implementation Source of Truth.

## 9. MVP Scope

The MVP is complete when a user can:

- upload a supported video;
- or provide a public YouTube URL;
- create a session;
- ask questions;
- receive Gemini answers;
- continue with follow-up questions;
- see conversation history;
- receive clear errors;
- experience automatic model fallback where configured;
- never see the Gemini API key.

The MVP should use the Gemini File API for uploaded files where appropriate. Google recommends the File API for large/reusable files; standard uploaded files are temporary and currently stored for 48 hours. [File API](https://ai.google.dev/gemini-api/docs/files)

## 10. Future Scope

Potential later additions:

- authentication
- persistent user accounts
- cloud object storage
- richer timestamp navigation
- export conversations
- multiple video sessions per user
- usage analytics
- production database
- configurable organization-level model policies
- direct public video URL support if officially documented for the required video workflow
- advanced access controls

These are not MVP requirements.

## 11. Important Current API Facts

As of 2026-09-09:

- Agentic video processing is supported by Gemini 3.8 Flash, 3.7 Flash, 3.6 Flash, and 3.5 Flash-Lite according to Google's current video-understanding documentation.
- Agentic processing is requested with `processing: "agentic"` through the Interactions API.
- The Generate Content API equivalent is `media_processing: "AGENTIC"`.
- Public YouTube videos are a documented video input method.
- Standard File API uploads are stored for 48 hours. For video input limits, use the current Video Understanding documentation for the selected service tier; do not infer an input limit from project storage capacity alone.
- Gemini API rate limits are project-scoped, not API-key-scoped.
- RPD quotas reset at midnight Pacific Time.
- Current Gemini API terms require API users to be 18+ and restrict API Clients from being directed to or likely accessed by people under 18; they also describe the Gemini API as intended for professional/business use rather than consumer use.
- The exact active limits depend on model and usage tier and should be read from Google AI Studio rather than hard-coded in this project.

Sources:
- [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)
- [File input methods](https://ai.google.dev/gemini-api/docs/file-input-methods)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [Gemini API Terms](https://ai.google.dev/gemini-api/terms)

## 12. Source-of-Truth Policy

### Documentation is the Source of Truth.

When implementing the project:

1. Read the relevant documentation first.
2. Follow the documented architecture.
3. Do not invent new architecture without justification.
4. Do not replace Gemini-native functionality with custom implementations unnecessarily.
5. If code and documentation disagree, documentation wins until explicitly updated.
6. If a requirement is ambiguous, identify the ambiguity rather than silently inventing behavior.
7. If Google changes an API behavior, update the relevant documentation before changing the implementation.
8. Keep documentation and implementation synchronized.

## 13. AI Coding Agent Rules

OpenCode must:

- read `README.md` before implementation;
- read the relevant `docs/*.md` files before changing code;
- implement only the requested scope;
- preserve documented interfaces and architecture;
- never invent Gemini parameters;
- verify current Gemini behavior against official documentation when making Gemini-specific changes;
- use mocks for unit tests instead of requiring live Gemini calls;
- run relevant tests after changes;
- report assumptions and unresolved ambiguities;
- update documentation when an intentional architecture change is approved;
- never introduce FFmpeg, Whisper, vector search, RAG, or custom frame processing unless a documented requirement proves Gemini-native processing insufficient;
- never add Google accounts/API keys to bypass quotas.

OpenCode should treat the documentation as the contract for implementation.
