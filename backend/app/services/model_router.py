"""Model Router.

Selects an eligible configured Gemini model in priority order and performs
bounded fallback on retryable/model-availability failures, following
docs/04-model-router.md and docs/10-error-handling.md.

The router depends on an injectable Gemini service collaborator rather than
the SDK directly (docs/04-model-router.md §14).
"""

import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from app.core.config import resolve_max_model_attempts, settings
from app.models.video_session import VideoSession
from app.services.gemini_service import (
    GeminiAnswer,
    GeminiError,
    GeminiErrorCategory,
)

logger = logging.getLogger(__name__)


# Categories where the request itself is broken or the answer would be
# refused regardless of model: stop immediately, never rotate
# (docs/04-model-router.md §4 "Do NOT fallback").
STOP_CATEGORIES = frozenset({
    GeminiErrorCategory.AUTHENTICATION,
    GeminiErrorCategory.PERMISSION_DENIED,
    GeminiErrorCategory.INVALID_REQUEST,
    GeminiErrorCategory.CONTENT_BLOCKED,
    GeminiErrorCategory.NOT_FOUND,
})

# Categories eligible for at most one short same-model retry before moving to
# the next configured model (docs/04-model-router.md §9, docs/10-error-handling.md
# §10/§12: timeout retry once; unknown one bounded retry).
SAME_MODEL_RETRY_CATEGORIES = frozenset({
    GeminiErrorCategory.TIMEOUT,
    GeminiErrorCategory.UNKNOWN,
})

DEFAULT_MODEL = "gemini-3.8-flash"


class ModelRouter:
    """Routes a question to eligible configured models with bounded fallback."""

    def __init__(
        self,
        gemini_service: Any,
        models: Optional[Sequence[str]] = None,
        max_fallback_attempts: Optional[int] = None,
        retries_per_model: Optional[int] = None,
    ):
        """Initialize the router.

        Args:
            gemini_service: Gemini service collaborator exposing
                create_interaction(...). Injectable for tests.
            models: Eligible models in priority order. Defaults to
                settings.gemini_models_list.
            max_fallback_attempts: Configured attempt cap. Defaults to
                settings.GEMINI_MAX_FALLBACK_ATTEMPTS. The effective budget is
                min(max_fallback_attempts, number of models), including the
                initial call (Phase 5 approved decision 4).
            retries_per_model: Maximum same-model retries. Defaults to
                settings.GEMINI_MAX_RETRIES_PER_MODEL.
        """
        self.gemini_service = gemini_service
        configured = list(models) if models is not None else list(settings.gemini_models_list)
        self.models: List[str] = configured or [DEFAULT_MODEL]
        if max_fallback_attempts is None:
            max_fallback_attempts = settings.GEMINI_MAX_FALLBACK_ATTEMPTS
        self.max_fallback_attempts = max(1, int(max_fallback_attempts))
        if retries_per_model is None:
            retries_per_model = settings.GEMINI_MAX_RETRIES_PER_MODEL
        try:
            self.retries_per_model = max(0, int(retries_per_model))
        except (TypeError, ValueError):
            self.retries_per_model = 1

    # ------------------------------------------------------------------
    # Candidate ordering
    # ------------------------------------------------------------------
    def ordered_models(self, active_model: Optional[str]) -> List[str]:
        """Sticky ordering: active model first if configured, then the rest
        in configured priority order (docs/04-model-router.md §11)."""
        if active_model and active_model in self.models:
            return [active_model] + [m for m in self.models if m != active_model]
        return list(self.models)

    # ------------------------------------------------------------------
    # Question composition
    # ------------------------------------------------------------------
    @staticmethod
    def _compose_question(
        question: str,
        conversation_context: str,
        continuation_id: Optional[str],
    ) -> str:
        """Compose the text input for one attempt.

        Same-model continuation sends the raw question only (server-side
        state carries history). A fresh interaction on another model receives
        the bounded application-managed history plus the current question
        (docs/04-model-router.md §12, docs/06-conversation-system.md §6).
        The current question is never duplicated: persisted history only
        contains already-answered turns.
        """
        if continuation_id or not conversation_context:
            return question
        return f"{conversation_context}\nCurrent user question: {question}"

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def answer(
        self,
        *,
        session: VideoSession,
        question: str,
        conversation_context: str = "",
    ) -> GeminiAnswer:
        """Answer a question using eligible configured models.

        Args:
            session: The video session (supplies active_model,
                previous_interaction_id and the video reference).
            question: The user's current question.
            conversation_context: Bounded reconstructed history from persisted
                messages (used only when a fresh interaction is required).

        Returns:
            The normalized answer from the model that succeeded.

        Raises:
            GeminiError: Non-retryable upstream error, or when the attempt
                budget is exhausted.
        """
        ordered = self.ordered_models(session.active_model)
        # Shared single-source formula with Settings.max_model_attempts
        # (Phase 5 decision 4): min(configured attempts, eligible models).
        budget = resolve_max_model_attempts(self.max_fallback_attempts, len(ordered))
        video_uri = session.gemini_file_uri or session.source_url

        calls_used = 0
        failure_categories: List[GeminiErrorCategory] = []

        for index, model in enumerate(ordered):
            if calls_used >= budget:
                break

            # Only reuse server-side conversation state when it belongs to
            # the model being called (docs/04-model-router.md §12).
            continuation_id = (
                session.previous_interaction_id
                if (model == session.active_model and session.previous_interaction_id)
                else None
            )
            retries_used = 0

            while True:
                if calls_used >= budget:
                    break

                calls_used += 1
                attempt_number = calls_used
                effective_question = self._compose_question(
                    question, conversation_context, continuation_id
                )
                started = time.monotonic()

                try:
                    answer = self.gemini_service.create_interaction(
                        question=effective_question,
                        video_uri=video_uri,
                        model=model,
                        previous_interaction_id=continuation_id,
                    )
                    latency_ms = int((time.monotonic() - started) * 1000)
                    logger.info(
                        "model_router attempt result=session:%s model:%s attempt:%s "
                        "result:success latency_ms:%s",
                        session.id,
                        model,
                        attempt_number,
                        latency_ms,
                    )
                    logger.info(
                        "model_router success session:%s model:%s attempts_used:%s",
                        session.id,
                        model,
                        calls_used,
                    )
                    return answer

                except GeminiError as exc:
                    latency_ms = int((time.monotonic() - started) * 1000)
                    failure_categories.append(exc.category)
                    logger.warning(
                        "model_router attempt result=session:%s model:%s attempt:%s "
                        "result:failure error_category:%s retryable:%s latency_ms:%s",
                        session.id,
                        model,
                        attempt_number,
                        exc.category.value,
                        exc.retryable,
                        latency_ms,
                    )

                    if exc.category in STOP_CATEGORIES:
                        logger.error(
                            "model_router stop session:%s model:%s reason_category:%s",
                            session.id,
                            model,
                            exc.category.value,
                        )
                        raise

                    # One bounded same-model retry for transient/uncertain
                    # failures; every call consumes the shared budget.
                    if (
                        exc.category in SAME_MODEL_RETRY_CATEGORIES
                        and retries_used < self.retries_per_model
                        and calls_used < budget
                    ):
                        retries_used += 1
                        continue

                    next_model = ordered[index + 1] if index + 1 < len(ordered) else None
                    if next_model is not None and calls_used < budget:
                        logger.info(
                            "model_router fallback_started session:%s from_model:%s "
                            "to_model:%s reason_category:%s",
                            session.id,
                            model,
                            next_model,
                            exc.category.value,
                        )
                    break

        raise self._exhausted_error(session, failure_categories, calls_used)

    # ------------------------------------------------------------------
    # Exhaustion
    # ------------------------------------------------------------------
    @staticmethod
    def _exhausted_error(
        session: VideoSession,
        failure_categories: List[GeminiErrorCategory],
        calls_used: int,
    ) -> GeminiError:
        """Build the terminal error when the attempt budget is exhausted.

        Quota/rate-limit exhaustion keeps its specific classification so the
        API layer can preserve the documented rate-limit behavior; every other
        exhaustion maps to service-unavailable (docs/07-api-design.md §5,
        docs/10-error-handling.md §7).
        """
        if failure_categories and all(
            category == GeminiErrorCategory.RATE_LIMITED
            for category in failure_categories
        ):
            logger.error(
                "model_router exhausted session:%s reason:quota attempts_used:%s",
                session.id,
                calls_used,
            )
            return GeminiError(
                category=GeminiErrorCategory.RATE_LIMITED,
                message="The video service is currently at capacity. Please try again later.",
                retryable=True,
            )

        logger.error(
            "model_router exhausted session:%s reason:all_models_unavailable "
            "attempts_used:%s failure_categories:%s",
            session.id,
            calls_used,
            [category.value for category in failure_categories],
        )
        return GeminiError(
            category=GeminiErrorCategory.SERVICE_UNAVAILABLE,
            message="All supported models are temporarily unavailable. Please try again later.",
            retryable=True,
        )
