# YouTube Adapter

## Ответственность

Адаптер `youtube` отвечает за **взаимодействие с YouTube Data API v3**.

## Задачи

- Аутентификация через OAuth 2.0
- Загрузка видео на YouTube
- Управление метаданными видео (заголовок, описание, теги, категория, приватность)
- Обработка ответов API и преобразование их в доменные модели

## Зависимости

Адаптер **может зависеть** от:
- `core` — использует модели данных и конфигурацию из core-слоя
- Библиотеки YouTube API (`google-api-python-client`, `google-auth-oauthlib`)

Адаптер **не должен** содержать бизнес-логику — только технические детали работы с API.

## YouTubeUploader

### Описание

Класс `YouTubeUploader` (файл `uploader.py`) реализует загрузку видео на YouTube через YouTube Data API v3.

### Возможности

- Автоматическая OAuth 2.0 аутентификация
- Кэширование токенов для повторного использования
- Загрузка видео с метаданными (заголовок, описание, теги)
- Настройка приватности видео (public, unlisted, private)
- Обработка ошибок API

### Использование

```python
from src.adapters.youtube import YouTubeUploader

# Создание uploader'а (использует конфигурацию из .env)
uploader = YouTubeUploader()

# Загрузка видео
video_id = uploader.upload_video(
    file_path="video.mp4",
    title="My Video Title",
    description="Video description",
    tags=["tag1", "tag2"],
    privacy_status="unlisted"
)

print(f"Video uploaded: https://youtube.com/watch?v={video_id}")
```

### Требования к конфигурации

Для работы `YouTubeUploader` необходимы следующие файлы:

1. **`credentials.json`** — OAuth 2.0 Client ID из Google Cloud Console
   - Получите в [Google Cloud Console](https://console.cloud.google.com/)
   - Тип: Desktop application
   - Включите YouTube Data API v3
   - **НЕ КОММИТИТЬ** в Git (уже в `.gitignore`)

2. **`token.json`** — OAuth токен (создаётся автоматически)
   - Создаётся при первой аутентификации
   - Сохраняется автоматически для повторного использования
   - **НЕ КОММИТИТЬ** в Git (уже в `.gitignore`)

### Первый запуск

При первом использовании `YouTubeUploader`:
1. Откроется браузер с запросом OAuth авторизации
2. Войдите в Google аккаунт
3. Разрешите доступ к YouTube API
4. Токен будет сохранён в `token.json`
5. Последующие запуски будут использовать сохранённый токен

### Безопасность

**ВАЖНО:** Файлы `credentials.json` и `token.json` содержат конфиденциальные данные и не должны попадать в систему контроля версий. Они уже добавлены в `.gitignore`.

## Структура

```
youtube/
  __init__.py       # Экспорт YouTubeUploader
  uploader.py       # Реализация загрузки видео
  README.md         # Эта документация
```
