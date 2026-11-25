# ru-ranges

Address-list российских IP-префиксов для MikroTik RouterOS. Обновляется ежедневно из данных RIPE NCC.
## Скачать

Актуальные файлы доступны по прямым ссылкам — они подходят для скачивания из RouterOS без перенаправления GitHub Releases:

```
https://raw.githubusercontent.com/drkop/ru-ranges/downloads/ru_ranges.rsc
https://raw.githubusercontent.com/drkop/ru-ranges/downloads/ru_ranges_timeout.rsc
```

Архивы также доступны на странице [Releases](https://github.com/drkop/ru-ranges/releases/tag/latest).

## Как это работает

- GitHub Actions запускается ежедневно в 01:00 UTC (04:00 MSK)
- Скрипт запрашивает все IPv4-префиксы РФ через [RIPE NCC API](https://stat.ripe.net/)
- Генерируется [`ru_ranges.rsc`](https://github.com/drkop/ru-ranges/releases/tag/latest) (~11 000 префиксов) — каждая строка это `/ip firewall address-list add` в list `RU`
- Файлы публикуются как GitHub Release и в ветку `downloads` для прямой загрузки

## Настройка MikroTik

### 1. Создать скрипт обновления

```routeros
/system script add name=update_ru_list policy=read,write,test,ftp source={
    :local url "https://raw.githubusercontent.com/drkop/ru-ranges/downloads/ru_ranges.rsc"
    :local fileName "ru_ranges.rsc"

    # --- Fetch ---
    :do {
        /tool fetch url=$url dst-path=$fileName mode=https http-header-field="User-Agent: MikroTik" http-max-redirect-count=10
    } on-error={
        :log error "RU list: fetch failed"
        :error "fetch failed"
    }
    :delay 2s

    # --- File size check (expect ~750KB for ~11K prefixes) ---
    :local fileSize [/file get [find name=$fileName] size]
    :if ($fileSize < 400000 || $fileSize > 2000000) do={
        :log error ("RU list: BLOCKED - bad file size " . $fileSize . " bytes")
        /file remove $fileName
        :error "bad file size"
    }

    # --- Snapshot before import (for rollback checks) ---
    :local oldRuCount [/ip firewall address-list print count-only where list=RU and comment=RIPE-RU]
    :local oldUserCount [/user print count-only]
    :local oldFilterCount [/ip firewall filter print count-only]
    :local oldNatCount [/ip firewall nat print count-only]
    :local oldMangleCount [/ip firewall mangle print count-only]
    :local oldScriptCount [/system script print count-only]
    :local oldSchedulerCount [/system scheduler print count-only]

    # --- Remove old entries and import ---
    /ip firewall address-list remove [find where list=RU and comment=RIPE-RU]

    :do {
        /import file=$fileName
    } on-error={
        :log error "RU list: import failed"
        /file remove $fileName
        :error "import failed"
    }

    # --- Post-import safety checks ---
    # If import injected anything beyond address-list entries, rollback
    :local safe true

    :local newRuCount [/ip firewall address-list print count-only where list=RU and comment=RIPE-RU]
    :if ($newRuCount < 1000) do={
        :log error ("RU list: BLOCKED - too few entries: " . $newRuCount)
        :set safe false
    }

    :if ([/user print count-only] != $oldUserCount) do={
        :log error "RU list: BLOCKED - user count changed after import!"
        :set safe false
    }
    :if ([/ip firewall filter print count-only] != $oldFilterCount) do={
        :log error "RU list: BLOCKED - firewall filter rules changed!"
        :set safe false
    }
    :if ([/ip firewall nat print count-only] != $oldNatCount) do={
        :log error "RU list: BLOCKED - NAT rules changed!"
        :set safe false
    }
    :if ([/ip firewall mangle print count-only] != $oldMangleCount) do={
        :log error "RU list: BLOCKED - mangle rules changed!"
        :set safe false
    }
    :if ([/system script print count-only] != $oldScriptCount) do={
        :log error "RU list: BLOCKED - scripts changed!"
        :set safe false
    }
    :if ([/system scheduler print count-only] != $oldSchedulerCount) do={
        :log error "RU list: BLOCKED - schedulers changed!"
        :set safe false
    }

    /file remove $fileName

    :if ($safe = false) do={
        :log error "RU list: TAMPERING DETECTED - check log for details"
        :error "tampering detected"
    }

    :log info ("RU list updated: " . $oldRuCount . " -> " . $newRuCount . " entries")
}
```

### 2. Добавить scheduler

```routeros
/system scheduler add name=update_ru_list interval=1d start-time=04:05:00 on-event="/system script run update_ru_list" policy=read,write,test,ftp
```

### 3. Запустить вручную (первый раз)

```routeros
/system script run update_ru_list
```

### 4. Проверить

```routeros
/ip firewall address-list print count-only where list=RU and comment=RIPE-RU
```

Должно вернуть ~11 000.

### 5. Посмотреть лог

```routeros
/log print where message~"RU list"
```
