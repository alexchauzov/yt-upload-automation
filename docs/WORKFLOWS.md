\# Workflows



\## Publishing Flow



1\. PublishService.publish\_all\_ready\_tasks()

2\. MetadataRepository.get\_ready\_tasks() — читает задачи со статусом READY

3\. Для каждой задачи:

&nbsp;  - Storage.validate\_file\_exists()

&nbsp;  - VideoBackend.upload\_video()

&nbsp;  - VideoBackend.set\_thumbnail() (если есть)

&nbsp;  - MetadataRepository.update\_task\_status()



\## Idempotency



\- Задачи с заполненным youtube\_video\_id пропускаются

\- Повторные запуски не создают дубликатов



