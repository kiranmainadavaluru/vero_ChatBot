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

## Hit a daily quota wall?

Google cut Gemini free-tier daily quotas sharply in December 2025.
As of mid-2026, the free tier for `gemini-3.5-flash` is around **20
requests/day** (confirmed directly - this is what actually happened
running this harness). That's not a per-minute throttle you can wait
out in under a minute; it's a hard daily cap that resets on Google's
schedule (typically midnight Pacific time), and `ragas_eval.py`
detects this specifically (`DailyQuotaExhausted`) and fails fast
instead of retrying something that can't succeed until then.

The problem: a full run of this harness needs on the order of
**100+ Gemini calls** - the agent's tool-calling loop makes at least
one call per question (12 questions), and RAGAS's own scoring makes
several calls per metric per question (4 metrics × 12 questions).
20/day doesn't cover that, and spreading it across many days with
`--limit` is technically possible but painfully slow for what's
meant to be a quick eval.

Realistic options, roughly in order of how much sense they make for
a portfolio project:

1. **Enable billing on the API key.** Gemini 3.5 Flash is priced
   around $1.50/million input tokens and $9/million output tokens as
   of mid-2026. Every call this harness makes is a short chat
   completion (a few hundred to a couple thousand tokens each) - a
   full run is very unlikely to cost more than a dollar, probably a
   few cents to tens of cents. This is the practical fix if you want
   to actually see full RAGAS scores today.
2. **Wait for the daily reset and use `--limit`** to spread a run
   across several days for free. Given the ~100+ call requirement
   against a 20/day cap, expect this to take the better part of a
   week for one full pass - fine if you're not in a hurry, awkward
   otherwise.
3. **Point `config.CHAT_MODEL` at a cheaper/higher-quota model** (e.g.
   a Flash-Lite variant) if your account's free tier gives it a more
   generous daily allowance than Flash - worth checking your own
   Google AI Studio dashboard, since published numbers vary by
   account and change often enough that anything written here could
   be stale by the time you read it.

Whichever you pick, `--limit N` is there so you don't have to spend
your whole daily budget finding out the harness itself works before
committing to a full run.

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
