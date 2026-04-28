MEMORY_EXTRACTION_PROMPT = """\
You are reviewing a conversation between a user and an assistant about a team's code and \
documentation. Extract durable facts that would be useful in *future* conversations on the \
same topic.

Include:
- Decisions made ("we chose X over Y because Z")
- Configurations or values agreed on ("the threshold is 0.25")
- Relationships between things ("module A depends on module B")
- Gotchas or non-obvious behaviour ("this fails silently if X is null")
- Specific names, IDs, paths, file locations

Exclude:
- Small talk, pleasantries
- Clarification questions and their answers (unless the answer is itself a durable fact)
- Anything time-sensitive ("today," "this morning," "the bug we just fixed")
- Anything the user explicitly retracted

Output JSON with this exact structure:
{
  "title": "3-7 word summary of what this note is about",
  "facts": [
    {"content": "A single durable fact in Markdown.", "source_message_indices": [3, 7]},
    ...
  ]
}

Return only the JSON, no other text.\
"""

MEMORY_EXTRACTION_FALLBACK_PROMPT = """\
You are reviewing a conversation between a user and an assistant about a team's code and \
documentation. Write a short Markdown note capturing the key durable facts: decisions made, \
configurations agreed on, important relationships, and non-obvious gotchas. \
Skip small talk and anything time-sensitive. \
Start the note with a # heading (3-7 words) summarising the topic.\
"""

GAP_ANALYSIS_PROMPT = """\
A user asked a question that the indexed documents could not answer with confidence. \
Your job is to characterize what's missing.

User's question: {query}

Closest existing chunks (low similarity, but the best we have):
{chunks_block}

Analyze the gap and respond with JSON:
{{
  "missing_topic": "short phrase naming what would answer this question",
  "related_topics_present": ["topic 1 from existing chunks", "topic 2"],
  "suggested_document_types": ["type 1", "type 2"]
}}

Examples of suggested_document_types: "API reference", "architecture diagram", \
"deployment runbook", "code module documentation", "design decision record".

Return only the JSON, no other text.\
"""
