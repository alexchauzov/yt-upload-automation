\# Testing Strategy



Проект использует pytest и маркеры для разделения типов тестов.



\## Test Markers



\- smoke — smoke tests (imports, CLI)

\- unit — unit tests с моками

\- acceptance — тесты с живым Google Sheets

\- integration — placeholder (future)



\## Test Types



\### Smoke Tests (tests/smoke/)



\- Проверяют imports и CLI --help

\- Не требуют credentials

\- Всегда должны проходить в CI



Команда:

pytest -m smoke



\### Unit Tests (tests/unit/)



\- Используют моки ports интерфейсов

\- Быстрые

\- Не обращаются к реальным API



Команда:

pytest -m unit



\### Acceptance Tests (tests/acceptance/)



\- Работают с живым Google Spreadsheet

\- Требуют credentials

\- READONLY по данным

\- В CI автоматически skip без credentials



Команда:

pytest -m acceptance



\### Integration Tests (tests/integration/)



\- Пока не реализованы



