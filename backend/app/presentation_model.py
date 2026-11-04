"""Модель презентации: слайды, разбор Markdown, нормализация, проверки."""
from __future__ import annotations

import re
import uuid
from .doc_model import LANG_LABELS, language_code, _s

LAYOUTS = ("title", "section", "content", "bullets", "two_col", "closing")
MAX_SLIDES, MAX_BULLETS = 20, 10
MAX_FIELD = 2000
_SLIDE_HEAD = re.compile(
    r"^\s*##\s*Слайд\s*(\d+)\s*\|\s*([a-z_]+)\s*$",
    re.I | re.M,
)
_FIELD = re.compile(
    r"^(TITLE|SUBTITLE|BODY|BULLETS|LEFT|RIGHT|NOTES|ACCENT)\s*:\s*(.*)$",
    re.I,
)


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def empty_slide(layout: str = "content") -> dict:
    return {
        "id": new_id(),
        "layout": layout if layout in LAYOUTS else "content",
        "title": "",
        "subtitle": "",
        "body": "",
        "bullets": [],
        "left": "",
        "right": "",
        "notes": "",
        "accent": "",
    }


def _parse_bullets(lines: list[str]) -> list[str]:
    out = []
    for ln in lines:
        m = re.match(r"^\s*[-*•]\s+(.*)$", ln)
        if m:
            t = m.group(1).strip()
            if t:
                out.append(t[:500])
        elif ln.strip() and not _FIELD.match(ln):
            out.append(ln.strip()[:500])
        if len(out) >= MAX_BULLETS:
            break
    return out


def parse_presentation_markdown(text: str) -> list[dict]:
    """Разбирает ответ AI в список слайдов."""
    text = (text or "").replace("\r\n", "\n")
    # Найти все заголовки слайдов
    matches = list(_SLIDE_HEAD.finditer(text))
    if not matches:
        # fallback: каждый ## как слайд
        parts = re.split(r"(?m)^\s*##\s+", text)
        slides = []
        for chunk in parts[1:]:
            lines = chunk.strip().split("\n")
            title = lines[0].strip()[:300] if lines else "Слайд"
            body = "\n".join(lines[1:]).strip()
            s = empty_slide("content")
            s["title"] = title
            bullets = _parse_bullets(lines[1:])
            if bullets:
                s["bullets"] = bullets
                s["layout"] = "bullets"
            else:
                s["body"] = body[:MAX_FIELD]
            slides.append(s)
        return slides[:MAX_SLIDES]

    slides = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        layout = m.group(2).lower().strip()
        if layout not in LAYOUTS:
            layout = "content"
        slide = empty_slide(layout)
        current_field = None
        buf: list[str] = []

        def flush():
            nonlocal current_field, buf
            if not current_field:
                buf = []
                return
            raw = "\n".join(buf).strip()
            key = current_field.lower()
            if key == "bullets":
                slide["bullets"] = _parse_bullets(buf)
            elif key in slide:
                slide[key] = raw[:MAX_FIELD]
            current_field = None
            buf = []

        for line in chunk.split("\n"):
            fm = _FIELD.match(line.strip())
            if fm:
                flush()
                current_field = fm.group(1).upper()
                rest = fm.group(2)
                if rest.strip():
                    buf.append(rest)
                continue
            buf.append(line)
        flush()
        if not slide["title"] and slide["body"]:
            slide["title"] = slide["body"].split("\n")[0][:120]
        slides.append(slide)
    return slides[:MAX_SLIDES]


def sanitize_presentation(content: dict) -> dict:
    c = content if isinstance(content, dict) else {}
    lang = language_code(c.get("language"))
    raw = c.get("slides") if isinstance(c.get("slides"), list) else []
    slides = []
    used = set()
    for rs in raw[:MAX_SLIDES]:
        if not isinstance(rs, dict):
            continue
        sid = rs.get("id") if isinstance(rs.get("id"), str) and re.match(r"^[a-z0-9]{4,16}$", rs["id"]) else new_id()
        if sid in used:
            sid = new_id()
        used.add(sid)
        layout = rs.get("layout") if rs.get("layout") in LAYOUTS else "content"
        bullets = rs.get("bullets") if isinstance(rs.get("bullets"), list) else []
        bullets = [_s(b, 500) for b in bullets[:MAX_BULLETS] if str(b).strip()]
        slides.append({
            "id": sid,
            "layout": layout,
            "title": _s(rs.get("title"), 300),
            "subtitle": _s(rs.get("subtitle"), 300),
            "body": _s(rs.get("body"), MAX_FIELD),
            "bullets": bullets,
            "left": _s(rs.get("left"), MAX_FIELD),
            "right": _s(rs.get("right"), MAX_FIELD),
            "notes": _s(rs.get("notes"), MAX_FIELD),
            "accent": _s(rs.get("accent"), 300),
        })
    if not slides:
        slides = [empty_slide("title")]
    return {
        "editor_version": 2,
        "doc_type": "presentation",
        "language": lang,
        "room_conditions": _s(c.get("room_conditions"), 500),
        "slides": slides,
        "blocks": [],  # не КСП-модули
        "params": {},
    }


def build_presentation_content(text: str, language: str, room_conditions: str = "") -> dict:
    slides = parse_presentation_markdown(text)
    return sanitize_presentation({
        "language": language,
        "room_conditions": room_conditions,
        "slides": slides,
    })


def check_presentation(content: dict) -> list[dict]:
    warnings = []

    def add(level, code, message):
        warnings.append({"level": level, "module": None, "code": code, "message": message})

    slides = content.get("slides") or []
    if not slides:
        add("error", "empty", "Презентация пуста.")
        return warnings
    if not content.get("language"):
        add("warn", "language", "Не выбран язык документа.")
    if len(slides) < 5:
        add("warn", "few_slides", f"Мало слайдов: {len(slides)}. Обычно 8–12.")
    if len(slides) > 14:
        add("warn", "many_slides", f"Много слайдов: {len(slides)}. Для 45-мин урока лучше ≤12.")
    empty = sum(1 for s in slides if not (s.get("title") or s.get("body") or s.get("bullets")))
    if empty:
        add("warn", "empty_slides", f"Пустых слайдов: {empty}.")
    layouts = {s.get("layout") for s in slides}
    if "title" not in layouts:
        add("warn", "no_title", "Нет титульного слайда (layout=title).")
    long_bullets = [i + 1 for i, s in enumerate(slides) if len(s.get("bullets") or []) > 6]
    if long_bullets:
        add("warn", "dense", f"Слишком много пунктов на слайдах: {', '.join(map(str, long_bullets[:5]))}.")
    return warnings


def find_slide(content: dict, slide_id: str):
    return next((s for s in content.get("slides", []) if s.get("id") == slide_id), None)
