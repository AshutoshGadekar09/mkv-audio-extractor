#!/usr/bin/env bash
# build-deb.sh — Build Debian (.deb) package for mkv-audio-extractor
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="mkv-audio-extractor"
PKG_VERSION="1.0.1"
PKG_ARCH="all"
PKG_FULLNAME="${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"

BUILD_ROOT="$SCRIPT_DIR/build/deb"
BUILD_DIR="$BUILD_ROOT/$PKG_FULLNAME"
DIST_DIR="$SCRIPT_DIR/dist"

echo "=========================================="
echo " Building Debian package: $PKG_FULLNAME.deb"
echo "=========================================="

# Clean up any previous builds
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# 1. Directory Structure
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/lib/python3/dist-packages/mkv_audio_extractor"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$BUILD_DIR/usr/share/doc/$PKG_NAME"
mkdir -p "$BUILD_DIR/usr/share/man/man1"

# 2. Copy Python source files
echo "-> Copying package sources..."
cp -r "$SCRIPT_DIR/mkv_audio_extractor/"* "$BUILD_DIR/usr/lib/python3/dist-packages/mkv_audio_extractor/"

# Clean cache files
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true

# 3. Create Executable Launcher
echo "-> Creating /usr/bin/$PKG_NAME launcher..."
cat << 'EOF' > "$BUILD_DIR/usr/bin/$PKG_NAME"
#!/usr/bin/python3
import sys
from mkv_audio_extractor.__main__ import main

if __name__ == "__main__":
    main()
EOF
chmod 755 "$BUILD_DIR/usr/bin/$PKG_NAME"

# 4. Desktop Entry
echo "-> Creating desktop launcher..."
cat << 'EOF' > "$BUILD_DIR/usr/share/applications/$PKG_NAME.desktop"
[Desktop Entry]
Type=Application
Name=MKV Audio Extractor
GenericName=Audio Extractor
Comment=Extract audio tracks from MKV files with language selection
Exec=mkv-audio-extractor
Icon=mkv-audio-extractor
Terminal=false
Categories=AudioVideo;Audio;AudioVideoEditing;Utility;
Keywords=mkv;audio;extract;ffmpeg;multitrack;
MimeType=video/x-matroska;
StartupNotify=true
EOF

# 5. Icon
echo "-> Installing SVG icon..."
cp "$SCRIPT_DIR/mkv-audio-extractor.svg" "$BUILD_DIR/usr/share/icons/hicolor/scalable/apps/$PKG_NAME.svg"

# 6. Man page
echo "-> Compressing man page..."
gzip -9 -c "$SCRIPT_DIR/mkv-audio-extractor.1" > "$BUILD_DIR/usr/share/man/man1/$PKG_NAME.1.gz"

# 7. Documentation & Changelog
echo "-> Generating documentation and changelog..."
cp "$SCRIPT_DIR/README.md" "$BUILD_DIR/usr/share/doc/$PKG_NAME/"

cat << EOF > "$BUILD_DIR/usr/share/doc/$PKG_NAME/copyright"
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: mkv-audio-extractor
Source: https://github.com/AshutoshGadekar09/mkv-audio-extractor

Files: *
Copyright: 2026 Ashutosh Gadekar
License: MIT

License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
EOF

cat << EOF | gzip -9 -c > "$BUILD_DIR/usr/share/doc/$PKG_NAME/changelog.Debian.gz"
$PKG_NAME ($PKG_VERSION) unstable; urgency=medium

  * Initial release of mkv-audio-extractor.
  * Added PyQt6 GUI with drag & drop and multi-track selection.
  * Added CLI interface with language filtering and batch processing.
  * Support for lossless copy mode and convert mode (MP3, AAC, FLAC, Opus, WAV).

 -- Ashutosh Gadekar <ashutosh@localhost>  Tue, 06 Oct 2026 15:00:00 +0000
EOF

# 8. DEBIAN Maintenance Scripts
echo "-> Creating maintainer scripts..."
cat << 'EOF' > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
    if which py3compile >/dev/null 2>&1; then
        py3compile -p mkv-audio-extractor /usr/lib/python3/dist-packages/mkv_audio_extractor || true
    fi
fi
exit 0
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

cat << 'EOF' > "$BUILD_DIR/DEBIAN/postrm"
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
    if which py3clean >/dev/null 2>&1; then
        py3clean -p mkv-audio-extractor /usr/lib/python3/dist-packages/mkv_audio_extractor || true
    fi
fi
exit 0
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postrm"

# 9. Calculate Installed-Size and Generate control file
INSTALLED_SIZE=$(du -sk "$BUILD_DIR" | cut -f1)

cat << EOF > "$BUILD_DIR/DEBIAN/control"
Package: $PKG_NAME
Version: $PKG_VERSION
Section: video
Priority: optional
Architecture: $PKG_ARCH
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.10), ffmpeg, python3-pyqt6
Recommends: mkvtoolnix
Maintainer: Ashutosh Gadekar <ashutosh@localhost>
Description: Extract audio tracks from MKV files with language selection
 MKV Audio Extractor is a fast Linux utility to extract audio tracks from
 Matroska (.mkv) video files. It supports lossless copy mode (preserving original
 codecs such as EAC3/DDP, AC3, AAC, FLAC) and conversion to MP3, AAC, FLAC,
 Opus, and WAV with custom bitrates. Includes both a PyQt6 graphical interface
 and a command-line interface.
EOF

# 10. Fix permissions
echo "-> Setting standard Debian permissions..."
find "$BUILD_DIR" -type d -exec chmod 755 {} +
find "$BUILD_DIR" -type f -exec chmod 644 {} +
chmod 755 "$BUILD_DIR/usr/bin/$PKG_NAME"
chmod 755 "$BUILD_DIR/DEBIAN/postinst" "$BUILD_DIR/DEBIAN/postrm"

# 11. Build with dpkg-deb
echo "-> Assembling package with dpkg-deb..."
DEB_FILE="$DIST_DIR/${PKG_FULLNAME}.deb"
dpkg-deb --build --root-owner-group "$BUILD_DIR" "$DEB_FILE"

# Also copy to Downloads directory for easy access if present
if [ -d "$HOME/Downloads" ]; then
    cp "$DEB_FILE" "$HOME/Downloads/${PKG_FULLNAME}.deb"
    echo "  Copy in:  $HOME/Downloads/${PKG_FULLNAME}.deb"
fi
echo
echo "To install on any Debian/Ubuntu system:"
echo "  sudo apt install ./$PKG_FULLNAME.deb"
echo "  # or: sudo dpkg -i $PKG_FULLNAME.deb && sudo apt install -f"
