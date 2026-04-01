#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>

int main(int argc, char** argv) {
    FT_Library library;
    if (FT_Init_FreeType(&library)) return 1;
    for(int i=1; i<argc; i++) {
        FT_Face face;
        if (FT_New_Face(library, argv[i], 0, &face)) continue;
        printf("Font: %s\n", argv[i]);
        printf("  units_per_EM: %d\n", face->units_per_EM);
        printf("  ascender: %d\n", face->ascender);
        printf("  descender: %d\n", face->descender);
        printf("  height: %d\n", face->height);
        FT_Done_Face(face);
    }
    FT_Done_FreeType(library);
    return 0;
}
