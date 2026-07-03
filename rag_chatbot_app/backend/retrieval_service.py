"""
Retrieval strategy.

This is what answers the concern you raised at the start: plain
vector search across every chunk in Weaviate can accidentally blend
content from two different documents if their embeddings happen to
land close together (e.g. two contracts, two resumes, two quarterly
reports).

Two retrieval modes:

  - Explicit filter: caller passes document_id, and the search is
    scoped to only that document via a Weaviate `where` clause. Used
    when the frontend lets someone pick a document to ask about.

  - Automatic routing (default, no document_id given): search a
    wider candidate pool across every document, group the results by
    document_id, and identify which single document is the best
    match for the question. Only that document's chunks are then
    used as context - so even though the search ran across
    everything, chunks from unrelated documents never make it into
    the final answer.
"""
import vectorstore

# How many candidates to pull before grouping by document. This needs
# to be comfortably larger than top_k, otherwise a single stray
# similar chunk from the wrong document could get treated as if it
# were that document's best evidence.
CANDIDATE_POOL_SIZE = 15


def retrieve(client, embedding_model, question, top_k=3, document_id=None):
    """
    Returns (chunks, retrieval_info). retrieval_info documents which
    document(s) were considered and why - useful both for debugging
    and for showing "answered from: filename.pdf" in the UI.
    """
    question_vector = embedding_model.encode(question).tolist()

    if document_id:
        where_filter = _document_id_filter(document_id)
        chunks = vectorstore.query(client, question_vector, top_k=top_k, where_filter=where_filter)
        return chunks, {
            "mode": "explicit_filter",
            "document_id": document_id,
            "filename": chunks[0]["filename"] if chunks else None,
        }

    candidates = vectorstore.query(client, question_vector, top_k=CANDIDATE_POOL_SIZE)
    if not candidates:
        return [], {"mode": "no_results"}

    ranked_documents = _rank_documents_by_relevance(candidates)
    best_document_id = ranked_documents[0]["document_id"]

    routed_chunks = [c for c in candidates if c["document_id"] == best_document_id][:top_k]

    return routed_chunks, {
        "mode": "auto_routed",
        "document_id": best_document_id,
        "filename": routed_chunks[0]["filename"] if routed_chunks else None,
        "candidate_documents": ranked_documents,
    }


def _rank_documents_by_relevance(candidates):
    """
    Groups candidate chunks by document_id and scores each document
    by its single best (lowest-distance) chunk. Using the best chunk
    rather than an average means one long, mostly-irrelevant document
    doesn't get penalized just for having more so-so chunks in the
    candidate pool - what matters is whether it has the single best
    piece of evidence for this question.
    """
    best_distance_by_doc = {}
    filename_by_doc = {}

    for chunk in candidates:
        doc_id = chunk["document_id"]
        distance = chunk["_additional"]["distance"]
        if doc_id not in best_distance_by_doc or distance < best_distance_by_doc[doc_id]:
            best_distance_by_doc[doc_id] = distance
            filename_by_doc[doc_id] = chunk["filename"]

    ranked = sorted(
        (
            {"document_id": doc_id, "filename": filename_by_doc[doc_id], "best_distance": dist}
            for doc_id, dist in best_distance_by_doc.items()
        ),
        key=lambda d: d["best_distance"],
    )
    return ranked


def _document_id_filter(document_id):
    return {
        "path": ["document_id"],
        "operator": "Equal",
        "valueText": document_id,
    }