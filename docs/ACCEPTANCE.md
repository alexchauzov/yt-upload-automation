\# Acceptance Tests



\## КРИТИЧНО



\- НЕ запускать pytest -m acceptance напрямую

\- Использовать ТОЛЬКО:

&nbsp; - scripts/acceptance.cmd (Windows)

&nbsp; - scripts/acceptance.sh (Linux/macOS)



Эти скрипты:

\- автоматически reset spreadsheet

\- гарантируют чистое состояние данных



\## Local Setup



1\. Создать тестовый Google Spreadsheet

2\. Расшарить его на service account email

3\. Установить env vars:

&nbsp;  - GOOGLE\_SHEETS\_ID

&nbsp;  - GOOGLE\_APPLICATION\_CREDENTIALS

4\. Запустить acceptance скрипт



\## Проверка skip поведения



Если credentials отсутствуют:

\- acceptance тесты должны быть автоматически skip

\- с понятным сообщением



