# KiCad 10.0.1 Patch Porting Report

Дата проверки: 2026-05-06

## База

- Проверяемая версия: KiCad 10.0.1.
- Официальный релиз: опубликован 2026-04-15 как стабильный bugfix-релиз 10.0.1:
  <https://www.kicad.org/blog/2026/04/KiCad-10.0.1-Release/>
- Исходники для анализа: `kicad-src-10.0.1`, архив GitLab tag `10.0.1`.
- Старый рабочий `kicad-src` не переключался: в нем остались локально примененные патчи 9.0.8.

## Итог по патчам

Активный набор для сборочного скрипта:

- `patches/kicad-10.0.1/local-patches-combined.diff`

Сохранено как reference, но не применяется автоматически:

- `patches/kicad-10.0.1/upstreamed/field-selection-shadow-rotation.diff`

Сборочный скрипт берет только `*.patch`/`*.diff` из корня `patches/kicad-$version` с `maxdepth 1`, поэтому файл в `upstreamed/` не попадет в автоматическое применение.

## Необходимость изменений

### field-selection-shadow-rotation

Статус: основная проблема закрыта upstream в KiCad 10.0.1.

В 9.0.8 локальный фикс исправлял расчет selection-shadow для повернутых полей: shadow-box должен строиться от центра bounding box с центрированными text attributes, а не от `GetDrawPos()`. В исходниках 10.0.1 upstream уже использует `bbox.Centre()` внутри outline-shadow ветки и повторяет центрирование в обеих ветках. Поэтому активный патч для этой ошибки не нужен.

Сохраненный reference-патч только выносит общую подготовку `textpos`/attributes перед ветвлением и добавляет shadow width до outline-ветки. Это можно оставить как косметическую унификацию, но для исправления rotation-bug он уже не требуется.

### outline_font GetInterline guard

Статус: нужен.

В 10.0.1 код все еще делает `GetFace()->units_per_EM` без проверки `GetFace()` и без проверки положительных `height/units_per_EM`. Локальная защита портирована без конфликтов.

### lib tree group-by-column

Статус: нужен.

В 10.0.1 нет `LIB_TREE_NODE_GROUP`, `lib_tree.group_by_column`, `SetGroupColumn()`, `GetGroupColumn()` и header-menu пунктов `Group by`/`Remove Grouping` для дерева библиотек. Патч портирован с учетом изменений 10.0.1:

- `LIB_TREE_MODEL_ADAPTER::loadColumnConfig()` теперь отдельная точка загрузки колонок.
- `AssignIntrinsicRanks()` в sync-коде принимает `m_shownColumns`.
- footprint adapter в 10.0.1 добавил `RefreshLibraryIfChanged()`, поэтому flatten групп вставлен перед refresh/re-enumerate.

### smooth drag zoom

Статус: нужен, если оставляем локальное поведение "курсор стоит на месте".

Upstream 10.0.1 уже имеет часть инфраструктуры infinite-drag для pan (`m_infinitePanWorks`), но drag-zoom по-прежнему использует edge-warp и обновляет `m_dragStartPoint = mousePos`. Локальный патч портирован на код 10.0.1: zoom прячет курсор, готовит infinite drag и возвращает pointer в `m_zoomStartPoint`.

### bus entry size properties

Статус: нужен.

В 10.0.1 upstream добавил/оставил свойства `Wire Style`, `Line Width`, `Color`, но `Size X` и `Size Y` для `SCH_BUS_ENTRY_BASE` отсутствуют. Getter/setter и свойства панели портированы.

### auto wire-to-bus entry

Статус: нужен.

В 10.0.1 нет `tryConvertLastSegmentToBusEntry()`. Патч портирован, включая добавление созданного `SCH_BUS_WIRE_ENTRY` в `finishSegments()`.

При портировании исправлена несовместимость со старым hunk: в 10.0.1 параметр commit называется `aCommit`, поэтому вставка должна быть `aCommit.Added( autoBusEntry, screen )`, а не `commit.Added(...)`.

## Проверка применимости

Выполнено:

- Старые патчи 9.0.8 проверены через `patch --dry-run`: часть hunks легла, часть дала reject из-за изменений 10.0.1.
- Портированные патчи проверены через `git apply --check --cached`.
- Активный `local-patches-combined.diff` проверен через `patch -p1 --dry-run` на чистом экспортированном baseline.
- `git diff --check` на портированном дереве проходит без whitespace errors.

Дополнительно после портирования:

- Полная сборка KiCad 10.0.1 выполнена через `scripts/build_and_install.sh --version 10.0.1 --rebuild`.
- Установка из cache повторно проверена через `scripts/build_and_install.sh --version 10.0.1 --from-cache`.
- `kicad-cli version` возвращает `10.0.1`.
- Проверены загрузчик shared libraries, локализации, footprint/symbol libraries, runtime data path.
- CLI-тесты `Attiny-test.SchLib` и `test_bug_nullbyte.SchLib` проходят.

Не выполнено:

- Runtime GUI-проверка поведения патчей не выполнялась.

## Технические заметки

- Старый `kicad-src` удален и заменен чистым деревом KiCad 10.0.1 из release tarball. Сейчас `kicad-src` содержит исходники 10.0.1 и build-директорию.
- Для первичного анализа использовался `kicad-src-10.0.1` из release tarball; после успешной сборки отдельный анализный снимок удален.
- Попытка `git fetch` в старом `kicad-src` уперлась в права на `.git/FETCH_HEAD`: файл принадлежит `nobody:nogroup`. Для анализа это обошли скачиванием release archive, не меняя владельцев в существующем репозитории.
- При первой полной сборке были исправлены две ошибки портирования group-by-column под API 10.0.1:
  `ShowResults()` -> `showResults()` и `AssignIntrinsicRanks()` -> `AssignIntrinsicRanks( m_shownColumns )`.
- Скрипт сборки переписан на подготовку исходников из release archive и исправлен для установки новых `libki*.so.<version>`, которых еще нет в системе.
- Верификация скрипта переведена на временные XDG-директории в `/tmp`, чтобы CLI-проверки не зависели от доступности пользовательского `~/.config` в sandbox/CI.
