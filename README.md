# Video AI Assistant

Video AI Assistant is a simple web application that lets a user upload a video or provide a public YouTube URL and ask natural-language questions about the video.

The application delegates video understanding to Google's **Gemini Agentic Video Understanding** capability rather than building its own frame extraction, transcription, embedding, or video-retrieval pipeline.

> **Deployment eligibility:** The current Gemini API Additional Terms require API users to be 18+ and state that API Clients must not be directed to or likely accessed by individuals under 18. They also describe Gemini API/AI Studio use as intended for professional or business use, not consumer use. Treat this as a release gate and re-check the current terms before public deployment. [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)

## Main Features

- Video upload
- Public YouTube URL input
- Video sessions
- Natural-language questions
- Follow-up questions
- Conversation history
- Gemini agentic video understanding
- Configurable Gemini model fallback
- Timestamp references when provided by Gemini
- User-friendly errors
- Server-side Gemini API key protection

## Architecture

```text
User
  |
  v
Frontend
  |
  v
FastAPI
  |
  +--> Video Session Service --> Gemini File API
  |
  +--> Conversation Service --> SQLite
  |
  +--> Model Router --> Gemini Interactions API
                              |
                              v
                     Agentic Video Understanding
```

The detailed architecture is in [`docs/02-architecture.md`](docs/02-architecture.md).

## Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLModel or SQLAlchemy
- SQLite
- official `google-genai` SDK

### Frontend

- React
- TypeScript
- Vite

### Gemini

The current default model is:

```text
gemini-3.8-flash
```

Current documented agentic-video fallback candidates are:

```text
gemini-3.8-flash
gemini-3.7-flash
gemini-3.6-flash
gemini-3.5-flash-lite
```

The model list is configuration, not hard-coded application policy.

See [`docs/03-gemini-integration.md`](docs/03-gemini-integration.md) and [`docs/04-model-router.md`](docs/04-model-router.md).

## Repository Structure

```text
video-ai-assistant/
├── backend/
├── frontend/
├── docs/
│   ├── 00-project-overview.md
│   ├── 01-requirements.md
│   ├── 02-architecture.md
│   ├── 03-gemini-integration.md
│   ├── 04-model-router.md
│   ├── 05-video-processing.md
│   ├── 06-conversation-system.md
│   ├── 07-api-design.md
│   ├── 08-database.md
│   ├── 09-frontend.md
│   ├── 10-error-handling.md
│   ├── 11-security.md
│   ├── 12-testing.md
│   └── 13-development-roadmap.md
├── .env.example
├── .gitignore
└── README.md
```

## Local Development

### 1. Clone the repository

```bash
git clone <repository-url>
cd video-ai-assistant
```

### 2. Create Python environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```powershell
pip install -r backend/requirements.txt
```

The final dependency list must include the official `google-genai` SDK and the chosen FastAPI/database dependencies.

### 4. Configure environment

Copy:

```text
.env.example
```

to:

```text
.env
```

Set:

```env
GEMINI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./video_ai_assistant.db
GEMINI_MODELS=gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite
GEMINI_TIMEOUT_SECONDS=120
GEMINI_MAX_FALLBACK_ATTEMPTS=4
MAX_UPLOAD_SIZE_MB=500
CORS_ORIGINS=http://localhost:5173
```

Never commit `.env`.

## Run Backend

The final implementation should expose a standard FastAPI entry point.

Example:

```powershell
uvicorn backend.app.main:app --reload
```

The exact module path may be adjusted during implementation, but it must remain consistent with the repository structure.

## Run Frontend

From the frontend directory:

```powershell
npm install
npm run dev
```

The development frontend should communicate with the FastAPI backend.

## Gemini Configuration

The backend uses:

1. Gemini File API for uploaded videos where appropriate.
2. Gemini Interactions API for question/answer interactions.
3. Agentic video processing.
4. A configurable model router.

Current official sources:

- [Gemini Video Understanding](https://ai.google.dev/gemini-api/docs/video-understanding)
- [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)
- [Gemini File API](https://ai.google.dev/gemini-api/docs/files)
- [Gemini Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API Terms](https://ai.google.dev/gemini-api/terms)

## Documentation Index

Read these before implementation:

1. [`docs/00-project-overview.md`](docs/00-project-overview.md)
2. [`docs/01-requirements.md`](docs/01-requirements.md)
3. [`docs/02-architecture.md`](docs/02-architecture.md)
4. [`docs/03-gemini-integration.md`](docs/03-gemini-integration.md)
5. [`docs/04-model-router.md`](docs/04-model-router.md)
6. [`docs/05-video-processing.md`](docs/05-video-processing.md)
7. [`docs/06-conversation-system.md`](docs/06-conversation-system.md)
8. [`docs/07-api-design.md`](docs/07-api-design.md)
9. [`docs/08-database.md`](docs/08-database.md)
10. [`docs/09-frontend.md`](docs/09-frontend.md)
11. [`docs/10-error-handling.md`](docs/10-error-handling.md)
12. [`docs/11-security.md`](docs/11-security.md)
13. [`docs/12-testing.md`](docs/12-testing.md)
14. [`docs/13-development-roadmap.md`](docs/13-development-roadmap.md)

## Current Project Status

**Documentation / architecture:** Complete  
**Application implementation:** Not started by this documentation task

This repository intentionally does not include application implementation code as part of the documentation phase.

## Source of Truth

### Documentation is the Source of Truth.

When implementing the project:

1. Read the relevant documentation first.
2. Follow documented architecture.
3. Do not invent new architecture without justification.
4. Do not replace Gemini-native functionality with custom implementations unnecessarily.
5. If code and documentation disagree, documentation wins until explicitly updated.
6. If a requirement is ambiguous, identify the ambiguity rather than silently inventing behavior.
7. If Google changes API behavior, update the relevant documentation before changing the implementation.
8. Keep documentation and implementation synchronized.

## OpenCode / AI Coding Agent Workflow

OpenCode should:

1. Read `README.md`.
2. Read the relevant files under `docs/`.
3. Identify the exact requirements for the requested task.
4. Check the architecture before changing code.
5. Implement only the requested scope.
6. Run relevant tests.
7. Report what changed.
8. Report assumptions and unresolved ambiguities.
9. If implementation exposes a documentation problem, identify it instead of silently redesigning the system.
10. Update documentation only when the architecture/requirements are intentionally changed.

### AI Coding Agent Rules

```text
DOCUMENTATION IS THE SOURCE OF TRUTH.

Before coding:
- Read README.md.
- Read the relevant docs/*.md.
- Verify Gemini-specific behavior against official Google documentation.

While coding:
- Follow the documented architecture.
- Keep Gemini behind a service/interface.
- Do not invent Gemini parameters.
- Keep model routing configurable.
- Do not expose GEMINI_API_KEY to the frontend.
- Do not add FFmpeg, Whisper, vector DB, RAG, custom frame extraction, or custom video retrieval unless a documented requirement proves Gemini-native capability insufficient.
- Do not create multiple Google accounts or API keys to bypass quotas.
- Keep the MVP simple.
- Make Gemini calls mockable.

After coding:
- Run tests.
- Check the implementation against the relevant documentation.
- Report changes and assumptions.
- If code conflicts with documentation, stop and identify the conflict.
```

## Important API Note

Gemini's API evolves quickly. Before implementing or changing Gemini integration, verify current official documentation, especially:

- supported models;
- agentic processing parameters;
- video input methods;
- File API retention;
- Interactions API state behavior;
- rate limits;
- pricing;
- terms.

Official documentation wins over this repository when the provider changes, but this repository must then be updated before implementation proceeds.
