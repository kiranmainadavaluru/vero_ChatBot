#!/usr/bin/env python3
"""
Day 7: RAGAS eval harness.

Runs the labeled Q&A set in qa_dataset.json through the actual RAG
pipeline - agent_service.run_agent by default, or crew_service.run_crew
with --crew, the same swap point main.py's /api/chat uses - against a
document you either ingest fresh or already have in Qdrant, then
scores the (question, answer, retrieved_contexts, ground_truth)
tuples with RAGAS: faithfulness, answer relevancy, context precision,
and context recall.

Usage (from rag_chatbot_app/backend/):
    python -m eval.ragas_eval --ingest eval/sample_docs/30-Day-Python-Mastery-Checklist.md
    python -m eval.ragas_eval --document-id <existing-doc-id>
    python -m eval.ragas_eval --ingest <path> --crew   # score the CrewAI pipeline instead

Requires:
    - The main app's requirements.txt already installed, PLUS
      eval/requirements-eval.txt on top of it (ragas is pinned to
      0.3.9 - see _ragas_compat.py for why).
    - A reachable Postgres + Qdrant configured the same way the main
      app is (DATABASE_URL, QDRANT_URL, QDRANT_API_KEY) and a working
      GEMINI_API_KEY - this hits the real pipeline and the real
      Gemini endpoint, it isn't mocked.

Known limitation worth being upfront about: this uses the same
Gemini model as both the answer-generator and the RAGAS judge. A
model judging its own family's output tends to run lenient - that's
a real bias, not just a caveat to mention once. Treat the scores as
"good enough for tracking regressions on this project between
changes," not as an absolute quality certification. A second,
independent judge model (e.g. a different provider) would be the
fix if this needs to be airtight for something higher-stakes than a
portfolio eval.
"""
import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from eval import _ragas_compat  # noqa: E402,F401 - must run before any `ragas` import below

import config  # noqa: E402
import agent_service  # noqa: E402
import crew_service  # noqa: E402
import upload_service  # noqa: E402
import vectorstore  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from openai import OpenAI, RateLimitError  # noqa: E402

from ragas import evaluate, EvaluationDataset, SingleTurnSample  # noqa: E402
from ragas.metrics import (  # noqa: E402
    Faithfulness,
    ResponseRelevancy,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)
from ragas.embeddings import HuggingFaceEmbeddings  # noqa: E402
from ragas.llms import llm_factory  # noqa: E402
from ragas.run_config import RunConfig  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = EVAL_DIR / "qa_dataset.json"
RESULTS_CSV = EVAL_DIR / "results.csv"

# Columns as ragas names them in the result dataframe, in display order.
SUMMARY_COLUMNS = [
    "faithfulness",
    "answer_relevancy",
    "llm_context_precision_with_reference",
    "context_recall",
]


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


class DailyQuotaExhausted(RuntimeError):
    """Raised instead of retrying when Gemini's 429 is a per-day quota,
    not a per-minute throttle - see _is_daily_quota_exhausted."""


def _parse_retry_delay(error, default=20.0):
    """
    Gemini's free-tier 429 includes a human-readable 'Please retry in
    41.8s' in the message (and a structured retryDelay in the response
    body, but the message is the reliable part across SDK versions).
    Best-effort regex extraction with a safety margin; falls back to a
    fixed default rather than guessing low and hammering a still-
    exhausted quota again immediately.
    """
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(error), re.IGNORECASE)
    if match:
        return float(match.group(1)) + 2.0
    return default


def _is_daily_quota_exhausted(error) -> bool:
    """
    Google's 429 body includes a quotaId that distinguishes a per-day
    cap (e.g. 'GenerateRequestsPerDayPerProjectPerModel-FreeTier')
    from a per-minute one - that's the reliable signal, not the
    message text, which says 'Please retry in Ns' for *both* cases
    even though the wait genuinely won't help for a daily cap (the
    next call 41s from now hits the same exhausted daily quota and
    fails again). Retrying a daily-quota 429 just burns wall-clock
    time for nothing - confirmed directly against a real run that did
    exactly that for ~5 minutes before finally giving up.
    """
    return "perday" in str(error).lower().replace(" ", "")


def _call_with_retry(fn, *args, max_retries=6, **kwargs):
    """
    Free-tier Gemini keys are rate-limited (5 requests/minute at the
    time this was written) - the --delay pacing in run_pipeline below
    is the primary defense, but a single question can still trigger
    more than one LLM call internally (the agent's tool-calling loop),
    which can burn through the per-minute budget within one question.
    This is the backup: retry on 429 specifically, honoring the
    provider's suggested wait, rather than failing the whole eval run
    over a transient quota window.

    A per-day quota exhaustion is a different failure mode entirely -
    see _is_daily_quota_exhausted - and is raised immediately instead
    of retried, since retrying literally cannot succeed until the
    quota resets.
    """
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except RateLimitError as e:
            if _is_daily_quota_exhausted(e):
                raise DailyQuotaExhausted(
                    "Gemini's free-tier DAILY request quota is exhausted for this model - "
                    "this is not a per-minute throttle, so waiting/retrying now won't help. "
                    "It resets on Google's schedule (typically midnight Pacific time). See "
                    "eval/README.md's 'Hit a daily quota wall?' section for options."
                ) from e
            if attempt == max_retries:
                raise
            delay = _parse_retry_delay(e)
            print(f"    Rate limited (attempt {attempt + 1}/{max_retries}) - waiting {delay:.0f}s...")
            time.sleep(delay)


def run_pipeline(qa_pairs, qdrant_client, embedding_model, llm_client, document_id, use_crew, delay_seconds):
    """
    Calls the real pipeline once per question and builds RAGAS
    SingleTurnSample records from the (answer, sources, retrieval_info)
    it returns. No mocking - this is the same code path a real chat
    request takes.

    delay_seconds paces requests to stay under a free-tier rate limit -
    see _call_with_retry for the reactive backup when pacing alone
    isn't enough for a given question.
    """
    samples = []
    for i, qa in enumerate(qa_pairs, start=1):
        if i > 1 and delay_seconds > 0:
            time.sleep(delay_seconds)

        # A fresh throwaway session_id per question - run_agent/run_crew
        # only *read* chat history for context (they don't require the
        # session to already exist as a row), so this is safe without
        # any extra DB setup.
        session_id = f"ragas-eval-{uuid.uuid4().hex[:8]}"
        question = qa["question"]

        if use_crew:
            answer, sources, retrieval_info = _call_with_retry(
                crew_service.run_crew,
                qdrant_client, embedding_model, session_id, question, document_id=document_id,
            )
        else:
            answer, sources, retrieval_info = _call_with_retry(
                agent_service.run_agent,
                llm_client, qdrant_client, embedding_model, session_id, question, document_id=document_id,
            )

        contexts = [s["content"] for s in sources] or ["(no context retrieved for this question)"]
        samples.append(
            SingleTurnSample(
                user_input=question,
                response=answer,
                retrieved_contexts=contexts,
                reference=qa["ground_truth"],
            )
        )
        print(f"  [{i}/{len(qa_pairs)}] {question[:70]!r} -> {len(sources)} chunk(s) retrieved, mode={retrieval_info.get('mode')}")

    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ingest", help="Path to a document to ingest fresh before evaluating")
    parser.add_argument("--document-id", help="Use an already-ingested document instead of --ingest")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to the labeled Q&A JSON file")
    parser.add_argument("--crew", action="store_true", help="Score crew_service.run_crew instead of agent_service.run_agent")
    parser.add_argument(
        "--delay", type=float, default=13.0,
        help="Seconds to wait between pipeline calls, to stay under a free-tier rate limit (default: 13, i.e. "
             "under Gemini's free-tier 5 requests/minute with some margin). Set to 0 if you're on a paid tier.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N questions (useful for a quick smoke test)")
    args = parser.parse_args()

    if not args.ingest and not args.document_id:
        parser.error("pass either --ingest <path> or --document-id <id>")

    print("Connecting to Qdrant and loading the embedding model...")
    qdrant_client = vectorstore.get_client()
    vectorstore.ensure_schema(qdrant_client, reset=False)
    embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
    llm_client = OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL)

    document_id = args.document_id
    if args.ingest:
        print(f"Ingesting {args.ingest} ...")
        result = upload_service.ingest_saved_file(qdrant_client, embedding_model, args.ingest)
        document_id = result["document_id"]
        print(f"Ingested as document_id={document_id} ({result['chunks_stored']} chunk(s))")

    qa_pairs = load_dataset(Path(args.dataset))
    if args.limit:
        qa_pairs = qa_pairs[: args.limit]
    pipeline_name = "crew_service.run_crew" if args.crew else "agent_service.run_agent"
    print(f"\nRunning {len(qa_pairs)} question(s) through {pipeline_name} (--delay {args.delay}s between calls)...")
    samples = run_pipeline(qa_pairs, qdrant_client, embedding_model, llm_client, document_id, args.crew, args.delay)

    dataset = EvaluationDataset(samples=samples)

    print(
        "\nScoring with RAGAS (calls Gemini several times per metric per question - "
        "this is the slow part, especially on a free-tier key; expect this to take a while)..."
    )
    ragas_llm = llm_factory(model=config.CHAT_MODEL, client=llm_client)
    # Local, free embeddings for the metric that needs them (answer
    # relevancy) - same model the app itself embeds chunks with, so
    # this doesn't add an OpenAI-embeddings dependency or cost.
    ragas_embeddings = HuggingFaceEmbeddings(model=config.EMBEDDING_MODEL_NAME)

    metrics = [
        Faithfulness(llm=ragas_llm),
        ResponseRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
        LLMContextPrecisionWithReference(llm=ragas_llm),
        LLMContextRecall(llm=ragas_llm),
    ]
    # max_workers=1 serializes ragas's own LLM calls (default is 16
    # concurrent, which blows straight through a 5 req/min free-tier
    # quota) - max_retries/max_wait give its built-in retry loop room
    # to back off on a 429 (any Exception triggers a retry by default)
    # instead of failing the whole run on the first one.
    run_config = RunConfig(max_workers=1, max_retries=10, max_wait=90)
    result = evaluate(dataset=dataset, metrics=metrics, run_config=run_config)

    df = result.to_pandas()
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\nPer-question results saved to {RESULTS_CSV}")

    print("\n=== Summary (mean across all questions) ===")
    for col in SUMMARY_COLUMNS:
        if col in df.columns:
            print(f"  {col:42} {df[col].mean():.3f}")
        else:
            print(f"  {col:42} (column not present in result)")

    print(
        "\nReminder: the judge here is the same Gemini model that generated "
        "the answers - treat these as regression-tracking numbers for this "
        "project, not an independent quality certification."
    )


if __name__ == "__main__":
    try:
        main()
    except DailyQuotaExhausted as e:
        print(f"\n❌ {e}")
        sys.exit(1)
