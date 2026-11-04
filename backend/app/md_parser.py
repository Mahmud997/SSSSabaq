"""Разбор Markdown-ответа AI в структуру модулей и частей (текст / таблица).

Модуль намеренно не зависит от FastAPI и БД, чтобы его можно было тестировать отдельно.
"""
import re

_SEP_LINE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_BR = re.compile(r"<br\s*/?>", re.I)
_MODULE_WORD = re.compile(r"^(?:модуль|module|модул)\s*[№#]?\s*", re.I)
_CHECKLIST = re.compile(r"чек-?\s?лист|checklist|самопровер|тексеру|текшириш", re.I)


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells = re.split(r"(?<!\\)\|", s)
    return [_BR.sub("\n", c.replace("\\|", "|")).strip() for c in cells]


def _is_table_line(line: str) -> bool:
    return line.strip().startswith("|")


def parse_parts(text: str) -> list[dict]:
    """Преобразует Markdown в список частей: {'type':'text'|'table', ...}."""
    parts: list[dict] = []
    buf: list[str] = []
    table: list[str] = []
    in_fence = False

    def flush_text():
        t = "\n".join(buf).strip("\n")
        if t.strip():
            parts.append({"type": "text", "text": t})
        buf.clear()

    def flush_table():
        if not table:
            return
        lines = list(table)
        table.clear()
        data = [l for l in lines if not _SEP_LINE.match(l)]
        if len(lines) < 2 or len(data) < 1:
            buf.extend(lines)  # одиночная строка с «|» — это обычный текст
            return
        flush_text()
        rows = [_split_row(l) for l in data]
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        parts.append({"type": "table", "header": rows[0], "rows": rows[1:]})

    for line in (text or "").replace("\r\n", "\n").split("\n"):
        if line.strip().startswith("```"):
            flush_table()
            in_fence = not in_fence
            buf.append(line)
            continue
        if not in_fence and _is_table_line(line):
            table.append(line)
            continue
        flush_table()
        buf.append(line)
    flush_table()
    flush_text()
    return parts


def _module_marker(line: str):
    """Возвращает (номер, заголовок), если строка — заголовок модуля 1–5."""
    s = line.strip()
    if not s or len(s) > 200:
        return None
    marked = s.startswith(("#", "**", "__")) or bool(_MODULE_WORD.match(s))
    if not marked:
        return None
    core = re.sub(r"^[#\s*_]+", "", s)
    word = _MODULE_WORD.match(core)
    if word:
        rest = core[word.end():]
        m = re.match(r"([1-5])(?:\s*[.):—–\-]\s*|\s+|$)", rest)
    else:
        rest = core
        m = re.match(r"([1-5])\s*[.):—–\-]\s*", rest)
    if not m:
        return None
    title = re.sub(r"[\s*_#]+$", "", core).strip()
    return int(m.group(1)), title


def _is_checklist_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 160 or not s.startswith(("#", "**", "__")):
        return False
    return bool(_CHECKLIST.search(s))


def parse_generated_blocks(text: str):
    """Делит ответ AI на модули 1–5 и дополнительные разделы.

    Возвращает список {'module': int|None, 'heading': str, 'parts': [...]} или None,
    если структура не распознана (найдено меньше двух модулей).
    """
    lines = (text or "").replace("\r\n", "\n").split("\n")
    sections: list[dict] = [{"module": None, "heading": "", "lines": [], "pre": True}]
    expected = 1
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
        marker = None if in_fence else _module_marker(line)
        if marker and marker[0] == expected:
            sections.append({"module": marker[0], "heading": marker[1], "lines": []})
            expected += 1
            continue
        if not in_fence and _is_checklist_heading(line) and not marker:
            heading = re.sub(r"^[#\s*_]+|[\s*_#:]+$", "", line.strip())
            sections.append({"module": None, "heading": heading, "lines": []})
            continue
        sections[-1]["lines"].append(line)

    found = sum(1 for s in sections if s["module"])
    if found < 2:
        return None

    preamble = "\n".join(sections[0]["lines"]).strip()
    blocks = []
    for s in sections[1:]:
        parts = parse_parts("\n".join(s["lines"]))
        blocks.append({"module": s["module"], "heading": s["heading"], "parts": parts})
    if len(preamble) >= 80:  # вводный текст не теряем: кладём в начало первого модуля
        first = next((b for b in blocks if b["module"] == 1), blocks[0])
        first["parts"] = parse_parts(preamble) + first["parts"]
    return blocks


def strip_leading_heading(text: str) -> str:
    """Убирает заголовок, если AI всё же добавил его в ответ при перегенерации блока."""
    lines = (text or "").strip().split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and (lines[0].lstrip().startswith("#") or _module_marker(lines[0])):
        lines.pop(0)
    return "\n".join(lines).strip()


_SECTION = re.compile(r"^\s{0,3}(#{1,2})\s+(.+?)\s*#*\s*$")


def parse_sections(text: str):
    """Делит Markdown на разделы по заголовкам # и ## (для материалов, не КСП)."""
    secs = [{"level": 0, "heading": "", "lines": []}]
    in_fence = False
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _SECTION.match(line)
        if m:
            secs.append({"level": len(m.group(1)), "heading": re.sub(r"[*_]+", "", m.group(2)).strip(), "lines": []})
        else:
            secs[-1]["lines"].append(line)
    pre = "\n".join(secs[0]["lines"]).strip()
    body = secs[1:]
    if not body:
        return None
    if len(body) > 1 and body[0]["level"] == 1 and all(s["level"] == 2 for s in body[1:]):
        if "".join(body[0]["lines"]).strip() == "":
            body = body[1:]  # единственный заголовок документа — он уже есть в названии
    blocks = [{"module": None, "heading": s["heading"], "parts": parse_parts("\n".join(s["lines"]))} for s in body]
    if len(pre) >= 20:
        blocks[0]["parts"] = parse_parts(pre) + blocks[0]["parts"]
    return blocks
