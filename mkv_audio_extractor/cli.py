"""CLI entry point for MKV Audio Extractor."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .core.extractor import (
    ConvertFormat,
    ExtractionMode,
    ExtractionTask,
    Extractor,
    FileExistsAction,
    build_output_path,
    sanitize_filename,
)
from .core.languages import get_language_name, is_valid_language_code
from .core.probe import check_ffmpeg, check_ffprobe, probe_file

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def find_mkv_files(paths: list[str], recursive: bool = False) -> list[Path]:
    """Find MKV files from given paths (files or directories).

    Args:
        paths: List of file or directory paths.
        recursive: Whether to scan directories recursively.

    Returns:
        List of MKV file paths.
    """
    mkv_files: list[Path] = []

    for path_str in paths:
        path = Path(path_str)
        if not path.exists():
            logger.warning("Path not found: %s", path)
            continue

        if path.is_file():
            if path.suffix.lower() == ".mkv":
                mkv_files.append(path)
            else:
                logger.warning("Not an MKV file: %s", path)
        elif path.is_dir():
            pattern = "**/*.mkv" if recursive else "*.mkv"
            found = sorted(path.glob(pattern))
            if not found:
                logger.warning("No MKV files found in: %s", path)
            mkv_files.extend(found)

    return mkv_files


def print_tracks(file_info) -> None:
    """Print audio track information for a file."""
    print(f"\n{'='*70}")
    print(f"File: {file_info.path.name}")
    print(f"Size: {file_info.display_size}")
    if file_info.duration:
        mins, secs = divmod(int(file_info.duration), 60)
        hours, mins = divmod(mins, 60)
        print(f"Duration: {hours:02d}:{mins:02d}:{secs:02d}")
    print(f"{'='*70}")

    if not file_info.has_audio:
        print("  No audio tracks found.")
        return

    print(f"\n  {'#':<4} {'Language':<15} {'Codec':<10} {'Channels':<12} "
          f"{'Bitrate':<10} {'Title'}")
    print(f"  {'-'*4} {'-'*15} {'-'*10} {'-'*12} {'-'*10} {'-'*20}")

    for track in file_info.audio_tracks:
        bitrate = f"{track.bit_rate // 1000}k" if track.bit_rate else "N/A"
        flags = []
        if track.is_default:
            flags.append("D")
        if track.is_forced:
            flags.append("F")
        flag_str = f" [{','.join(flags)}]" if flags else ""

        print(
            f"  {track.stream_index:<4} "
            f"{track.language_name + ' (' + track.language_code + ')':<15} "
            f"{track.codec.upper():<10} "
            f"{track.channel_layout:<12} "
            f"{bitrate:<10} "
            f"{track.title}{flag_str}"
        )


def progress_callback(task_index: int, total_tasks: int, pct: float, msg: str) -> None:
    """Print progress to terminal."""
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    print(
        f"\r  [{task_index + 1}/{total_tasks}] [{bar}] {pct:5.1f}% {msg}",
        end="", flush=True,
    )
    if pct >= 100:
        print()  # Newline when complete


def run_cli(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        args: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(
        prog="mkv-audio-extractor",
        description="Extract audio tracks from MKV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s movie.mkv --lang hin,tam,jpn --mode copy
  %(prog)s movie.mkv --all -o ~/Music/extracted
  %(prog)s movie.mkv --lang eng --mode convert --convert-to mp3 --bitrate 320k
  %(prog)s /path/to/folder --recursive --all
  %(prog)s movie.mkv --list  # Just list tracks, don't extract
        """,
    )

    parser.add_argument(
        "input",
        nargs="+",
        help="MKV files or directories to process.",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        help="Comma-separated language codes to extract (e.g., hin,tam,jpn).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract all audio tracks.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_tracks",
        help="List audio tracks and exit (don't extract).",
    )
    parser.add_argument(
        "--track",
        type=str,
        default=None,
        help="Comma-separated track indices to extract (e.g., 0,2,4).",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "convert"],
        default="copy",
        help="Extraction mode (default: copy).",
    )
    parser.add_argument(
        "--convert-to",
        choices=["mp3", "aac", "flac", "opus", "wav"],
        default=None,
        help="Target format for convert mode.",
    )
    parser.add_argument(
        "--bitrate",
        type=str,
        default=None,
        help="Audio bitrate for convert mode (e.g., 192k, 320k).",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: folder named after source file).",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Scan directories recursively for MKV files.",
    )
    parser.add_argument(
        "--overwrite",
        choices=["overwrite", "skip", "rename"],
        default="rename",
        help="Action for existing files (default: rename).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    parsed = parser.parse_args(args)
    setup_logging(parsed.verbose)

    # Check dependencies
    ffprobe_ok, ffprobe_msg = check_ffprobe()
    if not ffprobe_ok:
        print(f"Error: {ffprobe_msg}", file=sys.stderr)
        return 1

    ffmpeg_ok, ffmpeg_msg = check_ffmpeg()
    if not ffmpeg_ok:
        print(f"Error: {ffmpeg_msg}", file=sys.stderr)
        return 1

    # Validate mode/format
    extraction_mode = ExtractionMode.COPY if parsed.mode == "copy" else ExtractionMode.CONVERT
    convert_format: Optional[ConvertFormat] = None

    if extraction_mode == ExtractionMode.CONVERT:
        if not parsed.convert_to:
            print("Error: --convert-to is required when --mode=convert", file=sys.stderr)
            return 1
        convert_format = ConvertFormat(parsed.convert_to)

    # Parse language filter
    lang_filter: Optional[set[str]] = None
    if parsed.lang:
        lang_filter = set()
        for code in parsed.lang.split(","):
            code = code.strip().lower()
            if not code:
                continue
            if is_valid_language_code(code):
                lang_filter.add(code)
            else:
                print(f"Warning: Unknown language code '{code}' "
                      f"(will try anyway)", file=sys.stderr)
                lang_filter.add(code)

    # Parse track filter
    track_filter: Optional[set[int]] = None
    if parsed.track:
        try:
            track_filter = {int(t.strip()) for t in parsed.track.split(",")}
        except ValueError:
            print("Error: --track must be comma-separated integers", file=sys.stderr)
            return 1

    # Need at least one selection method (unless listing)
    if not parsed.list_tracks and not parsed.all and not lang_filter and not track_filter:
        print("Error: Specify --all, --lang, or --track to select tracks.", file=sys.stderr)
        return 1

    # Find files
    mkv_files = find_mkv_files(parsed.input, parsed.recursive)
    if not mkv_files:
        print("Error: No MKV files found.", file=sys.stderr)
        return 1

    print(f"Found {len(mkv_files)} MKV file(s).")

    # File exists action
    file_exists_map = {
        "overwrite": FileExistsAction.OVERWRITE,
        "skip": FileExistsAction.SKIP,
        "rename": FileExistsAction.RENAME,
    }
    file_exists_action = file_exists_map[parsed.overwrite]

    # Process each file
    all_tasks: list[ExtractionTask] = []
    all_results: list = []
    extractor = Extractor()

    for mkv_file in mkv_files:
        try:
            file_info = probe_file(mkv_file)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            print(f"Error probing {mkv_file.name}: {e}", file=sys.stderr)
            continue

        print_tracks(file_info)

        if parsed.list_tracks:
            continue

        if not file_info.has_audio:
            print(f"  Skipping: no audio tracks.")
            continue

        # Select tracks
        selected_tracks = []
        for track in file_info.audio_tracks:
            if parsed.all:
                selected_tracks.append(track)
            elif lang_filter and track.language_code.lower() in lang_filter:
                selected_tracks.append(track)
            elif track_filter and track.stream_index in track_filter:
                selected_tracks.append(track)

        if not selected_tracks:
            print(f"  No matching tracks found.")
            continue

        print(f"\n  Selected {len(selected_tracks)} track(s) for extraction:")
        for t in selected_tracks:
            print(f"    - {t.display_name}")

        # Build output directory
        if parsed.output:
            output_dir = Path(parsed.output)
        else:
            output_dir = mkv_file.parent / sanitize_filename(mkv_file.stem)

        # Build tasks
        tasks = []
        for track in selected_tracks:
            output_path = build_output_path(
                file_info, track, output_dir, extraction_mode, convert_format
            )
            task = ExtractionTask(
                file_info=file_info,
                track=track,
                output_path=output_path,
                mode=extraction_mode,
                convert_format=convert_format,
                bitrate=parsed.bitrate,
            )
            tasks.append(task)

        all_tasks.extend(tasks)

        # Extract
        print(f"\n  Extracting to: {output_dir}")
        results = extractor.extract_tracks(
            tasks,
            file_exists_action=file_exists_action,
            progress_callback=progress_callback,
        )
        all_results.extend(results)

    if parsed.list_tracks:
        return 0

    # Summary
    if all_results:
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")

        success_count = sum(1 for r in all_results if r.success and not r.skipped)
        skip_count = sum(1 for r in all_results if r.skipped)
        fail_count = sum(1 for r in all_results if not r.success)

        print(f"  ✓ Extracted: {success_count}")
        print(f"  ⏭ Skipped:   {skip_count}")
        print(f"  ✗ Failed:    {fail_count}")

        if fail_count > 0:
            print("\n  Failures:")
            for r in all_results:
                if not r.success:
                    print(f"    - {r.task.track.display_name}: {r.error}")

        return 0 if fail_count == 0 else 1

    return 0


def main() -> None:
    """Entry point for the CLI."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
