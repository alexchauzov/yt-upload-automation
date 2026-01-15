\# Workflows



\## Publishing Flow



1\. PublishService.publish\_all\_ready\_tasks()

2\. MetadataRepository.get\_ready\_tasks() — читает задачи со статусом READY

3\. Для каждой задачи:

&nbsp;  - Storage.validate\_file\_exists()

&nbsp;  - VideoBackend.upload\_video()

&nbsp;  - VideoBackend.set\_thumbnail() (если есть)

&nbsp;  - MetadataRepository.update\_task\_status()



\## Retry Logic



Автоматические retry выполняются только для временных ошибок:

\- HTTP 429 (Rate Limit)

\- HTTP 5xx (Server Errors)

\- Network timeouts



Постоянные ошибки (400, 401, 403) не ретраятся.



Счётчик attempts хранится в Google Sheets и увеличивается через

MetadataRepository.increment\_attempts().



\## Idempotency



\- Задачи с заполненным youtube\_video\_id пропускаются

\- Повторные запуски не создают дубликатов



