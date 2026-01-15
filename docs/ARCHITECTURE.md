\# Architecture



Проект YouTube Publisher построен на принципах Clean Architecture

с чётким разделением ответственности между слоями.



\## Project Structure



\- domain/ — бизнес-логика (models, services)

\- ports/ — интерфейсы для внешних зависимостей

\- adapters/ — реализации портов (Google Sheets, YouTube API, Storage)

\- app/ — CLI приложение и dependency injection wiring



\## Ports



Проект использует интерфейсы (ABC / Protocol) для изоляции domain logic:



\- MetadataRepository — чтение и обновление задач из Google Sheets

\- VideoBackend — загрузка видео на YouTube

\- Storage — работа с локальными файлами



При добавлении новой зависимости:

1\. Определи интерфейс в ports/

2\. Используй интерфейс в domain/

3\. Реализуй адаптер в adapters/

4\. Подключи реализацию в app/main.py



