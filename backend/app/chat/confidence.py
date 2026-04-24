from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: float
    token_count: int


@dataclass
class ConfidenceAssessment:
    sufficient: bool
    reason: str
    top_similarity: float
    avg_similarity: float


def assess_confidence(
    chunks: list[RetrievedChunk],
    min_top_similarity: float,
    min_avg_similarity: float,
    avg_window: int,
) -> ConfidenceAssessment:
    if not chunks:
        return ConfidenceAssessment(
            sufficient=False,
            reason="no results found in corpus",
            top_similarity=0.0,
            avg_similarity=0.0,
        )
    top = chunks[0].score
    window = chunks[:avg_window]
    avg = sum(c.score for c in window) / len(window)

    if top < min_top_similarity:
        return ConfidenceAssessment(
            sufficient=False,
            reason=f"top similarity {top:.3f} is below threshold {min_top_similarity:.3f}",
            top_similarity=top,
            avg_similarity=avg,
        )
    if avg < min_avg_similarity:
        return ConfidenceAssessment(
            sufficient=False,
            reason=f"average similarity {avg:.3f} is below threshold {min_avg_similarity:.3f}",
            top_similarity=top,
            avg_similarity=avg,
        )
    return ConfidenceAssessment(
        sufficient=True,
        reason="ok",
        top_similarity=top,
        avg_similarity=avg,
    )
