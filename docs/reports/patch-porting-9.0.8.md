# KiCad 9.0.8 Patch Porting Report

Date: 2026-04-28

## Installed KiCad

- Installed version: `9.0.8`
- Debian package: `9.0.8~ubuntu24.04.1`
- `dpkg -V kicad`: clean, so active `/usr/bin/_eeschema.kiface` matches the package.
- Old manual backup still exists: `/usr/bin/_eeschema.kiface.orig`, but it is not active.

## Altium Null Byte Import Bug

Status: fixed upstream in KiCad 9.0.8.

Evidence:

- Installed `kicad-cli sym upgrade` succeeds on the local reproducer used by
  `fix_kicad_altium.sh --check`.
- KiCad 9.0.8 source contains:

```cpp
std::string str = std::string( m_pos, length - ( ( hasNullByte && !isBinary ) ? 1 : 0 ) );
```

The local patch/commit `f8bfa0050d Fix: don't strip trailing null byte...` is
therefore skipped when porting to 9.0.8.

## Source Tree

- Source path: `/home/anton/VsCode/kicad-research/kicad`
- Repository was expanded from shallow to full history.
- Working branch: `local/9.0.8-patches`
- Base tag: `9.0.8`

## Patch Inventory

Full archived local 9.0.7 patch series:

`docs/patches/local-kicad-9.0.7-plus5/`

Combined final diff against KiCad 9.0.8:

`docs/patches/kicad-9.0.8-local-patches-combined.diff`

| Patch | Status on 9.0.8 | Notes |
|---|---|---|
| `0001-fix-smooth-drag-zoom-with-fixed-cursor-position.patch` | Applied | Same patch already existed as `docs/kicad-copy-research/SMOOTH_ZOOM_PATCH.diff`. |
| `0002-Fix-don-t-strip-trailing-null-byte-from-binary-recor.patch` | Skipped | Already upstream in 9.0.8. |
| `0003-Feature-auto-convert-45-wire-segment-to-bus-entry-on.patch` | Applied | Implements auto conversion of a 45 degree wire segment ending on a bus into `SCH_BUS_WIRE_ENTRY`. |
| `0004-Feature-group-by-column-in-library-tree-symbol-footp.patch` | Applied | Same patch already existed as `docs/kicad-groupby-column.diff`. |
| `0005-Fix-auto-bus-entry-handle-posture-true-case-where-45.patch` | Applied after `0003` | Dependent fix for the auto bus-entry implementation. |
| `bugfix_gost_font_multiline.patch` | Applied | Guards font metrics in `OUTLINE_FONT::GetInterline()`. |
| `docs/bus-entry-size-properties.patch` | Applied | New patch created from local uncommitted KiCad changes. |

## Hierarchical Labels

Status: report still matches KiCad 9.0.8 architecture.

The key implementation points are still present:

- `LABEL_FLAG_SHAPE` in `eeschema/sch_label.h`
- hardcoded `Template*` polygon arrays in `eeschema/sch_label.cpp`
- `SCH_HIERLABEL::CreateGraphicShape()`
- `SCH_SHEET_PIN::CreateGraphicShape()` with input/output inversion
- GAL draw path in `SCH_PAINTER::draw( const SCH_HIERLABEL* ... )`

No hierlabel visual patch was applied yet.  A simple polygon-geometry patch
should be low risk; SVG/bitmap/custom shape support is still a larger feature.

## Wire To Bus

Status: the original report is still true for upstream 9.0.8: direct wire to
bus is not a native connection.  The local auto bus-entry patches were ported.

The patched 9.0.8 tree now contains:

- `SCH_LINE_WIRE_BUS_TOOL::tryConvertLastSegmentToBusEntry()`
- `SCH_LINE_WIRE_BUS_TOOL::finishSegments()` calling that helper
- `SCH_BUS_ENTRY_BASE` `Size X` / `Size Y` properties

## Verification

Commands completed:

```bash
git apply --check ...
git diff --check
ninja -C build eeschema/_eeschema.kiface -j16
```

Result:

- Patch applicability checks passed, except the dependent `0005` before `0003`
  was applied.  After `0003`, `0005` applied cleanly.
- `git diff --check` passed.
- `_eeschema.kiface` built successfully:
  `/home/anton/VsCode/kicad-research/kicad/build/eeschema/_eeschema.kiface`

## Current KiCad Diff

The patched 9.0.8 working tree modifies 15 files:

- `common/font/outline_font.cpp`
- `common/lib_tree_model.cpp`
- `common/lib_tree_model_adapter.cpp`
- `common/settings/app_settings.cpp`
- `common/view/wx_view_controls.cpp`
- `common/widgets/lib_tree.cpp`
- `eeschema/sch_bus_entry.cpp`
- `eeschema/sch_bus_entry.h`
- `eeschema/symbol_tree_synchronizing_adapter.cpp`
- `eeschema/tools/sch_line_wire_bus_tool.cpp`
- `eeschema/tools/sch_line_wire_bus_tool.h`
- `include/lib_tree_model.h`
- `include/lib_tree_model_adapter.h`
- `include/settings/app_settings.h`
- `pcbnew/fp_tree_synchronizing_adapter.cpp`
