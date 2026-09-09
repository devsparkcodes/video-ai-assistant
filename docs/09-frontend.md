# Video AI Assistant — Frontend UX

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Goal

The frontend should make the product feel like a simple "chat with a video" application.

Recommended stack:

- React
- TypeScript
- Vite

Do not add a large UI framework unless it clearly reduces implementation effort.

## 2. Main Screen

The primary screen contains:

1. Application title.
2. Upload video control.
3. YouTube URL field.
4. Session/video area.
5. Chat area.
6. Question input.
7. Loading/error status.

## 3. Initial State

Show two obvious options:

```text
Upload a video
or
Paste a YouTube link
```

Do not expose Gemini terminology.

Avoid labels such as:

- "Upload to File API"
- "Set media_processing"
- "Choose model"
- "Configure FPS"

## 4. Video Preview

For uploaded videos, display the browser-local preview if feasible.

For YouTube, use a normal YouTube preview/embed only if the URL and deployment policy allow it.

Video preview is a UI convenience. Gemini remains the source of understanding.

## 5. Chat

Messages:

```text
User message
Assistant answer
```

Assistant responses may contain timestamp references.

Example:

```text
At 12:34, the speaker begins explaining dependency injection.
[12:34]
```

The frontend should not invent timestamps.

## 6. Loading States

Show human-readable states:

```text
Uploading video...
Preparing your video...
Ready. Ask a question.
Analyzing the video...
Preparing your answer...
```

Do not expose provider implementation details unless useful for a technical admin UI later.

## 7. Error States

Examples:

### Invalid file

> This video format is not supported. Please choose another video.

### Expired session

> This video session has expired. Please upload the video again.

### Temporary service issue

> Gemini is temporarily unavailable. We're trying another supported model.

### Quota

> The video service has reached its current usage limit. Please try again later.

Do not say "Model A got 429" to normal users.

## 8. Conversation History

Show the current session's messages in chronological order.

MVP does not need:

- search;
- folders;
- favorites;
- multi-user history.

## 9. Accessibility

Minimum requirements:

- keyboard-accessible controls;
- visible focus states;
- labels for upload/URL fields;
- readable error messages;
- sufficient contrast;
- no status communicated only by color.

## 10. API Client

The frontend should have a small API client module:

```text
src/api/
    sessions.ts
    questions.ts
```

Do not put raw `fetch()` calls throughout components.

## 11. State

A simple session state is sufficient:

```text
no_session
creating
ready
asking
error
```

A global state library is unnecessary for MVP unless the implementation actually needs one.

## 12. Security

The frontend must never contain:

```text
GEMINI_API_KEY
```

or call the Gemini API directly.

All Gemini communication goes through FastAPI.
