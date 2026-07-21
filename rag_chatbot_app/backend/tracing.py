"""
Langfuse tracing around the CrewAI answering path (Day 8 of the
enhancement plan).

Scope: this instruments crew_service.run_crew() only, not
agent_service.run_agent(). The plan calls out "tracing wrapped around
the Crew run" specifically, and CrewAI's multi-agent/multi-task
structure (three agents, three sequential tasks, a tool call in the
middle) is what benefits most from seeing a real nested trace, versus
one flat span for a single model call. The same pattern below would
extend to agent_service.py later - noted here rather than doing it
speculatively for a path nobody asked to see traced yet.

How this fits together (Langfuse's OTel-native v3 SDK, not the older
@observe-only v1/v2 approach):
  - `openinference-instrumentation-crewai` patches CrewAI's
    Agent/Task/Crew execution to emit standard OpenTelemetry spans
    for every agent run, task, and underlying LLM call - this is a
    third-party instrumentation package, not something Langfuse or
    this project maintains.
  - The Langfuse Python SDK is itself an OTel exporter: once
    `CrewAIInstrumentor().instrument()` has run and the LANGFUSE_*
    env vars below are set, those spans are shipped to Langfuse
    automatically - no CrewAI-specific code needed on top.
  - `trace_crew_run()` below adds one more span *around* the whole
    `crew.kickoff()` call, so a trace has a single named root
    ("crew-chat-turn") tying one user question to its three-agent
    execution, instead of a pile of spans with no shared parent.
  - `propagate_attributes(session_id=...)` maps this app's chat
    session id onto Langfuse's own session concept, so every turn in
    the same conversation groups together in the Langfuse UI.

Optional by design: if LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
aren't set, TRACING_ENABLED is False and everything in this module is
a no-op passthrough. This is a portfolio project - cloning it and
running the chatbot shouldn't require signing up for Langfuse first.
See eval/README.md-style reasoning: optional pieces stay optional,
not silently required.
"""
import logging
from contextlib import contextmanager

import config

logger = logging.getLogger(__name__)

TRACING_ENABLED = bool(config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY)

_langfuse_client = None
_propagate_attributes = None

if TRACING_ENABLED:
    try:
        from langfuse import get_client, propagate_attributes
        from openinference.instrumentation.crewai import CrewAIInstrumentor

        # Must happen before crew.kickoff() is ever called - it patches
        # CrewAI's classes so their execution emits OTel spans. This
        # module is imported at the top of crew_service.py (before the
        # `from crewai import ...` line) specifically so the patch is
        # in place before any Agent/Task/Crew object does real work.
        CrewAIInstrumentor().instrument(skip_dep_check=True)

        _langfuse_client = get_client()
        _propagate_attributes = propagate_attributes

        if not _langfuse_client.auth_check():
            logger.warning(
                "LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are set but "
                "auth_check() failed - tracing will silently no-op. "
                "Check the keys and LANGFUSE_BASE_URL."
            )
            TRACING_ENABLED = False
    except Exception:
        # Any import/init failure (missing packages, bad keys, network
        # issues reaching Langfuse) should degrade to "no tracing", not
        # take the chat endpoint down with it - tracing is an add-on,
        # answering questions is the actual product.
        logger.exception("Langfuse/CrewAI instrumentation failed to initialize - tracing disabled")
        TRACING_ENABLED = False


@contextmanager
def trace_crew_run(session_id, question, document_id=None, strict_mode=False):
    """
    Wrap one crew.kickoff() call in a named root span, tagged with the
    chat session so multi-turn conversations group together in the
    Langfuse UI.

    No-ops entirely (plain passthrough, no overhead) when tracing
    isn't configured - crew_service.py doesn't need to check
    TRACING_ENABLED itself before using this.
    """
    if not TRACING_ENABLED:
        yield
        return

    with _langfuse_client.start_as_current_observation(
        as_type="span",
        name="crew-chat-turn",
        input={"question": question, "document_id": document_id, "strict_mode": strict_mode},
    ):
        with _propagate_attributes(
            session_id=str(session_id),
            tags=["crew", "strict_mode" if strict_mode else "open_mode"],
        ):
            yield

    # Flushing on every request costs a network round trip, which is a
    # real latency hit under real load - acceptable here because this
    # is a portfolio-scale app on a small number of concurrent users,
    # not a high-QPS deployment with a long-lived background batching
    # exporter. A production version would drop this explicit flush
    # and rely on the SDK's own background export instead, calling
    # flush() only at process shutdown.
    _langfuse_client.flush()