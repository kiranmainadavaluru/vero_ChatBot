"""
Qdrant integration.

All vector-database concerns - connecting, defining the schema,
inserting chunks, and querying - live here, separate from Flask
routes and business logic. Nothing in this module knows about
HTTP requests; it only knows about chunks and vectors.

Migrated from Weaviate (see git history for the old version) because
Weaviate Cloud dropped its permanent free tier - the "sandbox" is now
a 14-day trial that gets deleted. Qdrant Cloud's free tier (1GB RAM,
4GB disk) doesn't expire, though a cluster auto-suspends after a week
with zero traffic (one click in the dashboard wakes it back up).

Every function here keeps the exact same name and signature as the
old Weaviate version, so retrieval_service.py and upload_service.py
did not need to change at all. app.py and agent_service.py only got
a cosmetic rename (weaviate_client -> qdrant_client, plus the
weaviate_ready -> qdrant_ready health-check field) - no logic
changed there either. This file is where the actual migration lives.

IMPORTANT BEHAVIORAL DIFFERENCE from the old Weaviate version:
Weaviate's `with_hybrid(alpha=...)` blends BM25 and vector scores
into one weighted score, where alpha directly controls the mix.
Qdrant's hybrid approach is different - it runs BM25 and vector
search as two separate ranked lists, then fuses them with Reciprocal
Rank Fusion (RRF), which combines by *rank position* rather than by
raw score. This is a legitimate hybrid search technique - RRF is
what Qdrant recommends for this exact use case - but it does NOT use
alpha as a weighting knob. The `alpha` parameter is kept in the
query() signature for interface compatibility with retrieval_service.py
(which still passes it), but it is currently unused. If you need to
literally re-weight vector vs. keyword contribution, RRF's rank-based
fusion won't give you that; a manual weighted-score fusion would.
"""
import uuid

from qdrant_client import QdrantClient, models

import config

# BM25 sparse vectors are computed client-side by fastembed (bundled
# with qdrant-client) - the first call downloads the small BM25
# vocab/idf files from HuggingFace and caches them locally. This is a
# classic (non-neural) BM25 implementation, so it doesn't pull in
# torch or add meaningfully to memory usage.
_BM25_MODEL = "Qdrant/bm25"

# How many candidates each of the dense/BM25 prefetch stages pulls
# before RRF fusion narrows down to top_k. Needs to be comfortably
# larger than top_k for fusion to have enough to work with - same
# reasoning as CANDIDATE_POOL_SIZE in retrieval_service.py, just
# applied one level lower.
_PREFETCH_LIMIT_FLOOR = 50


def get_client():
    """Open a connection to the Qdrant instance."""
    return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)


def ensure_schema(client, reset=False):
    """
    Make sure the DocumentChunk collection exists in Qdrant, with a
    named dense vector ("dense", for sentence-transformers embeddings)
    and a named sparse vector ("bm25", for keyword matching).

    reset=True drops and recreates the collection first - see the
    original Weaviate version's docstring for why this must default
    to False once real documents are being ingested.
    """
    exists = client.collection_exists(config.QDRANT_COLLECTION_NAME)

    if exists and not reset:
        return

    if exists and reset:
        client.delete_collection(config.QDRANT_COLLECTION_NAME)
        print(f"🗑️  Dropped existing '{config.QDRANT_COLLECTION_NAME}' collection")

    client.create_collection(
        collection_name=config.QDRANT_COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=config.EMBEDDING_DIMENSIONS,
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(),
        },
    )
    print(f"✅ Created '{config.QDRANT_COLLECTION_NAME}' collection in Qdrant")


def insert_chunks(client, chunks, embeddings, metadata_list):
    """
    Insert chunks + their embeddings into Qdrant.

    metadata_list must be the same length as chunks/embeddings, each
    entry a dict with: document_id, filename, file_type,
    upload_timestamp, page_number, chunk_index.
    """
    points = []
    for chunk, embedding, meta in zip(chunks, embeddings, metadata_list):
        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": embedding.tolist(),
                    "bm25": models.Document(text=chunk, model=_BM25_MODEL),
                },
                payload={"content": chunk, **meta},
            )
        )

    # Batch in chunks of 64 rather than one giant upsert - keeps
    # request/response payloads reasonable for larger documents.
    batch_size = 64
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=config.QDRANT_COLLECTION_NAME,
            points=points[i : i + batch_size],
        )

    print(f"✅ Stored {len(chunks)} chunks in Qdrant")


def query(client, query_vector, query_text, top_k=3, where_filter=None, alpha=0.5):
    """
    Hybrid search: combines BM25 keyword matching with vector
    similarity, fused via Reciprocal Rank Fusion (RRF). See the
    module docstring for how this differs from the old Weaviate
    alpha-weighted approach.

    where_filter, if given, uses the same shape retrieval_service.py
    already builds for Weaviate:
        {"path": ["document_id"], "operator": "Equal", "valueText": "..."}
    translated internally to Qdrant's filter format.

    Returns chunks with `_additional.score` (higher = more relevant),
    matching the shape the old Weaviate version returned so nothing
    downstream needs to change.
    """
    qdrant_filter = _translate_filter(where_filter)
    prefetch_limit = max(top_k * 5, _PREFETCH_LIMIT_FLOOR)

    results = client.query_points(
        collection_name=config.QDRANT_COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=query_vector, using="dense",
                limit=prefetch_limit, filter=qdrant_filter,
            ),
            models.Prefetch(
                query=models.Document(text=query_text, model=_BM25_MODEL), using="bm25",
                limit=prefetch_limit, filter=qdrant_filter,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        query_filter=qdrant_filter,
        with_payload=True,
    )

    return [
        {**point.payload, "_additional": {"score": point.score}}
        for point in results.points
    ]


def list_documents(client):
    """
    Return one summary record per uploaded document, not per chunk.

    Aggregated in Python by scrolling through all points' payloads
    (no vectors, to keep the payload small) and grouping by
    document_id - same approach as the old Weaviate version.
    """
    documents = {}
    next_offset = None

    while True:
        points, next_offset = client.scroll(
            collection_name=config.QDRANT_COLLECTION_NAME,
            limit=1000,
            offset=next_offset,
            with_payload=["document_id", "filename", "file_type", "upload_timestamp"],
            with_vectors=False,
        )
        for point in points:
            doc_id = point.payload["document_id"]
            if doc_id not in documents:
                documents[doc_id] = {
                    "document_id": doc_id,
                    "filename": point.payload["filename"],
                    "file_type": point.payload["file_type"],
                    "upload_timestamp": point.payload["upload_timestamp"],
                    "chunk_count": 0,
                }
            documents[doc_id]["chunk_count"] += 1

        if next_offset is None:
            break

    return sorted(documents.values(), key=lambda d: d["upload_timestamp"], reverse=True)


def delete_document(client, document_id):
    """Delete every chunk belonging to one document."""
    client.delete(
        collection_name=config.QDRANT_COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=document_id),
                )]
            )
        ),
    )


def _translate_filter(where_filter):
    """
    Translate the one Weaviate-shaped filter this codebase actually
    produces (retrieval_service.py's _document_id_filter) into a
    Qdrant Filter. Raises rather than silently ignoring anything else,
    since a silently-dropped filter would mean chunks from unrelated
    documents leaking into results - the exact bug retrieval_service.py
    was written to prevent.
    """
    if where_filter is None:
        return None

    if (
        where_filter.get("path") == ["document_id"]
        and where_filter.get("operator") == "Equal"
        and "valueText" in where_filter
    ):
        return models.Filter(
            must=[models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=where_filter["valueText"]),
            )]
        )

    raise ValueError(f"Unrecognized where_filter shape, can't translate to Qdrant: {where_filter}")