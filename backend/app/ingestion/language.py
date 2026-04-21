from lingua import Language, LanguageDetectorBuilder

# Built once at import time — read-only thereafter, safe for concurrent use
_detector = (
    LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.GREEK)
    .with_minimum_relative_distance(0.2)
    .build()
)


def detect_language(text: str) -> str | None:
    if not text or not text.strip():
        return None
    sample = text[:5000]
    result = _detector.detect_language_of(sample)
    if result is None:
        return None
    return result.iso_code_639_1.name.lower()
