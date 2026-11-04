"""Модель документа КСП/КМЖ (editor_version 2).

content = {
  "editor_version": 2,
  "language": "ru" | "kk" | "en" | "uz" | "",   # язык ДОКУМЕНТА, не интерфейса
  "room_conditions": str,
  "blocks": [ {"id", "module": 1..5 | None, "heading", "parts": [text | table]} ]
}
text-часть:  {"type": "text", "text": str}
table-часть: {"type": "table", "header": [str], "rows": [[str]], "widths": [float]?}
Пять модулей присутствуют всегда и не удаляются; дополнительные разделы необязательны.
"""
import re
import uuid

from .md_parser import parse_generated_blocks, parse_parts, parse_sections

LANG_LABELS = {"ru": "Русский", "kk": "Қазақша", "en": "English", "uz": "Ўзбекча (кириллица)"}

MODULE_TITLES = {
    "ru": ["1. Концепт и сценарий учителя", "2. Таблица КСП / КМЖ", "3. Карточки уровней A / B / C",
           "4. Схема / визуализация", "5. Слайды, тест, домашнее задание и связь с уроками"],
    "kk": ["1. Тұжырымдама және мұғалім сценарийі", "2. ҚМЖ кестесі", "3. A / B / C деңгей карточкалары",
           "4. Сызба / визуализация", "5. Слайдтар, тест, үй тапсырмасы және келесі сабақтармен байланыс"],
    "en": ["1. Concept and teacher's script", "2. Short-term plan table", "3. Level cards A / B / C",
           "4. Diagram / visualization", "5. Slides, quiz, homework and links to next lessons"],
    "uz": ["1. Концепция ва ўқитувчи сценарийси", "2. Қисқа муддатли режа жадвали", "3. A / B / C даража карточкалари",
           "4. Схема / визуализация", "5. Слайдлар, тест, уй вазифаси ва кейинги дарслар билан боғлиқлик"],
}
CHECKLIST_TITLE = {"ru": "Чек-лист самопроверки", "kk": "Өзін-өзі тексеру чек-листі",
                   "en": "Self-check checklist", "uz": "Ўз-ўзини текшириш чек-листи"}
NOTES_TITLE = {"ru": "Материал урока", "kk": "Сабақ материалы", "en": "Lesson material", "uz": "Дарс материали"}
KSP_HEADERS = {
    "ru": ["Этап урока", "Время (мин)", "Деятельность учителя", "Деятельность учащихся", "Ресурсы",
           "ФО и дескрипторы", "Использование ИКТ / ИИ"],
    "kk": ["Сабақ кезеңі", "Уақыты (мин)", "Мұғалімнің әрекеті", "Оқушылардың әрекеті", "Ресурстар",
           "ҚБ және дескрипторлар", "АКТ / ЖИ қолдану"],
    "en": ["Lesson stage", "Time (min)", "Teacher activity", "Student activity", "Resources",
           "Formative assessment & descriptors", "ICT / AI use"],
    "uz": ["Дарс босқичи", "Вақт (дақ.)", "Ўқитувчи фаолияти", "Ўқувчилар фаолияти", "Ресурслар",
           "Шакллантирувчи баҳолаш ва дескрипторлар", "АКТ / СИ дан фойдаланиш"],
}

DOC_TYPES = {"ksp": "КСП / КМЖ", "tasks_abc": "Задания A / B / C", "cards": "Карточки",
             "worksheet": "Рабочий лист", "test": "Тест с ключом", "rubric": "Рубрика и дескрипторы",
             "presentation": "Презентация",
             "ktp": "КТП (календарно-тематическое)", "sor": "СОР (за раздел)",
             "soch": "СОЧ (за период)", "diagnostic": "Диагностика знаний",
             "year_plan": "Годовой план", "theme_plan": "Тематический план"}
PLAN_TYPES = ("ktp", "sor", "soch", "diagnostic", "year_plan", "theme_plan")
MATERIAL_TYPES = tuple(k for k in DOC_TYPES if k not in ("ksp", "presentation") and k not in PLAN_TYPES)

MAX_BLOCKS, MAX_PARTS, MAX_ROWS, MAX_COLS = 40, 40, 100, 12
MAX_TEXT, MAX_CELL, MAX_HEADING = 30000, 3000, 300
_ID_RE = re.compile(r"^[a-z0-9]{4,16}$")
_TIME_RE = re.compile(r"(врем|time|уақыт|вақт)", re.I)
_TIME_UNIT_RE = re.compile(r"\((мин|min|дақ)", re.I)
_TOTAL_RE = re.compile(r"(итого|всего|total|барлығы|жами)", re.I)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d()\- ]{7,}\d")


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def language_code(value) -> str:
    v = str(value or "").strip().lower()
    if v in LANG_LABELS:
        return v
    for code, label in LANG_LABELS.items():
        if v == label.lower():
            return code
    prefixes = {"uz": ("ўз", "узб", "uz"), "kk": ("қаз", "каз", "kk", "kaz"),
                "en": ("eng", "анг"), "ru": ("рус", "rus")}
    for code, pre in prefixes.items():
        if v.startswith(pre):
            return code
    return ""


def text_part(text: str = "") -> dict:
    return {"type": "text", "text": text}


def table_part(header, rows=None) -> dict:
    return {"type": "table", "header": list(header), "rows": [list(r) for r in (rows or [])]}


def default_blocks(lang: str = "ru") -> list[dict]:
    lang = lang if lang in LANG_LABELS else "ru"
    blocks = []
    for i, title in enumerate(MODULE_TITLES[lang], start=1):
        parts = [table_part(KSP_HEADERS[lang], [[""] * len(KSP_HEADERS[lang])])] if i == 2 else [text_part("")]
        blocks.append({"id": new_id(), "module": i, "heading": title, "parts": parts})
    return blocks


# ---------- очистка и нормализация ----------

def _s(value, limit):
    return str(value if value is not None else "")[:limit]


def _sanitize_part(p):
    if not isinstance(p, dict):
        return None
    if p.get("type") == "table":
        header = p.get("header") if isinstance(p.get("header"), list) else []
        header = [_s(h, MAX_CELL) for h in header[:MAX_COLS]] or [""]
        width = len(header)
        rows = []
        for r in (p.get("rows") if isinstance(p.get("rows"), list) else [])[:MAX_ROWS]:
            r = r if isinstance(r, list) else [r]
            r = [_s(c, MAX_CELL) for c in r[:width]]
            rows.append(r + [""] * (width - len(r)))
        out = {"type": "table", "header": header, "rows": rows}
        w = p.get("widths")
        if isinstance(w, list) and len(w) == width and all(isinstance(x, (int, float)) and x > 0 for x in w):
            out["widths"] = [float(x) for x in w]
        return out
    return {"type": "text", "text": _s(p.get("text"), MAX_TEXT)}


def sanitize_content(content: dict) -> dict:
    """Приводит документ к безопасному виду: лимиты, пять модулей, уникальные id."""
    c = content if isinstance(content, dict) else {}
    lang = language_code(c.get("language"))
    doc_type = c.get("doc_type") if c.get("doc_type") in DOC_TYPES else "ksp"
    params = {str(k)[:40]: (v if isinstance(v, (int, float)) and not isinstance(v, bool) else _s(v, 200))
              for k, v in list((c.get("params") or {}).items())[:10]} if isinstance(c.get("params"), dict) else {}
    raw_blocks = c.get("blocks") if isinstance(c.get("blocks"), list) else []
    used_ids, modules, extras = set(), {}, []
    for rb in raw_blocks[:MAX_BLOCKS]:
        if not isinstance(rb, dict):
            continue
        parts = [x for x in (_sanitize_part(p) for p in (rb.get("parts") or [])[:MAX_PARTS]) if x]
        bid = rb.get("id") if isinstance(rb.get("id"), str) and _ID_RE.match(rb.get("id", "")) else new_id()
        if bid in used_ids:
            bid = new_id()
        used_ids.add(bid)
        mod = rb.get("module")
        mod = mod if isinstance(mod, int) and not isinstance(mod, bool) and 1 <= mod <= 5 else None
        if doc_type != "ksp":
            mod = None  # пять модулей — только у КСП/КМЖ
        block = {"id": bid, "module": mod, "heading": _s(rb.get("heading"), MAX_HEADING), "parts": parts}
        if mod and mod not in modules:
            modules[mod] = block
        else:
            block["module"] = None  # дубликат модуля становится обычным разделом
            extras.append(block)
    if doc_type == "ksp":
        defaults = {b["module"]: b for b in default_blocks(lang or "ru")}
        ordered = [modules.get(n) or defaults[n] for n in range(1, 6)]
        for b in ordered:
            if not b["parts"]:
                b["parts"] = [text_part("")]
        blocks = ordered + extras
    else:
        blocks = extras or [{"id": new_id(), "module": None, "heading": DOC_TYPES[doc_type], "parts": [text_part("")]}]
        for b in blocks:
            if not b["parts"]:
                b["parts"] = [text_part("")]
    return {"editor_version": 2, "doc_type": doc_type, "params": params, "language": lang,
            "room_conditions": _s(c.get("room_conditions"), 500), "blocks": blocks}


def _migrate_legacy(c: dict, lang: str) -> list[dict]:
    legacy = c.get("blocks")
    if isinstance(legacy, list) and legacy:  # этап 3: {heading, body, table}
        blocks, used = [], set()
        for lb in legacy:
            if not isinstance(lb, dict):
                continue
            parts = []
            body = str(lb.get("body") or "")
            if body.strip() or not lb.get("table"):
                parts.append(text_part(body))
            tbl = lb.get("table")
            if isinstance(tbl, list) and tbl and isinstance(tbl[0], list):
                parts.append(table_part([str(x) for x in tbl[0]],
                                        [[str(x) for x in r] for r in tbl[1:] if isinstance(r, list)]))
            heading = str(lb.get("heading") or "")
            m = re.match(r"\s*([1-5])[.)\s]", heading)
            mod = int(m.group(1)) if m and int(m.group(1)) not in used else None
            if mod:
                used.add(mod)
            blocks.append({"module": mod, "heading": heading, "parts": parts})
        return blocks
    generated = str(c.get("generated_text") or "")
    if generated.strip():
        parsed = parse_generated_blocks(generated)
        if parsed:
            return parsed
        return [{"module": None, "heading": NOTES_TITLE[lang], "parts": parse_parts(generated)}]
    notes = str(c.get("notes") or "")
    if notes.strip():
        return [{"module": None, "heading": NOTES_TITLE[lang], "parts": [text_part(notes)]}]
    return []


def normalize_content(content) -> dict:
    """Любое сохранённое содержимое (этап 1–3 или v2) → безопасный документ v2."""
    c = content if isinstance(content, dict) else {}
    if c.get("doc_type") == "presentation":
        from .presentation_model import sanitize_presentation
        return sanitize_presentation(c)
    if c.get("editor_version") == 2 and isinstance(c.get("blocks"), list):
        return sanitize_content(c)
    lang = language_code(c.get("language"))
    migrated = {"language": lang, "room_conditions": c.get("room_conditions", ""),
                "blocks": _migrate_legacy(c, lang or "ru")}
    return sanitize_content(migrated)


def build_content_from_generated(text: str, language: str, room_conditions: str = "") -> dict:
    lang = language_code(language)
    blocks = parse_generated_blocks(text)
    if not blocks:
        blocks = [{"module": None, "heading": NOTES_TITLE[lang or "ru"], "parts": parse_parts(text)}]
    return sanitize_content({"language": lang, "room_conditions": room_conditions, "blocks": blocks})


def build_material_content(text: str, doc_type: str, language: str, room_conditions: str = "", params=None) -> dict:
    lang = language_code(language)
    blocks = parse_sections(text) or [{"module": None, "heading": DOC_TYPES[doc_type], "parts": parse_parts(text)}]
    return sanitize_content({"doc_type": doc_type, "params": params or {}, "language": lang,
                             "room_conditions": room_conditions, "blocks": blocks})


def blocks_from_variants(text: str) -> list[dict]:
    """Блоки для вариантов заданий: каждый «## Вариант N» — отдельный раздел с новым id."""
    blocks = parse_sections(text) or [{"module": None, "heading": "Вариант", "parts": parse_parts(text)}]
    clean = sanitize_content({"doc_type": "worksheet", "blocks": blocks})
    return clean["blocks"]


# ---------- утилиты ----------

def find_block(content: dict, block_id: str):
    return next((b for b in content.get("blocks", []) if b.get("id") == block_id), None)


def table_to_text(part: dict) -> str:
    lines = [" | ".join(part.get("header", []))]
    lines += [" | ".join(r) for r in part.get("rows", [])]
    return "\n".join(lines)


def block_to_plain(block: dict, limit: int = 1500) -> str:
    chunks = []
    for p in block.get("parts", []):
        chunks.append(table_to_text(p) if p.get("type") == "table" else p.get("text", ""))
    return "\n".join(chunks).strip()[:limit]


def time_column(header) -> int:
    for i, h in enumerate(header):
        if _TIME_RE.search(str(h)):
            return i
    for i, h in enumerate(header):
        if _TIME_UNIT_RE.search(str(h)):
            return i
    return -1


def sum_minutes(part: dict):
    """(сумма минут, число строк с временем) или None, если колонки времени нет."""
    idx = time_column(part.get("header", []))
    if idx < 0:
        return None
    total, counted = 0, 0
    for row in part.get("rows", []):
        if row and _TOTAL_RE.search(str(row[0])):
            continue
        m = re.search(r"\d+", str(row[idx])) if idx < len(row) else None
        if m:
            total += int(m.group())
            counted += 1
    return total, counted


def _all_strings(content: dict):
    for b in content.get("blocks", []):
        yield b.get("heading", "")
        for p in b.get("parts", []):
            if p.get("type") == "table":
                yield from p.get("header", [])
                for r in p.get("rows", []):
                    yield from r
            else:
                yield p.get("text", "")


_KEY_RE = re.compile(r"(ключ|ответ|answer|жауап|калит)", re.I)
_SCORE_RE = re.compile(r"(балл|point|ұпай|score)", re.I)


def _check_material(content: dict, doc_type: str, add):
    blocks = content.get("blocks", [])
    heads = " ".join(b.get("heading", "") for b in blocks)
    text = heads + "\n" + "\n".join(block_to_plain(b, 30000) for b in blocks)
    if not text.strip():
        add("warn", None, "empty", "Материал пуст.")
        return
    has_table = any(p.get("type") == "table" for b in blocks for p in b.get("parts", []))
    if doc_type in ("test", "tasks_abc", "cards", "worksheet") and not (_KEY_RE.search(heads) or _KEY_RE.search(text)):
        add("error", None, "no_key", "Нет ключа / ответов для учителя.")
    if doc_type in ("test", "tasks_abc", "rubric", "cards") and not _SCORE_RE.search(text):
        add("warn", None, "no_scores", "Не найдены баллы: добавьте критерии оценивания.")
    if doc_type == "rubric" and not has_table:
        add("error", None, "no_table", "В рубрике нет таблицы критериев.")
    if doc_type == "tasks_abc":
        missing = [x for x in "ABC" if not re.search(rf"(?<![A-Za-zА-Яа-я]){x}(?![A-Za-zА-Яа-я])", text)]
        if missing:
            add("warn", None, "levels", "Не найдены уровни: " + ", ".join(missing) + ".")
    if doc_type == "cards":
        cards_n = len(re.findall(r"(?i)карточк|card", heads))
        wanted = content.get("params", {}).get("count")
        if isinstance(wanted, (int, float)) and wanted and cards_n and cards_n < int(wanted):
            add("warn", None, "cards", f"Найдено карточек: {cards_n}, запрошено: {int(wanted)}.")
    if doc_type == "test":
        questions = len(re.findall(r"(?m)^\s*(?:\d{1,2}[.)]|#{3,4}\s*\d)", text))
        wanted = content.get("params", {}).get("count")
        if isinstance(wanted, (int, float)) and wanted and questions and questions < wanted:
            add("warn", None, "questions", f"Найдено вопросов: {questions}, запрошено: {int(wanted)}.")



_TABLE_HINT = re.compile(r"\|", re.M)

def _check_planning(content: dict, doc_type: str, add):
    blocks = content.get("blocks", [])
    heads = " ".join(b.get("heading", "") for b in blocks)
    text = heads + "\n" + "\n".join(block_to_plain(b, 30000) for b in blocks)
    if not text.strip():
        add("error", None, "empty", "Документ пуст.")
        return
    has_table = any(p.get("type") == "table" for b in blocks for p in b.get("parts", []))
    if doc_type in ("ktp", "year_plan", "theme_plan") and not has_table:
        add("error", None, "no_table", "В плане нет таблицы (КТП / распределение часов / поурочный план).")
    if doc_type in ("sor", "soch", "diagnostic"):
        if not (_KEY_RE.search(heads) or _KEY_RE.search(text) or re.search(r"критер", text, re.I)):
            add("error", None, "no_key", "Нет ключа / критериев оценивания.")
        if not _SCORE_RE.search(text):
            add("warn", None, "no_scores", "Не найдены баллы.")
        if not has_table:
            add("warn", None, "no_table", "Рекомендуется таблица ключа или спецификации.")
    if doc_type == "soch" and not re.search(r"(шкал|перевод|уровен)", text, re.I):
        add("warn", None, "no_scale", "Нет шкалы перевода баллов / уровней.")
    if doc_type == "diagnostic" and not re.search(r"(интерпрет|рекоменд|маршрут|коррекц)", text, re.I):
        add("warn", None, "no_interp", "Нет интерпретации результатов или маршрута коррекции.")

def check_document(content: dict, private_terms=None) -> list[dict]:
    """Проверка обязательных требований. Предупреждения не блокируют сохранение."""
    warnings = []

    def add(level, module, code, message):
        warnings.append({"level": level, "module": module, "code": code, "message": message})

    doc_type = content.get("doc_type", "ksp")
    by_module = {b["module"]: b for b in content.get("blocks", []) if b.get("module")}
    if not content.get("language"):
        add("warn", None, "language", "Не выбран язык документа: он нужен для перегенерации блоков и оформления.")
    if doc_type in PLAN_TYPES:
        _check_planning(content, doc_type, add)
        by_module = {}
    elif doc_type != "ksp" and doc_type != "presentation":
        _check_material(content, doc_type, add)
        by_module = {}
    for n in range(1, 6 if doc_type == "ksp" else 1):
        b = by_module.get(n)
        if not b or not block_to_plain(b, 50):
            add("warn", n, "empty_module", f"Модуль {n} пуст.")

    ksp = by_module.get(2)
    table = next((p for p in (ksp or {}).get("parts", []) if p.get("type") == "table"), None)
    if ksp and block_to_plain(ksp, 50):
        if not table:
            add("error", 2, "no_table", "В модуле 2 нет таблицы КСП / КМЖ.")
        else:
            res = sum_minutes(table)
            if res is None:
                add("warn", 2, "no_time_column", "В таблице КСП / КМЖ не найдена колонка времени.")
            elif res[0] != 45:
                add("error", 2, "timing", f"Сумма времени по этапам — {res[0]} мин, а урок должен длиться ровно 45 минут.")

    levels = by_module.get(3)
    if levels and block_to_plain(levels, 50):
        text = block_to_plain(levels, 20000)
        missing = [x for x in "ABC" if not re.search(rf"(?<![A-Za-zА-Яа-я]){x}(?![A-Za-zА-Яа-я])", text)]
        if missing:
            add("warn", 3, "levels", "В модуле 3 не найдены уровни: " + ", ".join(missing) + ".")

    blob = "\n".join(_all_strings(content))
    if _EMAIL_RE.search(blob) or _PHONE_RE.search(blob):
        add("warn", None, "contacts", "Найдены e-mail или телефон. Уберите их до публикации в общей библиотеке.")
    low = blob.lower()
    hits = [t for t in (private_terms or []) if len(str(t).strip()) >= 4 and str(t).strip().lower() in low]
    if hits:
        add("warn", None, "private_terms",
            "В тексте встречаются ФИО или название школы. В публичную копию они не попадут, но проверьте личный оригинал.")
    return warnings


def redact_terms(obj, terms):
    """Заменяет ФИО/название школы в строках на [СКРЫТО] (для обезличенной копии)."""
    pats = [re.compile(re.escape(str(t).strip()), re.I) for t in terms if len(str(t).strip()) >= 4]
    if isinstance(obj, dict):
        return {k: redact_terms(v, terms) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_terms(v, terms) for v in obj]
    if isinstance(obj, str):
        for p in pats:
            obj = p.sub("[СКРЫТО]", obj)
    return obj
