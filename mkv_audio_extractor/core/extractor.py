"""Audio extraction engine using ffmpeg."""

import logging
import os
import re
import signal
import subprocess
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .probe import AudioTrack, FileInfo

logger = logging.getLogger(__name__)


class ExtractionMode(Enum):
    """Audio extraction mode."""
    COPY = "copy"
    CONVERT = "convert"


class ConvertFormat(Enum):
    """Target format for conversion mode."""
    MP3 = "mp3"
    AAC = "aac"
    FLAC = "flac"
    OPUS = "opus"
    WAV = "wav"

    @property
    def extension(self) -> str:
        """File extension for this format."""
        ext_map = {
            "mp3": ".mp3",
            "aac": ".m4a",
            "flac": ".flac",
            "opus": ".opus",
            "wav": ".wav",
        }
        return ext_map[self.value]

    @property
    def ffmpeg_codec(self) -> str:
        """FFmpeg codec name for this format."""
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "flac": "flac",
            "opus": "libopus",
            "wav": "pcm_s16le",
        }
        return codec_map[self.value]


class FileExistsAction(Enum):
    """Action when output file already exists."""
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"


@dataclass
class ExtractionTask:
    """A single audio extraction task."""
    file_info: FileInfo
    track: AudioTrack
    output_path: Path
    mode: ExtractionMode = ExtractionMode.COPY
    convert_format: Optional[ConvertFormat] = None
    bitrate: Optional[str] = None  # e.g., "192k", "320k"


@dataclass
class ExtractionResult:
    """Result of an extraction task."""
    task: ExtractionTask
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    skipped: bool = False


# Progress callback signature: (task_index, total_tasks, track_progress_pct, message)
ProgressCallback = Callable[[int, int, float, str], None]


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename on Linux.

    Args:
        name: The raw filename string.

    Returns:
        A sanitized filename safe for Linux filesystems.
    """
    # Replace path separators and null bytes
    name = name.replace("/", "_").replace("\0", "")

    # Remove or replace problematic characters for general compatibility
    # Keep unicode letters, digits, spaces, dots, hyphens, underscores
    name = re.sub(r'[<>:"|?*]', "_", name)

    # Collapse multiple underscores/spaces
    name = re.sub(r"[_\s]+", "_", name)

    # Strip leading/trailing dots and whitespace
    name = name.strip(". \t")

    # Ensure non-empty
    if not name:
        name = "untitled"

    # Truncate to a reasonable length (255 bytes is Linux filename limit)
    # Use 200 to leave room for extension and language suffix
    if len(name.encode("utf-8")) > 200:
        while len(name.encode("utf-8")) > 200:
            name = name[:-1]
        name = name.rstrip(". \t")

    return name


def build_output_path(
    file_info: FileInfo,
    track: AudioTrack,
    output_dir: Path,
    mode: ExtractionMode,
    convert_format: Optional[ConvertFormat] = None,
    naming_template: str = "{original_name}.{lang}.{index}.{ext}",
) -> Path:
    """Build the output file path for an extracted track.

    Args:
        file_info: Source file information.
        track: Audio track to extract.
        output_dir: Output directory.
        mode: Extraction mode (copy or convert).
        convert_format: Target format for convert mode.
        naming_template: Template for output filename.

    Returns:
        Full output file path.
    """
    original_name = sanitize_filename(file_info.path.stem)

    if mode == ExtractionMode.COPY:
        ext = track.file_extension.lstrip(".")
    else:
        ext = convert_format.extension.lstrip(".") if convert_format else "mka"

    lang = track.language_code if track.language_code != "und" else "unknown"

    filename = naming_template.format(
        original_name=original_name,
        lang=lang,
        index=track.stream_index,
        ext=ext,
    )

    # If template didn't include {ext}, add it
    if not filename.endswith(f".{ext}"):
        filename = f"{filename}.{ext}"

    return output_dir / filename


def handle_existing_file(path: Path, action: FileExistsAction) -> tuple[Path, bool]:
    """Handle an existing output file.

    Args:
        path: The proposed output path.
        action: What to do if it exists.

    Returns:
        Tuple of (final_path, should_skip).
    """
    if not path.exists():
        return path, False

    if action == FileExistsAction.OVERWRITE:
        return path, False
    elif action == FileExistsAction.SKIP:
        return path, True
    elif action == FileExistsAction.RENAME:
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path, False
            counter += 1
    return path, False


class Extractor:
    """Audio extraction engine using ffmpeg."""

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._current_process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Cancel the current extraction."""
        self._cancel_event.set()
        with self._lock:
            if self._current_process and self._current_process.poll() is None:
                try:
                    self._current_process.send_signal(signal.SIGTERM)
                except OSError:
                    pass

    def reset(self) -> None:
        """Reset the cancel state for a new batch."""
        self._cancel_event.clear()

    @property
    def is_cancelled(self) -> bool:
        """Check if extraction has been cancelled."""
        return self._cancel_event.is_set()

    def extract_tracks(
        self,
        tasks: list[ExtractionTask],
        file_exists_action: FileExistsAction = FileExistsAction.RENAME,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> list[ExtractionResult]:
        """Extract multiple audio tracks.

        Args:
            tasks: List of extraction tasks to process.
            file_exists_action: How to handle existing output files.
            progress_callback: Optional callback for progress updates.

        Returns:
            List of extraction results.
        """
        results: list[ExtractionResult] = []

        for i, task in enumerate(tasks):
            if self.is_cancelled:
                results.append(ExtractionResult(
                    task=task,
                    success=False,
                    error="Cancelled by user",
                ))
                continue

            if progress_callback:
                progress_callback(
                    i, len(tasks), 0.0,
                    f"Extracting {task.track.language_name} "
                    f"({task.track.codec.upper()}) from {task.file_info.path.name}",
                )

            result = self._extract_single(task, file_exists_action, progress_callback, i, len(tasks))
            results.append(result)

            if progress_callback:
                status = "✓ Done" if result.success else ("⏭ Skipped" if result.skipped else f"✗ {result.error}")
                progress_callback(i, len(tasks), 100.0, status)

        return results

    def _extract_single(
        self,
        task: ExtractionTask,
        file_exists_action: FileExistsAction,
        progress_callback: Optional[ProgressCallback],
        task_index: int,
        total_tasks: int,
    ) -> ExtractionResult:
        """Extract a single audio track.

        Args:
            task: The extraction task.
            file_exists_action: How to handle existing files.
            progress_callback: Progress callback.
            task_index: Current task index.
            total_tasks: Total number of tasks.

        Returns:
            Extraction result.
        """
        try:
            # Ensure output directory exists
            task.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle existing files
            final_path, should_skip = handle_existing_file(task.output_path, file_exists_action)
            if should_skip:
                logger.info("Skipping existing file: %s", final_path)
                return ExtractionResult(
                    task=task,
                    success=True,
                    output_path=final_path,
                    skipped=True,
                )

            # Check disk space (rough estimate)
            self._check_disk_space(final_path.parent, task)

            # Build ffmpeg command
            cmd = self._build_ffmpeg_command(task, final_path)
            logger.info("Running: %s", " ".join(str(c) for c in cmd))

            # Run ffmpeg with progress parsing
            return self._run_ffmpeg(cmd, task, final_path, progress_callback, task_index, total_tasks)

        except PermissionError as e:
            logger.error("Permission error: %s", e)
            return ExtractionResult(task=task, success=False, error=f"Permission denied: {e}")
        except OSError as e:
            logger.error("OS error: %s", e)
            return ExtractionResult(task=task, success=False, error=f"OS error: {e}")
        except Exception as e:
            logger.error("Extraction error: %s", e)
            return ExtractionResult(task=task, success=False, error=str(e))

    def _check_disk_space(self, directory: Path, task: ExtractionTask) -> None:
        """Check if there's enough disk space for extraction.

        Raises:
            OSError: If there's not enough disk space.
        """
        try:
            stat = os.statvfs(directory)
            free_bytes = stat.f_bavail * stat.f_frsize
            # Estimate: audio is typically much smaller than video
            # Use 10% of source file size as a rough estimate
            estimated_size = task.file_info.size // 10
            if free_bytes < estimated_size:
                raise OSError(
                    f"Insufficient disk space. Free: {free_bytes // 1_048_576}MB, "
                    f"estimated need: {estimated_size // 1_048_576}MB"
                )
        except OSError:
            raise
        except Exception:
            pass  # If we can't check, proceed anyway

    def _build_ffmpeg_command(
        self, task: ExtractionTask, output_path: Path
    ) -> list[str]:
        """Build the ffmpeg command for extraction.

        Args:
            task: Extraction task.
            output_path: Output file path.

        Returns:
            Command as a list of strings.
        """
        cmd: list[str] = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(task.file_info.path),
            "-map", f"0:{task.track.index}",
            "-progress", "pipe:1",
            "-nostats",
        ]

        if task.mode == ExtractionMode.COPY:
            cmd.extend(["-c:a", "copy"])
        else:
            if task.convert_format is None:
                raise ValueError("convert_format must be set for CONVERT mode")

            cmd.extend(["-c:a", task.convert_format.ffmpeg_codec])

            if task.bitrate:
                cmd.extend(["-b:a", task.bitrate])
            elif task.convert_format == ConvertFormat.MP3:
                cmd.extend(["-b:a", "192k"])
            elif task.convert_format == ConvertFormat.AAC:
                cmd.extend(["-b:a", "192k"])
            elif task.convert_format == ConvertFormat.OPUS:
                cmd.extend(["-b:a", "128k"])

            # WAV and FLAC don't need bitrate

        cmd.extend(["-vn", str(output_path)])
        return cmd

    def _run_ffmpeg(
        self,
        cmd: list[str],
        task: ExtractionTask,
        output_path: Path,
        progress_callback: Optional[ProgressCallback],
        task_index: int,
        total_tasks: int,
    ) -> ExtractionResult:
        """Run ffmpeg and parse progress output.

        Args:
            cmd: FFmpeg command.
            task: Extraction task.
            output_path: Output file path.
            progress_callback: Progress callback.
            task_index: Current task index.
            total_tasks: Total number of tasks.

        Returns:
            Extraction result.
        """
        try:
            with self._lock:
                self._current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            duration = task.track.duration or task.file_info.duration or 0

            stderr_lines: list[str] = []
            stderr_thread = threading.Thread(
                target=self._read_stderr,
                args=(self._current_process, stderr_lines),
                daemon=True,
            )
            stderr_thread.start()

            # Parse progress from stdout
            if self._current_process.stdout:
                self._parse_progress(
                    self._current_process.stdout,
                    duration,
                    progress_callback,
                    task_index,
                    total_tasks,
                    task,
                )

            self._current_process.wait(timeout=300)
            stderr_thread.join(timeout=5)

            with self._lock:
                returncode = self._current_process.returncode
                self._current_process = None

            if self.is_cancelled:
                # Clean up partial file
                if output_path.exists():
                    output_path.unlink()
                return ExtractionResult(
                    task=task, success=False, error="Cancelled by user"
                )

            if returncode != 0:
                stderr_text = "\n".join(stderr_lines[-10:])
                # Clean up failed file
                if output_path.exists() and output_path.stat().st_size == 0:
                    output_path.unlink()
                return ExtractionResult(
                    task=task, success=False,
                    error=f"ffmpeg exited with code {returncode}: {stderr_text}",
                )

            # Verify output file exists and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                return ExtractionResult(
                    task=task, success=False,
                    error="Output file is empty or was not created",
                )

            logger.info("Successfully extracted: %s", output_path)
            return ExtractionResult(
                task=task, success=True, output_path=output_path
            )

        except subprocess.TimeoutExpired:
            with self._lock:
                if self._current_process:
                    self._current_process.kill()
                    self._current_process = None
            return ExtractionResult(
                task=task, success=False, error="ffmpeg timed out"
            )

    def _parse_progress(
        self,
        stdout,
        duration: float,
        progress_callback: Optional[ProgressCallback],
        task_index: int,
        total_tasks: int,
        task: ExtractionTask,
    ) -> None:
        """Parse ffmpeg progress output from stdout."""
        current_time = 0.0

        for line in stdout:
            if self.is_cancelled:
                break

            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    time_us = int(line.split("=")[1])
                    current_time = time_us / 1_000_000
                except (ValueError, IndexError):
                    continue

                if duration > 0 and progress_callback:
                    pct = min(99.0, (current_time / duration) * 100)
                    progress_callback(
                        task_index, total_tasks, pct,
                        f"Extracting {task.track.language_name} "
                        f"({task.track.codec.upper()}): "
                        f"{current_time:.0f}s / {duration:.0f}s",
                    )

            elif line.startswith("progress=end"):
                if progress_callback:
                    progress_callback(
                        task_index, total_tasks, 100.0,
                        f"Completed {task.track.language_name}",
                    )

    @staticmethod
    def _read_stderr(process: subprocess.Popen, lines: list[str]) -> None:
        """Read stderr from ffmpeg process into a list."""
        if process.stderr:
            for line in process.stderr:
                lines.append(line.strip())
