"""Text processing for OCR results."""

import re

# === Japanese character Unicode ranges ===
_JP_CHARS = r"\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uFF00-\uFFEF\u3000-\u303F"

_JAPANESE_SPACING_PATTERN = re.compile(rf"(?<=[{_JP_CHARS}])\s+(?=[{_JP_CHARS}])")


def remove_japanese_spaces(text: str) -> str:
    """
    Remove unnecessary spaces between Japanese characters.

    "わ た し" -> "わたし"
    "Hello World" -> "Hello World" (English unchanged)
    """
    return _JAPANESE_SPACING_PATTERN.sub("", text)


# === Line break rules (optimized for LLM RAG) ===

_BULLET_PATTERN = re.compile(r"^[・･●■▶▷◆◇○◎★☆\-‐－―]+")

_NUMBERED_PATTERN = re.compile(
    r"^([0-9]+[\.\-][0-9]*|"
    r"\([0-9]+\)|"
    r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|"
    r"[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]|"
    r"[a-z]\)|"
    r"[A-Z]\.)"
)

_CHAPTER_PATTERN = re.compile(
    r"^(第[0-9一二三四五六七八九十百千]+[章節編部話回]|"
    r"Chapter\s*[0-9]+|CHAPTER\s*[0-9]+|"
    r"Section\s*[0-9]+|SECTION\s*[0-9]+|"
    r"はじめに|おわりに|まとめ|序章|終章|"
    r"目次|索引|参考文献|付録|あとがき|謝辞|著者紹介)$",
    re.IGNORECASE,
)


def _should_break_before(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _BULLET_PATTERN.match(stripped):
        return True
    if _NUMBERED_PATTERN.match(stripped):
        return True
    if _CHAPTER_PATTERN.match(stripped):
        return True
    return False


def _should_break_after(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.endswith("。"):
        return True
    if _CHAPTER_PATTERN.match(stripped):
        return True
    return False


def _should_keep_line_break(current_line: str, next_line: str | None) -> bool:
    """
    Determine whether to keep a line break after the current line.

    For LLM RAG optimization:
    - After period "。" -> keep break
    - Before bullet/number/chapter -> keep break
    - Otherwise -> merge
    """
    if next_line is None:
        return True

    next_stripped = next_line.strip()
    if not next_stripped:
        return True
    if _should_break_after(current_line):
        return True
    if _should_break_before(next_stripped):
        return True
    return False


def merge_line_text(line: list[tuple[str, float, tuple[float, float, float, float]]]) -> str:
    """
    Merge text within a single line.

    Japanese characters are joined without spaces.
    """
    texts = [result[0] for result in line]
    merged = "".join(texts)
    return remove_japanese_spaces(merged)


def merge_paragraph_lines(lines: list[str]) -> str:
    """
    Remove mid-sentence line breaks and merge by paragraph.

    Args:
        lines: List of text lines

    Returns:
        Text merged by paragraph
    """
    if not lines:
        return ""

    result_parts: list[str] = []
    current_paragraph: list[str] = []

    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else None
        current_paragraph.append(line)

        if _should_keep_line_break(line, next_line):
            result_parts.append("".join(current_paragraph))
            current_paragraph = []

    if current_paragraph:
        result_parts.append("".join(current_paragraph))

    return "\n".join(result_parts)
