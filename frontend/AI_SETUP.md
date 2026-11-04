# Подключение AI (серверная сторона)

В `.env` задайте одного провайдера:
- `AI_PROVIDER=gemini` + `GEMINI_API_KEY=...`
- `AI_PROVIDER=openai` + `OPENAI_API_KEY=...`
- `AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=...`
- `AI_PROVIDER=xai` + `XAI_API_KEY=...`

Дополнительно:
- `AI_MODEL` — модель провайдера (если пусто, используется модель по умолчанию адаптера).
- `AI_TIMEOUT_SECONDS=90`

Ключи хранятся только в `.env` на сервере. Никогда не помещайте их в `frontend/`, HTML, JavaScript, GitHub Pages или публичный репозиторий.
Для production используйте менеджер секретов/зашифрованные секреты CI, ограничение сетевого доступа и ротацию ключей.
