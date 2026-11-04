"""Генерация презентации к уроку: слайды в структурированном Markdown."""
from ..doc_model import LANG_LABELS, language_code, block_to_plain
from .prompts import build_system_prompt
from .providers import AIProvider

SLIDE_FORMAT = """
ФОРМАТ ОТВЕТА (строго, парсер разбирает слайды автоматически):
Каждый слайд — блок, начинающийся строкой:
## Слайд N | layout
где layout — одно из: title, section, content, bullets, two_col, closing
Внутри слайда используй только эти поля (каждое с новой строки, префикс обязателен):
TITLE: заголовок слайда
SUBTITLE: подзаголовок (можно пустым)
BODY: основной текст абзацем (можно пустым)
BULLETS:
- пункт 1
- пункт 2
LEFT: текст левой колонки (только для two_col)
RIGHT: текст правой колонки (только для two_col)
NOTES: заметки для учителя (не на экране)
ACCENT: короткая ключевая фраза / формула (необязательно)

Правила содержания:
- 8–12 слайдов (не больше 14).
- Слайд 1 — title (тема, класс, цель одной фразой).
- Далее: section/content/bullets по ходу урока (актуализация → объяснение → практика → рефлексия).
- Предпоследние — закрепление / мини-итог; последний — closing (ДЗ или «спасибо»).
- На слайде не более 6 пунктов; формулировки короткие, для проектора.
- Формулы и обозначения пиши текстом (например x², a/b, H₂O).
- Не вставляй ФИО, школу, ссылки, QR, облачные сервисы.
- Если в условиях кабинета нет проектора — формулируй слайды так, чтобы их можно было
  переписать на доску или распечатать как опорный конспект (короче, крупнее мысль).
"""


def build_presentation_prompts(data: dict, context: str = ""):
    code = language_code(data.get("language"))
    if not code:
        raise ValueError("Уточните язык документа")
    label = LANG_LABELS[code]
    for key, name in (("subject", "предмет"), ("grade", "класс"), ("topic", "тема")):
        if not str(data.get(key, "")).strip():
            raise ValueError("Уточните: " + name)
    count = int(data.get("slide_count") or 10)
    count = max(6, min(14, count))
    system = build_system_prompt(data["subject"], data.get("methodical_profile", "")) + (
        "\n\nРЕЖИМ ПРЕЗЕНТАЦИИ: создай только слайды к уроку. "
        "Весь текст на языке документа: " + label + "."
    )
    user = f"""ТИП: Презентация к уроку
Предмет: {data['subject']}
Класс: {data['grade']}
Тема: {data['topic']}
Язык: {label}
Условия кабинета: {data.get('room_conditions') or 'Не указаны'}
Желаемое число слайдов: {count}
Пожелание учителя: {(data.get('instruction') or '').strip() or 'Не указано'}

КОНТЕКСТ УРОКА (цель и сценарий, если есть):
{context or '(не задан — сформулируй измеримую цель по теме сам)'}

{SLIDE_FORMAT}
"""
    return system, user


async def generate_presentation(data: dict, context: str = "") -> str:
    system, user = build_presentation_prompts(data, context)
    return await AIProvider.from_settings().generate(system, user)


def build_slide_regen_prompts(meta: dict, content: dict, slide: dict, instruction: str):
    code = content.get("language") or "ru"
    label = LANG_LABELS.get(code, "Русский")
    system = build_system_prompt(meta["subject"], "") + (
        "\n\nРЕЖИМ ПЕРЕГЕНЕРАЦИИ СЛАЙДА: перепиши ТОЛЬКО один слайд. "
        "Верни ровно один блок «## Слайд 1 | layout» с полями TITLE/SUBTITLE/BODY/BULLETS/LEFT/RIGHT/NOTES/ACCENT. "
        "Язык: " + label + "."
    )
    others = []
    for i, s in enumerate(content.get("slides") or [], 1):
        if s.get("id") == slide.get("id"):
            continue
        others.append(f"{i}. [{s.get('layout')}] {s.get('title','')}")
    user = f"""Предмет: {meta['subject']}; класс: {meta['grade']}; тема: {meta['topic']}
Язык: {label}
Условия кабинета: {content.get('room_conditions') or 'Не указаны'}
Пожелание: {instruction.strip() or 'Улучши слайд, сохрани смысл'}

ТЕКУЩИЙ СЛАЙД:
layout={slide.get('layout')}
TITLE: {slide.get('title','')}
SUBTITLE: {slide.get('subtitle','')}
BODY: {slide.get('body','')}
BULLETS: {slide.get('bullets') or []}
LEFT: {slide.get('left','')}
RIGHT: {slide.get('right','')}
NOTES: {slide.get('notes','')}
ACCENT: {slide.get('accent','')}

ОСТАЛЬНЫЕ СЛАЙДЫ (для согласованности):
{chr(10).join(others) or '(нет)'}
"""
    return system, user


async def regenerate_slide(meta: dict, content: dict, slide: dict, instruction: str = "") -> str:
    system, user = build_slide_regen_prompts(meta, content, slide, instruction)
    return await AIProvider.from_settings().generate(system, user)
