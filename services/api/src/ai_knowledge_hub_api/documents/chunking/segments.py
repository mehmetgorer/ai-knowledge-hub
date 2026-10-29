import re

from ai_knowledge_hub_api.documents.chunking.errors import ChunkingConfigurationError

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
    if max_characters < 1:
        raise ValueError("max_characters must be at least 1")
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
    return _enforce_part_lengths(parts, max_characters=max_characters)


def _enforce_part_lengths(parts: list[str], *, max_characters: int) -> list[str]:
    enforced: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        if len(part) <= max_characters:
            enforced.append(part)
        else:
            enforced.extend(_hard_split(part, max_characters=max_characters))
    return enforced


def _fence_shell_length(opener: str, closer: str) -> int:
    return len(opener) + 1 + len(closer)


def _fenced_code_cannot_fit(max_characters: int, opener: str, closer: str) -> None:
    shell_len = _fence_shell_length(opener, closer)
    raise ChunkingConfigurationError(
        "max_characters is too small to preserve Markdown fenced code "
        f"(fence shell requires at least {shell_len} characters)"
    )


def _split_code_block(block: str, *, max_characters: int) -> list[str]:
    lines = block.split("\n")
    if not lines:
        return _hard_split(block, max_characters=max_characters)

    opener = lines[0]
    has_closing_fence = lines[-1].strip().startswith(("```", "~~~"))
    closer = lines[-1] if has_closing_fence else "```"
    body_lines = lines[1:-1] if has_closing_fence else lines[1:]

    shell = _fence_shell_length(opener, closer)
    if shell > max_characters or max_characters < 4:
        _fenced_code_cannot_fit(max_characters, opener, closer)

    inner_limit = max_characters - shell - 1
    if inner_limit < 1:
        _fenced_code_cannot_fit(max_characters, opener, closer)

    if len(opener) + 1 + len(closer) > max_characters:
        _fenced_code_cannot_fit(max_characters, opener, closer)

    chunks: list[str] = []
    current_body: list[str] = []
    current_len = shell

    for line in body_lines:
        line_len = len(line) + (1 if current_body else 0)
        if current_body and current_len + line_len > max_characters:
            piece = "\n".join([opener, *current_body, closer])
            if len(piece) > max_characters:
                raise ValueError("Generated fenced chunk exceeds max_characters")
            chunks.append(piece)
            current_body = []
            current_len = shell

        single_line_piece = "\n".join([opener, line, closer])
        if len(single_line_piece) > max_characters:
            for piece in _hard_split(line, max_characters=inner_limit):
                wrapped = "\n".join([opener, piece, closer])
                if len(wrapped) > max_characters:
                    _fenced_code_cannot_fit(max_characters, opener, closer)
                chunks.append(wrapped)
            continue

        current_body.append(line)
        current_len = len("\n".join([opener, *current_body, closer]))

    if current_body:
        piece = "\n".join([opener, *current_body, closer])
        if len(piece) > max_characters:
            for line in current_body:
                chunks.extend(
                    _hard_split(
                        "\n".join([opener, line, closer]),
                        max_characters=max_characters,
                    )
                )
        else:
            chunks.append(piece)

    if not chunks:
        minimal = "\n".join([opener, closer])
        if len(minimal) <= max_characters:
            return [minimal]
        _fenced_code_cannot_fit(max_characters, opener, closer)

    return _enforce_part_lengths(chunks, max_characters=max_characters)


def _hard_split(text: str, *, max_characters: int) -> list[str]:
    if max_characters < 1:
        return [text]
    return [text[i : i + max_characters] for i in range(0, len(text), max_characters)]
