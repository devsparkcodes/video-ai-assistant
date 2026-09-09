# Video AI Assistant — Security

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. API Key Protection

The Gemini API key must remain server-side.

Correct:

```text
Browser -> FastAPI -> Gemini
```

Incorrect:

```text
Browser -> Gemini
```

The frontend must never receive `GEMINI_API_KEY`.

## 2. Environment Variables

Use:

```env
GEMINI_API_KEY=...
DATABASE_URL=sqlite:///./video_ai_assistant.db
GEMINI_MODELS=gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite
```

Never commit `.env`.

`.gitignore` must include:

```gitignore
.env
.env.*
!.env.example
*.db
__pycache__/
```

## 3. `.env.example`

Commit an example:

```env
GEMINI_API_KEY=
DATABASE_URL=sqlite:///./video_ai_assistant.db
GEMINI_MODELS=gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite
GEMINI_TIMEOUT_SECONDS=120
GEMINI_MAX_FALLBACK_ATTEMPTS=4
MAX_UPLOAD_SIZE_MB=500
CORS_ORIGINS=http://localhost:5173
```

The example must contain no real secret.

## 4. File Validation

Validate:

- extension;
- MIME type;
- file size;
- filename;
- content where practical.

Never use the original filename as a server filesystem path.

Use generated temporary names.

## 5. Upload Limits

The application should impose its own conservative upload limit.

Do not rely solely on the maximum limit advertised by Gemini.

This protects:

- bandwidth;
- RAM;
- disk;
- request processing;
- denial-of-service exposure.

## 6. URL Validation

For YouTube:

- require `https`;
- accept only known YouTube hostnames;
- normalize common YouTube URL forms;
- reject credentials/userinfo in URL;
- reject local/private-network URLs.

Do not fetch arbitrary URLs from the backend in MVP.

## 7. SSRF

Because the MVP accepts only YouTube URLs, the backend should not implement generic URL fetching.

This reduces server-side request forgery risk.

If arbitrary remote video URLs are added later, a dedicated SSRF-safe fetch policy is required.

## 8. CORS

Allow only known frontend origins.

Development example:

```text
http://localhost:5173
```

Do not use:

```text
allow_origins=["*"]
```

with credentialed requests in production.

## 9. Application Rate Limiting

Gemini's rate limits do not protect the FastAPI server from application abuse.

A production deployment should add an application-level rate limit if the endpoint is publicly reachable.

MVP local development does not need a complex distributed limiter.

## 10. Logging

Never log:

- API keys;
- authorization headers;
- cookies;
- raw video content;
- full sensitive prompts if unnecessary.

Prefer:

```text
request_id
session_id
model
status
latency
error_category
```

## 11. Privacy

The application must not claim that user videos are private in a stronger sense than Google's current Gemini API terms permit.

Google's current terms distinguish Paid Services from free use regarding use of prompts/responses to improve products. Review the current terms before public deployment.

[Gemini API Terms](https://ai.google.dev/gemini-api/terms)

## 12. Gemini Interaction Storage

The Interactions API stores interaction objects by default when `store=true`.

Current documentation states:

- Paid tier: 55 days by default;
- Free tier: 1 day by default.

`store=false` disables server-side interaction storage but prevents later use of `previous_interaction_id`.

[Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)

The product must choose storage behavior deliberately based on its privacy requirements.

## 13. Terms and Deployment Eligibility

The current Gemini API Additional Terms state that API users must be 18 or older and that API Clients must not be directed to or likely accessed by individuals under 18. They also state that Gemini API/AI Studio use is for developers building with Google AI models for professional or business purposes, not consumer use.

Therefore:

- local development/testing is allowed only when the developer/user satisfies the current terms;
- the MVP must not be positioned as a general consumer or minor-facing service;
- public deployment requires an explicit eligibility/access review before release;
- the deployment team must re-check the current terms before launch;
- safety controls must not be bypassed, and the application must not attempt to reverse engineer or replicate Google's provider technology.

[Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)

## 14. No Quota Bypass

The application must use one configured Google API project/key for MVP.

Never implement:

- rotating Google accounts;
- rotating API keys to evade project limits;
- automated credential creation;
- quota laundering.

Gemini rate limits are applied per project, not per API key. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 15. Dependency Security

Pin or constrain production dependencies.

Regularly update:

- FastAPI;
- Pydantic;
- SQLModel/SQLAlchemy;
- google-genai;
- frontend dependencies.

Run dependency vulnerability checks before production deployment.
