from .providers import AIProvider, AIConfigurationError
from .prompts import build_system_prompt

REQUIRED = ("subject", "grade", "topic", "room_conditions", "language")

def validate_lesson_input(data: dict):
    missing = [k for k in REQUIRED if not str(data.get(k, "")).strip()]
    placeholders = [k for k in REQUIRED if "${" in str(data.get(k, "")) or "YOUR_" in str(data.get(k, ""))]
    if missing or placeholders:
        labels = {"subject":"предмет", "grade":"класс", "topic":"тема",
                  "room_conditions":"условия кабинета", "language":"язык"}
        raise ValueError("Уточните: " + ", ".join(labels[x] for x in sorted(set(missing + placeholders))))
    if int(data.get("lesson_minutes", 45)) != 45:
        raise ValueError("Продолжительность урока должна составлять 45 минут.")
    return data

def build_user_prompt(data: dict) -> str:
    return f"""
ВХОДНЫЕ ДАННЫЕ:
Предмет: {data['subject']}
Класс: {data['grade']}
Тема: {data['topic']}
Условия кабинета: {data['room_conditions']}
Методический профиль: {data.get('methodical_profile') or 'Не задан'}
Язык: {data['language']}

Сформируй материал строго в пяти модулях:
1. Концепт и сценарий учителя: измеримая цель, тайминг ровно 45 минут,
   типичные ошибки и темп.
2. Таблица КСП/КМЖ: этап, время, деятельность учителя, деятельность учащихся,
   ресурсы, ФО и дескрипторы, использование ИКТ/ИИ.
3. Карточки уровней A/B/C с заданиями, дескрипторами и баллами.
4. Mermaid-схема только если она действительно нужна; иначе напиши «Схема не требуется».
5. Ровно 3 слайда и ровно 3 вопроса теста с ключом, домашнее задание и связь со следующими уроками.

ФОРМАТ ОТВЕТА (обязателен, документ разбирается автоматически):
- Весь текст, включая заголовки, пиши на языке документа: {data['language']}.
- Каждый модуль начинай отдельной строкой «## N. Название модуля» (N = 1…5, по порядку).
- Модуль 2 — одна Markdown-таблица ровно из 7 колонок: этап, время (целые минуты, сумма строго 45,
  без строки «Итого»), деятельность учителя, деятельность учащихся, ресурсы, ФО и дескрипторы, ИКТ/ИИ.
- В конце добавь отдельный раздел «## Чек-лист самопроверки» (в заголовке должно быть слово «чек-лист»
  или его перевод). Не добавляй шестой модуль.
"""
async def generate_lesson(data: dict) -> str:
    validate_lesson_input(data)
    provider = AIProvider.from_settings()
    system = build_system_prompt(data["subject"], data.get("methodical_profile", ""))
    return await provider.generate(system, build_user_prompt(data))
