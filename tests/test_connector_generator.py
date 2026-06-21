import sys
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "connector_generator"))

import connector_generator as cg  # noqa: E402


class ConnectorGeneratorTests(unittest.TestCase):
    def test_row_numbering(self):
        spec = cg.SymbolSpec(name="Con-2X-03P-R", rows=2, pins_per_row=3, numbering="row")

        nums = [
            cg.pin_number(spec, row, index)
            for row in range(spec.rows)
            for index in range(spec.pins_per_row)
        ]

        self.assertEqual(nums, [1, 2, 3, 4, 5, 6])

    def test_column_numbering(self):
        spec = cg.SymbolSpec(name="Con-2X-03P-S", rows=2, pins_per_row=3, numbering="column")

        row_a = [cg.pin_number(spec, 0, index) for index in range(spec.pins_per_row)]
        row_b = [cg.pin_number(spec, 1, index) for index in range(spec.pins_per_row)]

        self.assertEqual(row_a, [1, 3, 5])
        self.assertEqual(row_b, [2, 4, 6])

    def test_series_expansion_skips_non_row_for_single_row(self):
        series = cg.SeriesSpec(
            prefix="Con",
            rows=(1, 2),
            pins_per_row=(2, 3),
            pins_per_row_by_rows=None,
            schemes=("R", "S"),
            scheme_map={"R": "row", "S": "column"},
            display_name="Разъем универсальный",
        )

        specs = cg.specs_from_series(series)
        names = [spec.name for spec in specs]

        self.assertEqual(
            names,
            [
                "Con-1X-02P-R",
                "Con-1X-03P-R",
                "Con-2X-02P-R",
                "Con-2X-02P-S",
                "Con-2X-03P-R",
                "Con-2X-03P-S",
            ],
        )

    def test_series_expansion_can_use_row_specific_pin_lists(self):
        series = cg.SeriesSpec(
            prefix="Con",
            rows=(1, 2, 3),
            pins_per_row=(),
            pins_per_row_by_rows={1: (1, 2), 2: (2, 3), 3: (3, 4)},
            schemes=("R", "S"),
            scheme_map={"R": "row", "S": "column"},
        )

        names = [spec.name for spec in cg.specs_from_series(series)]

        self.assertEqual(names[0], "Con-1X-01P-R")
        self.assertIn("Con-2X-02P-S", names)
        self.assertIn("Con-3X-03P-S", names)
        self.assertNotIn("Con-1X-01P-S", names)

    def test_pin_preview_is_human_readable_matrix(self):
        spec = cg.SymbolSpec(name="Con-2X-03P-S", rows=2, pins_per_row=3, numbering="column")

        preview = cg.format_pin_preview(spec)

        self.assertIn("Con-2X-03P-S", preview)
        self.assertIn("1  2", preview)
        self.assertIn("3  4", preview)
        self.assertIn("5  6", preview)

    def test_generated_unit_has_visible_number_text_and_separator(self):
        spec = cg.SymbolSpec(name="Con-2X-03P-S", rows=2, pins_per_row=3, numbering="column")

        unit = cg.generate_unit(spec, row=0)

        self.assertIn('(xy 5 0) (xy 5 -15)', unit)
        self.assertIn('(text "1"', unit)
        self.assertIn('(text "3"', unit)
        self.assertIn('(text "5"', unit)

    def test_generated_unit_can_fill_body_with_background(self):
        spec = cg.SymbolSpec(
            name="Con-1X-02P-R",
            rows=1,
            pins_per_row=2,
            numbering="row",
            geometry=cg.Geometry(body_fill="background"),
        )

        unit = cg.generate_unit(spec, row=0)

        self.assertIn("(fill\n\t\t\t\t\t(type background)", unit)

    def test_pin_number_visibility_setting_matches_kicad_property(self):
        visible = cg.SymbolSpec(name="Con-1X-02P-R", rows=1, pins_per_row=2, numbering="row")
        hidden = cg.SymbolSpec(
            name="Con-1X-02P-R",
            rows=1,
            pins_per_row=2,
            numbering="row",
            show_pin_numbers=False,
        )

        visible_symbol = cg.generate_symbol(visible)
        hidden_symbol = cg.generate_symbol(hidden)

        self.assertNotIn("(pin_numbers", visible_symbol)
        self.assertIn("(pin_names\n\t\t\t(hide yes)", visible_symbol)
        self.assertIn("(pin_numbers\n\t\t\t(hide yes)", hidden_symbol)

    def test_reference_and_value_match_two_by_ten_grid_alignment(self):
        spec = cg.SymbolSpec(name="Con-2X-10P-R", rows=2, pins_per_row=10, numbering="row")

        symbol = cg.generate_symbol(spec)

        self.assertIn(
            '(property "Reference" "X"\n\t\t\t(at 0 1.25 0)',
            symbol,
        )
        self.assertIn(
            '(property "Value" "XX"\n\t\t\t(at 0 -52.5 0)',
            symbol,
        )
        self.assertIn("(justify left bottom)", symbol)

    def test_manual_body_styles_are_preserved(self):
        library = textwrap.dedent(
            """\
            (kicad_symbol_lib
            \t(version 20241209)
            \t(generator "test")
            \t(symbol "Con-2X-02P-R"
            \t\t(body_styles "BASE" "CUSTOM")
            \t\t(symbol "Con-2X-02P-R_1_1"
            \t\t\t(text "old generated")
            \t\t)
            \t\t(symbol "Con-2X-02P-R_1_2"
            \t\t\t(text "manual custom")
            \t\t)
            \t)
            )
            """
        )
        spec = cg.SymbolSpec(name="Con-2X-02P-R", rows=2, pins_per_row=2, numbering="row")

        generated = cg.generate_library(library, [spec])

        self.assertIn('(symbol "Con-2X-02P-R_1_2"', generated)
        self.assertIn('(text "manual custom")', generated)
        self.assertNotIn("old generated", generated)
        self.assertIn('(number "1"', generated)
        self.assertIn('(number "4"', generated)


if __name__ == "__main__":
    unittest.main()
