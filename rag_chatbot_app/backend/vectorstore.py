"""
Weaviate integration.

All vector-database concerns — connecting, defining the schema,
inserting chunks, and querying — live here, separate from Flask
routes and business logic. Nothing in this module knows about
HTTP requests; it only knows about chunks and vectors.
"""
import weaviate

import config


def get_client():
    """Open a connection to the Weaviate instance."""
    client = weaviate.Client(config.WEAVIATE_URL)
    return client


def ensure_schema(client, reset=False):
    """
    Make sure the DocumentChunk class exists in Weaviate.

    reset=True drops and recreates the class first. This is only safe
    while we're still ingesting a single throwaway sample PDF on every
    startup (current behavior). Once real multi-document upload exists
    (a later step), this must default to False so uploaded documents
    aren't wiped every time the server restarts.
    """
    class_exists = client.schema.exists(config.WEAVIATE_CLASS_NAME)

    if class_exists and not reset:
        return

    if class_exists and reset:
        client.schema.delete_class(config.WEAVIATE_CLASS_NAME)
        print(f"🗑️  Dropped existing '{config.WEAVIATE_CLASS_NAME}' class")

    schema = {
        "class": config.WEAVIATE_CLASS_NAME,
        "description": "A single chunk of text extracted from an uploaded document",
        "vectorizer": "none",  # embeddings are generated ourselves via sentence-transformers
        "properties": [
            {
                "name": "content",
                "dataType": ["text"],
                "description": "The chunk's raw text",
            },
            {
                "name": "document_id",
                "dataType": ["text"],
                "description": "UUID grouping all chunks belonging to the same uploaded document",
            },
            {
                "name": "filename",
                "dataType": ["text"],
                "description": "Original filename as uploaded by the user",
            },
            {
                "name": "file_type",
                "dataType": ["text"],
                "description": "File extension without the dot, e.g. 'pdf', 'docx', 'csv'",
            },
            {
                "name": "upload_timestamp",
                "dataType": ["date"],
                "description": "RFC3339 timestamp of when the document was uploaded",
            },
            {
                "name": "page_number",
                "dataType": ["int"],
                "description": "Page number this chunk came from. -1 for formats without pages",
            },
            {
                "name": "chunk_index",
                "dataType": ["int"],
                "description": "0-based position of this chunk within its document",
            },
        ],
    }

    client.schema.create_class(schema)
    print(f"✅ Created '{config.WEAVIATE_CLASS_NAME}' class in Weaviate")


def insert_chunks(client, chunks, embeddings, metadata_list):
    """
    Insert chunks + their embeddings into Weaviate.

    metadata_list must be the same length as chunks/embeddings, each
    entry a dict with: document_id, filename, file_type,
    upload_timestamp, page_number, chunk_index.
    """
    with client.batch as batch:
        batch.batch_size = 10
        for chunk, embedding, meta in zip(chunks, embeddings, metadata_list):
            data_object = {"content": chunk, **meta}
            batch.add_data_object(
                data_object=data_object,
                class_name=config.WEAVIATE_CLASS_NAME,
                vector=embedding.tolist(),
            )

    print(f"✅ Stored {len(chunks)} chunks in Weaviate")


def query(client, query_vector, top_k=3, where_filter=None):
    """
    Run a nearest-neighbor search.

    where_filter is an optional Weaviate `where` clause dict, used in
    a later step to restrict retrieval to a specific document.
    """
    builder = (
        client.query
        .get(config.WEAVIATE_CLASS_NAME, [
            "content", "document_id", "filename", "file_type",
            "upload_timestamp", "page_number", "chunk_index",
        ])
        .with_near_vector({"vector": query_vector})
        .with_limit(top_k)
        .with_additional(["distance"])
    )

    if where_filter:
        builder = builder.with_where(where_filter)

    result = builder.do()
    return result["data"]["Get"][config.WEAVIATE_CLASS_NAME]


def list_documents(client):
    """
    Return one summary record per uploaded document, not per chunk.

    Aggregated in Python by pulling metadata fields (no `content`, to
    keep the payload small) and grouping by document_id - simpler and
    plenty fast at this app's scale than Weaviate's GraphQL
    aggregate/group-by API.
    """
    result = (
        client.query
        .get(config.WEAVIATE_CLASS_NAME, [
            "document_id", "filename", "file_type", "upload_timestamp",
        ])
        .with_limit(10000)
        .do()
    )
    chunks = result["data"]["Get"][config.WEAVIATE_CLASS_NAME]

    documents = {}
    for chunk in chunks:
        doc_id = chunk["document_id"]
        if doc_id not in documents:
            documents[doc_id] = {
                "document_id": doc_id,
                "filename": chunk["filename"],
                "file_type": chunk["file_type"],
                "upload_timestamp": chunk["upload_timestamp"],
                "chunk_count": 0,
            }
        documents[doc_id]["chunk_count"] += 1

    return sorted(documents.values(), key=lambda d: d["upload_timestamp"], reverse=True)


def delete_document(client, document_id):
    """Delete every chunk belonging to one document."""
    client.batch.delete_objects(
        class_name=config.WEAVIATE_CLASS_NAME,
        where={
            "path": ["document_id"],
            "operator": "Equal",
            "valueText": document_id,
        },
    )