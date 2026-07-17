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
import sys
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
from openai import OpenAI  # noqa: E402

from ragas import evaluate, EvaluationDataset, SingleTurnSample  # noqa: E402
from ragas.metrics import (  # noqa: E402
    Faithfulness,
    ResponseRelevancy,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)
from ragas.embeddings import HuggingFaceEmbeddings  # noqa: E402
from ragas.llms import llm_factory  # noqa: E402

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


def run_pipeline(qa_pairs, qdrant_client, embedding_model, llm_client, document_id, use_crew):
    """
    Calls the real pipeline once per question and builds RAGAS
    SingleTurnSample records from the (answer, sources, retrieval_info)
    it returns. No mocking - this is the same code path a real chat
    request takes.
    """
    samples = []
    for i, qa in enumerate(qa_pairs, start=1):
        # A fresh throwaway session_id per question - run_agent/run_crew
        # only *read* chat history for context (they don't require the
        # session to already exist as a row), so this is safe without
        # any extra DB setup.
        session_id = f"ragas-eval-{uuid.uuid4().hex[:8]}"
        question = qa["question"]

        if use_crew:
            answer, sources, retrieval_info = crew_service.run_crew(
                qdrant_client, embedding_model, session_id, question, document_id=document_id,
            )
        else:
            answer, sources, retrieval_info = agent_service.run_agent(
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
    args = parser.parse_args()

    if not args.ingest and not args.document_id:
        parser.error("pass either --ingest <path> or --document-id <id>")

    print("Connecting to Qdrant and loading the embedding model...")
    qdrant_client = vectorstore.get_client()
    embedding_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
    llm_client = OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL)

    document_id = args.document_id
    if args.ingest:
        print(f"Ingesting {args.ingest} ...")
        result = upload_service.ingest_saved_file(qdrant_client, embedding_model, args.ingest)
        document_id = result["document_id"]
        print(f"Ingested as document_id={document_id} ({result['chunks_stored']} chunk(s))")

    qa_pairs = load_dataset(Path(args.dataset))
    pipeline_name = "crew_service.run_crew" if args.crew else "agent_service.run_agent"
    print(f"\nRunning {len(qa_pairs)} question(s) through {pipeline_name}...")
    samples = run_pipeline(qa_pairs, qdrant_client, embedding_model, llm_client, document_id, args.crew)

    dataset = EvaluationDataset(samples=samples)

    print("\nScoring with RAGAS (calls Gemini once per metric per question - this is the slow part)...")
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
    result = evaluate(dataset=dataset, metrics=metrics)

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
    main()
