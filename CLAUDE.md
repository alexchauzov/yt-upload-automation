# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Publisher - автоматизированная публикация видео на YouTube по расписанию из Google Sheets.

Проект построен на принципах Clean Architecture с чёткими границами между слоями:
- **domain/** - бизнес-логика (models, services)
- **ports/** - интерфейсы для внешних зависимостей
- **adapters/** - реализации портов (Google Sheets, YouTube API, Storage)
- **app/** - CLI приложение и dependency injection wiring

## Architecture

### Dependency Rules (CRITICAL)

**domain/** НЕ МОЖЕТ зависеть от:
- adapters/
- app/
- ports/ (импортирует только типы Protocol/ABC для type hints)
- Конкретных внешних API

**domain/** может зависеть только от:
- Стандартной библиотеки Python
- Общих библиотек (dataclasses, enum)
- Других модулей внутри domain/

**adapters/** зависит от ports/ (реализует интерфейсы) и domain/ (использует модели)

**app/** зависит от domain/, ports/, и adapters/ (dependency injection)

### Ports Pattern

Проект использует интерфейсы (ABC) для изоляции domain logic:
- `MetadataRepository` - чтение/обновление задач из Google Sheets
- `VideoBackend` - загрузка видео на YouTube
- `Storage` - работа с локальными файлами

При добавлении новых зависимостей:
1. Определи интерфейс в ports/
2. Используй интерфейс в domain/
3. Реализуй адаптер в adapters/
4. Wire в app/main.py

## Commands

### Development

```bash
# Активация виртуального окружения (Windows)
.venv\Scripts\activate

# Активация (Linux/Mac)
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### Running

```bash
# Основной запуск
python -m app.main

# Dry-run (валидация без загрузки)
python -m app.main --dry-run

# Verbose логирование
python -m app.main --verbose

# Кастомное количество ретраев
python -m app.main --max-retries 5
```

### Testing

```bash
# Все тесты
pytest

# Только unit-тесты
pytest tests/unit/

# Отдельный тест-файл
pytest tests/unit/domain/test_publish_service.py

# Coverage
pytest --cov=domain --cov=adapters --cov=app

# Verbose
pytest -v
```

## Configuration

### Environment Variables

Конфигурация через .env файл (см. .env.example):

**Google Sheets (обязательно):**
- `GOOGLE_SHEETS_ID` - ID таблицы из URL
- `GOOGLE_SHEETS_RANGE` - диапазон (default: Videos!A:Z)
- `GOOGLE_APPLICATION_CREDENTIALS` - путь к service_account.json
- `SHEETS_READY_STATUS` - статус для обработки (default: READY)

**YouTube API (обязательно):**
- `YOUTUBE_CLIENT_SECRETS_FILE` - путь к client_secrets.json
- `YOUTUBE_TOKEN_FILE` - путь для OAuth токена (default: .data/youtube_token.pickle)

**Storage (опционально):**
- `STORAGE_BASE_PATH` - базовая директория для видео файлов

**Application:**
- `MAX_RETRIES` - количество попыток для временных ошибок (default: 3)

### Google Sheets Format

Формат таблицы задокументирован в docs/SHEETS_FORMAT.md.

Ключевые особенности:
- Порядок колонок не важен - система определяет по названиям в header
- Регистр названий колонок не важен
- Обязательные колонки: task_id, status, title, video_file_path
- Система обновляет статусы в реальном времени

## Key Workflows

### Publishing Flow

1. PublishService.publish_all_ready_tasks()
2. MetadataRepository.get_ready_tasks() - читает READY задачи из Sheets
3. Для каждой задачи:
   - Storage.validate_file_exists() - проверка наличия файлов
   - VideoBackend.upload_video() - загрузка на YouTube
   - VideoBackend.set_thumbnail() - загрузка thumbnail (если есть)
   - MetadataRepository.update_task_status() - обновление статуса в Sheets

### Retry Logic

Автоматические retry только для временных ошибок:
- HTTP 429 (Rate Limit)
- HTTP 5xx (Server Errors)
- Network timeouts

Постоянные ошибки (401, 403, 400) НЕ ретраятся.

Счётчик attempts хранится в Google Sheets и инкрементируется через MetadataRepository.increment_attempts().

### Idempotency

Задачи с заполненным youtube_video_id пропускаются при повторных запусках - это предотвращает дубликаты при перезапуске скрипта.

## AI Conversation Rules (from PROJECT_GUARDRAILS.md)

- Обращайся на "ты", не "вы"
- Избегай вежливо-формального тона
- Будь кратким, техническим, прямым
- Без мотивационных речей
- Фокус на анализе и конкретных фактах
- НЕ пиши комментарии в коде

## Testing Strategy

Юнит-тесты (tests/unit/):
- Используют моки для внешних зависимостей
- Быстрые (миллисекунды)
- Независимые друг от друга
- Не обращаются к реальным API

Интеграционные тесты (tests/integration/):
- Пока не реализованы (есть placeholder)

При написании тестов для domain/:
- Мокай только ports/ интерфейсы
- Не мокай domain logic
- Используй pytest-mock для создания моков
