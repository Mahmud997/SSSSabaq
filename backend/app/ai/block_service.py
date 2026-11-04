"""Перегенерация одного модуля документа через AI."""
from ..doc_model import (KSP_HEADERS, LANG_LABELS, block_to_plain, check_document, find_block)
from ..md_parser import parse_parts, strip_leading_heading
from .prompts import build_system_prompt
from .providers import AIProvider


class AIOutputError(RuntimeError):
    pass


MODULE_RULES = {
    1: "Концепт и сценарий учителя: измеримая цель (действие + объект + условие + критерий), "
       "тайминг ровно 45 минут (сумма по этапам 45), типичные ошибки и темп урока.",
    2: "Таблица КСП/КМЖ — ОДНА Markdown-таблица ровно из 7 колонок с заголовками: {headers}. "
       "В колонке времени в каждой строке — целое число минут, сумма строго 45, строку «Итого» не добавляй. "
       "Каждый этап связан с целью урока. Таблицу не оборачивай в блок кода.",
    3: "Карточки уровней A/B/C. В начале каждого уровня «Проверяет: ...», задания, дескрипторы, баллы: "
       "A — 1–2; B — 3–4; C — 5–6. Интерпретация: 5–6 достиг; 3–4 частично; 0–2 требует коррекции. "
       "Для учеников используй только «Ученик 1», «Ученик 2».",
    4: "Mermaid-схема в блоке ```mermaid только если она действительно нужна; иначе одной фразой "
       "сообщи, что схема не требуется (на языке документа).",
    5: "Ровно 3 слайда и ровно 3 вопроса теста с ключом, домашнее задание и связь со следующими уроками. "
       "Слайды учитывают условия кабинета (нет проектора — запись на доске или раздаточный материал).",
}


def build_block_prompts(lesson: dict, content: dict, block: dict, instruction: str):
    lang = content.get("language") or "ru"
    label = LANG_LABELS.get(lang, "Русский")
    system = build_system_prompt(lesson["subject"], "") + (
        "\n\nРЕЖИМ ПЕРЕГЕНЕРАЦИИ: ты переписываешь ТОЛЬКО ОДИН модуль готового документа. "
        "Верни только содержимое модуля в Markdown, без заголовка модуля, без пояснений и без вступления. "
        "Таблицы — только Markdown-таблицы. Весь текст пиши на языке документа: " + label + "."
    )
    ksp = content.get("doc_type", "ksp") == "ksp"
    if block.get("module"):
        rules = MODULE_RULES[block["module"]].format(headers=" | ".join(KSP_HEADERS.get(lang, KSP_HEADERS["ru"])))
    else:
        rules = ("Перепиши раздел, сохранив его назначение, формат (таблицы — Markdown-таблицами), "
                 "цель урока и согласованность с остальными разделами. Баллы: A — 1–2; B — 3–4; C — 5–6.")
    others = []
    for b in content["blocks"]:
        if b["id"] != block["id"] and (b.get("module") or not ksp):
            text = block_to_plain(b, 1200)
            if text:
                others.append(f"[{b['heading']}]\n{text}")
    current = block_to_plain(block, 6000)
    user = f"""ДОКУМЕНТ
Предмет: {lesson['subject']}
Класс: {lesson['grade']}
Тема: {lesson['topic']}
Язык документа: {label}
Условия кабинета: {content.get('room_conditions') or 'Не указаны'}

ПЕРЕГЕНЕРИРУЕМЫЙ БЛОК: {block['heading']}
ТРЕБОВАНИЯ: {rules}

ПОЖЕЛАНИЕ УЧИТЕЛЯ: {instruction.strip() or 'Не указано — улучши модуль, сохранив цель урока.'}

ТЕКУЩЕЕ СОДЕРЖИМОЕ МОДУЛЯ:
{current or '(пусто)'}

ОСТАЛЬНЫЕ МОДУЛИ ДОКУМЕНТА (для согласованности, не повторяй их):
{chr(10).join(others) or '(пока пусты)'}
"""
    return system, user


async def regenerate_block(lesson: dict, content: dict, block_id: str, instruction: str = ""):
    block = find_block(content, block_id)
    if not block:
        raise ValueError("Блок не найден")
    if not block.get("module") and content.get("doc_type", "ksp") == "ksp":
        raise ValueError("Перегенерация доступна только для модулей 1–5")
    if not content.get("language"):
        raise ValueError("Выберите язык документа в реквизитах")
    system, user = build_block_prompts(lesson, content, block, instruction)
    raw = await AIProvider.from_settings().generate(system, user)
    parts = parse_parts(strip_leading_heading(raw))
    if not parts:
        raise AIOutputError("AI вернул пустой ответ. Повторите перегенерацию.")
    if block["module"] == 2 and not any(p["type"] == "table" for p in parts):
        raise AIOutputError("AI не вернул таблицу КСП / КМЖ. Повторите перегенерацию.")
    return parts


def warnings_with_parts(content: dict, block_id: str, parts: list, terms=None):
    probe = {**content, "blocks": [{**b, "parts": parts} if b["id"] == block_id else b for b in content["blocks"]]}
    return check_document(probe, terms)
