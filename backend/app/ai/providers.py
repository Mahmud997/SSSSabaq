import os
import time
from typing import Any, Callable, Optional
import httpx

class AIConfigurationError(RuntimeError):
    pass

# optional callback: (provider, model, status, error, latency_ms) -> None
_usage_hook: Optional[Callable] = None


def set_usage_hook(hook: Optional[Callable]):
    global _usage_hook
    _usage_hook = hook


def _notify(provider, model, status, error="", latency_ms=0):
    if _usage_hook:
        try:
            _usage_hook(provider=provider, model=model, status=status,
                        error_message=error, latency_ms=latency_ms)
        except Exception:
            pass


class AIProvider:
    """Server-side provider adapter. API keys only from environment. Provider/model from env or admin DB."""
    def __init__(self, provider: str | None = None, model: str | None = None, timeout: float | None = None,
                 enabled: bool = True):
        self.provider = (provider or os.getenv("AI_PROVIDER", "gemini")).lower()
        self.model = model if model is not None else os.getenv("AI_MODEL", "")
        self.timeout = float(timeout if timeout is not None else os.getenv("AI_TIMEOUT_SECONDS", "90"))
        self.enabled = enabled

    @classmethod
    def from_settings(cls, db=None):
        try:
            from ..admin_settings import get_ai_config
            cfg = get_ai_config(db)
            return cls(provider=cfg.get("provider"), model=cfg.get("model") or "",
                       timeout=cfg.get("timeout_seconds"), enabled=cfg.get("enabled", True))
        except Exception:
            return cls()

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled:
            raise AIConfigurationError("AI временно отключён администратором")
        t0 = time.perf_counter()
        try:
            if self.provider == "openai":
                text = await self._openai(system_prompt, user_prompt)
            elif self.provider == "gemini":
                text = await self._gemini(system_prompt, user_prompt)
            elif self.provider == "anthropic":
                text = await self._anthropic(system_prompt, user_prompt)
            elif self.provider == "xai":
                text = await self._openai_compatible(
                    "https://api.x.ai/v1/chat/completions", "XAI_API_KEY",
                    self.model or "grok-3-latest", system_prompt, user_prompt
                )
            else:
                raise AIConfigurationError("Неизвестный AI_PROVIDER")
            _notify(self.provider, self.model or "", "ok", "", int((time.perf_counter() - t0) * 1000))
            return text
        except AIConfigurationError:
            _notify(self.provider, self.model or "", "error", "configuration", int((time.perf_counter() - t0) * 1000))
            raise
        except Exception as exc:
            _notify(self.provider, self.model or "", "error", str(exc)[:400], int((time.perf_counter() - t0) * 1000))
            raise

    async def _openai(self, system_prompt, user_prompt):
        return await self._openai_compatible(
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
            "OPENAI_API_KEY", self.model or "gpt-4.1-mini", system_prompt, user_prompt
        )

    async def _openai_compatible(self, url, key_name, model, system_prompt, user_prompt):
        key = os.getenv(key_name)
        if not key:
            raise AIConfigurationError(f"На сервере не задан {key_name}")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": model, "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], "temperature": 0.4}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _gemini(self, system_prompt, user_prompt):
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise AIConfigurationError("На сервере не задан GEMINI_API_KEY")
        model = self.model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.4}}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params={"key": key}, json=body)
            response.raise_for_status()
            data = response.json()
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])

    async def _anthropic(self, system_prompt, user_prompt):
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise AIConfigurationError("На сервере не задан ANTHROPIC_API_KEY")
        model = self.model or "claude-sonnet-4-20250514"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        body = {"model": model, "max_tokens": 12000, "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post("https://api.anthropic.com/v1/messages",
                                         headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        return "".join(x.get("text", "") for x in data.get("content", []) if x.get("type") == "text")
