"""
PII scrubbing on ingestion (Day 6 of the enhancement plan).

Runs every chunk through Microsoft Presidio's analyzer + anonymizer
before it's embedded and written to Qdrant, so raw PII from an
uploaded document never lands in the vector store or a source
citation returned to the user. This is a document-ingestion concern,
not a chat concern - it's wired into upload_service.ingest_saved_file(),
not into agent_service/crew_service.

Model choice: Presidio's own default NLP config asks for
en_core_web_lg (~400MB). This pins en_core_web_sm (~13MB) explicitly
instead - same "small, free, CPU-friendly" reasoning already used for
the reranker's cross-encoder choice (see reranker.py). Recall on
PERSON/LOCATION-style entities is measurably worse with the small
model, which is a real tradeoff, not a free lunch - worth naming if
this comes up in an interview.

Entity selection is deliberately narrower than "everything Presidio
can detect": PERSON, EMAIL_ADDRESS, PHONE_NUMBER, and the
financial/government-ID entities are unambiguously PII and safe to
redact. LOCATION, ORGANIZATION, and DATE_TIME are left out of the
default set on purpose - a document about "Microsoft's Seattle
office opening in March 2019" isn't a privacy leak, and redacting
those entities would gut retrieval quality (the whole chunk becomes
useless as searchable content) for very little privacy benefit. This
is a precision-over-recall choice; DEFAULT_ENTITIES below is the
single place to widen it.

Limitation worth documenting: this scrubs the *ingested document*
text. It does not scrub chat messages (those are conversational, not
a document-storage concern) and it does not re-scrub already-ingested
documents retroactively if the entity list changes later.
"""
import os

import config

AGENT_DEBUG = os.getenv("AGENT_DEBUG", "false").lower() == "true"

# Entities that are unambiguously personal/financial/government-ID
# data. See module docstring for why LOCATION/ORGANIZATION/DATE_TIME
# are deliberately excluded from the default.
DEFAULT_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "CRYPTO",
    "IBAN_CODE",
    "IP_ADDRESS",
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "US_BANK_NUMBER",
    "US_ITIN",
    "MEDICAL_LICENSE",
    "UK_NHS",
]

# Lazy singletons - loading spaCy + building the analyzer registry
# takes real time (~1-2s), so this pays that cost once per process,
# not once per chunk, same pattern as reranker.py's _get_model().
_analyzer = None
_anonymizer = None


def _get_engines():
    global _analyzer, _anonymizer
    if _analyzer is None:
        # Imported lazily so importing this module doesn't force a
        # presidio/spacy import (and the model-load cost) in code
        # paths where ENABLE_PII_SCRUBBING=false, e.g. quick local
        # runs without the spaCy model downloaded yet.
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


def scrub_text(text: str, entities=None, score_threshold=None) -> tuple[str, list[str]]:
    """
    Returns (scrubbed_text, entity_types_found). Each detected span is
    replaced with a `<ENTITY_TYPE>` placeholder (Presidio's default
    "replace" operator) - readable enough to keep the surrounding
    chunk useful for retrieval, unlike fully deleting the span.
    """
    if not text or not text.strip():
        return text, []

    analyzer, anonymizer = _get_engines()
    entities = entities if entities is not None else DEFAULT_ENTITIES
    threshold = score_threshold if score_threshold is not None else config.PII_SCORE_THRESHOLD

    results = analyzer.analyze(
        text=text,
        language="en",
        entities=entities,
        score_threshold=threshold,
    )
    if not results:
        return text, []

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    found = sorted({r.entity_type for r in results})
    return anonymized.text, found


def scrub_chunks(chunks: list[dict]) -> tuple[list[dict], int]:
    """
    Scrubs `content` in place for every chunk dict (the shape
    chunking.chunk_pages() returns). Returns (chunks, redacted_count)
    so the caller can log/report how many chunks were touched -
    useful ingestion telemetry, and handy for demoing this feature
    without needing to eyeball diffs.

    No-op pass-through when config.ENABLE_PII_SCRUBBING is False, so
    the flag genuinely disables the feature rather than just hiding
    its effect.
    """
    if not config.ENABLE_PII_SCRUBBING:
        return chunks, 0

    redacted_count = 0
    for chunk in chunks:
        scrubbed, found = scrub_text(chunk["content"])
        if found:
            chunk["content"] = scrubbed
            chunk["pii_redacted"] = found  # kept off the vectorstore payload; see upload_service.py
            redacted_count += 1
            if AGENT_DEBUG:
                print(f"🔒 Redacted {found} in chunk {chunk.get('chunk_index')}")

    return chunks, redacted_count
