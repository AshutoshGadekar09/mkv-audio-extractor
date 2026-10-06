#!/usr/bin/env bash
# install.sh — Install MKV Audio Extractor on Linux
set -euo pipefail

APP_NAME="mkv-audio-extractor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║   MKV Audio Extractor — Installer    ║"
echo "╚══════════════════════════════════════╝"
echo

# ── Check Python ──
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "   Install it with: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PYTHON_VERSION found"

# ── Check ffmpeg ──
if command -v ffmpeg &>/dev/null; then
    echo "✓ ffmpeg found: $(ffmpeg -version 2>/dev/null | head -1)"
else
    echo "⚠ ffmpeg not found. Installing..."
    if command -v apt &>/dev/null; then
        sudo apt update && sudo apt install -y ffmpeg
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y ffmpeg
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm ffmpeg
    else
        echo "❌ Please install ffmpeg manually."
        exit 1
    fi
fi

# ── Create virtual environment ──
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# ── Install dependencies ──
echo
echo "Installing dependencies..."
pip install --upgrade pip setuptools wheel -q
pip install -e "$SCRIPT_DIR[gui,dev]" -q

echo
echo "✓ All dependencies installed"

# ── Create CLI wrapper ──
CLI_WRAPPER="/usr/local/bin/$APP_NAME"
echo
echo "Creating CLI wrapper at $CLI_WRAPPER ..."

sudo tee "$CLI_WRAPPER" > /dev/null << WRAPPER
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
exec python3 -m mkv_audio_extractor "\$@"
WRAPPER

sudo chmod +x "$CLI_WRAPPER"
echo "✓ CLI wrapper created"

# ── Install desktop file ──
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESKTOP_DIR"

ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
mkdir -p "$ICON_DIR"

cp "$SCRIPT_DIR/mkv-audio-extractor.desktop" "$DESKTOP_DIR/"

# Update desktop file paths
sed -i "s|Exec=.*|Exec=$VENV_DIR/bin/python3 -m mkv_audio_extractor --gui|" \
    "$DESKTOP_DIR/mkv-audio-extractor.desktop"

# Update desktop database
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "✓ Desktop launcher installed"

echo
echo "╔══════════════════════════════════════╗"
echo "║      Installation Complete! 🎉       ║"
echo "╚══════════════════════════════════════╝"
echo
echo "Usage:"
echo "  GUI:  $APP_NAME"
echo "  CLI:  $APP_NAME movie.mkv --all"
echo "  CLI:  $APP_NAME movie.mkv --lang hin,tam,jpn --mode copy"
echo
echo "Run tests:"
echo "  cd $SCRIPT_DIR && $VENV_DIR/bin/pytest tests/ -v"
echo
