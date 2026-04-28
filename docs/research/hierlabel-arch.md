# Архитектура иерархических меток (Hierarchical Labels) в KiCad 9.0.7

> Автор: Вася (opus-agent)  
> Дата: 26 февраля 2026 г.  
> Исходники: `/home/anton/VsCode/kicad-research/kicad/eeschema/`

---

## 1. Иерархия классов

Полная цепочка наследования:

```
EDA_ITEM
 └── SCH_ITEM                      (eeschema/sch_item.h)
      └── SCH_TEXT : SCH_ITEM, EDA_TEXT  (eeschema/sch_text.h:37)
           └── SCH_LABEL_BASE           (eeschema/sch_label.h:148)
                ├── SCH_LABEL           (eeschema/sch_label.h:400)
                ├── SCH_GLOBALLABEL     (eeschema/sch_label.h:540)
                ├── SCH_DIRECTIVE_LABEL (eeschema/sch_label.h:455)
                └── SCH_HIERLABEL      (eeschema/sch_label.h:608)
                     └── SCH_SHEET_PIN  (eeschema/sch_sheet_pin.h:68)
```

**Ключевые факты:**
- `SCH_HIERLABEL` наследует от `SCH_LABEL_BASE` (не напрямую от `SCH_TEXT`)
- `SCH_SHEET_PIN` наследует от `SCH_HIERLABEL` — это не отдельная иерархия, а *подкласс* самой иерархической метки
- `SCH_LABEL_BASE` — абстрактный класс с полем `m_shape` и виртуальным `CreateGraphicShape()`
- `SCH_LABEL` (простая метка) **не имеет** собственной формы (не вызывает `CreateGraphicShape`)

---

## 2. Форма (Shape) метки

### 2.1 Enum `LABEL_FLAG_SHAPE`

**Файл:** `eeschema/sch_label.h`, строки 102-113

```cpp
enum LABEL_FLAG_SHAPE : unsigned int
{
    L_INPUT,        // 0 — стрелка "вход"
    L_OUTPUT,       // 1 — стрелка "выход"
    L_BIDI,         // 2 — двунаправленная (ромб)
    L_TRISTATE,     // 3 — три состояния (ромб, как BIDI)
    L_UNSPECIFIED,  // 4 — прямоугольник (passive)

    F_FIRST,
    F_DOT = F_FIRST, // 5 — точка (для directive labels)
    F_ROUND,          // 6 — кружок
    F_DIAMOND,        // 7 — ромб
    F_RECTANGLE       // 8 — прямоугольник
};
```

Значения `L_*` (0-4) используются для `SCH_HIERLABEL`, `SCH_GLOBALLABEL`, `SCH_SHEET_PIN`.  
Значения `F_*` (5-8) используются для `SCH_DIRECTIVE_LABEL`.

### 2.2 Вспомогательные enum для Property Manager

```cpp
enum LABEL_SHAPE : unsigned int    // для SCH_HIERLABEL / SCH_GLOBALLABEL
{
    LABEL_INPUT, LABEL_OUTPUT, LABEL_BIDI, LABEL_TRISTATE, LABEL_PASSIVE
};

enum FLAG_SHAPE : unsigned int     // для SCH_DIRECTIVE_LABEL
{
    FLAG_DOT, FLAG_CIRCLE, FLAG_DIAMOND, FLAG_RECTANGLE
};
```

### 2.3 Где хранится

Поле `m_shape` типа `LABEL_FLAG_SHAPE` объявлено в `SCH_LABEL_BASE` (sch_label.h:388):

```cpp
protected:
    LABEL_FLAG_SHAPE  m_shape;
```

Доступ через `GetShape()` / `SetShape()` (sch_label.h:190-191).

---

## 3. Отрисовка метки

### 3.1 Шаблоны полигонов (hardcoded)

**Файл:** `eeschema/sch_label.cpp`, строки 57-89

Для `SCH_HIERLABEL` формы задаются **захардкоженными массивами координат** полигонов:

```cpp
// Формат: [кол-во_точек, x1,y1, x2,y2, ...]
// Координаты в единицах halfSize (половина высоты текста)
static int TemplateIN_HN[]   = { 6, 0,0, -1,-1, -2,-1, -2,1, -1,1, 0,0 };
static int TemplateOUT_HN[]  = { 6, -2,0, -1,1, 0,1, 0,-1, -1,-1, -2,0 };
static int TemplateUNSPC_HN[]= { 5, 0,-1, -2,-1, -2,1, 0,1, 0,-1 };
static int TemplateBIDI_HN[] = { 5, 0,0, -1,-1, -2,0, -1,1, 0,0 };
static int Template3STATE_HN[]={ 5, 0,0, -1,-1, -2,0, -1,1, 0,0 };
```

Для каждой формы есть 4 варианта ориентации: `_HN` (left), `_HI` (right), `_UP`, `_BOTTOM`.

Таблица маршрутизации:
```cpp
static int* TemplateShape[5][4] = {
    { TemplateIN_HN,   TemplateIN_UP,   TemplateIN_HI,   TemplateIN_BOTTOM   }, // L_INPUT
    { TemplateOUT_HN,  TemplateOUT_UP,  TemplateOUT_HI,  TemplateOUT_BOTTOM  }, // L_OUTPUT
    { TemplateBIDI_HN, TemplateBIDI_UP, TemplateBIDI_HI, TemplateBIDI_BOTTOM }, // L_BIDI
    { Template3STATE.. },                                                        // L_TRISTATE
    { TemplateUNSPC.. }                                                          // L_UNSPECIFIED
};
```

### 3.2 Метод `SCH_HIERLABEL::CreateGraphicShape()`

**Файл:** `eeschema/sch_label.cpp`, строки 2097-2125

```cpp
void SCH_HIERLABEL::CreateGraphicShape( const RENDER_SETTINGS* aSettings,
                                        std::vector<VECTOR2I>& aPoints,
                                        const VECTOR2I& aPos,
                                        LABEL_FLAG_SHAPE aShape ) const
{
    int* Template = TemplateShape[static_cast<int>(aShape)][static_cast<int>(GetSpinStyle())];
    int  halfSize = GetTextHeight() / 2;
    int  imax = *Template;
    Template++;

    aPoints.clear();

    for( int ii = 0; ii < imax; ii++ )
    {
        VECTOR2I corner;
        corner.x = ( halfSize * (*Template) ) + aPos.x;
        Template++;
        corner.y = ( halfSize * (*Template) ) + aPos.y;
        Template++;
        aPoints.push_back( corner );
    }
}
```

**Размер**: shape масштабируется по `halfSize = GetTextHeight() / 2`. Координаты шаблона — множители на halfSize.

### 3.3 Три слоя рендеринга

Форма метки рисуется в **трёх** местах:

| Метод | Файл | Строка | Когда используется |
|-------|-------|--------|--------------------|
| `SCH_LABEL_BASE::Print()` | sch_label.cpp | 1413 | DC-печать (legacy) |
| `SCH_LABEL_BASE::Plot()` | sch_label.cpp | 1282 | Плоттер (PDF/SVG/PS) |
| `SCH_PAINTER::draw(SCH_HIERLABEL*)` | sch_painter.cpp | 2490 | GAL-рендеринг (экран) |

Все три вызывают `CreateGraphicShape()` и рисуют результат как **полилинию** (`GRPoly` / `PlotPoly` / `DrawPolyline`).

### 3.4 Рендеринг (GAL, экранный)

**Файл:** `eeschema/sch_painter.cpp`, строки 2490-2542

```cpp
void SCH_PAINTER::draw( const SCH_HIERLABEL* aLabel, int aLayer, bool aDimmed )
{
    // ... проверки слоёв ...
    
    std::vector<VECTOR2I> i_pts;
    std::deque<VECTOR2D>  d_pts;

    aLabel->CreateGraphicShape( &m_schSettings, i_pts, aLabel->GetTextPos() );

    for( const VECTOR2I& i_pt : i_pts )
        d_pts.emplace_back( VECTOR2D( i_pt.x, i_pt.y ) );

    m_gal->SetIsFill( true );
    m_gal->SetFillColor( m_schSettings.GetLayerColor( LAYER_SCHEMATIC_BACKGROUND ) );
    m_gal->SetIsStroke( true );
    m_gal->SetLineWidth( getLineWidth( aLabel, drawingShadows ) );
    m_gal->SetStrokeColor( color );
    m_gal->DrawPolyline( d_pts );   // <-- рисуется полилиния (не заливка!)

    draw( static_cast<const SCH_TEXT*>( aLabel ), aLayer, false ); // текст
}
```

**Sheet pin тоже рисуется этим же методом** (sch_painter.cpp:2628):
```cpp
for( SCH_SHEET_PIN* sheetPin : aSheet->GetPins() )
    draw( static_cast<SCH_HIERLABEL*>( sheetPin ), aLayer, DNP );
```

### 3.5 Визуальная форма каждого типа

Формы в координатах `halfSize` (HN = left orientation):

| Shape | Точек | Контур (x,y для каждой) | Визуально |
|-------|-------|-------------------------|-----------|
| **L_INPUT** | 6 | (0,0)(-1,-1)(-2,-1)(-2,1)(-1,1)(0,0) | Стрелка → вправо |
| **L_OUTPUT** | 6 | (-2,0)(-1,1)(0,1)(0,-1)(-1,-1)(-2,0) | Стрелка ← влево |
| **L_BIDI** | 5 | (0,0)(-1,-1)(-2,0)(-1,1)(0,0) | Ромб |
| **L_TRISTATE** | 5 | (0,0)(-1,-1)(-2,0)(-1,1)(0,0) | Ромб (как BIDI!) |
| **L_UNSPECIFIED** | 5 | (0,-1)(-2,-1)(-2,1)(0,1)(0,-1) | Прямоугольник |

---

## 4. Связь SCH_HIERLABEL ↔ SCH_SHEET_PIN

### 4.1 Наследование

`SCH_SHEET_PIN` **наследует от** `SCH_HIERLABEL`:

```cpp
class SCH_SHEET_PIN : public SCH_HIERLABEL   // sch_sheet_pin.h:68
```

Это значит, что Sheet Pin — это специализированная иерархическая метка, привязанная к краю листа (sheet).

### 4.2 Общая форма с инверсией Input/Output

**Файл:** `eeschema/sch_sheet_pin.cpp`, строки 308-330

```cpp
void SCH_SHEET_PIN::CreateGraphicShape( ... )
{
    // INPUT и OUTPUT меняются местами!
    LABEL_FLAG_SHAPE shape = m_shape;
    switch( shape )
    {
    case L_INPUT:  shape = L_OUTPUT; break;
    case L_OUTPUT: shape = L_INPUT;  break;
    default: break;
    }
    SCH_HIERLABEL::CreateGraphicShape( aSettings, aPoints, aPos, shape );
}
```

Логика: если внутри листа метка помечена как "Input" (данные поступают в подсхему), то на самом листе пин рисуется как "Output" (данные выходят из листа). Bidirectional, Tristate, Passive — без изменений.

### 4.3 Дополнительные поля SCH_SHEET_PIN

- `m_edge` — сторона листа (LEFT/RIGHT/TOP/BOTTOM), `enum SHEET_SIDE`
- `m_number` — номер пина
- `Print()` просто вызывает `SCH_HIERLABEL::Print()` (sch_sheet_pin.cpp:68-72)

---

## 5. Сериализация (.kicad_sch)

### 5.1 Формат записи иерархической метки

```
(hierarchical_label "ИМЯ_МЕТКИ"
  (shape input|output|bidirectional|tri_state|passive)
  (at X Y ANGLE)
  (fields_autoplaced yes)
  (effects (font (size H W)) (justify left|right))
  (uuid "...")
)
```

### 5.2 Формат записи Sheet Pin (внутри блока sheet)

```
(sheet (at X Y) (size W H)
  ...
  (pin "ИМЯ" input|output|bidirectional|tri_state|passive
    (at X Y ANGLE)
    (effects ...)
    (uuid "...")
  )
)
```

### 5.3 Токены формы

| Токен в файле | LABEL_FLAG_SHAPE | Описание |
|---------------|------------------|----------|
| `input` | L_INPUT | Вход |
| `output` | L_OUTPUT | Выход |
| `bidirectional` | L_BIDI | Двунаправленный |
| `tri_state` | L_TRISTATE | Три состояния |
| `passive` | L_UNSPECIFIED | Пассивный |
| `dot` | F_DOT | Точка (directive) |
| `round` | F_ROUND | Кружок (directive) |
| `diamond` | F_DIAMOND | Ромб (directive) |
| `rectangle` | F_RECTANGLE | Прямоугольник (directive) |

### 5.4 Ключевые функции сериализации

- **Запись:** `getSheetPinShapeToken()` — `sch_io_kicad_sexpr_common.cpp:163`
- **Запись метки:** `SCH_IO_KICAD_SEXPR::saveText()` — `sch_io_kicad_sexpr.cpp:1282` (пишет `(shape ...)`)
- **Чтение:** `SCH_IO_KICAD_SEXPR_PARSER::parseSchText()` — `sch_io_kicad_sexpr_parser.cpp:4275-4345`
- **Тип токена:** `getTextTypeToken()` → `T_hierarchical_label` — `sch_io_kicad_sexpr_common.cpp:202`

---

## 6. Возможность замены визуального изображения

### 6.1 Текущее состояние

- **Нет системы кастомных форм.** Формы жёстко захардкожены в массивах `TemplateIN_*`, `TemplateOUT_*` и т.д.
- **Нет поддержки SVG/bitmap.** Рисуется полилиния по координатам полигона.
- **Нет расширяемого API** для добавления новых форм.

### 6.2 GUI для выбора формы

В диалоге свойств (`dialog_label_properties.cpp:188`) для `SCH_HIERLABEL` и `SCH_GLOBALLABEL` показывается выбор из 5 radio-кнопок:
- Input, Output, Bidirectional, Tri-State, Passive

Форма выбирается через radio-кнопки (`m_input`, `m_output`, `m_bidirectional`, `m_triState`, `m_passive`).  
Кнопки для directive-форм (dot, circle, diamond, rectangle) **скрыты** для иерархических меток.

### 6.3 Оценка сложности замены

#### Вариант А: Модификация существующих форм (ПРОСТОЙ)

**Сложность: низкая (< 1 день)**

Достаточно изменить координаты в массивах `TemplateIN_*`, `TemplateOUT_*` и т.д. (sch_label.cpp:57-87).

Что нужно:
1. Изменить массивы шаблонов в `sch_label.cpp:57-87`
2. Перекомпилировать

**Ограничения:** только полигоны (нет кривых, нет заливки цветом).

#### Вариант Б: Добавление новых форм (СРЕДНИЙ)

**Сложность: средняя (2-4 дня)**

1. Добавить новые значения в `LABEL_FLAG_SHAPE` (sch_label.h)
2. Добавить шаблоны полигонов в `TemplateShape[][]` (sch_label.cpp)
3. Обновить `getSheetPinShapeToken()` (sch_io_kicad_sexpr_common.cpp)
4. Обновить парсер (sch_io_kicad_sexpr_parser.cpp:4333)
5. Обновить диалог свойств (dialog_label_properties.cpp)
6. Обновить `getElectricalTypeLabel()` (sch_label.cpp:93)

#### Вариант В: Произвольные изображения (SVG/bitmap) (СЛОЖНЫЙ)

**Сложность: высокая (1-3 недели)**

Потребуется:
1. Расширить `CreateGraphicShape()` или создать альтернативный метод рисования
2. Изменить `SCH_PAINTER::draw(SCH_HIERLABEL*)` для поддержки растровых/SVG изображений
3. Изменить `Print()` и `Plot()` аналогично
4. Добавить хранение пользовательской формы (поле в классе)
5. Обновить сериализацию для сохранения ссылки на custom shape
6. Обновить `GetBodyBoundingBox()` для корректного вычисления размеров
7. Обновить диалог для выбора/загрузки пользовательских форм

#### Вариант Г: Замена формы целиком через GAL (СРЕДНИЙ-СЛОЖНЫЙ)

Можно переопределить только `SCH_PAINTER::draw(SCH_HIERLABEL*)` (sch_painter.cpp:2490) и вместо `DrawPolyline` использовать `DrawBitmap` или собственные GAL-примитивы. Но `Print()` и `Plot()` тоже потребуют обновления.

---

## 7. Ключевые файлы и строки

### Классы

| Что | Файл | Строки |
|-----|-------|--------|
| `SCH_LABEL_BASE` (объявление) | eeschema/sch_label.h | 148-395 |
| `SCH_HIERLABEL` (объявление) | eeschema/sch_label.h | 608-640 |
| `SCH_SHEET_PIN` (объявление) | eeschema/sch_sheet_pin.h | 68-222 |
| `SCH_GLOBALLABEL` (объявление) | eeschema/sch_label.h | 540-605 |
| `SCH_DIRECTIVE_LABEL` | eeschema/sch_label.h | 455-538 |
| `SCH_TEXT` (базовый) | eeschema/sch_text.h | 37 |
| `LABEL_FLAG_SHAPE` (enum) | eeschema/sch_label.h | 102-113 |
| `m_shape` (поле) | eeschema/sch_label.h | 388 |

### Отрисовка формы

| Что | Файл | Строки |
|-----|-------|--------|
| Шаблоны полигонов (массивы) | eeschema/sch_label.cpp | 57-89 |
| `SCH_HIERLABEL::CreateGraphicShape()` | eeschema/sch_label.cpp | 2097-2125 |
| `SCH_SHEET_PIN::CreateGraphicShape()` | eeschema/sch_sheet_pin.cpp | 308-330 |
| `SCH_GLOBALLABEL::CreateGraphicShape()` | eeschema/sch_label.cpp | 1987-2060 |
| `SCH_DIRECTIVE_LABEL::CreateGraphicShape()` | eeschema/sch_label.cpp | 1682-1718 |
| `SCH_LABEL_BASE::Print()` | eeschema/sch_label.cpp | 1413-1454 |
| `SCH_LABEL_BASE::Plot()` | eeschema/sch_label.cpp | 1282-1410 |
| `SCH_PAINTER::draw(SCH_HIERLABEL*)` | eeschema/sch_painter.cpp | 2490-2542 |
| `SCH_PAINTER::draw(SCH_SHEET*)` (рисует pins) | eeschema/sch_painter.cpp | 2613-2628 |
| `GetBodyBoundingBox()` для HIERLABEL | eeschema/sch_label.cpp | 2127-2176 |

### Сериализация

| Что | Файл | Строки |
|-----|-------|--------|
| `getSheetPinShapeToken()` | eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_common.cpp | 163-177 |
| `getTextTypeToken()` → hierarchical_label | eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_common.cpp | 196-207 |
| Запись shape | eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp | 1282-1287 |
| Чтение shape + создание SCH_HIERLABEL | eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp | 4275, 4333-4345 |
| Чтение sheet pin shape | eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp | 2370-2376 |

### Диалог свойств

| Что | Файл | Строки |
|-----|-------|--------|
| Показ/скрытие shape-кнопок | eeschema/dialogs/dialog_label_properties.cpp | 188-230 |
| Чтение shape из GUI | eeschema/dialogs/dialog_label_properties.cpp | 369-384 |
| Запись shape в объект | eeschema/dialogs/dialog_label_properties.cpp | 590-609 |

---

## Краткое резюме

- Форма `SCH_HIERLABEL` — это **полигон из 5-6 точек**, определённый захардкоженными массивами в `sch_label.cpp`
- Масштаб формы привязан к **½ высоты текста** (`halfSize`)
- `SCH_SHEET_PIN` **наследует от** `SCH_HIERLABEL` и **инвертирует** Input↔Output при отрисовке
- Форма сохраняется как `(shape input|output|...)` в S-expression формате
- **Замена изображения на SVG/bitmap потребует существенных изменений** (5-7 файлов, ~300-500 строк нового кода)
- **Изменение геометрии полигона** — элементарно: достаточно отредактировать массивы `Template*` (~30 строк в одном файле)
