"""Методический конструктор: задания A/B/C, карточки, рабочие листы, тесты, рубрики, варианты."""
from ..doc_model import DOC_TYPES, LANG_LABELS, MATERIAL_TYPES, block_to_plain, language_code
from .prompts import build_system_prompt
from .providers import AIProvider

SCORES = ("Баллы: A — 1–2; B — 3–4; C — 5–6. Интерпретация: 5–6 — достиг; 3–4 — частично; "
          "0–2 — требует коррекции.")

KIND_RULES = {
    "tasks_abc": """Дифференцированные задания трёх уровней.
Структура (каждый раздел — заголовок «## ...»):
- «## Уровень A (1–2 балла)», «## Уровень B (3–4 балла)», «## Уровень C (5–6 баллов)».
- В начале каждого уровня: «Проверяет: ...» (что именно из цели урока), затем 2–4 задания по нарастающей сложности.
- После заданий каждого уровня — таблица дескрипторов (колонки: Дескриптор | Балл).
- «## Ключ для учителя»: ответы и типичные ошибки по каждому уровню.
- «## Интерпретация результатов».
""" + SCORES,
    "cards": """Набор карточек для работы в классе, всего {count} шт.
Структура: каждая карточка — «## Карточка N (уровень A|B|C)»; внутри: название, условие,
место для ответа (строка из подчёркиваний), баллы. Распредели уровни A/B/C равномерно.
Для учеников используй только «Ученик 1», «Ученик 2» и т. п. В конце — «## Ключ для учителя» с ответами.
""" + SCORES,
    "worksheet": """Рабочий лист для печати.
Структура: «## Рабочий лист» (цель и инструкция учащимся), «## Задания» (5–8 заданий по нарастающей
сложности, место для ответов), «## Рефлексия» (2–3 вопроса самооценки), «## Ключ для учителя».
Оборудование — только из условий кабинета.""",
    "test": """Тест из {count} вопросов, формат: {test_format}.
Структура: «## Тест» — вопросы «### 1.», «### 2.», ... (для выбора ответа — 4 варианта A–D, ровно один верный);
«## Ключ ответов» — таблица (№ | Правильный ответ | Балл); «## Критерии оценивания» — таблица
(Баллы | Уровень | Интерпретация). Каждый вопрос проверяет цель урока. Типичные ошибки учеников
используй как дистракторы.""",
    "rubric": """Оценочная рубрика и дескрипторы, критериев: {count}.
Структура: «## Оценочная рубрика» — ОДНА Markdown-таблица: Критерий | Уровень 1 | Уровень 2 | Уровень 3 | Уровень 4
(описания наблюдаемых действий, без оценочных слов вроде «хорошо»); «## Дескрипторы» — таблица
(Критерий | Дескриптор | Балл); «## Интерпретация баллов».""",
}


def _lang_label(language: str) -> str:
    code = language_code(language)
    if not code:
        raise ValueError("Уточните язык документа")
    return LANG_LABELS[code]


def build_material_prompts(kind: str, data: dict, context: str = ""):
    if kind not in MATERIAL_TYPES:
        raise ValueError("Неизвестный тип материала")
    for key, label in (("subject", "предмет"), ("grade", "класс"), ("topic", "тема")):
        if not str(data.get(key, "")).strip():
            raise ValueError("Уточните: " + label)
    label = _lang_label(data["language"])
    rules = KIND_RULES[kind].format(count=data.get("count") or 6,
                                    test_format=data.get("test_format") or "выбор ответа")
    system = build_system_prompt(data["subject"], data.get("methodical_profile", "")) + (
        "\n\nРЕЖИМ КОНСТРУКТОРА: создай ровно один материал указанного типа. Формат — Markdown, документ "
        "разбирается автоматически: каждый крупный раздел начинай строкой «## Название», внутри разделов "
        "используй только «###». Весь текст пиши на языке документа: " + label + "."
    )
    user = f"""ТИП МАТЕРИАЛА: {DOC_TYPES[kind]}
Предмет: {data['subject']}
Класс: {data['grade']}
Тема: {data['topic']}
Язык документа: {label}
Условия кабинета: {data.get('room_conditions') or 'Не указаны'}

ТРЕБОВАНИЯ:
{rules}

ПОЖЕЛАНИЕ УЧИТЕЛЯ: {(data.get('instruction') or '').strip() or 'Не указано'}

КОНТЕКСТ УРОКА (цель и сценарий, если есть; задания должны проверять эту цель):
{context or '(не задан — сформулируй измеримую цель по теме сам)'}
"""
    return system, user


async def generate_material(kind: str, data: dict, context: str = "") -> str:
    system, user = build_material_prompts(kind, data, context)
    return await AIProvider.from_settings().generate(system, user)


def build_variant_prompts(meta: dict, content: dict, count: int, instruction: str):
    if content.get("doc_type", "ksp") == "ksp":
        raise ValueError("Варианты доступны для заданий, карточек, рабочих листов и тестов")
    if not 1 <= count <= 4:
        raise ValueError("Можно создать от 1 до 4 вариантов")
    if not content.get("language"):
        raise ValueError("Выберите язык документа в реквизитах")
    label = LANG_LABELS[content["language"]]
    source = "\n\n".join(f"[{b['heading']}]\n{block_to_plain(b, 6000)}" for b in content["blocks"])[:12000]
    system = build_system_prompt(meta["subject"], "") + (
        "\n\nРЕЖИМ ВАРИАНТОВ: создай новые варианты готового материала. Сохрани цель, структуру, уровень "
        "сложности, количество заданий и систему баллов; измени числа, данные, формулировки и контексты. "
        "Каждый вариант — отдельный раздел «## Вариант N» (нумерация с 2), внутри только «###». "
        "Если в материале есть ключ или критерии — в каждом варианте дай свой ключ. Язык: " + label + "."
    )
    user = f"""Предмет: {meta['subject']}; класс: {meta['grade']}; тема: {meta['topic']}
Тип: {DOC_TYPES[content['doc_type']]}
Создай вариантов: {count}
Условия кабинета: {content.get('room_conditions') or 'Не указаны'}
Пожелание: {instruction.strip() or 'Не указано'}

ИСХОДНЫЙ МАТЕРИАЛ (вариант 1):
{source}
"""
    return system, user


async def generate_variants(meta: dict, content: dict, count: int, instruction: str) -> str:
    system, user = build_variant_prompts(meta, content, count, instruction)
    return await AIProvider.from_settings().generate(system, user)
