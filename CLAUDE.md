# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Описание проекта

Генератор address-list российских IPv4-префиксов для MikroTik RouterOS. Скрипт `generate.py` запрашивает данные из RIPE NCC API и создаёт файл `ru_ranges.rsc` с командами `/ip firewall address-list add`. Файл публикуется как GitHub Release через GitHub Actions (ежедневно в 01:00 UTC).

## Запуск

```bash
python generate.py
```

Зависимостей нет — используется только стандартная библиотека Python 3 (`ipaddress`, `json`, `urllib.request`). Выходной файл: `ru_ranges.rsc`.

## Архитектура

Весь проект — один скрипт `generate.py`:

1. Fetch JSON из RIPE NCC API (`stat.ripe.net`, ресурс `RU`)
2. Валидация каждого префикса через `ipaddress.IPv4Network` — отсеиваются private/reserved/loopback/link-local диапазоны и невалидные строки
3. Sanity-check на количество префиксов (1 000–50 000)
4. Генерация `.rsc` файла — только команды `address-list add` с `list=RU comment=RIPE-RU`

## Важные соглашения

- **Безопасность** — ключевой приоритет. `.rsc` файл импортируется на роутерах, поэтому каждый префикс строго валидируется для предотвращения command injection. В `.rsc` записываются **только** `address-list add` команды — удаление старых записей и проверки целостности выполняются на стороне MikroTik-скрипта (см. README.md).
- Символы в префиксе ограничены набором `0123456789./` — дополнительная защита помимо `ipaddress`.
- Константы `MIN_PREFIXES` / `MAX_PREFIXES` — границы допустимого количества префиксов; при выходе за них скрипт завершается с ошибкой.
