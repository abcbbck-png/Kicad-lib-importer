# Исследование: Подключение проводника (Wire) к шине (Bus) в KiCad 9.0.7

## Краткий ответ

**В KiCad проводник (wire) НЕ МОЖЕТ напрямую подключаться к шине (bus). Это поведение — by design, не баг.**

Для подключения wire к bus **обязательно** требуется промежуточный элемент — **Bus Entry** (`SCH_BUS_WIRE_ENTRY`). Если подвести wire к bus без bus entry, появится маркер незавершённости (dangling marker).

---

## 1. Архитектура подключения Wire → Bus

### Конвейер:

```
Wire ←→ Bus Wire Entry ←→ Bus
         (перемычка)
```

### Ключевые классы:

| Класс | Файл | Назначение |
|-------|------|------------|
| `SCH_LINE` | `eeschema/sch_line.cpp` | Проводник (wire) или шина (bus) |
| `SCH_BUS_WIRE_ENTRY` | `eeschema/sch_bus_entry.cpp` | Перемычка wire↔bus |
| `SCH_BUS_BUS_ENTRY` | `eeschema/sch_bus_entry.cpp` | Перемычка bus↔bus |
| `SCH_LINE_WIRE_BUS_TOOL` | `eeschema/tools/sch_line_wire_bus_tool.cpp` | Инструмент рисования |
| `CONNECTION_GRAPH` | `eeschema/connection_graph.cpp` | Граф подключений |

---

## 2. Алгоритм автоподключения — его НЕТ

### 2.1. Доказательство из кода

#### `SCH_LINE::UpdateDanglingState()` (sch_line.cpp:596-643)

```cpp
// Строки 616-617: wire игнорирует BUS_END при проверке dangling
if( ( IsWire() && item.GetType() != BUS_END && item.GetType() != BUS_ENTRY_END )
    || ( IsBus() && item.GetType() != WIRE_END && item.GetType() != PIN_END ) )
{
    m_startIsDangling = false;
    break;
}
```

**Логика**: Wire считает себя «не dangling» только если на его конце есть:
- Другой wire (`WIRE_END`)
- Wire entry (`WIRE_ENTRY_END`)  
- Pin (`PIN_END`)
- Label, junction, sheet pin и т.д.

Wire **НЕ** считает подключение к `BUS_END` и `BUS_ENTRY_END` как валидное соединение. Поэтому при контакте wire c bus — wire остаётся dangling.

#### `SCH_SCREEN::IsTerminalPoint()` (sch_screen.cpp:596-656)

```cpp
case LAYER_WIRE:
    if( GetItem( aPosition, 1, SCH_BUS_WIRE_ENTRY_T ) )  // ← BUS ENTRY, не bus!
        return true;
    if( GetItem( aPosition, 1, SCH_JUNCTION_T ) )
        return true;
    if( GetPin( aPosition, nullptr, true ) )
        return true;
    if( GetWire( aPosition ) )
        return true;
    // ... label, sheet_pin
    break;
```

Wire может терминироваться на: bus entry, junction, pin, другом wire, label, sheet pin.  
**Bus (LAYER_BUS) НЕ является terminal point для wire.**

### 2.2. Единственный способ подключения wire к bus

**Bus Unfold** — специальный инструмент, который:
1. Создаёт `SCH_BUS_WIRE_ENTRY` (перемычку) на шине
2. Создаёт `SCH_LABEL` с именем сигнала из шины
3. Начинает рисование wire от конца bus entry

Код: `SCH_LINE_WIRE_BUS_TOOL::doUnfoldBus()` (sch_line_wire_bus_tool.cpp:393-447)

```cpp
m_busUnfold.entry = new SCH_BUS_WIRE_ENTRY( pos );
m_busUnfold.label = new SCH_LABEL( m_busUnfold.entry->GetEnd(), aNet );
return startSegments( LAYER_WIRE, m_busUnfold.entry->GetEnd() );
```

### 2.3. Автоматическая вставка bus entry при рисовании wire — НЕ реализована

В `doDrawSegments()` и `finishSegments()` нет кода, который бы проверял «а не рисуем ли мы wire к bus?» и автоматически вставлял bus entry. Wire просто устанавливается на позицию курсора и проверяется `IsTerminalPoint()`.

---

## 3. Bus Entry (SCH_BUS_WIRE_ENTRY)

### 3.1. Структура

- **Файлы**: `eeschema/sch_bus_entry.h`, `eeschema/sch_bus_entry.cpp`
- **Размер по умолчанию**: 100 mil × 100 mil (определено в `DEFAULT_SCH_ENTRY_SIZE`)
- **Ориентация**: 4 варианта (flipX/flipY меняют знак `m_size`)
- **Один конец** подключается к bus, **другой** — к wire

### 3.2. Стиль bus entry

Bus entry рисуется как **линия** под 45° от bus:

```
Bus (горизонтальный):
════════╗
        │ ← bus entry (45°)
        │
wire ───┘
```

Настройки стиля через объект `m_stroke`:
- **Ширина**: `m_stroke.SetWidth()` — по умолчанию 0 (из netclass)
- **Тип линии**: `m_stroke.SetLineStyle()` — `LINE_STYLE::DEFAULT`
- **Цвет**: `m_stroke.SetColor()` — `COLOR4D::UNSPECIFIED`

Диалог свойств: `DIALOG_WIRE_BUS_PROPERTIES` — можно задать ширину, стиль (сплошная, пунктир и т.п.), цвет.

### 3.3. Dangling detection для bus entry

`SCH_BUS_WIRE_ENTRY::UpdateDanglingState()` (sch_bus_entry.cpp:315-374):

Bus entry считается корректно подключённым когда:
- Один конец лежит на wire (`has_wire[x] == true`)
- Другой конец лежит на bus (`has_bus[x] == true`)

Если хотя бы одно условие не выполнено — конец помечается как dangling.

---

## 4. Connection Graph и Bus

### 4.1. Как bus entry связывается с bus

В `CONNECTION_GRAPH::buildConnectionGraph()` (connection_graph.cpp:1260-1400):

```cpp
if( connected_item->Type() == SCH_BUS_WIRE_ENTRY_T )
{
    if( test_item->GetLayer() == LAYER_BUS )
    {
        auto bus_entry = static_cast<SCH_BUS_WIRE_ENTRY*>( connected_item );
        bus_entry->m_connected_bus_item = test_item;
    }
}
```

Bus entry хранит указатель на подключённый bus через `m_connected_bus_item`.

### 4.2. Как определяется имя сигнала через bus

Bus содержит список members (например, `D[0..7]` содержит `D0`, `D1`, ..., `D7`).
Wire, подключённый через bus entry, получает имя сигнала от **label** на wire.
Connection graph сопоставляет имя label с member шины.

---

## 5. Почему появляется dangling marker

### Сценарий пользователя:
1. Нарисовал шину (bus)
2. Рисует проводник (wire) к шине
3. Конец wire совпадает с bus → **dangling marker**

### Причина:
- Строка 616 `sch_line.cpp`: wire фильтрует `BUS_END` из списка допустимых подключений
- Строка 632: то же самое для конца wire
- Без bus entry wire не может иметь электрическое соединение с bus

### Это не баг — это архитектурное ограничение:
Wire = один сигнал. Bus = группа сигналов.
Подключение wire напрямую к bus бессмысленно с точки зрения нетлиста — непонятно, какой именно сигнал из группы подключается.

---

## 6. Правильный workflow подключения wire к bus

### Способ 1: Unfold Bus (рекомендуемый)
1. Нарисуйте шину (Place → Bus или клавиша **B**)
2. Добавьте label шины (например `D[0..7]`)
3. **Правый клик** на шине → **Unfold from Bus**
4. Выберите нужный сигнал (например `D0`)
5. KiCad автоматически создаст bus entry + label + начнёт wire

### Способ 2: Вручную
1. Нарисуйте шину
2. **Place → Bus Wire Entry** (или клавиша **/**) — размещаете bus entry на шине
3. Рисуете wire от свободного конца bus entry
4. Ставите label на wire с именем сигнала

---

## 7. Возможные улучшения (если нужно реализовать автоподключение)

### Минимальное изменение: автоинсерт bus entry при завершении wire на bus

В `SCH_LINE_WIRE_BUS_TOOL::finishSegments()` (sch_line_wire_bus_tool.cpp:1183):

```cpp
// Перед commit.Push(), проверяем каждый новый wire:
for( SCH_LINE* wire : m_wires )
{
    if( wire->GetLayer() != LAYER_WIRE )
        continue;
    
    VECTOR2I endPos = wire->GetEndPoint();
    SCH_LINE* bus = screen->GetBus( endPos );
    
    if( bus && !screen->GetItem( endPos, 0, SCH_BUS_WIRE_ENTRY_T ) )
    {
        // Автоматически создать bus entry
        SCH_BUS_WIRE_ENTRY* entry = new SCH_BUS_WIRE_ENTRY( endPos );
        // Расчёт ориентации entry...
        m_frame->AddToScreen( entry, screen );
        commit.Added( entry, screen );
        
        // Сдвинуть конец wire к свободному концу bus entry
        wire->SetEndPoint( entry->GetEnd() );
    }
}
```

**Но** это не решает проблему именования сигнала — без label подключение bus entry к wire не даёт нетлисту информации о том, какой сигнал используется.

---

## 8. Стиль соединения к шине (Bus Entry Style)

### Текущий стиль по умолчанию:
- Линия 45° длиной 100×100 mil
- Ширина = netclass wire width (по умолчанию ~6 mil)
- Цвет = цвет слоя

### Как изменить:
1. **Свойства конкретного bus entry**: двойной клик или E → диалог `DIALOG_WIRE_BUS_PROPERTIES`
   - Ширина линии
   - Стиль линии (сплошная, пунктир, точки, dash-dot и т.д.)
   - Цвет

2. **Глобальные настройки**: 
   - `Preferences → Schematic Editor → Display Options → Default bus thickness`
   - Netclass настройки: `Setup → Net Classes` → Bus width

3. **Размер bus entry**: может быть изменён через свойства (m_size), по умолчанию 100 mil

---

## 9. Ключевые файлы

| Файл | Строки | Описание |
|------|--------|----------|
| `eeschema/sch_line.cpp` | 596-643 | `UpdateDanglingState()` — фильтрует BUS_END |
| `eeschema/sch_line.cpp` | 660-680 | `CanConnect()` — типы совместимых подключений |
| `eeschema/sch_screen.cpp` | 596-656 | `IsTerminalPoint()` — bus не terminal для wire|
| `eeschema/sch_bus_entry.cpp` | 45-100 | Конструкторы bus entry, размер по умолчанию |
| `eeschema/sch_bus_entry.cpp` | 175-220 | Стиль bus entry (stroke, color, width) |
| `eeschema/sch_bus_entry.cpp` | 315-374 | Dangling detection для bus wire entry |
| `eeschema/tools/sch_line_wire_bus_tool.cpp` | 393-447 | `doUnfoldBus()` — unfold шины |
| `eeschema/tools/sch_line_wire_bus_tool.cpp` | 608-1072 | `doDrawSegments()` — рисование wire |
| `eeschema/tools/sch_line_wire_bus_tool.cpp` | 1183-1280 | `finishSegments()` — завершение wire |
| `eeschema/tools/sch_drawing_tools.cpp` | 1390-1560 | Размещение bus entry через Place |
| `eeschema/connection_graph.cpp` | 1260-1400 | Связывание bus entry с bus в графе |
| `eeschema/default_values.h` | 56-66 | DEFAULT_SCH_ENTRY_SIZE = 100 mil |

---

## 10. Вывод

Поведение KiCad **корректно**:
- Wire → Bus напрямую **невозможно** — это by design
- Нужен промежуточный элемент **Bus Entry** 
- Самый удобный способ — **Unfold from Bus** (ПКМ на шине)
- Маркер dangling появляется потому что в `SCH_LINE::UpdateDanglingState()` wire явно отфильтровывает `BUS_END`

Если нужна реализация **автоматического** создания bus entry при рисовании wire к bus — это потребует модификации `finishSegments()` + добавление UI для выбора сигнала из шины.
