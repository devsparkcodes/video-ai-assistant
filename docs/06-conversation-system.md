# Video AI Assistant — Conversation System

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Concept

A **VideoSession** represents the user's application-level "chat with this video" workspace.

It connects:

```text
Video source
+
application conversation
+
Gemini interaction state
+
active model
```

## 2. Session IDs

The application creates its own opaque `session_id`.

Do not expose database primary-key assumptions to the frontend.

Example:

```text
session_id = UUID
```

## 3. Message Model

Each visible message contains:

```text
id
session_id
role
content
created_at
model
interaction_id (optional)
```

Roles:

- `user`
- `assistant`
- optionally `system` internally, but system messages should not be exposed as ordinary chat messages.

## 4. Same-Model Conversation

The Interactions API supports:

```text
previous_interaction_id
```

for continuing a conversation without resending the complete history.

Example conceptual flow:

```text
Question 1
 -> Interaction A
 -> save interaction_id=A

Question 2
 -> previous_interaction_id=A
 -> Interaction B
 -> save interaction_id=B
```

[Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

## 5. Model Fallback

A fallback can occur when the current model fails.

Do not assume:

```text
Interaction A from Model A
 -> previous_interaction_id=A
 -> Model B
```

is a supported cross-model contract.

Instead:

```text
Model A fails
 -> router selects Model B
 -> create fresh interaction on B
 -> include video input
 -> include application-managed conversation context
 -> save B's interaction ID
```

This is safer and keeps routing behavior explicit.

## 6. Conversation Context During Fallback

The application database is the authoritative record of visible conversation history.

For fallback, the backend may reconstruct a bounded text history:

```text
User: ...
Assistant: ...
User: ...
Assistant: ...
Current user question: ...
```

The implementation must impose a context-size policy.

Do not send unlimited history forever.

A future optimization may use a summarization mechanism, but that is not required for MVP.

## 7. Video Reuse

The application should reuse the same Gemini File URI for multiple requests while it remains valid.

For YouTube sessions, reuse the source URL.

Do not upload the same local video again for every question.

## 8. Session Expiration

Because standard Gemini File API uploads are stored for 48 hours, application sessions referencing such files must be treated as potentially expirable.

The local session can remain in SQLite, but the video source may no longer be usable.

The UI should report:

> This video's Gemini file has expired. Please upload the video again.

## 9. Persistence

SQLite stores:

- session;
- video metadata;
- visible messages;
- active model;
- previous interaction ID;
- Gemini file URI where necessary;
- timestamps/status.

Gemini stores its own interaction state when `store=true`.

The application should not copy Gemini's internal execution trace into SQLite.

## 10. Interaction Retention

Current Gemini Interactions API documentation states:

- Paid tier: interactions retained for 55 days by default;
- Free tier: interactions retained for 1 day by default;
- `store=false` disables server-side storage but also prevents using `previous_interaction_id` for later turns.

These values are subject to API changes and must be verified before deployment. [Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

## 11. Example Conversation

```text
User:
What is this lecture mainly about?

Assistant:
The lecture explains how HTTP requests move through a web application...

User:
What happens after the request reaches the API server?

Assistant:
The server validates the request and then passes it to...

User:
At what point does authentication happen?

Assistant:
Authentication is discussed around 18:42.
```

The final timestamp should only be shown if Gemini provides it or the application has a verified mechanism for deriving it.

## 12. Conversation Service Interface

Conceptual:

```python
class ConversationService(Protocol):
    async def ask(
        self,
        session_id: UUID,
        question: str,
    ) -> GeminiAnswer:
        ...

    async def get_history(
        self,
        session_id: UUID,
    ) -> list[Message]:
        ...
```
