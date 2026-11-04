# Развёртывание USTAZ AI PRO MAX на Ubuntu 24.04 (VPS)

## Требования
- Ubuntu 24.04 LTS
- Docker Engine 24+ и Docker Compose plugin
- Домен (для HTTPS) или IP (для теста по HTTP на порту 8080)

## 1. Установка Docker
```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
# перелогиньтесь
```

## 2. Проект и .env
```bash
cd /opt
sudo mkdir -p ustaz && sudo chown $USER:$USER ustaz
# скопируйте файлы проекта в /opt/ustaz
cd /opt/ustaz
cp .env.example .env
nano .env
```

Обязательно задайте:
- `POSTGRES_PASSWORD` — длинный случайный пароль
- `DATABASE_URL=postgresql+psycopg://ustaz:ПАРОЛЬ@db:5432/ustaz`
- `ADMIN_SECRET` — секрет админ-панели
- `APP_SECRET` — для хеширования ключей workspace
- `AI_PROVIDER` и соответствующий API-ключ
- `PUBLIC_BASE_URL=https://your.domain`

## 3а. Быстрый запуск (без HTTPS, порт 8080)
```bash
docker compose up -d --build
curl -s http://127.0.0.1:8080/api/health
```

## 3б. Production с Nginx + HTTPS
```bash
mkdir -p certs
# Вариант A: уже есть сертификаты
# cp fullchain.pem privkey.pem certs/

# Вариант B: Let's Encrypt (на хосте)
sudo apt install -y certbot
sudo certbot certonly --standalone -d your.domain
sudo cp /etc/letsencrypt/live/your.domain/fullchain.pem certs/
sudo cp /etc/letsencrypt/live/your.domain/privkey.pem certs/
sudo chown -R $USER:$USER certs

docker compose -f docker-compose.prod.yml up -d --build
```

## 4. Проверки
```bash
docker compose -f docker-compose.prod.yml ps
curl -s https://your.domain/api/health
# {"status":"ok","service":"USTAZ AI PRO MAX"}
```

## 5. Резервное копирование PostgreSQL
```bash
# дамп БД
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U ustaz ustaz > backup-$(date +%F).sql

# восстановление
cat backup-YYYY-MM-DD.sql | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U ustaz ustaz
```

Пользователь также может скачать **личный JSON-бэкап** из интерфейса (IndexedDB-ключ + материалы).

## 6. Обновление
```bash
cd /opt/ustaz
# обновите код
docker compose -f docker-compose.prod.yml up -d --build
```

## Безопасность (этап 10)
- Нет регистрации: доступ по workspace key, ключ в первую очередь хранится в **IndexedDB**; при ошибке IndexedDB возможен fallback в localStorage.
- Публикации только после модерации администратора, с обезличиванием.
- API-ключи AI только на сервере (env), не в браузере.
- HTTPS через Nginx; приложение не публикует порт наружу в prod-compose.
- `ADMIN_SECRET` и `APP_SECRET` — уникальные, длинные.

## Экспорт форматов
| Формат | Как |
|--------|-----|
| DOCX | Редактор → Экспорт DOCX |
| PPTX | Презентации → Экспорт PPTX |
| XLSX | Редактор / презентации → Экспорт XLSX |
| PDF | Просмотр → Печать браузера → «Сохранить как PDF» |
| PNG | Через печать/скриншот слайда (серверная растеризация не включена) |
| JSON | Бэкап workspace |

## Проверено на
- Сборка Docker-образа (python:3.12-slim)
- Схема docker-compose: PostgreSQL 16 + app + nginx
- Целевая ОС: Ubuntu 24.04 LTS
