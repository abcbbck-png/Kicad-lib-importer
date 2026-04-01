# KiCad Multiline Text Rendering Bug (GOST Fonts)

## Description
When using certain GOST TrueType fonts (e.g., `GOST_A.TTF`), multiline text in KiCad's Eeschema exhibits an issue where lines overlap. The interline spacing is calculated incorrectly, often resulting in a value of `0` or near `0`. 

## Root Cause
The KiCad font metrics subsystem calculates a conversion factor `glyphToFontHeight` in `OUTLINE_FONT::GetInterline()` (`common/font/outline_font.cpp`). The original code was:

```cpp
if( GetFace()->units_per_EM )
    glyphToFontHeight = GetFace()->height / GetFace()->units_per_EM;
```

Because `height` and `units_per_EM` are integers, the division `height / units_per_EM` performs integer truncating division. For many typical fonts, `height` is slightly larger than or equal to `units_per_EM` (e.g. `2048 / 2048 = 1`). However, in some GOST fonts, `height` is smaller than `units_per_EM` (for instance, `height = 1875` and `units_per_EM = 2048`). The result of `1875 / 2048` truncates to `0`. Consequently, the `glyphToFontHeight` becomes strictly `0`, leading to a `0` interline spacing for the entire text block and causing overlapping text lines.

## Solution
The bug is fixed by casting the properties to `double` before division and performing an explicit check to avoid division-by-zero.

```cpp
if( GetFace() && GetFace()->units_per_EM > 0 && GetFace()->height > 0 )
{
    glyphToFontHeight = static_cast<double>( GetFace()->height )
                        / static_cast<double>( GetFace()->units_per_EM );
}
```

## Patch
The fix has been verified and provided in `bugfix_gost_font_multiline.patch`. It should be merged into the KiCad master branch (and backported to stable versions) to resolve text rendering issues for non-standard TrueType fonts having `height < units_per_EM`.
