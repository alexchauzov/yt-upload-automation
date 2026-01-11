# YouTube Publisher

Автоматизированная публикация видео на YouTube по расписанию из Google Sheets.

## Архитектура

Проект построен на принципах **Clean Architecture** с чёткими границами между слоями:

```
yt-upload-automation/
├── domain/          # Бизнес-логика (models, services)
├── ports/           # Интерфейсы для внешних зависимостей
├── adapters/        # Реализации портов (Google Sheets, YouTube API, Storage)
├── app/             # CLI приложение и wiring
└── tests/           # Тесты
    ├── unit/        # Юнит-тесты с моками
    └── integration/ # Интеграционные тесты
```

**Ключевые принципы:**
- Domain не зависит от внешних сервисов
- Легко тестируемая логика с использованием моков
- Легко заменяемые адаптеры (например, заменить Google Sheets на Database)

## Возможности

- Чтение задач публикации из Google Sheets
- Валидация метаданных и файлов
- Загрузка видео на YouTube с метаданными (title, description, tags, thumbnail)
- **Отложенная публикация** (scheduled publishing) - указываете время в Sheets
- Автоматические ретраи при временных ошибках (rate limits, network errors)
- Идемпотентность - повторный запуск не создаст дубликаты
- Dry-run режим - проверка без реальной загрузки
- Структурированное логирование
- Обновление статусов в Google Sheets в реальном времени

## Требования

- Python 3.11+
- Google Cloud Project с включёнными API:
  - Google Sheets API v4
  - YouTube Data API v3
- Service Account для Google Sheets
- OAuth2 credentials для YouTube

## Установка

### 1. Клонирование и создание окружения

```bash
# Создайте виртуальное окружение
python -m venv .venv

# Активация (Windows)
.venv\Scripts\activate

# Активация (Linux/Mac)
source .venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 2. Настройка Google Cloud

#### 2.1. Создайте проект в Google Cloud Console

1. Перейдите на https://console.cloud.google.com/
2. Создайте новый проект или выберите существующий

#### 2.2. Включите необходимые API

1. Перейдите в **APIs & Services > Library**
2. Найдите и включите:
   - **Google Sheets API**
   - **YouTube Data API v3**

#### 2.3. Создайте Service Account для Google Sheets

1. Перейдите в **IAM & Admin > Service Accounts**
2. Нажмите **Create Service Account**
3. Укажите имя (например, `youtube-publisher-sheets`)
4. Нажмите **Create and Continue**
5. Нажмите **Done** (роли не требуются)
6. Нажмите на созданный Service Account
7. Перейдите на вкладку **Keys**
8. Нажмите **Add Key > Create new key**
9. Выберите тип **JSON**
10. Скачайте файл и сохраните как `service_account.json` в корне проекта

**Важно:** Скопируйте email service account (например, `youtube-publisher-sheets@project-id.iam.gserviceaccount.com`)

#### 2.4. Создайте OAuth2 Client для YouTube

1. Перейдите в **APIs & Services > Credentials**
2. Нажмите **Create Credentials > OAuth client ID**
3. Если требуется, настройте OAuth consent screen:
   - User Type: **External**
   - App name: `YouTube Publisher`
   - User support email: ваш email
   - Developer contact: ваш email
   - Scopes: добавьте `../auth/youtube.upload` и `../auth/youtube`
   - Test users: добавьте свой Google аккаунт
4. Application type: **Desktop app**
5. Name: `YouTube Publisher Desktop`
6. Нажмите **Create**
7. Скачайте JSON файл и сохраните как `client_secrets.json` в корне проекта

### 3. Настройка Google Sheets

1. Создайте новую Google Таблицу или откройте существующую
2. Создайте лист с названием `Videos` (или любым другим)
3. Добавьте заголовки колонок согласно [docs/SHEETS_FORMAT.md](docs/SHEETS_FORMAT.md)
4. **Предоставьте доступ Service Account:**
   - Нажмите **Share** в правом верхнем углу
   - Вставьте email service account (из шага 2.3)
   - Выберите роль **Editor**
   - Нажмите **Send**

Минимальный формат таблицы:

| task_id | status | title | video_file_path | description | tags | publish_at | privacy_status |
|---------|--------|-------|-----------------|-------------|------|------------|----------------|
| vid_001 | READY  | My Video | /path/to/video.mp4 | Description | tag1,tag2 | 2025-12-20T10:00:00Z | unlisted |

> **Порядок колонок не важен.** Важно, чтобы первая строка содержала заголовки с указанными именами. Система автоматически определяет позиции колонок по их названиям.

Подробнее в [docs/SHEETS_FORMAT.md](docs/SHEETS_FORMAT.md)

### 4. Настройка переменных окружения

```bash
# Скопируйте пример конфигурации
cp .env.example .env

# Отредактируйте .env
```

Обязательные параметры в `.env`:

```bash
# ID вашей Google Таблицы (из URL)
# https://docs.google.com/spreadsheets/d/ЭТОТ_ID/edit
GOOGLE_SHEETS_ID=your_spreadsheet_id

# Диапазон листа
GOOGLE_SHEETS_RANGE=Videos!A:Z

# Путь к service account JSON
GOOGLE_APPLICATION_CREDENTIALS=service_account.json

# Путь к OAuth2 client secrets
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json

# Путь для хранения OAuth токена (создастся автоматически)
YOUTUBE_TOKEN_FILE=.data/youtube_token.pickle

# Базовая директория для видео файлов (опционально)
STORAGE_BASE_PATH=/path/to/videos
```

Полный список параметров смотрите в `.env.example`.

## Использование

### Первый запуск - OAuth авторизация

При первом запуске откроется браузер для авторизации YouTube:

```bash
python -m app.main
```

1. Войдите в Google аккаунт (тот, который добавили в Test Users)
2. Разрешите доступ к YouTube API
3. Токен сохранится в `.data/youtube_token.pickle`
4. Последующие запуски не требуют авторизации

### Основные команды

**Обычный запуск** - публикация всех задач со статусом READY:

```bash
python -m app.main
```

**Dry-run режим** - валидация без загрузки:

```bash
python -m app.main --dry-run
```

В dry-run режиме:
- Проверяются все валидации
- Проверяется наличие файлов
- Статус меняется на `DRY_RUN_OK`
- **НЕ** выполняется загрузка на YouTube

**Verbose логирование:**

```bash
python -m app.main --verbose
```

**Настройка ретраев:**

```bash
python -m app.main --max-retries 5
```

### Workflow

1. Добавьте строки в Google Sheets со статусом `READY`
2. Запустите `python -m app.main`
3. Система:
   - Прочитает READY задачи
   - Проверит наличие видео файлов
   - Загрузит видео на YouTube
   - Установит scheduled publish (если указано `publish_at`)
   - Загрузит thumbnail (если указан)
   - Обновит статус на `SCHEDULED`
   - При ошибках установит `FAILED` + `error_message`

### Статусы задач

- **READY** - готова к публикации
- **UPLOADING** - загрузка в процессе
- **SCHEDULED** - успешно загружено и запланировано
- **FAILED** - ошибка (смотрите `error_message`)
- **DRY_RUN_OK** - валидация прошла (dry-run режим)

### Идемпотентность

Если задача уже имеет `youtube_video_id`, она будет пропущена. Это позволяет безопасно перезапускать скрипт.

### Ретраи

Автоматические повторы только для временных ошибок:
- 429 (Rate Limit)
- 5xx (Server Errors)
- Network timeouts

Постоянные ошибки (401, 403, 400) не ретраятся.

Счётчик попыток сохраняется в колонке `attempts`.

## Тестирование

### Локальный запуск

```bash
# Unit-тесты (с моками, без внешних API)
pytest -m unit

# Acceptance-тесты (требуют настроенные credentials)
pytest -m acceptance

# Все тесты
pytest

# С coverage
pytest --cov=domain --cov=adapters --cov=app
```

### GitHub Actions CI

CI автоматически запускает тесты на push и PR. Для работы acceptance-тестов настройте секреты репозитория.

#### Настройка GitHub Secrets

Перейдите в **Settings > Secrets and variables > Actions** и добавьте:

| Secret | Описание | Как получить |
|--------|----------|--------------|
| `GOOGLE_SA_JSON` | Полное содержимое JSON-файла service account | `cat service_account.json` |
| `GOOGLE_SHEETS_ID` | ID таблицы из URL | `https://docs.google.com/spreadsheets/d/{ID}/edit` |
| `GOOGLE_SHEETS_RANGE` | Диапазон листа | Например: `Videos!A:Z` |

#### Пример добавления GOOGLE_SA_JSON

```bash
# Скопируйте весь вывод (включая фигурные скобки)
cat service_account.json
```

Вставьте полный JSON как значение секрета:
```json
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  ...
}
```

#### Без секретов

Если секреты не настроены, acceptance-тесты упадут с сообщением:
```
Google Sheets credentials not configured.

Missing:
  - GOOGLE_APPLICATION_CREDENTIALS env var not set
  - GOOGLE_SHEETS_ID env var not set

For GitHub Actions:
  Configure these secrets in Settings > Secrets and variables > Actions:
  - GOOGLE_SA_JSON (full service account JSON)
  - GOOGLE_SHEETS_ID
  - GOOGLE_SHEETS_RANGE
```

## Структура проекта

```
yt-upload-automation/
├── domain/
│   ├── models.py              # VideoTask, PublishResult, enums
│   └── services.py            # PublishService (бизнес-логика)
├── ports/
│   ├── metadata_repository.py # MetadataRepository interface
│   ├── storage.py             # Storage interface
│   └── video_backend.py       # VideoBackend interface
├── adapters/
│   ├── google_sheets_repository.py  # Google Sheets реализация
│   ├── youtube_backend.py           # YouTube API реализация
│   └── local_storage.py             # Локальное хранилище
├── app/
│   └── main.py                # CLI entry point, DI wiring
├── tests/
│   └── unit/
│       └── domain/
│           └── test_publish_service.py  # Тесты PublishService
├── docs/
│   └── SHEETS_FORMAT.md       # Спецификация формата Google Sheets
├── .env.example               # Пример конфигурации
├── requirements.txt           # Зависимости
└── README.md                  # Этот файл
```

## Troubleshooting

### Ошибка: "GOOGLE_SHEETS_ID not configured"

Убедитесь, что файл `.env` существует и содержит `GOOGLE_SHEETS_ID`.

### Ошибка: "Failed to initialize Google Sheets client"

Проверьте:
- Файл `service_account.json` существует
- Путь в `GOOGLE_APPLICATION_CREDENTIALS` корректный
- Google Sheets API включён в проекте

### Ошибка: "Client secrets file not found"

Проверьте:
- Файл `client_secrets.json` существует
- Путь в `YOUTUBE_CLIENT_SECRETS_FILE` корректный

### Ошибка: "403 Forbidden" при доступе к Sheets

- Убедитесь, что вы предоставили доступ service account к вашей таблице
- Email service account должен иметь права Editor

### Ошибка: "Video file not found"

- Проверьте пути к файлам в колонке `video_file_path`
- Если используете относительные пути, установите `STORAGE_BASE_PATH`

### OAuth окно не открывается

Скопируйте URL из консоли и откройте вручную в браузере.

## Безопасность

- **НЕ коммитьте** `.env`, `service_account.json`, `client_secrets.json`, `*.pickle` файлы
- Все секретные файлы уже добавлены в `.gitignore`
- Service Account имеет доступ только к конкретной таблице
- OAuth токен хранится локально в зашифрованном виде

## Лицензия

MIT
