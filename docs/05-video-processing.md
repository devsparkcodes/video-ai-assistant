# Video AI Assistant — Video Processing

**Status:** MVP Source of Truth  
**Last verified:** 2026-09-09

## 1. Principle

The application does not process video frames, audio, or transcripts itself unless a later documented requirement proves Gemini's native capabilities insufficient.

Gemini's agentic video understanding dynamically navigates the video timeline and can inspect visual frames, audio, and transcripts as needed. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

## 2. Supported MVP Sources

### A. Local upload

Flow:

```text
Browser
 -> FastAPI
 -> validate file
 -> Gemini File API
 -> Gemini file URI
 -> VideoSession
```

### B. Public YouTube URL

Flow:

```text
Browser
 -> FastAPI
 -> validate YouTube URL
 -> VideoSession stores source URL
 -> Gemini interaction references URL
```

Public YouTube videos are explicitly documented as a video input method. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

## 3. Validation

The backend must validate:

- allowed MIME types;
- file size;
- filename/path safety;
- empty files;
- YouTube URL format;
- supported source type.

The application must not trust a browser-provided MIME type alone for security-sensitive validation.

## 4. File Size and Supported Formats

Google currently documents these video input options:

| Method | Current documented guidance |
|---|---|
| Inline data | under 100 MB |
| File API | 2 GB free / 20 GB paid for video use on the current Video Understanding page |
| YouTube URL | public YouTube videos |

The current documented video MIME types are:

- `video/mp4`
- `video/mpeg`
- `video/quicktime` (MOV)
- `video/avi`
- `video/x-flv`
- `video/mpg`
- `video/webm`
- `video/wmv`
- `video/3gpp`

The current Video Understanding page also documents that free-tier YouTube input is limited to 8 hours of YouTube video per day; the paid tier has no limit based on video length. Only public YouTube videos are supported by that input method. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

The separate Files API page currently describes a 2 GB per-file and 20 GB per-project storage model. Because the official pages currently present limits differently, the implementation must follow the current Video Understanding limit for the selected service tier and re-check the official documentation before production deployment. [Files API](https://ai.google.dev/gemini-api/docs/files)

Limits may change and can depend on API/model context. The official documentation must be rechecked before changing production limits.

The application's own upload limit may be set lower than Google's maximum to protect local resources.

## 5. File API Lifecycle

Standard File API uploads are stored for 48 hours and should be treated as temporary.

Therefore, a VideoSession must not assume that a stored Gemini file URI remains valid forever.

The application should represent file state explicitly:

```text
UPLOADING
PROCESSING
READY
EXPIRED
FAILED
```

When an expired file is needed, the application must require the original source to be available before attempting re-upload.

[File API](https://ai.google.dev/gemini-api/docs/files)

## 6. Processing State

Application-level states:

```text
CREATING
UPLOADING
READY
ERROR
EXPIRED
DELETED
```

The UI should show these states in plain language.

## 7. Large Videos

Agentic processing is particularly relevant to long-form video because it can dynamically inspect relevant portions rather than forcing the application to ingest a fixed frame stream.

The application should not impose artificial short-duration limits unless needed for operational safety.

Google recommends agentic mode especially for long-form videos or queries targeting specific moments. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)

## 8. Unsupported Inputs

Reject or clearly report:

- private YouTube videos;
- malformed URLs;
- unsupported file types;
- files above application limits;
- unavailable/expired Gemini file references;
- inputs rejected by Gemini.

## 9. Cleanup

MVP cleanup:

- local temporary upload files should be deleted after successful Gemini upload or failed processing;
- SQLite session records may be deleted through the session-delete endpoint;
- Gemini file deletion should only be implemented if explicitly needed and supported by the current API.

Do not create a background cleanup system in MVP unless testing shows it is necessary.

## 10. Why No FFmpeg/Whisper

The MVP does not need:

```text
video -> frames
video -> audio
audio -> Whisper
frames -> embeddings
embeddings -> vector DB
```

Google already provides video understanding, including transcript/audio/visual inspection in agentic mode.

A custom pipeline would:

- increase implementation complexity;
- increase storage and processing requirements;
- create synchronization problems;
- duplicate capabilities supplied by Gemini;
- create additional failure modes.

Therefore it is explicitly out of scope unless Gemini cannot satisfy a verified requirement.

## 11. Timestamp Handling

The application may display timestamps returned by Gemini.

It must not independently claim precise timestamp detection unless the timestamp is supported by Gemini's documented response or a clearly defined application feature.

Google documents that Gemini can refer to specific timestamps in video understanding. [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)
