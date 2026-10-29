import re

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_INLINE_WHITESPACE = re.compile(r"[^\S\n]+")


def normalize_extracted_text(raw: str) -> str:
    """Normalize whitespace while keeping paragraphs and line-oriented structure."""
    if not raw:
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    joined = "\n".join(lines)
    joined = _MULTI_BLANK_LINES.sub("\n\n", joined)

    normalized_lines: list[str] = []
    for line in joined.split("\n"):
        if not line.strip():
            normalized_lines.append("")
            continue
        normalized_lines.append(_INLINE_WHITESPACE.sub(" ", line).strip())

    result = "\n".join(normalized_lines).strip()
    return _MULTI_BLANK_LINES.sub("\n\n", result)
