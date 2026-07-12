"""
Fine-tune the sentence-transformers embedding model on vero's own
documents, using PyTorch under the hood (sentence-transformers is a
PyTorch library - training this counts as real PyTorch experience).

WHY THIS EXISTS
----------------
retrieval_service.py already has to work around same-template chunks
(the "Day N" regex boost in _boost_exact_day_match) because the base
all-MiniLM-L6-v2 model embeds "Day 2" and "Day 4" chunks almost
identically - they share the same "Learn / Build / Interview Q"
headings, so generic semantic similarity doesn't separate them well.

That regex boost is a good, cheap patch. Fine-tuning the embedding
model on your own chunks is the complementary fix: it teaches the
model itself to pull matching-day queries and chunks closer together
and push other-day chunks apart, so retrieval is stronger even before
the regex boost kicks in, and it generalizes to documents that don't
happen to have a clean day-number regex signal.

WHAT THIS SCRIPT DOES
----------------------
1. Pulls every chunk out of your live Qdrant collection (same one
   app.py reads from) - no separate export step needed.
2. Builds (anchor, positive, negative) training triplets:
     - Chunks matching "### Day N: <title>" headings get an anchor
       query like "day 2", paired with their own chunk as the
       positive, and a same-document different-day chunk as a hard
       negative (this directly targets the Day 2 vs Day 4 confusion).
     - All other chunks fall back to a generic filename-based anchor
       query, paired with themselves as positive and a random chunk
       from a *different* document as negative. Keeps the model from
       overfitting only to the day-numbered structure.
3. Fine-tunes all-MiniLM-L6-v2 with MultipleNegativesRankingLoss
   (the standard sentence-transformers loss for exactly this
   anchor/positive/negative shape).
4. Saves the fine-tuned model to ./fine_tuned_embedding_model.

HOW TO RUN
----------
Needs your real QDRANT_URL / QDRANT_API_KEY in .env (same ones app.py
already uses), so run this from your own machine, not a sandbox:

    cd rag_chatbot_app/backend
    pip install sentence-transformers torch
    python finetune_embeddings.py

If you have more than a few hundred chunks, this is faster on a free
Colab GPU: zip this backend/ folder (or just this file + your .env
values), upload to Colab, `!pip install sentence-transformers`, run.
CPU works fine for the chunk counts a personal RAG project has -
expect a few minutes, not hours.

AFTER TRAINING
---------------
1. Point config.py's EMBEDDING_MODEL_NAME at the saved folder, e.g.
   in .env:  EMBEDDING_MODEL_NAME=./fine_tuned_embedding_model
2. Re-ingest your documents (the vectors need to be recomputed with
   the new model - old vectors and new vectors aren't comparable).
   Easiest path: drop the Qdrant collection (ensure_schema(reset=True))
   and re-upload your documents through the app.
3. Compare retrieval quality on the same day-number queries that
   originally exposed the ranking bug, with and without the model
   swap, to have a concrete before/after for your resume/interview
   story.
"""
import random
import re

from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
    losses,
)
from datasets import Dataset

import config
import vectorstore

_DAY_RE = re.compile(r"###\s*Day\s*(\d+)\s*:?\s*(.*)", re.IGNORECASE)

BASE_MODEL = config.EMBEDDING_MODEL_NAME if config.EMBEDDING_MODEL_NAME != "./fine_tuned_embedding_model" else "all-MiniLM-L6-v2"
OUTPUT_DIR = "./fine_tuned_embedding_model"


def fetch_all_chunks():
    """Scroll every chunk out of the live Qdrant collection."""
    client = vectorstore.get_client()
    chunks = []
    next_offset = None

    while True:
        points, next_offset = client.scroll(
            collection_name=config.QDRANT_COLLECTION_NAME,
            limit=1000,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload
            chunks.append({
                "content": payload["content"],
                "document_id": payload["document_id"],
                "filename": payload["filename"],
            })
        if next_offset is None:
            break

    return chunks


def build_training_triplets(chunks):
    """
    Returns a list of dicts: {"anchor": ..., "positive": ..., "negative": ...}

    Day-numbered chunks get a targeted hard negative (a different-day
    chunk from the SAME document - the exact confusion the regex
    boost was written to fix). Everything else gets a random
    different-document chunk as a generic negative.
    """
    # Group chunks by document for same-doc negative sampling.
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c["document_id"], []).append(c)

    day_chunks = []  # (chunk, day_number)
    for c in chunks:
        m = _DAY_RE.search(c["content"])
        if m:
            day_chunks.append((c, m.group(1)))

    triplets = []

    # Day-numbered chunks: hard negatives from the same doc, other days.
    for chunk, day_num in day_chunks:
        same_doc_other_days = [
            oc for oc, od in day_chunks
            if oc["document_id"] == chunk["document_id"] and od != day_num
        ]
        if not same_doc_other_days:
            continue
        negative = random.choice(same_doc_other_days)
        for anchor in (f"day {day_num}", f"what did I learn on day {day_num}"):
            triplets.append({
                "anchor": anchor,
                "positive": chunk["content"],
                "negative": negative["content"],
            })

    # Everything else: generic filename-based anchor, cross-document negative.
    doc_ids = list(by_doc.keys())
    for c in chunks:
        other_doc_ids = [d for d in doc_ids if d != c["document_id"]]
        if not other_doc_ids:
            continue
        negative_doc = random.choice(other_doc_ids)
        negative = random.choice(by_doc[negative_doc])
        anchor = f"information from {c['filename']}"
        triplets.append({
            "anchor": anchor,
            "positive": c["content"],
            "negative": negative["content"],
        })

    random.shuffle(triplets)
    return triplets


def train(triplets, base_model=BASE_MODEL, output_dir=OUTPUT_DIR, epochs=3):
    if not triplets:
        raise ValueError(
            "No training triplets built - need at least a couple of "
            "documents with more than one chunk in Qdrant first."
        )

    model = SentenceTransformer(base_model)
    train_dataset = Dataset.from_list(triplets)
    loss = losses.MultipleNegativesRankingLoss(model)

    args = SentenceTransformerTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=16,
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="no",
    )

    trainer = SentenceTransformerTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        loss=loss,
    )
    trainer.train()

    model.save(output_dir)
    print(f"✅ Fine-tuned model saved to {output_dir}")
    return model


if __name__ == "__main__":
    print("Fetching chunks from Qdrant...")
    chunks = fetch_all_chunks()
    print(f"  {len(chunks)} chunks across {len({c['document_id'] for c in chunks})} documents")

    print("Building training triplets...")
    triplets = build_training_triplets(chunks)
    print(f"  {len(triplets)} (anchor, positive, negative) triplets")

    print("Training...")
    train(triplets)