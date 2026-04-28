# Bus Entry Size Properties Patch

## What It Does

This patch exposes the existing `SCH_BUS_ENTRY_BASE::m_size` vector in the
schematic property manager as two editable size properties:

- `Size X`
- `Size Y`

The bus entry already uses `m_size` as its geometry vector.  Changing the vector
changes the entry endpoint returned by `GetEnd()`, and the same geometry is then
used by drawing, plotting, hit testing, connection points, and serialization.

## Changed Files

- `eeschema/sch_bus_entry.h`
  - Adds small accessors/mutators for `m_size.x` and `m_size.y`.
- `eeschema/sch_bus_entry.cpp`
  - Registers `Size X` and `Size Y` as `PROPERTY_DISPLAY::PT_SIZE` properties
    on `SCH_BUS_ENTRY_BASE`.

## Why It Is Low Risk

The patch does not change default bus entry construction, connectivity rules, or
file format parsing.  It only exposes fields that already exist and are already
saved through the current bus entry size serialization.

## Patch File

Apply from the KiCad source root:

```bash
git apply /home/anton/VsCode/KiCAD_Importer/docs/bus-entry-size-properties.patch
```

## Verification To Run After Rebase

1. Check that the patch applies cleanly on the target KiCad version:

```bash
git apply --check /home/anton/VsCode/KiCAD_Importer/docs/bus-entry-size-properties.patch
```

2. Build at least `eeschema/_eeschema.kiface`.
3. In Schematic Editor, select a bus entry and verify that `Size X` and
   `Size Y` appear in the properties panel.
4. Change both values, save, reopen, and verify that the bus entry keeps the new
   shape and remains connected when both endpoints are still valid.
