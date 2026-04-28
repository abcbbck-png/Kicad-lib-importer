# Архитектура диалога выбора символов KiCad — Детальный отчёт

> Исследование по исходному коду KiCad (ветка master, путь `/home/anton/VsCode/kicad-research/kicad`)

---

## 1. Архитектура диалога выбора символов

### 1.1 Иерархия классов

```
DIALOG_SHIM
  └── DIALOG_SYMBOL_CHOOSER          (eeschema/dialogs/dialog_symbol_chooser.h)
        └── содержит PANEL_SYMBOL_CHOOSER

wxPanel
  ├── PANEL_SYMBOL_CHOOSER           (eeschema/widgets/panel_symbol_chooser.h)
  │     └── содержит LIB_TREE
  └── LIB_TREE                       (include/widgets/lib_tree.h)
        └── содержит WX_DATAVIEWCTRL + LIB_TREE_MODEL_ADAPTER

wxDataViewModel
  └── LIB_TREE_MODEL_ADAPTER         (include/lib_tree_model_adapter.h)     [ОБЩИЙ]
        ├── SYMBOL_TREE_MODEL_ADAPTER          (eeschema/symbol_tree_model_adapter.h)
        └── SYMBOL_TREE_SYNCHRONIZING_ADAPTER  (eeschema/symbol_tree_synchronizing_adapter.h)

LIB_TREE_NODE                        (include/lib_tree_model.h)             [МОДЕЛЬ ДАННЫХ]
  ├── LIB_TREE_NODE_ROOT
  ├── LIB_TREE_NODE_LIBRARY
  ├── LIB_TREE_NODE_ITEM
  └── LIB_TREE_NODE_UNIT
```

### 1.2 Диаграмма взаимодействия

```
┌──────────────────────────┐
│  DIALOG_SYMBOL_CHOOSER   │  ← Диалог верхнего уровня (dialog_shim)
│  eeschema/dialogs/       │
│  dialog_symbol_chooser.* │
└────────┬─────────────────┘
         │ содержит
         ▼
┌──────────────────────────┐
│  PANEL_SYMBOL_CHOOSER    │  ← Панель выбора символа (wxPanel)
│  eeschema/widgets/       │     Создаёт адаптер, дерево, превью
│  panel_symbol_chooser.*  │
└────────┬─────────────────┘
         │ содержит m_tree, m_adapter
         ▼
┌──────────────────────────┐      ┌─────────────────────────────┐
│  LIB_TREE                │──────│  LIB_TREE_MODEL_ADAPTER     │
│  common/widgets/         │      │  (wxDataViewModel)          │
│  lib_tree.*              │      │  common/lib_tree_model_     │
│                          │      │  adapter.*                  │
│  wxPanel с:              │      │                             │
│  - wxSearchCtrl          │      │  ┌───────────────────────┐  │
│  - WX_DATAVIEWCTRL ◄─────┼──────┤  │ LIB_TREE_NODE_ROOT    │  │
│  - HTML_WINDOW           │      │  │  ├── NODE_LIBRARY (N)  │  │
│                          │      │  │  │    ├── NODE_ITEM (M) │  │
│                          │      │  │  │    │    └── NODE_UNIT │  │
└──────────────────────────┘      │  └───────────────────────┘  │
                                  └─────────────────────────────┘
```

### 1.3 Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `eeschema/dialogs/dialog_symbol_chooser.h/.cpp` | Диалог, обёртка над PANEL_SYMBOL_CHOOSER |
| `eeschema/widgets/panel_symbol_chooser.h/.cpp` | Главная панель выбора. Создаёт адаптер, дерево, превью символов/футпринтов |
| `include/widgets/lib_tree.h`, `common/widgets/lib_tree.cpp` | Виджет дерева (wxPanel). Содержит wxSearchCtrl + WX_DATAVIEWCTRL + HTML_WINDOW |
| `include/lib_tree_model.h`, `common/lib_tree_model.cpp` | Модель данных — иерархия LIB_TREE_NODE |
| `include/lib_tree_model_adapter.h`, `common/lib_tree_model_adapter.cpp` | Адаптер wxDataViewModel → модель данных |
| `eeschema/symbol_tree_model_adapter.h/.cpp` | Специализация адаптера для символов. Загружает символы из SYMBOL_LIB_TABLE |
| `include/lib_tree_item.h` | Полиморфный интерфейс для элементов дерева (символ, футпринт) |
| `eeschema/lib_symbol.cpp` (строки 74-114) | Реализация `GetSearchTerms()` и `GetChooserFields()` для LIB_SYMBOL |

---

## 2. Механизм сворачивания/разворачивания

### 2.1 Используемый виджет

**`WX_DATAVIEWCTRL`** (кастомная обёртка над `wxDataViewCtrl`).

Определение виджета — [lib_tree.h](include/widgets/lib_tree.h), строка ~261:
```cpp
WX_DATAVIEWCTRL*   m_tree_ctrl;
```

Создание — [lib_tree.cpp](common/widgets/lib_tree.cpp), строки ~172-175:
```cpp
int dvFlags = ( aFlags & MULTISELECT ) ? wxDV_MULTIPLE : wxDV_SINGLE;
m_tree_ctrl = new WX_DATAVIEWCTRL( this, wxID_ANY, wxDefaultPosition, wxDefaultSize, dvFlags );
m_adapter->AttachTo( m_tree_ctrl );
```

### 2.2 Как реализовано сворачивание

Сворачивание/разворачивание целиком делегировано **wxDataViewCtrl** через стандартный API:

- `m_tree_ctrl->Expand(item)` / `m_tree_ctrl->Collapse(item)`
- `m_tree_ctrl->ExpandAll()` / `m_tree_ctrl->CollapseAll()`
- `m_tree_ctrl->IsExpanded(item)`
- `m_tree_ctrl->ExpandAncestors(item)` — используется при поиске

Хелпер-метод `LIB_TREE::toggleExpand()` (lib_tree.cpp, строка ~491):
```cpp
void LIB_TREE::toggleExpand( const wxDataViewItem& aTreeId )
{
    if( !aTreeId.IsOk() )
        return;
    if( m_tree_ctrl->IsExpanded( aTreeId ) )
        m_tree_ctrl->Collapse( aTreeId );
    else
        m_tree_ctrl->Expand( aTreeId );
}
```

### 2.3 Где хранится состояние свёрнутости

1. **Во время работы** — wxDataViewCtrl хранит состояние expansion внутренне.
2. **Между сессиями** — адаптер сохраняет список открытых библиотек:
   - `GetOpenLibs()` (lib_tree_model_adapter.cpp, строка ~167) — собирает имена развёрнутых библиотек
   - `OpenLibs()` (строка ~183) — восстанавливает состояние при загрузке
   - Сохраняются в `APP_SETTINGS_BASE::LIB_TREE::open_libs` (m_cfg.open_libs)
3. **При регенерации** — `LIB_TREE::getState()`/`setState()` (lib_tree.cpp, строки ~582-607) сохраняет/восстанавливает expanded items и выделение.

---

## 3. Модель данных дерева

### 3.1 Иерархия узлов LIB_TREE_NODE

Определено в `include/lib_tree_model.h`.

```
LIB_TREE_NODE (базовый абстрактный класс)
│
├── LIB_TREE_NODE::TYPE枚举:
│   ├── ROOT      — корень (невидимый)
│   ├── LIBRARY   — библиотека (сворачиваемый раздел)
│   ├── ITEM      — символ/футпринт (лист или контейнер с units)
│   ├── UNIT      — юнит символа
│   └── INVALID
│
├── LIB_TREE_NODE_ROOT     — корневой узел. Содержит Libraries
│   └── AddLib(name, desc) → LIB_TREE_NODE_LIBRARY
│
├── LIB_TREE_NODE_LIBRARY  — узел библиотеки. Содержит Items
│   └── AddItem(LIB_TREE_ITEM*) → LIB_TREE_NODE_ITEM
│
├── LIB_TREE_NODE_ITEM     — узел символа. Содержит Units (если multi-unit)
│   └── AddUnit(item, unit) → LIB_TREE_NODE_UNIT
│
└── LIB_TREE_NODE_UNIT     — узел юнита (Unit A, Unit B, ...)
```

### 3.2 Уровни вложенности (текущие)

```
ROOT
  └── LIBRARY (библиотека, напр. "Device", "Connector")
        └── ITEM (символ, напр. "R", "C", "ATmega328P")
              └── UNIT (юнит, напр. "Unit A", "Unit B") — только для multi-unit символов
```

**Всего 3 уровня вложенности** (4 типа узлов, но ROOT невидим для пользователя).

### 3.3 Данные в каждом узле

Каждый `LIB_TREE_NODE` (lib_tree_model.h, строки ~127-153) содержит:

| Поле | Тип | Описание |
|------|-----|----------|
| `m_Parent` | `LIB_TREE_NODE*` | Родитель |
| `m_Children` | `PTR_VECTOR` (vector<unique_ptr>) | Дети |
| `m_Type` | `enum TYPE` | ROOT / LIBRARY / ITEM / UNIT |
| `m_Name` | `wxString` | Имя для отображения |
| `m_Desc` | `wxString` | Описание |
| `m_Footprint` | `wxString` | Футпринт (текст поля) |
| `m_PinCount` | `int` | Количество пинов |
| `m_Fields` | `map<wxString, wxString>` | **Произвольные поля** из GetChooserFields |
| `m_SearchTerms` | `vector<SEARCH_TERM>` | Поисковые термины (ключевые слова и пр.) |
| `m_LibId` | `LIB_ID` | Идентификатор библиотеки:символа |
| `m_Unit` | `int` | Номер юнита |
| `m_Score` | `int` | Очки совпадения при поиске |
| `m_IntrinsicRank` | `int` | Изначальный ранг сортировки |
| `m_Pinned` | `bool` | Закреплённая библиотека |
| `m_IsRoot` | `bool` | Корневой символ (не алиас) |

### 3.4 Существующая группировка

На данный момент **группировки внутри библиотек нет**. Однако существует:

1. **Sub-Libraries (суб-библиотеки)** — в `SYMBOL_TREE_MODEL_ADAPTER::AddLibraries()` (строки 150-185):
   ```cpp
   if( row->SupportsSubLibraries() )
   {
       std::vector<wxString> subLibraries;
       row->GetSubLibraryNames( subLibraries );
       // Создает отдельные библиотечные узлы для каждой суб-библиотеки
       // с именем "LibName - SubLibName"
   }
   ```
   Это разделяет одну библиотеку на несколько корневых узлов (NODE_LIBRARY), но НЕ создаёт промежуточных уровней.

2. **Специальные группы** — "Recently Used" и "Already Placed" создаются как NODE_LIBRARY с особыми флагами `m_IsRecentlyUsedGroup`/`m_IsAlreadyPlacedGroup`.

---

## 4. Возможность группировки по полям

### 4.1 Доступные поля символов

Из `LIB_SYMBOL::GetChooserFields()` (lib_symbol.cpp, строка 107):
```cpp
void LIB_SYMBOL::GetChooserFields( std::map<wxString, wxString>& aColumnMap )
{
    for( SCH_ITEM& item : m_drawings[ SCH_FIELD_T ] )
    {
        SCH_FIELD* field = static_cast<SCH_FIELD*>( &item );
        if( field->ShowInChooser() )
            aColumnMap[field->GetName()] = field->EDA_TEXT::GetShownText( false );
    }
}
```

Поля определяются свойством `ShowInChooser()` (`SCH_FIELD::m_showInChooser`). По умолчанию доступны:
- **Value** — добавляется в SYMBOL_TREE_MODEL_ADAPTER (строка 62: `m_availableColumns.emplace_back( wxT( "Value" ) )`)
- **Любые кастомные поля** с флагом `ShowInChooser = true`
- **Description** — всегда доступно (встроено в модель)

Из `LIB_SYMBOL::GetSearchTerms()` (строки 74-101) индексируются для поиска:
- LibNickname (вес 4)
- Name (вес 8)
- LIB_ID полный (вес 16)
- Keywords (вес 4, по токенам)
- Все поля из GetChooserFields (вес 4)
- Keywords как строка (вес 1)
- Description (вес 1)
- Footprint (вес 1)

### 4.2 Существующий механизм фильтрации и сортировки

**Фильтрация:**
- Текстовый поиск через `EDA_COMBINED_MATCHER::ScoreTerms()` — ищет по всем `m_SearchTerms`
- Фильтр по типу (power symbols) через `m_filter` callback
- `UpdateScore()` рекурсивно пересчитывает очки; узлы с `m_Score == 0` скрываются через `GetChildren()` (строка 543: `if( child->m_Score > 0 )`)

**Сортировка:**
- `BEST_MATCH` — по score (при поиске)
- `ALPHABETIC` — по intrinsic rank (алфавитный порядок, StrNumCmp)
- Pinned библиотеки всегда наверху
- "Recently Used" и "Already Placed" всегда наверху

### 4.3 Оценка сложности добавления группировки

#### Что нужно изменить:

**Уровень 1: Модель данных (lib_tree_model.h/.cpp)**

1. Добавить новый тип узла `LIB_TREE_NODE::TYPE::GROUP` (или переиспользовать LIBRARY)
2. Создать класс `LIB_TREE_NODE_GROUP` — промежуточный уровень между LIBRARY и ITEM:

```cpp
class LIB_TREE_NODE_GROUP : public LIB_TREE_NODE
{
public:
    LIB_TREE_NODE_GROUP( LIB_TREE_NODE* aParent, const wxString& aGroupName );
    
    LIB_TREE_NODE_ITEM& AddItem( LIB_TREE_ITEM* aItem );
    
    void UpdateScore( const std::vector<std::unique_ptr<EDA_COMBINED_MATCHER>>& aMatchers,
                      std::function<bool( LIB_TREE_NODE& aNode )>* aFilter ) override;
};
```

3. Модифицировать `LIB_TREE_NODE_LIBRARY::AddItem()` — добавить логику определения группы для элемента на основе указанного поля.

**Уровень 2: Адаптер (lib_tree_model_adapter.h/.cpp)**

1. `GetChildren()` (строка ~540) — уже поддерживает NODE_LIBRARY и NODE_ITEM как контейнеры. Нужно добавить `TYPE::GROUP`:

```cpp
// Текущий код:
if( node->m_Type == LIB_TREE_NODE::TYPE::ROOT
    || node->m_Type == LIB_TREE_NODE::TYPE::LIBRARY
    || ( m_show_units && node->m_Type == LIB_TREE_NODE::TYPE::ITEM ) )

// С группировкой:
if( node->m_Type == LIB_TREE_NODE::TYPE::ROOT
    || node->m_Type == LIB_TREE_NODE::TYPE::LIBRARY
    || node->m_Type == LIB_TREE_NODE::TYPE::GROUP       // ← НОВОЕ
    || ( m_show_units && node->m_Type == LIB_TREE_NODE::TYPE::ITEM ) )
```

2. `IsContainer()` — уже проверяет `m_Children.size()`, должно работать автоматически.

3. `GetParent()` — уже корректно возвращает parent для любого узла. Единственное ограничение: ROOT → null. Работает.

4. `GetValue()` — работает через `m_Name`, `m_Desc`, `m_Fields`. Для GROUP нужно заполнить хотя бы `m_Name`.

5. `FindItem()` — текущий код ищет только на 2 уровнях (lib → item). Нужно добавить третий уровень:

```cpp
// Сейчас:
for lib in root.children:
    for alias in lib.children:
        if alias.name == item_name: return

// Нужно:
for lib in root.children:
    for child in lib.children:
        if child.type == GROUP:
            for alias in child.children:
                if alias.name == item_name: return
        elif child.name == item_name:
            return
```

6. Добавить настройку групировки: `m_groupByField` / `m_groupingEnabled`.

**Уровень 3: SYMBOL_TREE_MODEL_ADAPTER**

1. В `AddLibraries()` / `DoAddLibrary()` — после добавления всех символов в библиотеку, сгруппировать их:

```cpp
void groupLibraryItems( LIB_TREE_NODE_LIBRARY& aLib, const wxString& aFieldName )
{
    std::map<wxString, std::vector<LIB_TREE_NODE*>> groups;
    
    for( auto& child : aLib.m_Children )
    {
        wxString groupKey;
        auto it = child->m_Fields.find( aFieldName );
        if( it != child->m_Fields.end() && !it->second.IsEmpty() )
            groupKey = it->second;
        else
            groupKey = _( "Other" );
        
        groups[groupKey].push_back( child.get() );
    }
    
    if( groups.size() <= 1 )
        return; // Нет смысла группировать
    
    // Переорганизовать дерево: создать GROUP-узлы
    PTR_VECTOR newChildren;
    for( auto& [groupName, items] : groups )
    {
        auto group = std::make_unique<LIB_TREE_NODE_GROUP>( &aLib, groupName );
        for( auto* item : items )
        {
            // Перенести item из aLib.m_Children в group->m_Children
            // Обновить item->m_Parent = group.get()
        }
        newChildren.push_back( std::move(group) );
    }
    aLib.m_Children = std::move( newChildren );
}
```

**Уровень 4: View (lib_tree.cpp)**

1. Минимальные изменения — wxDataViewCtrl уже поддерживает произвольную вложенность.
2. `onTreeCharHook` — WXK_ADD/WXK_SUBTRACT проверяет `TYPE::LIBRARY`. Нужно добавить `TYPE::GROUP`.
3. `getState()`/`setState()` — сохранение expanded state на уровне библиотек. Для полноценной работы нужно расширить на группы.

**Уровень 5: UI настройки**

1. Добавить в сортировочное меню (строка ~109 lib_tree.cpp) опцию "Group by field..."
2. Или добавить настройку в EESCHEMA_SETTINGS.

### 4.4 Конкретные строки для Key-изменений

| Файл | Строки | Что менять |
|------|--------|-----------|
| `include/lib_tree_model.h` | 109-113 | Добавить `TYPE::GROUP` в enum |
| `include/lib_tree_model.h` | 180-205 | Добавить класс `LIB_TREE_NODE_GROUP` |
| `common/lib_tree_model.cpp` | 246-260 | Реализовать `LIB_TREE_NODE_GROUP::UpdateScore()` |
| `common/lib_tree_model_adapter.cpp` | 540-555 | `GetChildren()` — добавить поддержку GROUP |
| `common/lib_tree_model_adapter.cpp` | 506-524 | `FindItem()` — поиск на 3 уровнях |
| `common/lib_tree_model_adapter.cpp` | 239-247 | `DoAddLibrary()` — группировка после добавления |
| `common/lib_tree_model_adapter.h` | 424 | Добавить `m_groupByField` member |
| `common/widgets/lib_tree.cpp` | 109 | Меню сортировки — добавить "Group by..." |
| `common/widgets/lib_tree.cpp` | 668 | WXK_ADD/SUBTRACT — добавить GROUP |
| `eeschema/symbol_tree_model_adapter.cpp` | 120-195 | `AddLibraries()` — вызов группировки |

---

## 5. Конкретные файлы и ключевые строки

### 5.1 Диалог и панель выбора

| Файл | Строки | Описание |
|------|--------|----------|
| `eeschema/dialogs/dialog_symbol_chooser.h` | 40-90 | Класс `DIALOG_SYMBOL_CHOOSER : DIALOG_SHIM` |
| `eeschema/dialogs/dialog_symbol_chooser.cpp` | 42-64 | Конструктор: создание `PANEL_SYMBOL_CHOOSER` |
| `eeschema/widgets/panel_symbol_chooser.h` | 48-100 | Класс `PANEL_SYMBOL_CHOOSER : wxPanel` |
| `eeschema/widgets/panel_symbol_chooser.cpp` | 87-99 | Создание `SYMBOL_TREE_MODEL_ADAPTER` |
| `eeschema/widgets/panel_symbol_chooser.cpp` | 192-200 | Добавление "Recently Used" и "Already Placed" |

### 5.2 Дерево (View)

| Файл | Строки | Описание |
|------|--------|----------|
| `include/widgets/lib_tree.h` | 49-65 | Класс `LIB_TREE : wxPanel`, FLAGS enum |
| `common/widgets/lib_tree.cpp` | 53-200 | Конструктор: создание wxSearchCtrl, WX_DATAVIEWCTRL, HTML_WINDOW |
| `common/widgets/lib_tree.cpp` | 172-175 | Создание `WX_DATAVIEWCTRL` и привязка адаптера |
| `common/widgets/lib_tree.cpp` | 456-465 | `Regenerate()` → `UpdateSearchString()` |
| `common/widgets/lib_tree.cpp` | 491-499 | `toggleExpand()` |
| `common/widgets/lib_tree.cpp` | 582-607 | `getState()`/`setState()` — сохранение expanded |

### 5.3 Модель данных

| Файл | Строки | Описание |
|------|--------|----------|
| `include/lib_tree_model.h` | 78-153 | Базовый `LIB_TREE_NODE` — TYPE enum, все data members |
| `include/lib_tree_model.h` | 159-175 | `LIB_TREE_NODE_UNIT` |
| `include/lib_tree_model.h` | 180-225 | `LIB_TREE_NODE_ITEM` — хранит символ |
| `include/lib_tree_model.h` | 231-260 | `LIB_TREE_NODE_LIBRARY` — хранит библиотеку |
| `include/lib_tree_model.h` | 265-295 | `LIB_TREE_NODE_ROOT` |
| `common/lib_tree_model.cpp` | 140-170 | Конструктор NODE_ITEM: заполнение полей из LIB_TREE_ITEM |
| `common/lib_tree_model.cpp` | 218-243 | `LIB_TREE_NODE_ITEM::UpdateScore()` |
| `common/lib_tree_model.cpp` | 246-260 | Конструктор NODE_LIBRARY |
| `common/lib_tree_model.cpp` | 263-267 | `AddItem()` — добавление символа в библиотеку |

### 5.4 Адаптер (wxDataViewModel)

| Файл | Строки | Описание |
|------|--------|----------|
| `include/lib_tree_model_adapter.h` | 109-155 | Основные методы: SetFilter, ShowUnits, SetPreselectNode, DoAddLibrary |
| `include/lib_tree_model_adapter.h` | 133-138 | TREE_COLS enum: NAME_COL, DESC_COL |
| `common/lib_tree_model_adapter.cpp` | 130-160 | Конструктор: default columns ("Item", "Description") |
| `common/lib_tree_model_adapter.cpp` | 240-254 | `DoAddLibrary()` — добавление библиотеки с элементами |
| `common/lib_tree_model_adapter.cpp` | 265-320 | `UpdateSearchString()` — обновление поиска |
| `common/lib_tree_model_adapter.cpp` | 540-558 | `GetChildren()` — **КЛЮЧЕВОЙ МЕТОД** для вложенности |
| `common/lib_tree_model_adapter.cpp` | 640-660 | `GetParent()` |
| `common/lib_tree_model_adapter.cpp` | 665-700 | `GetValue()` — отображение значений в колонках |
| `common/lib_tree_model_adapter.cpp` | 745-808 | `ShowResults()` — разворачивание при поиске |

### 5.5 Специализация для символов

| Файл | Строки | Описание |
|------|--------|----------|
| `eeschema/symbol_tree_model_adapter.h` | 34-85 | `SYMBOL_TREE_MODEL_ADAPTER : LIB_TREE_MODEL_ADAPTER` |
| `eeschema/symbol_tree_model_adapter.cpp` | 47-52 | `Create()` — фабричный метод |
| `eeschema/symbol_tree_model_adapter.cpp` | 55-62 | Конструктор: добавляет колонку "Value" |
| `eeschema/symbol_tree_model_adapter.cpp` | 65-200 | `AddLibraries()` — загрузка с прогрессом, sub-libraries |
| `eeschema/symbol_tree_model_adapter.cpp` | 150-185 | **Sub-libraries** — уже есть механизм разделения по группам (но на уровне ROOT, а не внутри) |

### 5.6 Данные символа для дерева

| Файл | Строки | Описание |
|------|--------|----------|
| `include/lib_tree_item.h` | 40-90 | Интерфейс `LIB_TREE_ITEM` — GetName, GetDesc, GetChooserFields, GetSearchTerms |
| `eeschema/lib_symbol.cpp` | 74-101 | `LIB_SYMBOL::GetSearchTerms()` — формирование поисковых терминов |
| `eeschema/lib_symbol.cpp` | 107-114 | `LIB_SYMBOL::GetChooserFields()` — поля с `ShowInChooser` |

---

## 6. Рекомендации по реализации

### 6.1 Архитектурный план

#### Фаза 1: Расширение модели данных

1. **Добавить `TYPE::GROUP`** в enum `LIB_TREE_NODE::TYPE` (lib_tree_model.h, строка 109):
```cpp
enum class TYPE
{
    ROOT,
    LIBRARY,
    GROUP,      // ← НОВОЕ: промежуточная группа внутри библиотеки
    ITEM,
    UNIT,
    INVALID
};
```

2. **Создать класс `LIB_TREE_NODE_GROUP`** (lib_tree_model.h):
```cpp
class LIB_TREE_NODE_GROUP : public LIB_TREE_NODE
{
public:
    LIB_TREE_NODE_GROUP( LIB_TREE_NODE_GROUP const& ) = delete;
    void operator=( LIB_TREE_NODE_GROUP const& ) = delete;

    LIB_TREE_NODE_GROUP( LIB_TREE_NODE* aParent, const wxString& aGroupName,
                         const wxString& aDesc = wxEmptyString );

    LIB_TREE_NODE_ITEM& AddItem( LIB_TREE_ITEM* aItem );

    void UpdateScore( const std::vector<std::unique_ptr<EDA_COMBINED_MATCHER>>& aMatchers,
                      std::function<bool( LIB_TREE_NODE& aNode )>* aFilter ) override;
};
```

Реализация `UpdateScore()` аналогична `LIB_TREE_NODE_LIBRARY::UpdateScore()` — агрегация максимального score детей.

#### Фаза 2: Обновление адаптера

3. **`GetChildren()`** — добавить `TYPE::GROUP` как контейнер.
4. **`FindItem()`** — рекурсивный поиск по всем уровням.
5. **Настройка группировки** — добавить методы:
```cpp
void SetGroupByField( const wxString& aFieldName );
wxString GetGroupByField() const;
bool IsGroupingEnabled() const;
```

6. **Метод группировки** — вызывается после `DoAddLibrary()`:
```cpp
void GroupLibraryByField( LIB_TREE_NODE_LIBRARY& aLib, const wxString& aFieldName );
```

#### Фаза 3: UI и настройки

7. В **lib_tree.cpp** добавить пункт "Group by..." в меню сортировки (от кнопки рядом с поиском).
8. Сохранять настройку группировки в `APP_SETTINGS_BASE::LIB_TREE` рядом с `columns` и `open_libs`.

### 6.2 Оценка сложности

| Компонент | Сложность | Объём |
|-----------|-----------|-------|
| Новый тип NODE + класс GROUP | Низкая | ~50 строк |
| Обновление GetChildren, IsContainer | Низкая | ~5 строк |
| Обновление FindItem для 3 уровней | Средняя | ~30 строк |
| Логика группировки по полю | Средняя | ~60 строк |
| ShowResults для 3 уровней | Средняя | ~15 строк |
| UI: пункт меню + настройка | Средняя | ~40 строк |
| Сохранение/загрузка настроек | Низкая | ~20 строк |
| **Итого** | **Средняя** | **~220 строк** |

### 6.3 Ключевые риски

1. **Производительность** — группировка выполняется после загрузки всех символов. Для больших библиотек (1000+ символов) это может замедлить открытие. Решение: группировать lazy или кешировать.

2. **Поиск** — при активном поиске группы должны «сворачиваться» (показывать только найденные элементы). Механизм `UpdateScore` уже поддерживает это через score=0.

3. **Sub-libraries** — уже существующий механизм суб-библиотек создаёт отдельные NODE_LIBRARY. Группировка будет работать внутри каждой суб-библиотеки отдельно. Конфликтов нет.

4. **Synchronizing adapter** — `SYMBOL_TREE_SYNCHRONIZING_ADAPTER` (для редактора символов) синхронизирует дерево с менеджером библиотек. При добавлении группировки нужно обновить `updateLibrary()` метод.

### 6.4 Пример: как будет выглядеть дерево

**До (текущее состояние):**
```
📁 IC
  ├── ATmega328P
  ├── LM358
  ├── NE555
  └── 74HC00
```

**После (с группировкой по Keywords "Type"):**
```
📁 IC
  ├── 📂 Microcontroller
  │     └── ATmega328P
  ├── 📂 OpAmp
  │     └── LM358
  ├── 📂 Timer
  │     └── NE555
  └── 📂 Logic
        └── 74HC00
```

### 6.5 Альтернативный подход: без нового типа узла

Можно **переиспользовать `TYPE::LIBRARY`** для промежуточных групп, создавая «виртуальные библиотеки» внутри реальных. Это проще, но:
- Путается семантика (библиотека ≠ группа)
- Нарушается логика `PinLibrary()`/`UnpinLibrary()`
- Сложнее отличить группу от библиотеки в UI

**Рекомендация: использовать отдельный TYPE::GROUP** — чище архитектурно, минимальные доп. затраты.

---

## 7. Меню выбора столбцов — точка входа для группировки

### 7.1 Текущий механизм

При **правом клике на заголовок столбца** в дереве символов вызывается контекстное меню с единственным пунктом **"Select Columns..."**. Механизм реализован в [lib_tree.cpp](../kicad-research-notes/lib_tree.cpp) → `LIB_TREE::onHeaderContextMenu()`:

```cpp
// common/widgets/lib_tree.cpp:997
void LIB_TREE::onHeaderContextMenu( wxDataViewEvent& aEvent )
{
    ACTION_MENU menu( true, nullptr );
    menu.Add( ACTIONS::selectLibTreeColumns );   // единственный пункт

    if( GetPopupMenuSelectionFromUser( menu ) != wxID_NONE )
    {
        EDA_REORDERABLE_LIST_DIALOG dlg( m_parent, _( "Select Columns" ),
                                         m_adapter->GetAvailableColumns(),
                                         m_adapter->GetShownColumns() );

        if( dlg.ShowModal() == wxID_OK )
            m_adapter->SetShownColumns( dlg.EnabledList() );
    }
}
```

### 7.2 Доступные столбцы

Столбцы формируются динамически из полей символов:

| Источник | Столбцы |
|----------|---------|
| По умолчанию | `Item`, `Description` |
| Из библиотеки | Всё, что возвращает `SYMBOL_LIB_TABLE_ROW::GetAvailableSymbolFields()` |
| Из символа | Поля из `LIB_TREE_ITEM::GetChooserFields()` → `m_Fields` |

Типичные дополнительные столбцы: **Footprint**, **Keywords**, **Datasheet**, **Manufacturer**, **Value**, кастомные поля.

Значения столбцов берутся из `m_Fields` каждого узла:
```cpp
// lib_tree_model_adapter.cpp:694
if( node->m_Fields.count( key ) )
    valueStr = UnescapeString( node->m_Fields.at( key ) );
```

### 7.3 Предложение: Добавить "Group by Column" в контекстное меню заголовка

Наиболее естественное место — **расширить контекстное меню заголовка столбца**. Вместо одного пункта добавить второй:

```
┌─────────────────────────────┐
│  Select Columns...          │  ← уже есть
│  ─────────────────────────  │
│  Group by This Column       │  ← НОВЫЙ пункт
│  ─────────────────────────  │
│  Remove Grouping            │  ← если группировка активна
└─────────────────────────────┘
```

#### Вариант реализации

```cpp
void LIB_TREE::onHeaderContextMenu( wxDataViewEvent& aEvent )
{
    ACTION_MENU menu( true, nullptr );

    menu.Add( ACTIONS::selectLibTreeColumns );

    // --- НОВОЕ: Group by Column ---
    wxString clickedColumn;
    int colIdx = aEvent.GetColumn();  // индекс столбца, по которому кликнули

    if( colIdx >= 0 && m_adapter->GetColumnName( colIdx, clickedColumn ) )
    {
        menu.AppendSeparator();

        wxString label = wxString::Format( _( "Group by '%s'" ), clickedColumn );
        wxMenuItem* groupItem = menu.Append( wxID_ANY, label );

        if( m_adapter->GetGroupColumn() == clickedColumn )
            groupItem->Enable( false );  // уже группировано по этому столбцу
    }

    if( !m_adapter->GetGroupColumn().IsEmpty() )
    {
        menu.Append( wxID_ANY, _( "Remove Grouping" ) );
    }
    // --- конец нового ---

    int selection = GetPopupMenuSelectionFromUser( menu );

    if( selection == ACTIONS::selectLibTreeColumns.GetUIId() )
    {
        EDA_REORDERABLE_LIST_DIALOG dlg( ... );
        if( dlg.ShowModal() == wxID_OK )
            m_adapter->SetShownColumns( dlg.EnabledList() );
    }
    else if( selection == groupItemId )
    {
        m_adapter->SetGroupColumn( clickedColumn );
    }
    else if( selection == removeGroupId )
    {
        m_adapter->SetGroupColumn( wxEmptyString );
    }
}
```

#### Ключевое преимущество подхода

- **Интуитивно**: правый клик по столбцу "Keywords" → "Group by Keywords" — как в Excel/Explorer
- **Минимум UI-изменений**: не нужен новый диалог, используется существующий механизм контекстного меню
- **Контекстно**: пользователь видит конкретный столбец, по которому хочет группировать
- **Обратимо**: пункт "Remove Grouping" легко убирает группировку

### 7.4 Необходимые изменения в адаптере

```cpp
// В LIB_TREE_MODEL_ADAPTER добавить:
class LIB_TREE_MODEL_ADAPTER : public wxDataViewModel
{
    // ...существующие поля...
    wxString m_groupByColumn;  // имя столбца для группировки (пусто = без группировки)

public:
    void SetGroupColumn( const wxString& aColumn );
    wxString GetGroupColumn() const { return m_groupByColumn; }
};

void LIB_TREE_MODEL_ADAPTER::SetGroupColumn( const wxString& aColumn )
{
    if( m_groupByColumn != aColumn )
    {
        m_groupByColumn = aColumn;
        // Перестроить дерево: добавить GROUP-узлы внутри каждой LIBRARY
        rebuildGroupNodes();
        // Уведомить wxDataViewCtrl об изменении структуры
        Cleared();
    }
}
```

### 7.5 Логика `rebuildGroupNodes()`

```cpp
void LIB_TREE_MODEL_ADAPTER::rebuildGroupNodes()
{
    for( auto& libNode : m_tree.m_Children )  // ROOT → LIBRARY
    {
        if( m_groupByColumn.IsEmpty() )
        {
            // Убрать GROUP-узлы, вернуть ITEM напрямую в LIBRARY
            flattenGroups( *libNode );
            continue;
        }

        // Собрать ITEM по значению поля
        std::map<wxString, std::vector<LIB_TREE_NODE*>> groups;

        for( auto& itemNode : libNode->m_Children )
        {
            wxString groupKey;
            if( itemNode->m_Fields.count( m_groupByColumn ) )
                groupKey = itemNode->m_Fields.at( m_groupByColumn );

            if( groupKey.IsEmpty() )
                groupKey = _( "(ungrouped)" );  // fallback

            groups[groupKey].push_back( itemNode.get() );
        }

        // Если все в одной группе — не группировать
        if( groups.size() <= 1 )
            continue;

        // Создать GROUP-узлы и перенести ITEM под них
        PTR_VECTOR newChildren;
        for( auto& [key, items] : groups )
        {
            auto groupNode = std::make_unique<LIB_TREE_NODE_GROUP>( libNode.get(), key );
            for( auto* item : items )
            {
                // Перенести владение
                // ...
            }
            newChildren.push_back( std::move( groupNode ) );
        }
        libNode->m_Children = std::move( newChildren );
    }
}
```

### 7.6 Сохранение настройки группировки

Значение `m_groupByColumn` сохраняется в конфигурацию рядом с `columns`:

```cpp
// в SaveSettings():
m_cfg.group_by_column = m_groupByColumn;

// в конструкторе адаптера:
m_groupByColumn = m_cfg.group_by_column;
```

---

## Приложение: Диаграмма MVC

```
┌─────────────────────────────────────────────────────────────────┐
│                          MODEL                                   │
│  LIB_TREE_NODE_ROOT                                              │
│    ├── LIB_TREE_NODE_LIBRARY  ("Device")                         │
│    │     ├── [LIB_TREE_NODE_GROUP ("Resistors")]  ← НОВОЕ        │
│    │     │     ├── LIB_TREE_NODE_ITEM ("R")                      │
│    │     │     │     └── LIB_TREE_NODE_UNIT ("Unit A")           │
│    │     │     └── LIB_TREE_NODE_ITEM ("R_Pack04")               │
│    │     └── [LIB_TREE_NODE_GROUP ("Capacitors")] ← НОВОЕ        │
│    │           └── LIB_TREE_NODE_ITEM ("C")                      │
│    └── LIB_TREE_NODE_LIBRARY  ("Connector")                      │
│          └── LIB_TREE_NODE_ITEM (...)                             │
└─────────────────────────────────────────────────────────────────┘
         │                              ▲
         │ wxDataViewModel interface    │ UpdateScore(), SortNodes()
         ▼                              │
┌─────────────────────────────────────────────────────────────────┐
│                         ADAPTER                                  │
│  LIB_TREE_MODEL_ADAPTER (wxDataViewModel)                        │
│    ├── GetChildren()  — определяет видимую вложенность            │
│    ├── GetValue()     — определяет что отображается в колонках    │
│    ├── GetParent()    — навигация вверх по дереву                 │
│    ├── IsContainer()  — может ли узел иметь детей                │
│    └── UpdateSearchString() → UpdateScore() → ShowResults()      │
│                                                                  │
│  SYMBOL_TREE_MODEL_ADAPTER (специализация для eeschema)          │
│    ├── AddLibraries() — загрузка символов из SYMBOL_LIB_TABLE    │
│    └── GroupLibraryByField() ← НОВОЕ                             │
└─────────────────────────────────────────────────────────────────┘
         │                              ▲
         │ wxDataViewCtrl              │ User events
         ▼                              │
┌─────────────────────────────────────────────────────────────────┐
│                           VIEW                                   │
│  LIB_TREE (wxPanel)                                              │
│    ├── wxSearchCtrl       — поиск                                │
│    ├── WX_DATAVIEWCTRL    — дерево (сворачивание/разворачивание)  │
│    └── HTML_WINDOW        — описание выбранного элемента         │
│                                                                  │
│  PANEL_SYMBOL_CHOOSER                                            │
│    ├── LIB_TREE                                                  │
│    ├── SYMBOL_PREVIEW_WIDGET                                     │
│    └── FOOTPRINT_PREVIEW_WIDGET                                  │
│                                                                  │
│  DIALOG_SYMBOL_CHOOSER (DIALOG_SHIM)                             │
│    └── PANEL_SYMBOL_CHOOSER                                      │
└─────────────────────────────────────────────────────────────────┘
```
