#!/bin/bash
# ============================================================================
# apply_smooth_zoom_patch.sh — Применение патча плавного масштабирования к KiCad
# ============================================================================
#
# Функция: улучшает drag-zoom операцию фиксацией курсора мыши при масштабировании
# Поддерживает: KiCad 9.0.7
#
# Использование:
#   ./apply_smooth_zoom_patch.sh [--stable|--nightly] [--build] [--help]
#
# ============================================================================

set -euo pipefail

# ── Цвета ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Конфигурация ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KICAD_REPO="https://gitlab.com/kicad/code/kicad.git"
BUILD_DIR="${BUILD_DIR:-/tmp/kicad-smooth-zoom}"
JOBS=$(nproc 2>/dev/null || echo 4)
PATCH_FILE="$SCRIPT_DIR/docs/kicad-copy-research/SMOOTH_ZOOM_PATCH.diff"

# ── Утилиты ──
log()    { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()     { echo -e "${GREEN}[  OK]${NC} $*"; }
warn()   { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()    { echo -e "${RED}[FAIL]${NC} $*"; }
die()    { err "$*"; exit 1; }
header() { echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }

# ── Help ──
show_help() {
    cat << 'EOF'
┌──────────────────────────────────────────────────────────┐
│  apply_smooth_zoom_patch.sh — Плавное масштабирование  │
└──────────────────────────────────────────────────────────┘

Применяет патч улучшения drag-zoom для KiCad, добавляя фиксацию курсора
при масштабировании через удержание средней кнопки мыши.

ИСПОЛЬЗОВАНИЕ:
  ./apply_smooth_zoom_patch.sh [ОПЦИИ]

ОПЦИИ:
  --stable       Применить для stable KiCad (9.0.7, default)
  --nightly      Применить для nightly
  --build        Собрать KiCad после применения патча
  --check        Проверить, применим ли патч без сборки
  -j, --jobs N   Потоки сборки (по умолчанию: все ядра)
  -h, --help     Эта справка

ПРИМЕРЫ:
  ./apply_smooth_zoom_patch.sh --check      # Проверить патч
  ./apply_smooth_zoom_patch.sh --build      # Применить + собрать (долго!)
  ./apply_smooth_zoom_patch.sh --stable     # Только prepare (без сборки)
EOF
}

# ── Определение версии KiCad ──
get_kicad_version() {
    if dpkg -s kicad &>/dev/null; then
        dpkg-query -W -f='${Version}' kicad 2>/dev/null | sed 's/~.*//'
    else
        echo ""
    fi
}

# ── Клонирование исходников ──
clone_source() {
    local ref="$1" src_dir="$2"
    
    if [[ -d "$src_dir/.git" ]]; then
        ok "Исходники уже есть: $src_dir"
        return 0
    fi
    
    log "Клонирование KiCad $ref из git..."
    mkdir -p "$BUILD_DIR"
    git clone --depth 1 --branch "$ref" "$KICAD_REPO" "$src_dir" 2>&1 | tail -3
    ok "Исходники клонированы"
}

# ── Проверка применимости патча ──
check_patch() {
    local src="$1" patch="$2"
    
    [[ -f "$patch" ]] || die "Патч не найден: $patch"
    
    cd "$src" || die "Не могу перейти в $src"
    
    # Проверяем, не применён ли уже патч
    if grep -q "Lock cursor at the initial smooth zoom position" \
            "common/view/wx_view_controls.cpp" 2>/dev/null; then
        ok "Патч уже применён"
        return 0
    fi
    
    # Проверяем, можно ли применить патч (сухой прогон)
    if patch --dry-run -p1 < "$patch" >/dev/null 2>&1; then
        ok "Патч применим"
        return 0
    else
        err "Патч не применим к этой версии"
        return 1
    fi
}

# ── Применение патча ──
apply_patch() {
    local src="$1" patch="$2"
    
    [[ -f "$patch" ]] || die "Патч не найден: $patch"
    
    cd "$src" || die "Не могу перейти в $src"
    
    # Проверяем, не применён ли уже
    if grep -q "Lock cursor at the initial smooth zoom position" \
            "common/view/wx_view_controls.cpp" 2>/dev/null; then
        ok "Патч уже применён"
        return 0
    fi
    
    log "Применение патча..."
    if patch -p1 < "$patch"; then
        ok "Патч успешно применён"
        return 0
    else
        err "Ошибка при применении патча"
        return 1
    fi
}

# ── Сборка ──
build_kiface() {
    local src="$1" bld="$src/build"
    mkdir -p "$bld" && cd "$bld"
    
    if [[ ! -f build.ninja ]]; then
        log "cmake configure..."
        cmake .. -G Ninja \
            -DCMAKE_BUILD_TYPE=Release \
            -DKICAD_SCRIPTING_WXPYTHON=OFF \
            -DKICAD_IPC_API=ON \
            -DKICAD_BUILD_I18N=OFF \
            -DKICAD_BUILD_QA_TESTS=OFF \
            -DKICAD_USE_CMAKE_FINDPROTOBUF=ON \
            2>&1 | tail -5
        [[ -f build.ninja ]] || die "cmake не удался"
        ok "cmake OK"
    fi
    
    log "ninja -j$JOBS (это займёт ~10-15 минут)..."
    ninja -j"$JOBS" eeschema/_eeschema.kiface 2>&1 | tail -10
    [[ -f "$bld/eeschema/_eeschema.kiface" ]] || die "Сборка не удалась"
    ok "Собрано: $(du -h "$bld/eeschema/_eeschema.kiface" | cut -f1)"
}

# ── Main ──
main() {
    local mode="check" version="9.0.7" should_build=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --stable)    version="9.0.7"; shift ;;
            --nightly)   version="master"; shift ;;
            --build)     should_build=true; shift ;;
            --check)     mode="check"; shift ;;
            -j|--jobs)   JOBS="$2"; shift 2 ;;
            -h|--help)   show_help; exit 0 ;;
            *)           die "Неизвестно: $1  (--help)" ;;
        esac
    done

    echo -e "\n${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║  KiCad Smooth Drag Zoom Patch                       ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}\n"

    [[ -f "$PATCH_FILE" ]] || die "Патч не найден: $PATCH_FILE"
    ok "Патч: $PATCH_FILE"

    local src="$BUILD_DIR/kicad-$version"
    clone_source "$version" "$src"

    if [[ "$mode" == "check" ]]; then
        header "Проверка применимости патча"
        if check_patch "$src" "$PATCH_FILE"; then
            echo ""
            echo -e "  ${GREEN}✓${NC} Патч можно применить (или уже применён)"
            echo ""
            if $should_build; then
                echo "  Для сборки: $0 --build"
            fi
        else
            exit 1
        fi
        exit 0
    fi

    if $should_build; then
        header "Применение патча"
        apply_patch "$src" "$PATCH_FILE"

        header "Сборка KiCad ($version)"
        log "Требуется: cmake, ninja, g++ + dev-пакеты"
        check_build_deps
        build_kiface "$src"

        echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        ok "Готово!"
        echo "  Собранный киФейс: $(du -h "$src/build/eeschema/_eeschema.kiface" | cut -f1)"
        echo "  Для установки: sudo cp $src/build/eeschema/_eeschema.kiface /usr/bin/"
        echo "  Или используйте: ./fix_kicad_altium.sh --stable"
        echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    fi
}

# ── Check build deps ──
check_build_deps() {
    local missing_cmds=()
    for cmd in cmake ninja g++ git; do
        command -v "$cmd" &>/dev/null || missing_cmds+=("$cmd")
    done
    
    if [[ ${#missing_cmds[@]} -gt 0 ]]; then
        warn "Не найдены: ${missing_cmds[*]}"
        return 1
    fi
}

main "$@"
