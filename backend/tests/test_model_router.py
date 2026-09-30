"""Tests for the model router (Phase 5 Checkpoint B).

All tests are deterministic and use fake Gemini services — no live API calls
(docs/12-testing.md §3, §8).
"""

import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.models import VideoSession, SessionStatus
from app.services.conversation import ConversationService
from app.services.gemini_service import GeminiAnswer, GeminiError, GeminiErrorCategory
from app.services.model_router import ModelRouter


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
MODEL_A = "model-a"
MODEL_B = "model-b"
MODEL_C = "model-c"


def make_answer(model: str, interaction_id: str = "ix-default") -> GeminiAnswer:
    return GeminiAnswer(
        text=f"answer-from-{model}",
        interaction_id=interaction_id,
        model=model,
    )


def make_error(category: GeminiErrorCategory, retryable: bool = True) -> GeminiError:
    return GeminiError(
        category=category,
        message=f"normalized {category.value}",
        retryable=retryable,
    )


class FakeGeminiService:
    """Fake Gemini service capturing calls and replaying scripted responses.

    responses maps a model id to either a result (GeminiAnswer), an exception,
    or a list of either (later entries repeat once the list is exhausted).
    """

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def create_interaction(self, **kwargs):
        self.calls.append(kwargs)
        model = kwargs["model"]
        if model not in self.responses:
            raise AssertionError(f"Unexpected model call: {model}")
        scripted = self.responses[model]
        if isinstance(scripted, list):
            result = scripted.pop(0) if len(scripted) > 1 else scripted[0]
        else:
            result = scripted
        if isinstance(result, Exception):
            raise result
        return result

    @property
    def models_called(self):
        return [call["model"] for call in self.calls]


def make_session(
    active_model=None,
    previous_interaction_id=None,
    source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
) -> VideoSession:
    return VideoSession(
        source_type="youtube",
        source_url=source_url,
        status=SessionStatus.READY,
        active_model=active_model,
        previous_interaction_id=previous_interaction_id,
    )


def make_router(service, models=None, attempts=None, retries=None) -> ModelRouter:
    return ModelRouter(
        gemini_service=service,
        models=models if models is not None else [MODEL_A, MODEL_B, MODEL_C],
        max_fallback_attempts=attempts,
        retries_per_model=retries,
    )


# ----------------------------------------------------------------------
# 1–3, 6: fallback behavior
# ----------------------------------------------------------------------
class TestFallbackBehavior:
    def test_first_configured_model_succeeds_and_no_other_model_called(self):
        fake = FakeGeminiService({MODEL_A: make_answer(MODEL_A)})
        router = make_router(fake)

        answer = router.answer(session=make_session(), question="What is this?")

        assert answer.model == MODEL_A
        assert fake.models_called == [MODEL_A]

    def test_rate_limit_falls_back_to_next_model(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.RATE_LIMITED),
            MODEL_B: make_answer(MODEL_B, "ix-b"),
        })
        router = make_router(fake)

        answer = router.answer(session=make_session(), question="What is this?")

        assert answer.model == MODEL_B
        assert fake.models_called == [MODEL_A, MODEL_B]

    def test_transient_server_error_falls_back_to_next_model(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.SERVER_ERROR),
            MODEL_B: make_answer(MODEL_B, "ix-b"),
        })
        router = make_router(fake)

        answer = router.answer(session=make_session(), question="What is this?")

        assert answer.model == MODEL_B
        assert fake.models_called == [MODEL_A, MODEL_B]

    def test_all_rate_limited_models_fail_with_quota_specific_error(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.RATE_LIMITED),
            MODEL_B: make_error(GeminiErrorCategory.RATE_LIMITED),
            MODEL_C: make_error(GeminiErrorCategory.RATE_LIMITED),
        })
        router = make_router(fake)

        with pytest.raises(GeminiError) as exc_info:
            router.answer(session=make_session(), question="What is this?")

        # Quota-specific classification is preserved (decision 5).
        assert exc_info.value.category == GeminiErrorCategory.RATE_LIMITED
        assert exc_info.value.retryable is True
        # Every eligible model was attempted exactly once.
        assert fake.models_called == [MODEL_A, MODEL_B, MODEL_C]
        # User-safe message: no raw exception detail.
        assert "capacity" in exc_info.value.message.lower()

    def test_all_models_failing_returns_deterministic_user_safe_error(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.NETWORK_ERROR),
            MODEL_B: make_error(GeminiErrorCategory.SERVER_ERROR),
            MODEL_C: make_error(GeminiErrorCategory.NETWORK_ERROR),
        })
        router = make_router(fake)

        with pytest.raises(GeminiError) as exc_info:
            router.answer(session=make_session(), question="What is this?")

        assert exc_info.value.category == GeminiErrorCategory.SERVICE_UNAVAILABLE
        assert exc_info.value.retryable is True
        assert "temporarily unavailable" in exc_info.value.message.lower()
        # No raw provider/exception details leak into the user-facing message.
        assert "Exception" not in exc_info.value.message

    def test_unknown_error_gets_one_bounded_retry_then_falls_back(self):
        """Decision 3: unknown errors get at most one bounded retry, never
        infinite — then rotation to the next configured model."""
        fake = FakeGeminiService({
            MODEL_A: [
                make_error(GeminiErrorCategory.UNKNOWN),
                make_error(GeminiErrorCategory.UNKNOWN),
            ],
            MODEL_B: make_answer(MODEL_B, "ix-b"),
            MODEL_C: make_answer(MODEL_C),
        })
        router = make_router(fake, attempts=4)

        answer = router.answer(session=make_session(), question="What is this?")

        assert answer.model == MODEL_B
        assert fake.models_called == [MODEL_A, MODEL_A, MODEL_B]


# ----------------------------------------------------------------------
# 4–5: non-retryable errors stop immediately
# ----------------------------------------------------------------------
class TestNonRetryableErrorsStop:
    @pytest.mark.parametrize(
        "category",
        [
            GeminiErrorCategory.AUTHENTICATION,
            GeminiErrorCategory.PERMISSION_DENIED,
            GeminiErrorCategory.INVALID_REQUEST,
            GeminiErrorCategory.CONTENT_BLOCKED,
        ],
    )
    def test_stop_categories_do_not_rotate_models(self, category):
        fake = FakeGeminiService({
            MODEL_A: make_error(category, retryable=False),
            MODEL_B: make_answer(MODEL_B),
            MODEL_C: make_answer(MODEL_C),
        })
        router = make_router(fake)

        with pytest.raises(GeminiError) as exc_info:
            router.answer(session=make_session(), question="What is this?")

        assert exc_info.value.category == category
        assert fake.models_called == [MODEL_A]


# ----------------------------------------------------------------------
# 9–10: model not found vs resource not found
# ----------------------------------------------------------------------
class TestNotFoundClassification:
    def test_model_not_found_skips_to_next_model(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.MODEL_NOT_FOUND, retryable=True),
            MODEL_B: make_answer(MODEL_B, "ix-b"),
        })
        router = make_router(fake)

        answer = router.answer(session=make_session(), question="What is this?")

        assert answer.model == MODEL_B
        # No same-model retry: model-not-found skips directly to the next model.
        assert fake.models_called == [MODEL_A, MODEL_B]

    def test_resource_not_found_does_not_trigger_model_rotation(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.NOT_FOUND, retryable=False),
            MODEL_B: make_answer(MODEL_B),
            MODEL_C: make_answer(MODEL_C),
        })
        router = make_router(fake)

        with pytest.raises(GeminiError) as exc_info:
            router.answer(session=make_session(), question="What is this?")

        assert exc_info.value.category == GeminiErrorCategory.NOT_FOUND
        assert fake.models_called == [MODEL_A]


# ----------------------------------------------------------------------
# 7: total call budget, including same-model retries
# ----------------------------------------------------------------------
class TestAttemptBudget:
    def test_budget_counts_same_model_retries(self):
        # budget = min(attempts, len(models)) = min(4, 3) = 3
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.TIMEOUT),
            MODEL_B: make_error(GeminiErrorCategory.TIMEOUT),
            MODEL_C: make_error(GeminiErrorCategory.TIMEOUT),
        })
        router = make_router(fake, attempts=4)

        with pytest.raises(GeminiError):
            router.answer(session=make_session(), question="What is this?")

        # A's same-model retry consumed budget: A, A-retry, B = 3 total calls.
        assert len(fake.calls) == 3
        assert fake.models_called == [MODEL_A, MODEL_A, MODEL_B]

    def test_budget_is_min_of_configured_attempts_and_model_count(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.RATE_LIMITED),
            MODEL_B: make_error(GeminiErrorCategory.RATE_LIMITED),
            MODEL_C: make_error(GeminiErrorCategory.RATE_LIMITED),
        })
        router = make_router(fake, attempts=2)

        with pytest.raises(GeminiError):
            router.answer(session=make_session(), question="What is this?")

        assert len(fake.calls) == 2
        assert fake.models_called == [MODEL_A, MODEL_B]

    def test_retries_per_model_cap_is_respected(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.TIMEOUT),
            MODEL_B: make_answer(MODEL_B, "ix-b"),
            MODEL_C: make_answer(MODEL_C),
        })
        router = make_router(fake, attempts=4, retries=0)

        answer = router.answer(session=make_session(), question="What is this?")

        # No same-model retries allowed: straight to the next model.
        assert answer.model == MODEL_B
        assert fake.models_called == [MODEL_A, MODEL_B]


# ----------------------------------------------------------------------
# 8: sticky model ordering
# ----------------------------------------------------------------------
class TestStickyModelOrdering:
    def test_active_model_is_attempted_first(self):
        fake = FakeGeminiService({MODEL_B: make_answer(MODEL_B, "ix-b")})
        router = make_router(fake)

        answer = router.answer(
            session=make_session(active_model=MODEL_B),
            question="What is this?",
        )

        assert answer.model == MODEL_B
        assert fake.models_called == [MODEL_B]

    def test_fallback_order_keeps_configured_priority_for_remaining_models(self):
        fake = FakeGeminiService({
            MODEL_B: make_error(GeminiErrorCategory.RATE_LIMITED),
            MODEL_A: make_answer(MODEL_A, "ix-a"),
            MODEL_C: make_answer(MODEL_C),
        })
        router = make_router(fake)

        answer = router.answer(
            session=make_session(active_model=MODEL_B),
            question="What is this?",
        )

        assert answer.model == MODEL_A
        # Sticky first, then remaining configured order: B, A, C.
        assert fake.models_called == [MODEL_B, MODEL_A]

    def test_unconfigured_active_model_is_ignored(self):
        fake = FakeGeminiService({MODEL_A: make_answer(MODEL_A, "ix-a")})
        router = make_router(fake)

        router.answer(
            session=make_session(active_model="unknown-model"),
            question="What is this?",
        )

        assert fake.models_called == [MODEL_A]


# ----------------------------------------------------------------------
# 11–12: conversation continuation across models
# ----------------------------------------------------------------------
class TestContinuation:
    def test_same_model_continuation_preserves_interaction_id(self):
        fake = FakeGeminiService({MODEL_A: make_answer(MODEL_A, "ix-new")})
        router = make_router(fake)
        session = make_session(
            active_model=MODEL_A,
            previous_interaction_id="ix-previous",
        )

        answer = router.answer(
            session=session,
            question="What happens next?",
            conversation_context="User: first question\nAssistant: first answer",
        )

        assert answer.model == MODEL_A
        call = fake.calls[0]
        assert call["previous_interaction_id"] == "ix-previous"
        assert call["model"] == MODEL_A
        # Same-model continuation must not resend reconstructed history.
        assert call["question"] == "What happens next?"

    def test_model_switch_starts_fresh_interaction_with_bounded_history(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.SERVER_ERROR),
            MODEL_B: make_answer(MODEL_B, "ix-b"),
        })
        router = make_router(fake)
        session = make_session(
            active_model=MODEL_A,
            previous_interaction_id="ix-old-model",
        )
        context = "User: first question\nAssistant: first answer"

        answer = router.answer(
            session=session,
            question="What happens next?",
            conversation_context=context,
        )

        assert answer.model == MODEL_B
        first, second = fake.calls

        # Attempt on the old model may use its own continuation state.
        assert first["model"] == MODEL_A
        assert first["previous_interaction_id"] == "ix-old-model"

        # Fresh interaction on the new model: no old interaction ID,
        # video input re-provided, bounded persisted history included,
        # and the current question appears exactly once.
        assert second["model"] == MODEL_B
        assert second["previous_interaction_id"] is None
        assert second["video_uri"] == session.source_url
        assert context in second["question"]
        assert second["question"].count("What happens next?") == 1
        assert second["question"].endswith("Current user question: What happens next?")

    def test_first_question_has_no_context_and_no_interaction_id(self):
        fake = FakeGeminiService({MODEL_A: make_answer(MODEL_A, "ix-1")})
        router = make_router(fake)

        router.answer(
            session=make_session(),
            question="What is this video about?",
            conversation_context="",
        )

        call = fake.calls[0]
        assert call["previous_interaction_id"] is None
        assert call["question"] == "What is this video about?"
        assert call["video_uri"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


# ----------------------------------------------------------------------
# 13: bounded timeout handling
# ----------------------------------------------------------------------
class TestTimeoutHandling:
    def test_timeout_retry_is_bounded_and_eventually_falls_back(self):
        fake = FakeGeminiService({
            MODEL_A: [
                make_error(GeminiErrorCategory.TIMEOUT),
                make_answer(MODEL_A, "ix-a"),
            ],
            MODEL_B: make_answer(MODEL_B),
        })
        router = make_router(fake, attempts=4)

        answer = router.answer(session=make_session(), question="What is this?")

        assert answer.model == MODEL_A
        # One bounded same-model retry, no infinite loop.
        assert fake.models_called == [MODEL_A, MODEL_A]

    def test_persistent_timeouts_respect_the_call_budget(self):
        fake = FakeGeminiService({
            MODEL_A: make_error(GeminiErrorCategory.TIMEOUT),
            MODEL_B: make_error(GeminiErrorCategory.TIMEOUT),
            MODEL_C: make_error(GeminiErrorCategory.TIMEOUT),
        })
        router = make_router(fake, attempts=4)

        with pytest.raises(GeminiError) as exc_info:
            router.answer(session=make_session(), question="What is this?")

        assert exc_info.value.category == GeminiErrorCategory.SERVICE_UNAVAILABLE
        # budget = min(4, 3) = 3: A, A-retry, B — never unbounded.
        assert len(fake.calls) == 3


# ----------------------------------------------------------------------
# 14–16: conversation-service integration (state updates & persistence)
# ----------------------------------------------------------------------
@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="ready_session")
def ready_session_fixture(session):
    video_session = VideoSession(
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status=SessionStatus.READY,
        active_model="gemini-3.8-flash",
        previous_interaction_id="ix-old-model",
    )
    session.add(video_session)
    session.commit()
    session.refresh(video_session)
    return video_session


class TestConversationStateUpdates:
    def test_successful_fallback_updates_active_model_and_interaction_id(
        self, session, ready_session
    ):
        fake = FakeGeminiService({
            "gemini-3.8-flash": make_error(GeminiErrorCategory.RATE_LIMITED),
            "gemini-3.7-flash": make_answer("gemini-3.7-flash", "ix-new-model"),
            "gemini-3.6-flash": make_answer("gemini-3.6-flash"),
            "gemini-3.5-flash-lite": make_answer("gemini-3.5-flash-lite"),
        })
        service = ConversationService(session, gemini_service=fake)

        answer = service.ask(ready_session.id, "What is this video about?")

        assert answer.model == "gemini-3.7-flash"
        updated = session.get(VideoSession, ready_session.id)
        assert updated.active_model == "gemini-3.7-flash"
        assert updated.previous_interaction_id == "ix-new-model"

        history = service.get_message_history(ready_session.id)
        assert len(history) == 2
        assert history[1].role == "assistant"
        assert history[1].model == "gemini-3.7-flash"
        assert history[1].interaction_id == "ix-new-model"

    def test_success_without_interaction_id_clears_stale_state(
        self, session, ready_session
    ):
        fake = FakeGeminiService({
            "gemini-3.8-flash": make_error(GeminiErrorCategory.RATE_LIMITED),
            "gemini-3.7-flash": make_answer("gemini-3.7-flash", interaction_id=None),
            "gemini-3.6-flash": make_answer("gemini-3.6-flash"),
            "gemini-3.5-flash-lite": make_answer("gemini-3.5-flash-lite"),
        })
        service = ConversationService(session, gemini_service=fake)

        answer = service.ask(ready_session.id, "What is this video about?")

        assert answer.model == "gemini-3.7-flash"
        updated = session.get(VideoSession, ready_session.id)
        assert updated.active_model == "gemini-3.7-flash"
        # Stale interaction ID from the previous model must not survive.
        assert updated.previous_interaction_id is None

    def test_failure_leaves_state_unchanged_and_persists_no_messages(
        self, session, ready_session
    ):
        fake = FakeGeminiService({
            "gemini-3.8-flash": make_error(GeminiErrorCategory.RATE_LIMITED),
            "gemini-3.7-flash": make_error(GeminiErrorCategory.RATE_LIMITED),
            "gemini-3.6-flash": make_error(GeminiErrorCategory.RATE_LIMITED),
            "gemini-3.5-flash-lite": make_error(GeminiErrorCategory.RATE_LIMITED),
        })
        service = ConversationService(session, gemini_service=fake)

        with pytest.raises(GeminiError):
            service.ask(ready_session.id, "What is this video about?")

        updated = session.get(VideoSession, ready_session.id)
        assert updated.active_model == "gemini-3.8-flash"
        assert updated.previous_interaction_id == "ix-old-model"
        # Decision 6: the failed question and no fake assistant answer are saved.
        assert service.get_message_history(ready_session.id) == []

    def test_context_is_truncated_to_configured_message_bound(
        self, session, ready_session, monkeypatch
    ):
        """Reconstructed history respects CONVERSATION_CONTEXT_MAX_MESSAGES."""
        from app.core.config import settings as app_settings

        monkeypatch.setattr(app_settings, "CONVERSATION_CONTEXT_MAX_MESSAGES", 4)
        service = ConversationService(
            session, gemini_service=FakeGeminiService({})
        )

        for index in range(6):
            service.create_user_message(ready_session.id, f"old question {index}")
        service.create_user_message(ready_session.id, "newest question")

        context = service._build_conversation_context(ready_session.id)
        lines = context.splitlines()

        # 7 persisted messages, bound of 4 => only the last 4 are included.
        assert len(lines) == 4
        assert "old question 2" not in context
        assert "old question 0" not in context
        assert lines[-1] == "User: newest question"
        # The current question is not persisted yet, so it never appears here.
        assert context.count("newest question") == 1


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
class TestRouterConfiguration:
    def test_default_max_model_attempts_is_bounded_by_model_count(self):
        from app.core.config import Settings

        settings = Settings(
            GEMINI_MODELS="model-a,model-b,model-c",
            GEMINI_MAX_FALLBACK_ATTEMPTS=4,
        )
        assert settings.max_model_attempts == 3

    def test_max_model_attempts_uses_configured_attempts_when_smaller(self):
        from app.core.config import Settings

        settings = Settings(
            GEMINI_MODELS="model-a,model-b",
            GEMINI_MAX_FALLBACK_ATTEMPTS=1,
        )
        assert settings.max_model_attempts == 1

    def test_defaults_exist_for_retry_and_context_settings(self):
        from app.core.config import Settings

        settings = Settings()
        assert settings.GEMINI_MAX_RETRIES_PER_MODEL == 1
        assert settings.CONVERSATION_CONTEXT_MAX_MESSAGES == 20

    def test_shared_budget_formula_clamps_and_handles_empty_model_list(self):
        from app.core.config import resolve_max_model_attempts

        # Single-source formula used by both Settings and ModelRouter.
        assert resolve_max_model_attempts(4, 3) == 3
        assert resolve_max_model_attempts(2, 5) == 2
        assert resolve_max_model_attempts(0, 3) == 1
        assert resolve_max_model_attempts(4, 0) == 4
        assert resolve_max_model_attempts(None, 3) == 1
