# -*- coding: utf-8 -*-
"""wxPython dialog for the connector generator plugin."""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "tools" / "connector_generator" / "connector_generator.py").is_file():
            return parent
    raise RuntimeError("Не найден корень проекта с tools/connector_generator")


def _load_generator():
    root = _repo_root()
    generator_dir = root / "tools" / "connector_generator"
    if str(generator_dir) not in sys.path:
        sys.path.insert(0, str(generator_dir))

    import connector_generator as generator

    return root, generator


def _default_config_path() -> Path:
    return _repo_root() / "tools" / "connector_generator" / "connectors.toml"


def _parse_int_list(text: str) -> tuple[int, ...]:
    values: list[int] = []
    for chunk in text.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.append(int(chunk))
    if not values:
        raise ValueError("Список пинов пуст")
    return tuple(values)


class ConnectorGeneratorDialog:
    def __new__(cls, *args, **kwargs):
        import wx

        class _Dialog(wx.Dialog):
            def __init__(self, parent):
                super().__init__(
                    parent,
                    title="Connector Generator",
                    style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                    size=(1040, 720),
                )
                self.root, self.generator = _load_generator()
                self.config_path = _default_config_path()
                self.library_path: Path | None = None
                self.specs = []

                self._build_ui()
                self._load_config()

            def _build_ui(self):
                import wx

                panel = wx.Panel(self)
                main = wx.BoxSizer(wx.VERTICAL)

                title = wx.StaticText(panel, label="Генератор разъемов")
                font = title.GetFont()
                font.SetPointSize(font.GetPointSize() + 4)
                font.SetWeight(wx.FONTWEIGHT_BOLD)
                title.SetFont(font)
                main.Add(title, 0, wx.ALL, 10)

                config_row = wx.BoxSizer(wx.HORIZONTAL)
                config_row.Add(wx.StaticText(panel, label="Конфиг:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
                self.config_ctrl = wx.TextCtrl(panel, value=str(self.config_path))
                config_row.Add(self.config_ctrl, 1, wx.RIGHT, 6)
                browse = wx.Button(panel, label="Выбрать")
                browse.Bind(wx.EVT_BUTTON, self._on_browse_config)
                config_row.Add(browse, 0)
                main.Add(config_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

                lib_row = wx.BoxSizer(wx.HORIZONTAL)
                lib_row.Add(wx.StaticText(panel, label="Библиотека:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
                self.library_ctrl = wx.TextCtrl(panel, style=wx.TE_READONLY)
                lib_row.Add(self.library_ctrl, 1)
                main.Add(lib_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

                series_box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Серия"), wx.VERTICAL)

                grid = wx.FlexGridSizer(rows=5, cols=4, hgap=8, vgap=8)
                grid.AddGrowableCol(1, 1)
                grid.AddGrowableCol(3, 1)

                self.prefix_ctrl = wx.TextCtrl(panel, value="Con")
                self.reference_ctrl = wx.TextCtrl(panel, value="X")
                self.value_ctrl = wx.TextCtrl(panel, value="XX")
                self.name_ctrl = wx.TextCtrl(panel, value="Разъем универсальный")
                self.pin_ctrls = {
                    1: wx.TextCtrl(panel, value=",".join(str(value) for value in range(1, 41))),
                    2: wx.TextCtrl(panel, value=",".join(str(value) for value in range(2, 41))),
                    3: wx.TextCtrl(panel, value=",".join(str(value) for value in range(3, 41))),
                }

                grid.Add(wx.StaticText(panel, label="Префикс"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.prefix_ctrl, 1, wx.EXPAND)
                grid.Add(wx.StaticText(panel, label="Reference"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.reference_ctrl, 1, wx.EXPAND)

                grid.Add(wx.StaticText(panel, label="Value"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.value_ctrl, 1, wx.EXPAND)
                grid.Add(wx.StaticText(panel, label="Имя"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.name_ctrl, 1, wx.EXPAND)

                grid.Add(wx.StaticText(panel, label="Пины: 1 ряд"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.pin_ctrls[1], 1, wx.EXPAND)
                grid.Add(wx.StaticText(panel, label="Пины: 2 ряда"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.pin_ctrls[2], 1, wx.EXPAND)

                grid.Add(wx.StaticText(panel, label="Пины: 3 ряда"), 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self.pin_ctrls[3], 1, wx.EXPAND)
                grid.AddSpacer(1)
                grid.AddSpacer(1)
                series_box.Add(grid, 0, wx.EXPAND | wx.ALL, 8)

                options = wx.BoxSizer(wx.HORIZONTAL)
                options.Add(wx.StaticText(panel, label="Ряды:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
                self.row_checks = {}
                for rows in (1, 2, 3):
                    chk = wx.CheckBox(panel, label=str(rows))
                    chk.SetValue(True)
                    self.row_checks[rows] = chk
                    options.Add(chk, 0, wx.RIGHT, 12)

                options.AddSpacer(18)
                options.Add(wx.StaticText(panel, label="Нумерация:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
                self.scheme_checks = {}
                for code, label in (
                    ("R", "R рядами"),
                    ("S", "S колонками"),
                    ("Z", "Z змейкой"),
                ):
                    chk = wx.CheckBox(panel, label=label)
                    chk.SetValue(code in ("R", "S"))
                    self.scheme_checks[code] = chk
                    options.Add(chk, 0, wx.RIGHT, 12)
                series_box.Add(options, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

                labels = wx.BoxSizer(wx.HORIZONTAL)
                labels.Add(wx.StaticText(panel, label="Надписи выводов:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
                self.show_pin_numbers_chk = wx.CheckBox(panel, label="Показать номер вывода")
                self.show_pin_numbers_chk.SetValue(True)
                labels.Add(self.show_pin_numbers_chk, 0, wx.RIGHT, 16)
                self.show_pin_names_chk = wx.CheckBox(panel, label="Показать имя вывода")
                self.show_pin_names_chk.SetValue(False)
                labels.Add(self.show_pin_names_chk, 0, wx.RIGHT, 16)
                self.body_fill_chk = wx.CheckBox(panel, label="Заливка фоном")
                self.body_fill_chk.SetValue(True)
                labels.Add(self.body_fill_chk, 0, wx.RIGHT, 16)
                series_box.Add(labels, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

                main.Add(series_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

                actions = wx.BoxSizer(wx.HORIZONTAL)
                for label, handler in (
                    ("Обновить список", self._on_preview),
                    ("Сгенерировать", self._on_write),
                    ("Открыть конфиг", self._on_open_config),
                    ("Технический diff", self._on_diff),
                ):
                    btn = wx.Button(panel, label=label)
                    btn.Bind(wx.EVT_BUTTON, handler)
                    actions.Add(btn, 0, wx.RIGHT, 8)
                actions.AddStretchSpacer(1)
                close = wx.Button(panel, wx.ID_CLOSE, label="Закрыть")
                close.Bind(wx.EVT_BUTTON, lambda _event: self.Close())
                actions.Add(close, 0)
                main.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

                content = wx.BoxSizer(wx.HORIZONTAL)
                self.symbols = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
                for idx, (heading, width) in enumerate(
                    [
                        ("Символ", 210),
                        ("Пинов", 70),
                        ("Схема", 110),
                        ("Статус", 260),
                    ]
                ):
                    self.symbols.InsertColumn(idx, heading, width=width)
                self.symbols.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_select_symbol)
                content.Add(self.symbols, 1, wx.EXPAND | wx.RIGHT, 8)

                self.preview = wx.TextCtrl(
                    panel,
                    style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL,
                )
                mono = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
                self.preview.SetFont(mono)
                content.Add(self.preview, 1, wx.EXPAND)
                main.Add(content, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

                self.status = wx.StaticText(panel, label="")
                main.Add(self.status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

                panel.SetSizer(main)
                sizer = wx.BoxSizer(wx.VERTICAL)
                sizer.Add(panel, 1, wx.EXPAND)
                self.SetSizer(sizer)

            def _current_config_path(self) -> Path:
                return Path(self.config_ctrl.GetValue()).expanduser()

            def _format_int_list(self, values):
                return ",".join(str(value) for value in values)

            def _load_config(self):
                try:
                    config = self._current_config_path()
                    library_path, series, symbols = self.generator.load_config(config)
                    self.library_path = library_path
                    self.library_ctrl.SetValue(str(library_path))

                    if series:
                        first = series[0]
                        self.prefix_ctrl.SetValue(first.prefix)
                        for rows, ctrl in self.pin_ctrls.items():
                            values = first.pins_per_row
                            if first.pins_per_row_by_rows is not None:
                                values = first.pins_per_row_by_rows.get(rows, ())
                            ctrl.SetValue(self._format_int_list(values))
                        self.reference_ctrl.SetValue(first.reference)
                        self.value_ctrl.SetValue(first.value)
                        self.name_ctrl.SetValue(first.display_name)
                        for rows, chk in self.row_checks.items():
                            chk.SetValue(rows in first.rows)
                        for code, chk in self.scheme_checks.items():
                            chk.SetValue(code in first.schemes)
                        self.show_pin_numbers_chk.SetValue(first.show_pin_numbers)
                        self.show_pin_names_chk.SetValue(first.show_pin_names)
                        self.body_fill_chk.SetValue(first.geometry.body_fill == "background")

                    self._refresh_preview()
                    if symbols:
                        self.status.SetLabel(f"Конфиг загружен. Точечных override: {len(symbols)}")
                    else:
                        self.status.SetLabel("Конфиг загружен.")
                except Exception as exc:
                    self.library_path = None
                    self.library_ctrl.SetValue("")
                    self.symbols.DeleteAllItems()
                    self.preview.SetValue(f"Ошибка загрузки конфига:\n{exc}\n")
                    self.status.SetLabel("Ошибка конфигурации")

            def _series_from_form(self):
                rows = tuple(row for row, chk in self.row_checks.items() if chk.GetValue())
                schemes = tuple(code for code, chk in self.scheme_checks.items() if chk.GetValue())
                if not rows:
                    raise ValueError("Выберите хотя бы один ряд")
                if not schemes:
                    raise ValueError("Выберите хотя бы одну схему нумерации")

                _library_path, _series, _symbols = self.generator.load_config(self._current_config_path())
                geometry = self.generator.parse_geometry(
                    {
                        "defaults": {
                            "geometry": {
                                "body_width": 20.0,
                                "pin_pitch": 5.0,
                                "pin_length": 2.5,
                            }
                        }
                    }
                )
                try:
                    _library_path, loaded_series, _symbols = self.generator.load_config(self._current_config_path())
                    if loaded_series:
                        geometry = loaded_series[0].geometry
                except Exception:
                    pass

                geometry = self.generator.Geometry(
                    body_width=geometry.body_width,
                    pin_pitch=geometry.pin_pitch,
                    pin_length=geometry.pin_length,
                    body_fill="background" if self.body_fill_chk.GetValue() else "none",
                )

                return self.generator.SeriesSpec(
                    prefix=self.prefix_ctrl.GetValue().strip() or "Con",
                    rows=rows,
                    pins_per_row=(),
                    pins_per_row_by_rows={
                        row: _parse_int_list(ctrl.GetValue())
                        for row, ctrl in self.pin_ctrls.items()
                    },
                    schemes=schemes,
                    scheme_map=dict(self.generator.DEFAULT_SCHEME_MAP),
                    reference=self.reference_ctrl.GetValue().strip() or "X",
                    value=self.value_ctrl.GetValue().strip() or "XX",
                    display_name=self.name_ctrl.GetValue().strip(),
                    show_pin_numbers=self.show_pin_numbers_chk.GetValue(),
                    show_pin_names=self.show_pin_names_chk.GetValue(),
                    zero_pad_pins=2,
                    skip_single_row_non_row=True,
                    geometry=geometry,
                )

            def _specs_from_form(self):
                return self.generator.specs_from_series(self._series_from_form())

            def _existing_symbols(self):
                if self.library_path is None:
                    return {}
                if not self.library_path.exists():
                    return {}
                text = self.library_path.read_text(encoding="utf-8")
                return {
                    block.name: block.text
                    for block in self.generator.find_symbol_blocks(text, target_depth=1)
                }

            def _refresh_preview(self):
                self.specs = self._specs_from_form()
                existing = self._existing_symbols()
                self.symbols.DeleteAllItems()

                for index, spec in enumerate(self.specs):
                    old = existing.get(spec.name)
                    manual = self.generator.manual_variant_count(old, spec.name)
                    status = "создать" if old is None else "обновить"
                    if manual:
                        status += f", сохранить ручных: {manual}"

                    self.symbols.InsertItem(index, spec.name)
                    self.symbols.SetItem(index, 1, str(spec.rows * spec.pins_per_row))
                    self.symbols.SetItem(index, 2, spec.numbering)
                    self.symbols.SetItem(index, 3, status)

                if self.specs:
                    self.symbols.Select(0)
                    self._show_spec(self.specs[0])
                else:
                    self.preview.SetValue("Нет символов для генерации.")

                self.status.SetLabel(f"Будет создано/обновлено символов: {len(self.specs)}")

            def _show_spec(self, spec):
                text = self.generator.format_pin_preview(spec)
                if spec.rows == 1 and spec.numbering != "row":
                    text += "\n\nДля одного ряда не-row схемы пропускаются автоматически."
                self.preview.SetValue(text)

            def _load_generation_from_form(self):
                if self.library_path is None:
                    self._load_config()
                if self.library_path is None:
                    raise ValueError("Библиотека не задана")

                specs = self._specs_from_form()
                library_text = self.library_path.read_text(encoding="utf-8")
                generated = self.generator.generate_library(library_text, specs)
                return self.library_path, specs, library_text, generated

            def _on_browse_config(self, _event):
                import wx

                with wx.FileDialog(
                    self,
                    "Выберите connectors.toml",
                    wildcard="TOML files (*.toml)|*.toml|All files (*.*)|*.*",
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
                ) as dlg:
                    if dlg.ShowModal() != wx.ID_OK:
                        return
                    self.config_ctrl.SetValue(dlg.GetPath())
                    self._load_config()

            def _on_preview(self, _event):
                try:
                    self._refresh_preview()
                except Exception as exc:
                    self.preview.SetValue(f"Ошибка предпросмотра:\n{exc}\n")
                    self.status.SetLabel("Ошибка предпросмотра")

            def _on_select_symbol(self, event):
                index = event.GetIndex()
                if 0 <= index < len(self.specs):
                    self._show_spec(self.specs[index])

            def _on_diff(self, _event):
                try:
                    library_path, _specs, old, new = self._load_generation_from_form()
                    diff = "".join(
                        difflib.unified_diff(
                            old.splitlines(keepends=True),
                            new.splitlines(keepends=True),
                            fromfile=str(library_path),
                            tofile="generated",
                        )
                    )
                    self.preview.SetValue(diff or "Изменений нет.\n")
                    self.status.SetLabel("Технический diff сформирован")
                except Exception as exc:
                    self.preview.SetValue(f"Ошибка diff:\n{exc}\n")

            def _validate_with_kicad_cli(self, generated_text: str) -> str:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".kicad_sym", delete=False) as tmp:
                    tmp.write(generated_text)
                    tmp_path = tmp.name

                out_path = tmp_path + ".upgraded.kicad_sym"
                try:
                    result = subprocess.run(
                        ["kicad-cli", "sym", "upgrade", tmp_path, "--output", out_path, "--force"],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    if result.returncode != 0:
                        return (result.stdout + result.stderr).strip() or "kicad-cli returned an error"
                    return "kicad-cli validation OK"
                except FileNotFoundError:
                    return "kicad-cli не найден, синтаксическая проверка пропущена"
                finally:
                    for path in (tmp_path, out_path):
                        try:
                            os.unlink(path)
                        except OSError:
                            pass

            def _on_write(self, _event):
                import wx

                try:
                    library_path, specs, old, new = self._load_generation_from_form()
                    if old == new:
                        self.status.SetLabel("Изменений нет, запись не требуется.")
                        return

                    answer = wx.MessageBox(
                        f"Сгенерировать {len(specs)} символов и обновить библиотеку?\n\n{library_path}",
                        "Connector Generator",
                        wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                    )
                    if answer != wx.YES:
                        return

                    validation = self._validate_with_kicad_cli(new)
                    if "returned an error" in validation:
                        self.preview.SetValue(f"Запись отменена.\n{validation}\n")
                        self.status.SetLabel("Проверка KiCad не пройдена")
                        return

                    library_path.write_text(new, encoding="utf-8")
                    self.status.SetLabel(f"Готово. Обновлено символов: {len(specs)}. {validation}")
                    self._refresh_preview()
                except Exception as exc:
                    self.preview.SetValue(f"Ошибка генерации:\n{exc}\n")
                    self.status.SetLabel("Ошибка генерации")

            def _on_open_config(self, _event):
                config = self._current_config_path()
                try:
                    subprocess.Popen(["xdg-open", str(config)])
                    self.status.SetLabel(f"Открыт конфиг: {config}")
                except Exception as exc:
                    self.status.SetLabel(f"Не удалось открыть конфиг: {exc}")

        return _Dialog(*args, **kwargs)
