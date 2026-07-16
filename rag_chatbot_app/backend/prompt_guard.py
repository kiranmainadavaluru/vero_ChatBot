"""
Prompt-injection pattern checks on chat input (Day 6 of the
enhancement plan).

This is a regex/keyword pass over the raw user question, run before
it ever reaches agent_service.run_agent() or crew_service.run_crew().
It exists as a cheap first line of defense, not a complete one -
worth being explicit about that distinction if this comes up in an
interview:

  - What this catches: known, literal injection phrasings - "ignore
    previous instructions", "reveal your system prompt", role-override
    attempts ("you are now DAN"), delimiter/context-escape tricks
    (fake "```system" blocks, "[END OF USER INPUT]" markers). These
    are the patterns that show up in essentially every public
    prompt-injection writeup and jailbreak-prompt collection.
  - What this does NOT catch: novel phrasings, injection written in
    another language, paraphrased/obfuscated attacks (base64,
    zero-width characters, homoglyphs), or *indirect* injection -
    instructions smuggled inside an uploaded document's text that
    the Retrieval Agent then feeds back to the Answer Agent. That
    last one is a real, documented class of RAG-specific attack and
    is a known gap here, not an oversight - a robust defense against
    it needs either a classifier model or treating retrieved content
    as data-only via strict prompt structuring, which is a bigger
    change than a Day-6 scope item.

Blocking is enforced in code (a short-circuit before the LLM call in
main.py), not left to a prompt instruction telling the model to
"refuse suspicious requests" - same reasoning as the strict_mode
short-circuit in agent_service.py/crew_service.py: a prompt is a
strong nudge, an if-statement is a guarantee.
"""
import re

# Each entry: (label, compiled pattern). Patterns are intentionally
# broad-but-specific phrase matches rather than single keywords
# ("ignore" alone would false-positive on "please ignore the typo in
# my last message") - every pattern below requires the
# instruction-override *shape*, not just an isolated trigger word.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
            r"(previous|prior|above|earlier|all|your)\b[^.\n]{0,20}\b"
            r"(instructions?|rules?|prompt|guidelines?|directives?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_exfiltration",
        re.compile(
            r"\b(reveal|show|print|output|repeat|display|leak)\b[^.\n]{0,20}\b"
            r"(your|the)\b[^.\n]{0,20}\b(system prompt|instructions|rules|configuration)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(you are now|act as if you|pretend (you|to be)|from now on you are|"
            r"enter (developer|dan|god) mode|jailbreak|do anything now)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "restriction_removal",
        re.compile(
            r"\b(no (restrictions|limits|filters|rules)|"
            r"without (any )?(restrictions|limits|filters|rules|censorship)|"
            r"unfiltered|uncensored)\b.{0,20}\b(mode|now|version|response)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "delimiter_escape",
        re.compile(
            r"(```\s*system|\[\s*system\s*\]|###\s*system|<\s*/?system\s*>|"
            r"\[\s*end of (user )?(input|prompt|context)\s*\])",
            re.IGNORECASE,
        ),
    ),
]


def check_prompt_injection(text: str) -> dict:
    """
    Returns {"flagged": bool, "matched_patterns": [labels]}.
    Pure pattern matching, no model call - deliberately cheap so it
    can run on every message with no latency/cost impact.
    """
    if not text:
        return {"flagged": False, "matched_patterns": []}

    matched = [label for label, pattern in _PATTERNS if pattern.search(text)]
    return {"flagged": bool(matched), "matched_patterns": matched}
