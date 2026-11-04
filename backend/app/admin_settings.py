"""Админ-настройки: AI-провайдер, предметные промпты, runtime-конфиг."""
from __future__ import annotations

import os
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import AppSetting
from .ai.prompts import SUBJECT_PROMPTS_DEFAULT, BASE_SYSTEM_PROMPT

SETTING_AI = "ai_config"
SETTING_PROMPTS = "subject_prompts"
SETTING_BASE_PROMPT = "base_system_prompt"


def _get(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def _set(db: Session, key: str, value: dict) -> dict:
    row = db.get(AppSetting, key)
    if not row:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        db.add(row)
    db.commit()
    db.refresh(row)
    return dict(row.value or {})


def get_ai_config(db: Session | None = None) -> dict:
    """Эффективный AI-конфиг: env + переопределения из БД."""
    cfg = {
        "provider": os.getenv("AI_PROVIDER", "gemini").lower(),
        "model": os.getenv("AI_MODEL", ""),
        "timeout_seconds": float(os.getenv("AI_TIMEOUT_SECONDS", "90")),
        "enabled": True,
    }
    if db is not None:
        stored = _get(db, SETTING_AI)
        for k in ("provider", "model", "timeout_seconds", "enabled"):
            if k in stored and stored[k] is not None and stored[k] != "":
                cfg[k] = stored[k]
        if "timeout_seconds" in cfg:
            try:
                cfg["timeout_seconds"] = float(cfg["timeout_seconds"])
            except (TypeError, ValueError):
                cfg["timeout_seconds"] = 90.0
    return cfg


def set_ai_config(db: Session, data: dict) -> dict:
    allowed = {}
    if "provider" in data and str(data["provider"]).strip():
        allowed["provider"] = str(data["provider"]).strip().lower()[:40]
    if "model" in data:
        allowed["model"] = str(data["model"] or "")[:80]
    if "timeout_seconds" in data:
        try:
            allowed["timeout_seconds"] = max(15.0, min(300.0, float(data["timeout_seconds"])))
        except (TypeError, ValueError):
            pass
    if "enabled" in data:
        allowed["enabled"] = bool(data["enabled"])
    current = _get(db, SETTING_AI)
    current.update(allowed)
    return _set(db, SETTING_AI, current)


def get_subject_prompts(db: Session | None = None) -> dict:
    base = dict(SUBJECT_PROMPTS_DEFAULT)
    if db is not None:
        stored = _get(db, SETTING_PROMPTS)
        if stored:
            base.update({str(k)[:80]: str(v)[:2000] for k, v in stored.items()})
    return base


def set_subject_prompts(db: Session, prompts: dict) -> dict:
    clean = {str(k).strip().lower()[:80]: str(v)[:2000] for k, v in (prompts or {}).items() if str(k).strip()}
    return _set(db, SETTING_PROMPTS, clean)


def get_base_prompt(db: Session | None = None) -> str:
    if db is not None:
        stored = _get(db, SETTING_BASE_PROMPT)
        if stored.get("text"):
            return str(stored["text"])[:8000]
    return BASE_SYSTEM_PROMPT.strip()


def set_base_prompt(db: Session, text: str) -> str:
    _set(db, SETTING_BASE_PROMPT, {"text": (text or "")[:8000]})
    return get_base_prompt(db)


def ai_keys_status() -> dict:
    """Какие ключи заданы в окружении (без раскрытия значений)."""
    keys = {
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
        "XAI_API_KEY": bool(os.getenv("XAI_API_KEY")),
    }
    return keys
