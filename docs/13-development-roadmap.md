# Video AI Assistant — Development Roadmap

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## Phase 0 — Documentation and Architecture

### Goal

Establish the implementation contract.

### Tasks

- read README;
- read all relevant docs;
- verify Gemini model/input behavior;
- create repository structure;
- create `.env.example`.

### Expected Result

A developer can implement without guessing core architecture.

### Definition of Done

- documentation reviewed;
- architecture approved;
- no unresolved critical contradiction.

## Phase 1 — Backend Skeleton

### Goal

Create FastAPI foundation.

### Tasks

- FastAPI application;
- settings/config;
- health endpoint;
- SQLite;
- SQLModel/SQLAlchemy models;
- error schema;
- CORS;
- basic logging.

### Dependencies

None.

### Definition of Done

- server starts locally;
- health endpoint passes;
- database initializes;
- tests run.

## Phase 2 — Gemini Integration

### Goal

Prove one successful agentic video request.

### Tasks

- install official `google-genai`;
- create Gemini service;
- implement File API upload;
- implement Interactions API request;
- configure `processing="agentic"`;
- normalize response/errors.

### Dependencies

Phase 1.

### Definition of Done

A controlled test can upload/use a supported video and receive an answer.

## Phase 3 — Video Upload and YouTube URL

### Goal

Make video sources usable through the backend.

### Tasks

- upload endpoint;
- validation;
- temporary-file handling;
- File API URI persistence;
- YouTube URL endpoint;
- session status.

### Dependencies

Phase 2.

### Definition of Done

Both source types create usable sessions.

## Phase 4 — Chat/Conversation

### Goal

Support follow-up questions.

### Tasks

- question endpoint;
- message persistence;
- previous interaction ID;
- active model tracking;
- session retrieval.

### Dependencies

Phase 3.

### Definition of Done

User can ask multiple questions against the same video.

## Phase 5 — Model Router

### Goal

Add reliability.

### Tasks

- configurable model list;
- error classification;
- bounded retry;
- fallback;
- logging;
- fallback tests.

### Dependencies

Phase 4.

### Definition of Done

Router tests prove correct fallback/non-fallback behavior.

## Phase 6 — Frontend

### Goal

Deliver the simple user experience.

### Tasks

- React/Vite setup;
- upload UI;
- YouTube URL UI;
- session status;
- chat;
- loading states;
- error states;
- timestamp rendering.

### Dependencies

Phase 3–5 backend APIs.

### Definition of Done

A non-technical user can complete the full flow without developer terminology.

## Phase 7 — Testing and Hardening

### Goal

Make the MVP reliable.

### Tasks

- complete unit tests;
- API tests;
- router tests;
- frontend tests;
- optional live Gemini test;
- security review;
- dependency review;
- documentation consistency review.

### Dependencies

All implementation phases.

### Definition of Done

CI tests pass and no known critical security issue remains.

## Phase 8 — Deployment

### Goal

Run the application outside local development.

### Tasks

- choose simple hosting;
- configure HTTPS;
- set server-side secret;
- configure CORS;
- configure upload limits;
- monitor errors;
- verify Gemini terms/region/age/use requirements.

### Dependencies

Phase 7.

### Definition of Done

Production deployment passes smoke tests and secrets are not exposed.

## Development Rule

Do not jump directly to advanced infrastructure.

If a phase can be completed with a simple implementation, choose the simple implementation.
