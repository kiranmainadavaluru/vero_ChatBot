"""
CrewAI multi-agent answering.

This is the Day 3-4 piece of the enhancement plan: a second answering
path, alongside agent_service.run_agent() (the single-model
tool-calling loop), built with three CrewAI agents running
sequentially:

    Retrieval Agent -> Answer Agent -> Verifier Agent

Why keep run_agent() instead of deleting it: run_agent() is a single
model deciding, turn by turn, whether to call a tool - genuinely
agentic, but unstructured, and there's no separate check on the
output before it reaches the user. This module trades that
flexibility for a fixed pipeline with an explicit verification step -
closer to what "agentic RAG" means in the JD sense (task
decomposition across specialized roles, not just one model with
tools). Both paths return the identical (answer, sources,
retrieval_info) tuple, so main.py can switch between them with one
config flag (config.USE_CREW) without touching the route.

Design choices worth calling out (useful for interview Q&A / the
"document assumptions and limitations" JD line):
  - Process.sequential, not hierarchical: three fixed stages is
    simpler to reason about and cheaper (no manager-agent overhead)
    than a planner deciding agent order at runtime. Revisit if a
    later stage needs to be skipped conditionally.
  - Retrieval is a single tool call, not a loop: the Retrieval Agent
    gets exactly one shot at search_documents per turn. Multi-hop
    retrieval (search, look at results, search again) is a real gap
    vs. a fully agentic retriever - noted here rather than hidden.
  - The Verifier is a check, not a re-generation: it's told to only
    remove/flag unsupported claims, not rewrite freely. Free
    rewriting would make its own output ungrounded in a new way.
  - strict_mode is still enforced in code, not just prompted (see
    the short-circuit at the bottom of run_crew) - same reasoning as
    agent_service.py: a prompt instruction alone isn't reliable
    enough to guarantee "never answer from general knowledge".

Day 8 addition: crew.kickoff() below runs inside
tracing.trace_crew_run(), which - only when Langfuse credentials are
configured - wraps the whole three-agent run in a named Langfuse
trace grouped by chat session. See tracing.py for how the CrewAI
instrumentation is wired up and why it's optional.
"""
import json
import os
from typing import Any, Optional, Type

import tracing  # noqa: F401 (side-effecting import - see tracing.py's
                 # module docstring: this must run and instrument CrewAI
                 # before any Agent/Task/Crew object does real work,
                 # so it's imported first, ahead of `from crewai import ...`)
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

import config
import retrieval_service
from agent_service import _recent_messages_as_chat, _chunks_to_sources  # reuse, don't duplicate

AGENT_DEBUG = os.getenv("AGENT_DEBUG", "false").lower() == "true"
SEARCH_TOP_K = 5
MAX_HISTORY_MESSAGES = 8


# ── Tool: wraps retrieval_service.retrieve() for the Retrieval Agent ──
class DocumentSearchInput(BaseModel):
    query: str = Field(
        description=(
            "A standalone search query capturing what the user wants to "
            "find, with pronouns/context resolved from the conversation."
        )
    )


class DocumentSearchTool(BaseTool):
    """
    Thin CrewAI wrapper around the existing hybrid-retrieval pipeline.
    Nothing about ranking, routing, or the relevance threshold changes
    here - retrieval_service.py stays the single source of truth for
    that logic, same as it is for agent_service.py.

    last_chunks / last_retrieval_info are captured as private state so
    run_crew() can pull real sources/retrieval_info back out after
    the Crew finishes - a Task's return value to the LLM has to be
    text, but the route needs the structured chunk data too.
    """

    name: str = "search_documents"
    description: str = (
        "Search the user's uploaded documents for content relevant to a query. "
        "Use this before answering any question that could plausibly be "
        "answered by something the user has uploaded."
    )
    args_schema: Type[BaseModel] = DocumentSearchInput

    qdrant_client: Any
    embedding_model: Any
    document_id: Optional[str] = None

    _last_chunks: list = PrivateAttr(default_factory=list)
    _last_retrieval_info: dict = PrivateAttr(default_factory=lambda: {"mode": "not_called"})

    def _run(self, query: str) -> str:
        chunks, retrieval_info = retrieval_service.retrieve(
            self.qdrant_client,
            self.embedding_model,
            query,
            top_k=SEARCH_TOP_K,
            document_id=self.document_id,
        )
        self._last_chunks = chunks
        self._last_retrieval_info = retrieval_info

        if not chunks:
            message = (
                "No document was specific enough to that query to be trusted."
                if retrieval_info.get("mode") == "below_threshold"
                else "No relevant content found in the uploaded documents for this query."
            )
            return json.dumps({"found": False, "message": message})

        return json.dumps({
            "found": True,
            "filename": retrieval_info.get("filename"),
            "chunks": [{"content": c["content"], "page_number": c["page_number"]} for c in chunks],
        })


def _build_llm() -> LLM:
    """
    CrewAI 1.15.x eagerly imports its native Google GenAI provider for
    any "gemini/<model>" string - even with is_litellm=True set - and
    that import fails without the extra `crewai[google-genai]`
    dependency (confirmed while building this, see commit notes).

    Rather than add a dependency just to route around it, this reuses
    the same trick already proven in app.py/main.py: point the
    "openai" provider at Gemini's OpenAI-compatible endpoint via
    base_url. CrewAI's native OpenAI provider needs no extra install,
    and GEMINI_API_KEY/GEMINI_BASE_URL are the same values already
    used for the OpenAI SDK client elsewhere in this codebase.
    """
    return LLM(
        model=f"openai/{config.CHAT_MODEL}",
        api_key=config.GEMINI_API_KEY,
        base_url=config.GEMINI_BASE_URL,
        temperature=0.4,
    )


def run_crew(qdrant_client, embedding_model, session_id, question, document_id=None, strict_mode=False):
    """
    CrewAI counterpart to agent_service.run_agent(). Same signature,
    same (answer, sources, retrieval_info) return shape - see the
    swap point marked in main.py's /api/chat handler.
    """
    llm = _build_llm()
    search_tool = DocumentSearchTool(
        qdrant_client=qdrant_client,
        embedding_model=embedding_model,
        document_id=document_id,
    )

    history = _recent_messages_as_chat(session_id)
    history_text = (
        "\n".join(f"{m['role']}: {m['content']}" for m in history[-MAX_HISTORY_MESSAGES:])
        or "(no prior messages in this session)"
    )

    grounding_rule = (
        "You must answer using ONLY content returned by search_documents. "
        "General knowledge is turned off - if nothing relevant is found, "
        "say plainly that the uploaded documents don't contain that information."
        if strict_mode else
        "Prefer grounding your answer in search_documents results. If the "
        "search returns nothing relevant, you may answer from general "
        "knowledge, but say so explicitly."
    )

    retrieval_agent = Agent(
        role="Document Retrieval Specialist",
        goal="Find the most relevant content from the user's uploaded documents for the current question.",
        backstory=(
            "You resolve follow-up questions against the conversation history into "
            "one clear standalone search query, then call search_documents exactly once."
        ),
        tools=[search_tool],
        llm=llm,
        verbose=AGENT_DEBUG,
        allow_delegation=False,
    )

    answer_agent = Agent(
        role="Answer Composer",
        goal="Draft a clear, concise answer to the user's question using the retrieved context.",
        backstory="You write direct, well-grounded answers and never pad them with filler.",
        llm=llm,
        verbose=AGENT_DEBUG,
        allow_delegation=False,
    )

    verifier_agent = Agent(
        role="Groundedness Verifier",
        goal=(
            "Check the drafted answer against the retrieved chunks. Remove or flag any "
            "claim not supported by them. Do not add new information - only trim or flag."
        ),
        backstory=(
            "You are the agentic version of the app's strict 'Docs-only' mode: a final "
            "check that catches ungrounded claims before they reach the user."
        ),
        llm=llm,
        verbose=AGENT_DEBUG,
        allow_delegation=False,
    )

    retrieval_task = Task(
        description=(
            f"Conversation so far:\n{history_text}\n\n"
            f"Current question: {question}\n\n"
            "Call search_documents once with a standalone query for this question. "
            "Report exactly what was found (or not found)."
        ),
        expected_output="A summary of the search_documents result: what was found, and its filename if any.",
        agent=retrieval_agent,
    )

    answer_task = Task(
        description=(
            f"Question: {question}\n\n{grounding_rule}\n\n"
            "Using the retrieval result from the previous step, draft an answer."
        ),
        expected_output="A clear, concise draft answer.",
        agent=answer_agent,
        context=[retrieval_task],
    )

    verify_task = Task(
        description=(
            f"Original question: {question}\n\n{grounding_rule}\n\n"
            "Compare the draft answer against the retrieved chunks from the retrieval "
            "step. Output the final answer text ONLY (no preamble like 'Here is the "
            "verified answer') - trimmed of any claim the chunks don't support."
        ),
        expected_output="The final answer text, and nothing else.",
        agent=verifier_agent,
        context=[retrieval_task, answer_task],
    )

    crew = Crew(
        agents=[retrieval_agent, answer_agent, verifier_agent],
        tasks=[retrieval_task, answer_task, verify_task],
        process=Process.sequential,
        verbose=AGENT_DEBUG,
    )

    with tracing.trace_crew_run(session_id, question, document_id=document_id, strict_mode=strict_mode):
        result = crew.kickoff()
    answer = str(result).strip()

    chunks = search_tool._last_chunks
    retrieval_info = search_tool._last_retrieval_info
    sources = _chunks_to_sources(chunks) if chunks else []

    # Code-level enforcement, not just the grounding_rule prompt text -
    # same reasoning as agent_service.run_agent()'s strict_mode
    # short-circuit: a prompt instruction is a strong nudge, not a
    # guarantee, so a real answer can't reach the user in strict mode
    # unless a document search actually found something.
    if strict_mode and not chunks:
        return (
            "I don't have that information in your uploaded documents.",
            [],
            {**retrieval_info, "strict_blocked": True},
        )

    return answer, sources, retrieval_info