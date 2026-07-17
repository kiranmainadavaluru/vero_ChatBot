# RAGAS eval harness (Day 7)

Scores the RAG pipeline's actual answers against a small hand-labeled
Q&A set, using [RAGAS](https://docs.ragas.io/) with Gemini as the
judge (the same Gemini setup the app already uses - see
`config.GEMINI_BASE_URL`).

## What's here

- `qa_dataset.json` - 12 question/ground-truth pairs written against
  `sample_docs/30-Day-Python-Mastery-Checklist.md`. One question
  (`q12`) deliberately asks about something the doc doesn't cover, to
  check the pipeline doesn't fabricate an answer when it should say
  it doesn't know.
- `sample_docs/` - the source document the dataset was written
  against, bundled so the harness is reproducible without needing to
  re-upload anything.
- `ragas_eval.py` - runs each question through the real pipeline
  (`agent_service.run_agent` or, with `--crew`, `crew_service.run_crew`),
  then scores the results.
- `_ragas_compat.py` - a workaround for a real upstream ragas bug, not
  project-specific code. See the comment at the top of that file and
  `requirements-eval.txt` for the details.
- `results.csv` - written each run with per-question scores (gitignored
  is *not* set up for this yet - fine for a portfolio project, but
  worth adding if this were shared more broadly).

## Setup

```bash
pip install -r requirements.txt              # main app deps, if not already installed
pip install -r eval/requirements-eval.txt     # ragas, pinned - see the file for why
```

Needs the same environment the app itself needs: `DATABASE_URL`,
`QDRANT_URL`, `QDRANT_API_KEY`, `GEMINI_API_KEY`. This calls the real
pipeline and the real Gemini endpoint - nothing here is mocked.

## Running it

```bash
# from rag_chatbot_app/backend/
python -m eval.ragas_eval --ingest eval/sample_docs/30-Day-Python-Mastery-Checklist.md

# reuse a document you've already ingested, instead of ingesting again
python -m eval.ragas_eval --document-id <existing-doc-id>

# score the CrewAI pipeline instead of the default agentic one
python -m eval.ragas_eval --ingest eval/sample_docs/30-Day-Python-Mastery-Checklist.md --crew
```

## The four metrics

- **Faithfulness** - does the answer only claim things the retrieved
  chunks actually support? Low faithfulness = hallucination, even if
  the answer sounds right.
- **Answer relevancy** - does the answer actually address the
  question asked, rather than being generically-true-but-off-target?
- **Context precision** - of the chunks retrieved, how many were
  actually relevant? Low precision = retrieval is pulling in noise
  even when it also finds the right chunk.
- **Context recall** - did retrieval find everything needed to
  construct the ground-truth answer? Low recall = the right chunk
  never got retrieved at all, so no amount of good generation could
  have fixed the answer.

Faithfulness and context precision are about the *generation* step;
context recall is about the *retrieval* step - a low score on one vs.
the other points at a different part of the pipeline to fix.

## Known limitations (worth saying out loud, not burying)

- **Same-model judging**: the judge LLM is the same Gemini model used
  to generate the answers. A model grading its own family's output
  tends to run lenient. Treat these scores as useful for catching
  regressions *within this project* between changes - not as an
  absolute, provider-independent quality bar. A stronger setup would
  use a different provider as judge.
- **Small N**: 12 questions is enough to sanity-check the pipeline and
  catch obvious regressions, not enough to be statistically
  confident about a specific score. This is a portfolio-scale harness,
  not a production eval suite.
- **Single-turn only**: every question is asked in a fresh session
  with no prior chat history, so this doesn't evaluate multi-turn
  behavior (follow-up questions, pronoun resolution across turns).
