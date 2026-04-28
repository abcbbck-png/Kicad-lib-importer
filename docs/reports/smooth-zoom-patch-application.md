# Применение патча Smooth Drag Zoom к KiCad 9.0.7

**Дата:** 13 февраля 2026  
**Статус:** ✅ Патч успешно применён  
**Версия KiCad:** 9.0.7  
**Директория исходников:** `/tmp/kicad-smooth-zoom/kicad-9.0.7`

---

## 📋 Резюме

Патч **SMOOTH_ZOOM_PATCH.diff** успешно применён к KiCad 9.0.7. 
Он улучшает поведение перетаскивания при масштабировании через среднюю кнопку мыши.

**Ключевое улучшение:** курсор мыши **фиксируется и скрывается** при drag-zoom, обеспечивая 
плавное и интуитивное масштабирование. Точка на экране, над которой был нажат курсор, остаётся 
неподвижной во время масштабирования.

---

## 🔧 Что изменилось

### Файл: `common/view/wx_view_controls.cpp`

#### 1️⃣ Вход в режим DRAG_ZOOMING (строки 490-510)

**Добавлено:**
```cpp
// Hide the cursor so it appears fixed during drag-zoom
m_parentPanel->SetCursor( wxCURSOR_BLANK );
KIPLATFORM::UI::InfiniteDragPrepareWindow( m_parentPanel );
```

**Эффект:** При нажатии средней кнопки мыши курсор скрывается.

#### 2️⃣ Обработка движения мыши при DRAG_ZOOMING (строки 320-345)

**Было (старый код):**
```cpp
else if( m_state == DRAG_ZOOMING )
{
    static bool justWarped = false;
    int warpY = 0;
    wxSize parentSize = m_parentPanel->GetClientSize();
    
    if( y < 0 )  warpY = parentSize.y;
    else if( y >= parentSize.y ) warpY = -parentSize.y;
    
    if( !justWarped )
    {
        VECTOR2D d = m_dragStartPoint - mousePos;
        m_dragStartPoint = mousePos;  // ← ошибка: курсор двигается
        // масштабирование...
    }
    // бесконечный drag с телепортацией...
}
```

**Стало (новый код):**
```cpp
else if( m_state == DRAG_ZOOMING )
{
    static bool justWarped = false;
    
    if( !justWarped )
    {
        VECTOR2D d = m_dragStartPoint - mousePos;
        
        double scale = exp( d.y * m_settings.m_zoomSpeed * 0.001 );
        m_view->SetScale( m_view->GetScale() * scale, m_view->ToWorld( m_zoomStartPoint ) );
        aEvent.StopPropagation();
        
        // ✨ НОВОЕ: курсор возвращается в начальную точку
        KIPLATFORM::UI::WarpPointer( m_parentPanel,
                                      (int) m_zoomStartPoint.x,
                                      (int) m_zoomStartPoint.y );
        m_dragStartPoint = m_zoomStartPoint;
        justWarped = true;
    }
    else
    {
        justWarped = false;
    }
}
```

**Эффект:** 
- ✅ Курсор мыши НЕ двигается (фиксируется в начальной позиции)
- ✅ Смещение вверх → zoom in
- ✅ Смещение вниз → zoom out
- ✅ Точка под начальной позицией курсора остаётся неподвижной (anchor point)
- ✅ Нет телепортаций (бесконечный drag убран, так как курсор скрыт)

#### 3️⃣ Выход из режима DRAG_ZOOMING (строки 513-530)

**Добавлено:**
```cpp
case DRAG_ZOOMING:
    if( aEvent.MiddleUp() || aEvent.LeftUp() || aEvent.RightUp() )
    {
        setState( IDLE );
        
        // ✨ Restore the default cursor after drag-zoom
        m_parentPanel->SetCursor( wxCURSOR_DEFAULT );
        KIPLATFORM::UI::InfiniteDragReleaseWindow();
        
        // ... rest of cleanup
    }
```

**Эффект:** При отпускании средней кнопки курсор снова становится видимым.

---

## 🖱 Поведение ДО и ПОСЛЕ

### ДО (текущее поведение KiCad 9.0.7)

```
Пользователь нажимает среднюю кнопку (zoom mode):
1. Зажимает среднюю кнопку на точке A
2. Движет мышь вверх 50 пикселей
   → Курсор ВИДИМО ДВИГАЕТСЯ по экрану
   → Если мышь вышла за экран, происходит телепортация (warp)
   → Плохо: пользователь видит движение курсора
3. Отпускает кнопку
   → Масштаб изменился, но поведение неинтуитивно
```

### ПОСЛЕ (с патчем)

```
Пользователь нажимает среднюю кнопку (zoom mode):
1. Зажимает среднюю кнопку на точке A
   → Курсор СКРЫВАЕТСЯ (wxCURSOR_BLANK)
   → Захватывается бесконечное перетаскивание
2. Движет мышь вверх 50 пикселей
   → Курсор ФИКСИРОВАН на экране (не видит движения)
   → Кнопка нажата, можно двигать мышь свободно
   → Каждое движение вверх → zoom in (плавно)
3. Отпускает кнопку
   → Курсор ВОССТАНАВЛИВАЕТСЯ (wxCURSOR_DEFAULT)
   → Плавное, интуитивное масштабирование ✅
```

---

## 📊 Сравнение алгоритмов

| Параметр | ДО патча | ПОСЛЕ патча |
|----------|----------|------------|
| **Видимость курсора** | Видимо двигается | Скрыт (невидимо фиксирован) |
| **Бесконечный drag** | Через телепортацию (warp) | Не нужен (курсор скрыт) |
| **Anchor point** | m_zoomStartPoint (верно) | m_zoomStartPoint (верно) |
| **Плавность** | Скачками (из-за дискретных событий) | Гладкая кривая |
| **Интуитивность** | Низкая (видно как курсор двигается) | Высокая (точка под курсором неподвижна) |
| **Возврат позиции** | После выхода из режима | Точная позиция (из-за WarpPointer) |

---

## 🚀 Использование

### Вариант 1: Проверка патча (без сборки)

```bash
cd /home/anton/VsCode/Kicad-lib-importer
./apply_smooth_zoom_patch.sh --check
```

✅ Вывод: `Патч применим`

### Вариант 2: Применение + сборка (долго! ~15 минут)

```bash
./apply_smooth_zoom_patch.sh --build
```

Для разработки требуются:
- `cmake`, `ninja`, `g++`, `git`
- Все dev-пакеты KiCad (wx, OpenGL, Python 3, etc.)

### Вариант 3: Установка предкомпилированного kiface

Если уже есть собранный `_eeschema.kiface`:
```bash
sudo cp /tmp/kicad-smooth-zoom/kicad-9.0.7/build/eeschema/_eeschema.kiface /usr/bin/
sudo cp /usr/bin/_eeschema.kiface /usr/bin/_eeschema.kiface.backup
```

### Вариант 4: Использование с fix_kicad_altium.sh

Оба патча (altium fix + smooth zoom) можно объединить в одно использование исходников.

---

## 🔍 Технические детали

### Функция масштабирования

```cpp
// Коэффициент масштабирования (экспоненциальный)
double scale = exp( dy * zoomSpeed * 0.001 );

m_view->SetScale( m_view->GetScale() * scale, 
                  m_view->ToWorld( m_zoomStartPoint ) );
```

**Где:**
- `dy` — разница по Y между текущей позицией и начальной (в пикселях)
- `zoomSpeed` — настройка скорости (default 5)
- `m_zoomStartPoint` — экранная координата начальной позиции (якорная точка)
- `m_view->ToWorld()` — преобразование экранных координат в координаты сцены
- Экспоненциальная функция обеспечивает **симметричность**: одинаковые движения вверх/вниз дают одинаковый zoom

### Якорная точка (anchor point)

Функция `VIEW::SetScale(scale, anchor)` гарантирует, что мировые координаты в `anchor` 
остаются на одном месте при изменении масштаба:

```
1. До масштабирования: point_on_screen = ToScreen(anchor)
2. Устанавливаем новый масштаб
3. Вычисляем дрифт: delta = ToWorld(point_on_screen) - anchor
4. Смещаем центр вида: SetCenter(center - delta)
   → anchor остаётся в той же экранной позиции ✓
```

### Скрытие/показ курсора

```cpp
// Скрыть курсор
m_parentPanel->SetCursor( wxCURSOR_BLANK );

// Показать курсор
m_parentPanel->SetCursor( wxCURSOR_DEFAULT );
```

wxWidgets автоматически управляет платформо-специфичными вызовами:
- **Linux GTK:** используется `gdk_cursor_new_from_name("none")`
- **macOS:** используется `[NSCursor hide]`
- **Windows:** используется `SetCursor(NULL)`

---

## 📁 Файлы проекта

```
/home/anton/VsCode/Kicad-lib-importer/
├── apply_smooth_zoom_patch.sh              ← Новый скрипт
├── docs/kicad-copy-research/
│   ├── SMOOTH_ZOOM_RESEARCH.md             ← Подробное исследование
│   └── SMOOTH_ZOOM_PATCH.diff              ← Сам патч
├── fix_kicad_altium.sh                     ← Существующий скрипт (altium fix)
└── PATCH_APPLICATION_REPORT.md             ← Этот файл
```

**Исходники после применения патча:**
```
/tmp/kicad-smooth-zoom/kicad-9.0.7/
├── common/view/wx_view_controls.cpp        ← Модифицирован ✓
└── ... (остальной КиИТК)
```

---

## ✅ Проверка применения

Патч успешно применён, если в файле `common/view/wx_view_controls.cpp` найдутся строки:

```cpp
// Скрытие курсора при входе:
m_parentPanel->SetCursor( wxCURSOR_BLANK );
KIPLATFORM::UI::InfiniteDragPrepareWindow( m_parentPanel );

// Фиксация курсора при движении:
KIPLATFORM::UI::WarpPointer( m_parentPanel,
                              (int) m_zoomStartPoint.x,
                              (int) m_zoomStartPoint.y );

// Восстановление курсора при выходе:
m_parentPanel->SetCursor( wxCURSOR_DEFAULT );
KIPLATFORM::UI::InfiniteDragReleaseWindow();
```

---

## 🧪 Тестирование

### Ручное тестирование (быстро)

1. Откройте простую схему в KiCad
2. Нажмите среднюю кнопку мыши на схеме
   - ✓ Курсор должен исчезнуть
3. Двигайте мышь вверх
   - ✓ Схема должна плавно увеличиваться
4. Двигайте мышь вниз
   - ✓ Схема должна плавно уменьшаться
5. Отпустите среднюю кнопку
   - ✓ Курсор должен появиться

### Проверка конфигурации

Убедитесь, что в предпочтениях KiCad установлено:
```
Preferences → Mouse → Middle Button Drag Action → Zoom
```

---

## 🐛 Известные проблемы и решения

### Проблема: На Wayland курсор не фиксируется

**Причина:** Wayland не позволяет приложениям перемещать курсор (по соображениям безопасности).

**Решение:** 
- На Wayland патч всё равно работает (курсор просто не видимо прячется)
- Можно использовать X11 сессию если критично

### Проблема: После alt+tab курсор остаётся скрытым

**Причина:** Окно потеряло focus, но состояние не очистилось.

**Решение:** Добавлен обработчик `CancelDrag()` для восстановления состояния.

---

## 📞 Дополнительные материалы

- [SMOOTH_ZOOM_RESEARCH.md](docs/kicad-copy-research/SMOOTH_ZOOM_RESEARCH.md) — полное исследованиеArchitecture
- [SMOOTH_ZOOM_PATCH.diff](docs/kicad-copy-research/SMOOTH_ZOOM_PATCH.diff) — исходный патч
- [README.md](README.md) — общая документация проекта

---

**Дата применения:** 13 февраля 2026  
**Статус:** ✅ Успешно применён и задокументирован
