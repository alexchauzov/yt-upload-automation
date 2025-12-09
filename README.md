# YouTube Upload Automation

Консольный инструмент для автоматизации загрузки видео на YouTube.

## Архитектура

Проект построен на принципах **чистой архитектуры** с разделением на слои:

- **`src/core/`** — доменная логика, независимая от внешних API
- **`src/adapters/`** — адаптеры для работы с внешними сервисами (YouTube API)
- **`src/cli/`** — точки входа командной строки

Подробное описание архитектуры см. в [docs/architecture.md](docs/architecture.md)

## Структура проекта

```
yt-upload-automation/
├── src/
│   ├── core/           # Доменная логика
│   ├── adapters/       # Внешние API
│   └── cli/            # CLI интерфейс
├── tests/
│   ├── unit/           # Юнит-тесты
│   └── integration/    # Интеграционные тесты
├── docs/               # Документация
└── requirements.txt    # Зависимости
```

## Установка

```bash
# Создание виртуального окружения
python -m venv .venv

# Активация (Windows)
.venv\Scripts\activate

# Активация (Linux/Mac)
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

## Конфигурация

Проект использует переменные окружения для конфигурации. Настройка выполняется через файл `.env` в корне проекта.

### Шаги настройки:

1. **Скопируйте example-файл:**
   ```bash
   cp .env.example .env
   ```

2. **Получите credentials от Google:**
   - Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
   - Создайте проект (или выберите существующий)
   - Включите YouTube Data API v3
   - Создайте OAuth 2.0 Client ID (тип: Desktop application)
   - Скачайте JSON-файл с credentials
   - Сохраните его как `credentials.json` в корне проекта

3. **Настройте переменные окружения в `.env`:**

   Файл `.env` поддерживает следующие параметры:

   - `YT_SCOPES` — OAuth scopes для YouTube API
     По умолчанию: `https://www.googleapis.com/auth/youtube.upload`
     Можно указать несколько через запятую или пробел

   - `YT_CREDENTIALS_FILE` — путь к файлу credentials.json
     По умолчанию: `credentials.json`

   - `YT_TOKEN_FILE` — путь для хранения OAuth токена
     По умолчанию: `token.json` (создаётся автоматически после первой аутентификации)

4. **Важно:** Файлы `.env`, `credentials.json` и `token.json` не должны попадать в Git (они уже добавлены в `.gitignore`)

### Пример .env файла:

```bash
YT_SCOPES="https://www.googleapis.com/auth/youtube.upload"
YT_CREDENTIALS_FILE="credentials.json"
YT_TOKEN_FILE="token.json"
```

## Использование

### Загрузка видео

Базовая команда для загрузки видео:

```bash
python -m src.cli.upload_video \
  --file path/to/video.mp4 \
  --title "My test video"
```

Полный пример с описанием, тегами и настройками приватности:

```bash
python -m src.cli.upload_video \
  --file path/to/video.mp4 \
  --title "My test video" \
  --description "Test upload from API" \
  --tags "tutorial,python,automation" \
  --privacy-status unlisted
```

### Параметры команды

- `--file` (обязательный) — путь к видеофайлу
- `--title` (обязательный) — заголовок видео
- `--description` (опциональный) — описание видео
- `--tags` (опциональный) — теги через запятую (например: "tag1,tag2,tag3")
- `--privacy-status` (опциональный) — уровень приватности:
  - `public` — публичное видео
  - `unlisted` — видео по ссылке (по умолчанию)
  - `private` — приватное видео

### Первый запуск

При первом запуске откроется браузер для OAuth авторизации:
1. Войдите в Google аккаунт
2. Разрешите доступ к YouTube API
3. Токен будет сохранён в `token.json`
4. Последующие запуски будут использовать сохранённый токен

### Примеры

Загрузка публичного видео:
```bash
python -m src.cli.upload_video \
  --file my_video.mp4 \
  --title "Public Tutorial" \
  --description "Complete guide" \
  --privacy-status public
```

Загрузка с тегами:
```bash
python -m src.cli.upload_video \
  --file tutorial.mp4 \
  --title "Python Tutorial" \
  --tags "python,programming,tutorial"
```

## Тестирование

Проект включает unit-тесты и заготовки для интеграционных тестов.

### Запуск тестов

```bash
# Запуск всех тестов
pytest

# Запуск только юнит-тестов
pytest tests/unit/

# Запуск только интеграционных тестов
pytest tests/integration/

# Запуск с покрытием кода
pytest --cov=src

# Подробный вывод
pytest -v
```

### Unit-тесты

Unit-тесты находятся в `tests/unit/` и проверяют отдельные компоненты в изоляции:

- **test_config.py** — тестирует загрузку конфигурации из переменных окружения
  - Проверяет значения по умолчанию
  - Проверяет кастомные переменные окружения
  - Проверяет парсинг множественных scopes
  - Проверяет кэширование конфигурации

- **test_cli_upload_video.py** — тестирует CLI-скрипт загрузки видео
  - Проверяет парсинг аргументов командной строки
  - Проверяет вызов uploader'а с правильными параметрами
  - Проверяет обработку ошибок

**Важно:** Unit-тесты **НЕ обращаются** к реальному YouTube API. Все внешние зависимости замоканы.

### Integration-тесты

Интеграционные тесты находятся в `tests/integration/`:

- Сейчас содержат только placeholder
- В будущем будут добавлены тесты с реальным YouTube API
- Потребуют валидные credentials и тестовый аккаунт

## Разработка

При разработке следуйте архитектурным принципам проекта (см. [docs/architecture.md](docs/architecture.md)):

- `core` не должен зависеть от `adapters` или `cli`
- Бизнес-логика в `core`, технические детали в `adapters`
- Пишите unit-тесты для новой функциональности

## Зависимости

- Python 3.8+
- Google API Client
- OAuth 2.0 authentication
- pytest для тестирования

## Лицензия

TODO
