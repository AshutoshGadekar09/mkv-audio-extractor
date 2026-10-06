"""Probe MKV files to extract audio track metadata using ffprobe."""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .languages import get_language_name

logger = logging.getLogger(__name__)


@dataclass
class AudioTrack:
    """Represents a single audio track in an MKV file."""

    index: int  # Stream index in the file
    stream_index: int  # Audio-specific stream index (0-based among audio streams)
    codec: str  # Codec name (e.g., eac3, ac3, aac, flac, opus, vorbis)
    codec_long: str  # Full codec name
    language_code: str  # ISO 639 language code (e.g., hin, eng)
    language_name: str  # Human-readable name (e.g., Hindi, English)
    channels: int  # Number of audio channels
    channel_layout: str  # Channel layout (e.g., stereo, 5.1)
    sample_rate: int  # Sample rate in Hz
    bit_rate: Optional[int]  # Bit rate in bps (may be None for some codecs)
    title: str  # Track title from metadata
    duration: Optional[float]  # Duration in seconds
    is_default: bool  # Whether this is the default track
    is_forced: bool  # Whether this is a forced track

    @property
    def display_name(self) -> str:
        """Human-readable display string for this track."""
        parts = [
            f"Track {self.stream_index}",
            f"[{self.language_name}]",
            self.codec.upper(),
            self.channel_layout or f"{self.channels}ch",
        ]
        if self.bit_rate:
            parts.append(f"{self.bit_rate // 1000}kbps")
        if self.title:
            parts.append(f'"{self.title}"')
        if self.is_default:
            parts.append("(Default)")
        return " | ".join(parts)

    @property
    def file_extension(self) -> str:
        """Get the appropriate file extension for copy-mode extraction."""
        codec_ext_map: dict[str, str] = {
            "aac": ".aac",
            "ac3": ".ac3",
            "eac3": ".eac3",
            "mp3": ".mp3",
            "flac": ".flac",
            "opus": ".opus",
            "vorbis": ".ogg",
            "dts": ".dts",
            "truehd": ".thd",
            "pcm_s16le": ".wav",
            "pcm_s24le": ".wav",
            "pcm_s32le": ".wav",
            "pcm_f32le": ".wav",
            "alac": ".m4a",
            "wmav2": ".wma",
            "wmav1": ".wma",
        }
        return codec_ext_map.get(self.codec.lower(), ".mka")


@dataclass
class FileInfo:
    """Information about an MKV file and its audio tracks."""

    path: Path
    format_name: str
    duration: Optional[float]
    size: int  # File size in bytes
    audio_tracks: list[AudioTrack] = field(default_factory=list)

    @property
    def has_audio(self) -> bool:
        """Check if the file has any audio tracks."""
        return len(self.audio_tracks) > 0

    @property
    def display_size(self) -> str:
        """Human-readable file size."""
        if self.size >= 1_073_741_824:
            return f"{self.size / 1_073_741_824:.1f} GB"
        elif self.size >= 1_048_576:
            return f"{self.size / 1_048_576:.1f} MB"
        elif self.size >= 1024:
            return f"{self.size / 1024:.1f} KB"
        return f"{self.size} B"


def check_ffprobe() -> tuple[bool, str]:
    """Check if ffprobe is available.

    Returns:
        Tuple of (is_available, message).
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            return True, f"ffprobe found: {version_line}"
        return False, "ffprobe found but returned an error."
    except FileNotFoundError:
        return False, (
            "ffprobe not found. Please install ffmpeg:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  Fedora: sudo dnf install ffmpeg\n"
            "  Arch: sudo pacman -S ffmpeg"
        )
    except subprocess.TimeoutExpired:
        return False, "ffprobe timed out."
    except Exception as e:
        return False, f"Error checking ffprobe: {e}"


def check_ffmpeg() -> tuple[bool, str]:
    """Check if ffmpeg is available.

    Returns:
        Tuple of (is_available, message).
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            return True, f"ffmpeg found: {version_line}"
        return False, "ffmpeg found but returned an error."
    except FileNotFoundError:
        return False, (
            "ffmpeg not found. Please install ffmpeg:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  Fedora: sudo dnf install ffmpeg\n"
            "  Arch: sudo pacman -S ffmpeg"
        )
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out."
    except Exception as e:
        return False, f"Error checking ffmpeg: {e}"


def probe_file(file_path: Path) -> FileInfo:
    """Probe an MKV file to extract audio track information.

    Args:
        file_path: Path to the MKV file.

    Returns:
        FileInfo with all audio track metadata.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not a valid media file.
        RuntimeError: If ffprobe fails.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    logger.info("Probing file: %s", file_path)

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out while probing: {file_path}")
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found. Please install ffmpeg.")

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "Unknown error"
        raise RuntimeError(f"ffprobe failed for {file_path.name}: {stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}")

    return parse_probe_data(data, file_path)


def parse_probe_data(data: dict, file_path: Path) -> FileInfo:
    """Parse ffprobe JSON output into FileInfo.

    Args:
        data: Parsed ffprobe JSON output.
        file_path: Path to the source file.

    Returns:
        FileInfo populated with audio track data.
    """
    format_info = data.get("format", {})

    file_info = FileInfo(
        path=file_path,
        format_name=format_info.get("format_name", "unknown"),
        duration=_safe_float(format_info.get("duration")),
        size=int(format_info.get("size", 0)),
    )

    audio_stream_index = 0
    for stream in data.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue

        tags = stream.get("tags", {})
        language_code = tags.get("language", "und")
        language_name = get_language_name(language_code)

        # Parse channel layout
        channel_layout = stream.get("channel_layout", "")
        if not channel_layout:
            channels = int(stream.get("channels", 0))
            if channels == 1:
                channel_layout = "mono"
            elif channels == 2:
                channel_layout = "stereo"
            elif channels == 6:
                channel_layout = "5.1"
            elif channels == 8:
                channel_layout = "7.1"
            else:
                channel_layout = f"{channels}ch"

        # Parse disposition
        disposition = stream.get("disposition", {})

        track = AudioTrack(
            index=int(stream.get("index", 0)),
            stream_index=audio_stream_index,
            codec=stream.get("codec_name", "unknown"),
            codec_long=stream.get("codec_long_name", "unknown"),
            language_code=language_code,
            language_name=language_name,
            channels=int(stream.get("channels", 0)),
            channel_layout=channel_layout,
            sample_rate=int(stream.get("sample_rate", 0)),
            bit_rate=_safe_int(stream.get("bit_rate")),
            title=tags.get("title", ""),
            duration=_safe_float(stream.get("duration"))
                     or _safe_float(tags.get("DURATION")),
            is_default=bool(disposition.get("default", 0)),
            is_forced=bool(disposition.get("forced", 0)),
        )

        file_info.audio_tracks.append(track)
        audio_stream_index += 1

    logger.info(
        "Found %d audio track(s) in %s",
        len(file_info.audio_tracks),
        file_path.name,
    )
    return file_info


def _safe_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    """Safely convert a value to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
