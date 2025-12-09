# CLI Layer

## Ответственность

Слой `cli` содержит **точки входа командной строки** для взаимодействия с приложением.

## Задачи

- Парсинг аргументов командной строки
- Вызов функций из `core` и `adapters`
- Форматирование вывода для пользователя
- Обработка ошибок и отображение понятных сообщений

## Зависимости

CLI **может зависеть** от:
- `core` — использует доменную логику и конфигурацию
- `adapters` — использует адаптеры для работы с внешними сервисами

## Примеры будущих команд

```bash
# Аутентификация
python -m src.cli.auth

# Загрузка одного видео
python -m src.cli.upload --video video.mp4 --title "My Video" --description "Description"

# Пакетная загрузка из конфигурационного файла
python -m src.cli.batch_upload --config uploads.json
```

## Будущая структура

```
cli/
  __init__.py
  auth.py         # Authentication commands
  upload.py       # Single video upload
  batch_upload.py # Batch upload from config
  utils.py        # CLI utilities (progress bars, etc.)
```
