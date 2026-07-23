"""
Agentic answering.

Replaces the old fixed pipeline (always retrieve -> always generate)
with a tool-calling loop: the model itself decides whether it needs
to search the uploaded documents, list what's available, or just
answer directly - the same way you'd expect a competent assistant to
reason about it, rather than us hard-coding "if chunks: ... else: ...".

Uses the OpenAI-compatible chat.completions API (currently pointed at
Google Gemini via config.GEMINI_BASE_URL - see app.py). Any provider
exposing that same interface (OpenAI itself, Gemini, or HF's router)
works here unchanged; only the client construction in app.py differs.

The underlying retrieval logic (document routing, the relevance
distance threshold, explicit document_id scoping) is untouched and
lives entirely in retrieval_service.py - this module only decides
*when* to call it.
"""
import json
import os

import config
import db
import retrieval_service
import vectorstore

# Set AGENT_DEBUG=true in your environment to print each iteration of
# the tool-calling loop (which tool was called, with what args, and
# what came back). Useful for seeing *why* the loop didn't converge,
# instead of only seeing the final "ran out of time" message.
AGENT_DEBUG = os.getenv("AGENT_DEBUG", "false").lower() == "true"

MAX_TOOL_ITERATIONS = 4          # hard stop so a confused loop can't run forever
MAX_HISTORY_MESSAGES = 8         # last N chat turns given to the model as context
SEARCH_TOP_K = 5

# Used when "Docs only" is OFF. In this mode the model has no access to
# search_documents / list_uploaded_documents at all - not "prefer docs,
# fall back to general knowledge", but no document access whatsoever.
# run_agent() pairs this prompt with a plain (tool-less) completion call,
# so there's nothing to enforce in code the way strict mode needs below -
# the model literally isn't given the tools, so it can't reach the
# documents even if it wanted to.
GENERAL_SYSTEM_PROMPT = """You are Vero, a helpful, direct assistant.

- Your name is Vero. If asked who you are, what model you are, or who built/trained \
you, answer only as Vero - never mention Claude, Anthropic, GPT, OpenAI, or any \
other assistant/company, even if that information feels familiar to you. You are Vero.
- "Docs only" mode is currently OFF - you do not have access to the user's uploaded \
documents right now. Answer every question from your own general knowledge, the way \
any helpful assistant would. Don't claim to have checked, searched, or looked at any \
documents, and don't mention that document access is unavailable unless the user \
directly asks about their documents.
- Keep answers clear and concise.
"""

# Used instead of SYSTEM_PROMPT when the user has strict mode turned on. The
# prompt-level instruction alone isn't fully trustworthy (a model can still
# ignore it), so run_agent() also enforces this in code below - see the
# `strict_mode` short-circuit after search_documents returns no result.
STRICT_SYSTEM_PROMPT = """You are Vero, an assistant that answers questions using \
ONLY the user's uploaded documents. General knowledge is turned off.

- Your name is Vero. If asked who you are, what model you are, or who built/trained \
you, answer only as Vero - never mention Claude, Anthropic, GPT, OpenAI, or any \
other assistant/company, even if that information feels familiar to you. You are Vero.
- Always call search_documents before answering a question, even if you think \
you already know the answer.
- Use list_uploaded_documents when the user asks what files are available.
- Answer strictly using the content returned by search_documents - do not add, \
assume, or fill in anything from your own general knowledge, even to complete \
a partial answer.
- If search_documents reports nothing relevant was found, tell the user plainly \
that their uploaded documents don't contain that information. Do not guess, and \
do not answer from general knowledge instead.
- Keep answers clear and concise.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the user's uploaded documents for content relevant to a "
                "query. Use this whenever the question could be answered by "
                "something the user has uploaded. If document_id is omitted, "
                "automatically routes to the single best-matching document."
            ),
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A standalone search query capturing what the user "
                            "wants to find, with pronouns/context resolved from "
                            "the conversation so far."
                        ),
                    },
                    "document_id": {
                        "type": "string",
                        "description": (
                            "Optional. Restrict the search to one specific "
                            "document's UUID, if the user has specified which "
                            "document to use."
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_uploaded_documents",
            "description": (
                "List all documents the user has uploaded, with filename and "
                "type. Use this when the user asks what files/documents are "
                "available, or before searching if you're not sure a relevant "
                "document exists."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_agent(llm_client, qdrant_client, embedding_model, session_id, question, document_id=None, strict_mode=False):
    """
    Agentic replacement for the old ask_llm().

    strict_mode is the "Docs only" toggle, and it's a hard switch, not a
    hint - the model is only ever given the search_documents /
    list_uploaded_documents tools when it's True:
      - strict_mode=True:  tools are attached, a document search is
        forced on the first turn, and an empty/weak result short-circuits
        straight to a fixed "not found" answer instead of letting the
        model fall back to its own general knowledge.
      - strict_mode=False: no tools are attached at all, so the model has
        no way to reach the uploaded documents even if it wanted to - it
        just answers normally, like a plain chat assistant.

    Returns (answer_text, sources, retrieval_info) - same shape the
    /api/chat route already expects, so the frontend contract doesn't
    change.
    """
    if not strict_mode:
        # No tools attached - the model has no code path to the
        # documents, so there's nothing to short-circuit or enforce here.
        messages = (
            [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]
            + _recent_messages_as_chat(session_id)
            + [{"role": "user", "content": question}]
        )
        completion = llm_client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=400,
        )
        answer = completion.choices[0].message.content.strip()
        return answer, [], {"mode": "docs_off"}

    messages = (
        [{"role": "system", "content": STRICT_SYSTEM_PROMPT}]
        + _recent_messages_as_chat(session_id)
        + [{"role": "user", "content": question}]
    )

    sources = []
    retrieval_info = {"mode": "agent_no_search"}

    for iteration in range(MAX_TOOL_ITERATIONS):
        # Don't let the model choose to skip retrieval on its first turn -
        # that's the other way it was reaching general knowledge (never
        # calling search_documents at all).
        force_search = iteration == 0
        completion = llm_client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice=(
                {"type": "function", "function": {"name": "search_documents"}}
                if force_search
                else "auto"
            ),
            temperature=0.6,
            max_tokens=400,
        )
        choice = completion.choices[0]

        if AGENT_DEBUG:
            print(f"[agent] iteration {iteration}: finish_reason={choice.finish_reason!r}")

        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            return choice.message.content.strip(), sources, retrieval_info

        messages.append(choice.message)

        for tool_call in choice.message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if AGENT_DEBUG:
                print(f"[agent]   -> calling {name}({args})")

            if name == "search_documents":
                tool_result, chunks, retrieval_info = _tool_search_documents(
                    qdrant_client,
                    embedding_model,
                    query=args.get("query", question),
                    document_id=args.get("document_id") or document_id,
                )
                if chunks:
                    sources = _chunks_to_sources(chunks)
                else:
                    # Code-level stop, not just a prompt instruction: there is
                    # nothing usable in the documents, so return a fixed
                    # answer directly rather than handing control back to the
                    # model, which could still choose to answer from memory.
                    #
                    # `retrieval_info` here has no `filename` (the search
                    # found nothing), which is the same shape the frontend
                    # uses to detect a *general-knowledge* answer. Without
                    # `strict_blocked`, the UI would mislabel this refusal
                    # as "general knowledge" - the opposite of what actually
                    # happened, since strict mode is precisely what kept it
                    # from answering that way.
                    return (
                        "I don't have that information in your uploaded documents.",
                        [],
                        {**retrieval_info, "strict_blocked": True},
                    )
            elif name == "list_uploaded_documents":
                tool_result = _tool_list_documents(qdrant_client)
            else:
                tool_result = {"error": f"Unknown tool '{name}'"}

            if AGENT_DEBUG:
                print(f"[agent]   <- {name} returned: {json.dumps(tool_result)[:300]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": json.dumps(tool_result),
            })

    # Safety valve: hit the iteration cap without a final answer. `sources`
    # may hold chunks from an earlier successful search_documents call, but
    # since no answer was ever generated from them, returning them here
    # would falsely imply this fallback message was grounded on them.
    return (
        "I wasn't able to finish researching that in time - could you "
        "rephrase or narrow the question?",
        [],
        retrieval_info,
    )


# ── Tool implementations ────────────────────────────────────────────
def _tool_search_documents(qdrant_client, embedding_model, query, document_id=None):
    chunks, retrieval_info = retrieval_service.retrieve(
        qdrant_client,
        embedding_model,
        query,
        top_k=SEARCH_TOP_K,
        document_id=document_id,
    )

    if not chunks:
        message = (
            "No document was specific enough to that query to be trusted."
            if retrieval_info.get("mode") == "below_threshold"
            else "No relevant content found in the uploaded documents for this query."
        )
        return {"found": False, "message": message}, [], retrieval_info

    tool_result = {
        "found": True,
        "filename": retrieval_info.get("filename"),
        "chunks": [{"content": c["content"], "page_number": c["page_number"]} for c in chunks],
    }
    return tool_result, chunks, retrieval_info


def _tool_list_documents(qdrant_client):
    documents = vectorstore.list_documents(qdrant_client)
    if not documents:
        return {"documents": [], "message": "No documents have been uploaded yet."}
    return {
        "documents": [
            {"filename": d["filename"], "file_type": d["file_type"], "chunk_count": d["chunk_count"]}
            for d in documents
        ]
    }


# ── Helpers ──────────────────────────────────────────────────────────
def _chunks_to_sources(chunks):
    """Same shape the old ask_llm-based route returned, except `distance`
    is now `score` (higher = more relevant) since retrieval switched
    from pure vector search to hybrid search - see retrieval_service.py.
    `rerank_score` is included when retrieval_service.ENABLE_RERANK
    added one (see reranker.py) - omitted otherwise, since a stale/
    absent field is more honest than inventing a default value."""
    return [
        {
            "content": c["content"],
            "score": round(float(c["_additional"]["score"]), 4),
            "rerank_score": round(float(c["rerank_score"]), 4) if "rerank_score" in c else None,
            "chunk_index": c["chunk_index"],
            "filename": c["filename"],
            "page_number": c["page_number"],
        }
        for c in chunks
    ]


def _recent_messages_as_chat(session_id):
    """
    Pull recent chat history as plain {role, content} dicts for the
    model's context window. This is what lets the model resolve
    follow-up questions ("how many days?") into a good standalone
    search query itself, without a separate rewrite LLM call.
    """
    try:
        messages = db.get_messages(session_id)
    except Exception:
        return []

    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    return [
        {"role": m["role"], "content": m["content"]}
        for m in trimmed
        if m["role"] in ("user", "assistant")
    ]