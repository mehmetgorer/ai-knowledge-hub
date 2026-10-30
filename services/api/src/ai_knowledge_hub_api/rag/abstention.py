"""Server-side abstention messages (fail-closed; never trust model text)."""


def build_insufficient_sources_answer(question: str) -> str:
    normalized = question.strip()
    if any("\u0400" <= char <= "\u04ff" for char in normalized):
        return (
            "Seçili koleksiyonda bu soruyu yanıtlamak için yeterli kaynak bulunamadı."
        )
    if any("\u0600" <= char <= "\u06ff" for char in normalized):
        return "لم أجد مصادر كافية في المجموعة المحددة للإجابة على هذا السؤال."
    lower = normalized.casefold()
    turkish_hints = ("ğ", "ı", "ş", "ç", "ö", "ü", " ve ", " bir ", " nedir")
    if any(hint in lower for hint in turkish_hints):
        return (
            "Seçili koleksiyonda bu soruyu yanıtlamak için yeterli kaynak bulunamadı."
        )
    return (
        "No sufficient sources were found in the selected collection to answer "
        "this question."
    )
