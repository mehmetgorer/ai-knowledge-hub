import re

_FENCED_CODE_BLOCK = re.compile(
    r"(^```[^\n]*\n.*?^```\s*$|^~~~[^\n]*\n.*?^~~~\s*$)",
    re.MULTILINE | re.DOTALL,
)
_HEADING_LINE = re.compile(r"^#{1,6}\s+\S")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+")


def split_markdown_units(text: str) -> list[str]:
    if not text.strip():
        return []

    units: list[str] = []
    last_index = 0
    for match in _FENCED_CODE_BLOCK.finditer(text):
        if match.start() > last_index:
            units.extend(_split_prose_units(text[last_index : match.start()]))
        units.append(match.group(0).strip("\n"))
        last_index = match.end()
    if last_index < len(text):
        units.extend(_split_prose_units(text[last_index:]))

    return [unit for unit in units if unit.strip()]


def split_plain_units(text: str) -> list[str]:
    if not text.strip():
        return []
    return _split_prose_units(text)


def _split_prose_units(prose: str) -> list[str]:
    blocks = re.split(r"\n\n+", prose.strip())
    merged: list[str] = []
    index = 0
    while index < len(blocks):
        block = blocks[index].strip()
        if not block:
            index += 1
            continue
        if _HEADING_LINE.match(block) and index + 1 < len(blocks):
            next_block = blocks[index + 1].strip()
            if next_block and not _HEADING_LINE.match(next_block):
                merged.append(f"{block}\n\n{next_block}")
                index += 2
                continue
        merged.append(block)
        index += 1
    return merged


def split_oversized_unit(unit: str, *, max_characters: int) -> list[str]:
    if len(unit) <= max_characters:
        return [unit]

    if unit.startswith("```") or unit.startswith("~~~"):
        return _split_code_block(unit, max_characters=max_characters)

    parts: list[str] = []
    for paragraph in re.split(r"\n\n+", unit):
        if len(paragraph) <= max_characters:
            parts.append(paragraph)
            continue
        sentences = _SENTENCE_BOUNDARY.split(paragraph)
        buffer = ""
        for sentence in sentences:
            candidate = sentence if not buffer else f"{buffer} {sentence}"
            if len(candidate) <= max_characters:
                buffer = candidate
                continue
            if buffer:
                parts.append(buffer.strip())
                buffer = ""
            if len(sentence) <= max_characters:
                buffer = sentence
                continue
            parts.extend(_hard_split(sentence, max_characters=max_characters))
        if buffer.strip():
            parts.append(buffer.strip())
    return [part for part in parts if part.strip()]


def _split_code_block(block: str, *, max_characters: int) -> list[str]:
    lines = block.split("\n")
    if not lines:
        return _hard_split(block, max_characters=max_characters)

    opener = lines[0]
    has_closing_fence = lines[-1].strip().startswith(("```", "~~~"))
    closer = lines[-1] if has_closing_fence else "```"
    body_lines = lines[1:-1] if has_closing_fence else lines[1:]

    chunks: list[str] = []
    current_body: list[str] = []
    current_len = len(opener) + 1 + len(closer)

    for line in body_lines:
        line_len = len(line) + 1
        if current_body and current_len + line_len > max_characters:
            chunks.append("\n".join([opener, *current_body, closer]))
            current_body = []
            current_len = len(opener) + 1 + len(closer)
        if len(opener) + 1 + line_len + 1 + len(closer) > max_characters:
            for piece in _hard_split(
                line, max_characters=max_characters - len(opener) - len(closer) - 4
            ):
                chunks.append("\n".join([opener, piece, closer]))
            continue
        current_body.append(line)
        current_len += line_len

    if current_body:
        chunks.append("\n".join([opener, *current_body, closer]))
    return chunks


def _hard_split(text: str, *, max_characters: int) -> list[str]:
    if max_characters < 1:
        return [text]
    return [text[i : i + max_characters] for i in range(0, len(text), max_characters)]
