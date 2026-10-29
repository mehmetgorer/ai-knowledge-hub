import re

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_INLINE_WHITESPACE = re.compile(r"[^\S\n]+")
_FENCED_CODE_BLOCK = re.compile(
    r"(^```[^\n]*\n.*?^```\s*$|^~~~[^\n]*\n.*?^~~~\s*$)",
    re.MULTILINE | re.DOTALL,
)


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


def _normalize_markdown_prose(prose: str) -> str:
    if not prose:
        return ""

    lines = [line.rstrip() for line in prose.split("\n")]
    joined = "\n".join(lines)
    joined = _MULTI_BLANK_LINES.sub("\n\n", joined)

    normalized_lines: list[str] = []
    for line in joined.split("\n"):
        if not line.strip():
            normalized_lines.append("")
            continue
        indent_match = re.match(r"^(\s+)(.*)$", line)
        if indent_match:
            indent, rest = indent_match.groups()
            rest_normalized = _INLINE_WHITESPACE.sub(" ", rest.rstrip())
            normalized_lines.append(indent + rest_normalized)
        else:
            normalized_lines.append(_INLINE_WHITESPACE.sub(" ", line).strip())

    result = "\n".join(normalized_lines)
    return _MULTI_BLANK_LINES.sub("\n\n", result)


def normalize_markdown_text(raw: str) -> str:
    """
    Normalize Markdown prose whitespace while preserving fenced code blocks,
    code indentation, nested list indentation and paragraph breaks.
    """
    if not raw:
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    parts: list[str] = []
    last_index = 0
    for match in _FENCED_CODE_BLOCK.finditer(text):
        if match.start() > last_index:
            parts.append(_normalize_markdown_prose(text[last_index : match.start()]))
        parts.append(match.group(0))
        last_index = match.end()
    if last_index < len(text):
        parts.append(_normalize_markdown_prose(text[last_index:]))

    combined = "".join(parts)
    return combined.strip()
