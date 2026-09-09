# Video AI Assistant — Testing Strategy

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Goals

Tests must prove application behavior without making the full suite dependent on Gemini API availability or paid usage.

## 2. Test Layers

### Unit

Test:

- URL validation;
- upload validation;
- error classification;
- router decisions;
- session state;
- conversation context reconstruction.

### API

Test FastAPI endpoints with mocked Gemini services.

### Integration

Use a small number of opt-in live Gemini tests.

Live tests must never be required for normal CI.

### Frontend

Test:

- upload interaction;
- URL validation;
- loading states;
- chat rendering;
- error rendering;
- timestamp display.

## 3. Mandatory Router Tests

### Test 1 — Model A succeeds

Expected:

```text
A called once
B not called
success returned
```

### Test 2 — Model A rate-limits, B succeeds

Expected:

```text
A called
429 classified retryable
B called
B answer returned
```

### Test 3 — Model A non-fallback error

Example: invalid request.

Expected:

```text
A called
B not called
mapped error returned
```

### Test 4 — All models fail

Expected:

```text
all eligible models attempted
single user-friendly final error
```

### Test 5 — Authentication failure

Expected:

```text
no model rotation
configuration error
```

### Test 6 — Timeout

Expected:

```text
bounded retry/fallback
no infinite loop
```

## 4. Video Tests

Test:

- valid video accepted;
- invalid extension rejected;
- oversized upload rejected;
- empty file rejected;
- YouTube URL accepted;
- malformed URL rejected;
- unsupported URL host rejected.

## 5. Session Tests

Test:

- session created;
- session retrieved;
- missing session returns 404;
- expired Gemini file state is handled;
- session deleted.

## 6. Conversation Tests

Test:

- first question creates interaction;
- interaction ID is saved;
- same-model follow-up uses previous interaction ID;
- fallback stores new active model;
- fallback creates safe new interaction state;
- messages are persisted in order.

## 7. Gemini Adapter Tests

Mock the SDK.

Verify:

- model ID passed correctly;
- video URI passed correctly;
- `processing="agentic"` passed;
- question passed correctly;
- previous interaction ID passed only where intended;
- exceptions normalized.

## 8. No Real API in Standard Tests

Do not make unit tests depend on:

- API quota;
- internet;
- active Gemini credentials;
- live YouTube availability.

## 9. Optional Live Test

Provide an explicit command such as:

```bash
pytest -m live
```

Live tests require:

```env
GEMINI_API_KEY=...
```

They should use a small, known test video and remain opt-in.

## 10. Test Matrix

| Scenario | Expected |
|---|---|
| valid upload | session ready |
| invalid file | 415/400 |
| oversized file | 413 |
| valid YouTube URL | session ready |
| invalid YouTube URL | 422 |
| first question | answer |
| follow-up | answer with context |
| Model A success | no fallback |
| Model A 429 | Model B attempted |
| Model A 403 | no fallback |
| all models fail | clear error |
| session missing | 404 |
| expired video | clear re-upload message |
| frontend API failure | visible retry state |

## 11. Regression Requirement

Whenever Gemini SDK integration changes, run:

```text
unit tests
API tests
router tests
mocked Gemini adapter tests
```

before considering the change complete.
