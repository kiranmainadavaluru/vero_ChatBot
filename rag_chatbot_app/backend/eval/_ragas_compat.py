"""
Workaround for a live upstream bug: ragas has an unconditional,
top-level import of ChatVertexAI from a langchain_community path that
langchain-community removed in its 0.4.x line (ChatVertexAI moved to
the separate langchain-google-vertexai package). See
https://github.com/vibrantlabsai/ragas/issues/2745 - confirmed by
hitting this directly while building this harness, not a hypothetical.

This project doesn't use Vertex AI at all - Gemini is called through
its OpenAI-compatible endpoint (config.GEMINI_BASE_URL) - so the
import is genuinely dead code on our path. Two lines of defense:

  1. requirements-eval.txt pins ragas==0.3.9, the version confirmed
     (by the same GitHub issue) to predate this break.
  2. This module stubs the missing import path in sys.modules before
     ragas is imported anywhere, so a future transitive dependency
     bump that reintroduces the problem degrades gracefully instead
     of hard-crashing at import time.

Import this module before importing anything from `ragas` -
ragas_eval.py does this as its very first import.
"""
import sys
import types


def apply():
    if "langchain_community.chat_models.vertexai" in sys.modules:
        return

    stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # pragma: no cover - never actually invoked
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "ChatVertexAI stub reached - this project doesn't use Vertex AI "
                "(Gemini goes through the OpenAI-compatible endpoint). If you're "
                "seeing this, something is trying to use Vertex AI for real."
            )

    stub.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = stub


apply()
