# MKV Audio Extractor

A Linux application to extract audio tracks from MKV files, with language selection, copy/convert modes, and both GUI and CLI interfaces.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Multi-track extraction** — extract one or more audio tracks from MKV files
- **Language selection** — filter by ISO 639 language codes (hin, tam, tel, jpn, eng, etc.)
- **Copy mode** — lossless extraction keeping the original codec (EAC3, AC3, AAC, etc.)
- **Convert mode** — re-encode to MP3, AAC (M4A), FLAC, Opus, or WAV with bitrate control
- **Batch processing** — queue multiple files without freezing the UI
- **GUI** — PyQt6 interface with drag & drop, checkboxes, progress bars, and a log panel
- **CLI** — full-featured command-line interface for scripting and headless use
- **Safe filenames** — handles spaces, brackets, parentheses, and Unicode in paths

## Requirements

- **Python 3.10+**
- **ffmpeg** and **ffprobe** (from the `ffmpeg` package)
- **PyQt6** (for the GUI; CLI works without it)

## Installation

### Method 1: Install Debian (.deb) Package (Recommended for Ubuntu/Debian)

Install the pre-built `.deb` package with apt:

```bash
# Install the .deb package and its system dependencies automatically:
sudo apt install ./mkv-audio-extractor_1.0.0_all.deb
```

To build a fresh `.deb` package yourself at any time:

```bash
cd mkv-audio-extractor
./build-deb.sh
```

### Method 2: Quick Install Script

```bash
cd mkv-audio-extractor
chmod +x install.sh
./install.sh
```

This will:
1. Check for Python and ffmpeg (installs ffmpeg if missing)
2. Create a virtual environment
3. Install all dependencies
4. Create a `mkv-audio-extractor` command in `/usr/local/bin`
5. Add a `.desktop` launcher for the app menu

### Manual Install

```bash
# Install ffmpeg
sudo apt install ffmpeg

# Clone and install
cd mkv-audio-extractor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,dev]"
```

## Usage

### GUI

Launch the GUI with:

```bash
mkv-audio-extractor
# or
python3 -m mkv_audio_extractor
```

1. **Open files** — click "Open Files..." or drag & drop MKV files onto the window
2. **Select tracks** — check the audio tracks you want, or use "Select All" / "Select by language"
3. **Choose options** — pick Copy or Convert mode, set the output folder
4. **Extract** — click "Extract Selected" and watch the progress

### CLI

```bash
# List all audio tracks in a file
mkv-audio-extractor movie.mkv --list

# Extract all audio tracks (copy mode, lossless)
mkv-audio-extractor movie.mkv --all

# Extract specific languages
mkv-audio-extractor movie.mkv --lang hin,tam,jpn --mode copy

# Extract and convert to MP3
mkv-audio-extractor movie.mkv --lang eng --mode convert --convert-to mp3 --bitrate 320k

# Extract to a specific folder
mkv-audio-extractor movie.mkv --all -o ~/Music/extracted

# Process an entire folder recursively
mkv-audio-extractor /path/to/anime/ --recursive --lang jpn --mode copy

# Extract specific tracks by index
mkv-audio-extractor movie.mkv --track 0,2,4
```

### Real-World Example

```bash
# Extract Hindi, Tamil, Telugu, Japanese, and Kannada from an anime file
mkv-audio-extractor \
  "/home/vickey/Downloads/[Toonworld4all] Attack on Titan S04E29 Final Chapters 1080p x265 10bit AMZN WEB-DL Multi Audio DDP2.0 ESub (1).mkv" \
  --lang hin,tam,tel,jpn,kan \
  --mode copy \
  -o ~/Music/AoT
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--list` | List audio tracks without extracting |
| `--all` | Extract all audio tracks |
| `--lang CODES` | Comma-separated ISO 639 language codes |
| `--track INDICES` | Comma-separated track indices (0-based) |
| `--mode copy\|convert` | Extraction mode (default: copy) |
| `--convert-to FORMAT` | Target format: mp3, aac, flac, opus, wav |
| `--bitrate RATE` | Bitrate for conversion (e.g., 192k, 320k) |
| `-o, --output DIR` | Output directory |
| `-r, --recursive` | Scan directories recursively |
| `--overwrite MODE` | File conflict: overwrite, skip, rename (default: rename) |
| `-v, --verbose` | Verbose logging |

## Project Structure

```
mkv-audio-extractor/
├── mkv_audio_extractor/
│   ├── __init__.py              # Package metadata
│   ├── __main__.py              # Entry point (GUI or CLI)
│   ├── cli.py                   # CLI interface (argparse)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── extractor.py         # FFmpeg extraction engine
│   │   ├── languages.py         # ISO 639 language mapping
│   │   └── probe.py             # FFprobe file analysis
│   └── gui/
│       ├── __init__.py
│       └── main_window.py       # PyQt6 GUI
├── tests/
│   ├── fixtures/
│   │   └── sample_ffprobe_output.json
│   └── test_core.py             # Unit & integration tests
├── install.sh                   # One-command installer
├── mkv-audio-extractor.desktop  # App menu launcher
├── pyproject.toml               # Python packaging config
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

## Running Tests

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run only unit tests (no ffmpeg needed)
pytest tests/test_core.py -v -k "not TestWithRealMKV"

# Run integration tests (generates a test MKV with ffmpeg)
pytest tests/test_core.py -v -k "TestWithRealMKV"
```

## Supported Codecs

### Copy Mode (lossless)

| Codec | Extension |
|-------|-----------|
| EAC3 (DDP) | `.eac3` |
| AC3 (Dolby Digital) | `.ac3` |
| AAC | `.aac` |
| MP3 | `.mp3` |
| FLAC | `.flac` |
| Opus | `.opus` |
| Vorbis | `.ogg` |
| DTS | `.dts` |
| TrueHD | `.thd` |
| PCM | `.wav` |
| Other | `.mka` |

### Convert Mode

| Target | Extension | Codec |
|--------|-----------|-------|
| MP3 | `.mp3` | libmp3lame |
| AAC | `.m4a` | aac |
| FLAC | `.flac` | flac |
| Opus | `.opus` | libopus |
| WAV | `.wav` | pcm_s16le |

## License

MIT
