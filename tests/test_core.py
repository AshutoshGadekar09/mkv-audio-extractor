"""Unit tests for MKV Audio Extractor core modules."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from mkv_audio_extractor.core.extractor import (
    ConvertFormat,
    ExtractionMode,
    ExtractionTask,
    Extractor,
    FileExistsAction,
    build_output_path,
    handle_existing_file,
    sanitize_filename,
)
from mkv_audio_extractor.core.languages import (
    get_language_code,
    get_language_name,
    is_valid_language_code,
)
from mkv_audio_extractor.core.probe import AudioTrack, FileInfo, parse_probe_data

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Language Tests ──


class TestLanguageMapping:
    """Tests for ISO 639 language code mapping."""

    def test_known_3letter_codes(self) -> None:
        assert get_language_name("hin") == "Hindi"
        assert get_language_name("tam") == "Tamil"
        assert get_language_name("tel") == "Telugu"
        assert get_language_name("jpn") == "Japanese"
        assert get_language_name("kan") == "Kannada"
        assert get_language_name("eng") == "English"

    def test_known_2letter_codes(self) -> None:
        assert get_language_name("hi") == "Hindi"
        assert get_language_name("en") == "English"
        assert get_language_name("ja") == "Japanese"
        assert get_language_name("ta") == "Tamil"
        assert get_language_name("te") == "Telugu"

    def test_case_insensitive(self) -> None:
        assert get_language_name("HIN") == "Hindi"
        assert get_language_name("Eng") == "English"
        assert get_language_name("JPN") == "Japanese"

    def test_unknown_code(self) -> None:
        assert get_language_name("xyz") == "Unknown (xyz)"
        assert get_language_name("zzz") == "Unknown (zzz)"

    def test_und_code(self) -> None:
        assert get_language_name("und") == "Unknown"
        assert get_language_name("undetermined") == "Unknown"

    def test_none_and_empty(self) -> None:
        assert get_language_name(None) == "Unknown"
        assert get_language_name("") == "Unknown"

    def test_get_language_code(self) -> None:
        assert get_language_code("Hindi") == "hin"
        assert get_language_code("English") == "eng"
        assert get_language_code("Japanese") == "jpn"

    def test_get_language_code_case_insensitive(self) -> None:
        assert get_language_code("hindi") == "hin"
        assert get_language_code("ENGLISH") == "eng"

    def test_get_language_code_not_found(self) -> None:
        assert get_language_code("Klingon") is None

    def test_is_valid_language_code(self) -> None:
        assert is_valid_language_code("hin") is True
        assert is_valid_language_code("eng") is True
        assert is_valid_language_code("xyz") is False
        assert is_valid_language_code("hi") is True


# ── Filename Sanitization Tests ──


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_simple_name(self) -> None:
        assert sanitize_filename("movie") == "movie"

    def test_special_characters(self) -> None:
        result = sanitize_filename('[Toonworld4all] Attack on Titan S04E29')
        assert "/" not in result
        assert "\0" not in result
        assert "<" not in result
        assert ">" not in result

    def test_preserves_brackets_parentheses(self) -> None:
        """Brackets and parentheses are valid in Linux filenames."""
        result = sanitize_filename("[Test] Movie (2024)")
        assert "[Test]" in result
        assert "(2024)" in result

    def test_slashes_replaced(self) -> None:
        result = sanitize_filename("path/to/file")
        assert "/" not in result

    def test_collapses_whitespace(self) -> None:
        result = sanitize_filename("too   many   spaces")
        assert "   " not in result

    def test_empty_string(self) -> None:
        assert sanitize_filename("") == "untitled"

    def test_only_dots(self) -> None:
        assert sanitize_filename("...") == "untitled"

    def test_long_name_truncated(self) -> None:
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        assert len(result.encode("utf-8")) <= 200

    def test_unicode_preserved(self) -> None:
        result = sanitize_filename("映画テスト")
        assert "映画テスト" in result

    def test_pipe_and_quotes_replaced(self) -> None:
        result = sanitize_filename('file|name"test')
        assert "|" not in result
        assert '"' not in result

    def test_complex_anime_filename(self) -> None:
        name = "[Toonworld4all] Attack on Titan S04E29 Final Chapters 1080p x265 10bit AMZN WEB-DL Multi Audio DDP2.0 ESub (1)"
        result = sanitize_filename(name)
        assert len(result) > 0
        assert "/" not in result
        assert "\0" not in result


# ── FFProbe Parsing Tests ──


class TestProbeDataParsing:
    """Tests for ffprobe JSON output parsing."""

    @pytest.fixture
    def sample_data(self) -> dict:
        with open(FIXTURES_DIR / "sample_ffprobe_output.json") as f:
            return json.load(f)

    def test_parse_basic_info(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        assert file_info.format_name == "matroska,webm"
        assert file_info.duration == pytest.approx(1440.123)
        assert file_info.size == 2147483648

    def test_parse_audio_tracks_count(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        assert len(file_info.audio_tracks) == 5  # 5 audio, 1 video, 1 subtitle

    def test_parse_track_languages(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        languages = [t.language_code for t in file_info.audio_tracks]
        assert languages == ["hin", "tam", "tel", "jpn", "kan"]

    def test_parse_track_language_names(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        names = [t.language_name for t in file_info.audio_tracks]
        assert names == ["Hindi", "Tamil", "Telugu", "Japanese", "Kannada"]

    def test_parse_track_codecs(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        codecs = [t.codec for t in file_info.audio_tracks]
        assert all(c == "eac3" for c in codecs)

    def test_parse_track_channels(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        for track in file_info.audio_tracks:
            assert track.channels == 2
            assert track.channel_layout == "stereo"

    def test_parse_track_bitrate(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        for track in file_info.audio_tracks:
            assert track.bit_rate == 128000

    def test_parse_default_track(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        assert file_info.audio_tracks[0].is_default is True
        assert file_info.audio_tracks[1].is_default is False

    def test_parse_track_titles(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        assert file_info.audio_tracks[0].title == "Hindi DDP 2.0"
        assert file_info.audio_tracks[3].title == "Japanese DDP 2.0"

    def test_parse_stream_indices(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        # Audio-specific indices should be 0-4
        assert [t.stream_index for t in file_info.audio_tracks] == [0, 1, 2, 3, 4]
        # Overall stream indices should be 1-5 (0 is video)
        assert [t.index for t in file_info.audio_tracks] == [1, 2, 3, 4, 5]

    def test_has_audio(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        assert file_info.has_audio is True

    def test_no_audio_tracks(self) -> None:
        data = {
            "format": {"format_name": "matroska", "duration": "100", "size": "1000"},
            "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264"}],
        }
        file_info = parse_probe_data(data, Path("/test/video_only.mkv"))
        assert file_info.has_audio is False
        assert len(file_info.audio_tracks) == 0

    def test_missing_language_tag(self) -> None:
        data = {
            "format": {"format_name": "matroska", "duration": "100", "size": "1000"},
            "streams": [
                {
                    "index": 0,
                    "codec_name": "aac",
                    "codec_long_name": "AAC",
                    "codec_type": "audio",
                    "sample_rate": "44100",
                    "channels": 2,
                    "tags": {},
                    "disposition": {"default": 0, "forced": 0},
                }
            ],
        }
        file_info = parse_probe_data(data, Path("/test/no_lang.mkv"))
        assert file_info.audio_tracks[0].language_name == "Unknown"
        assert file_info.audio_tracks[0].language_code == "und"

    def test_display_size(self, sample_data: dict) -> None:
        file_info = parse_probe_data(sample_data, Path("/test/movie.mkv"))
        assert "GB" in file_info.display_size


# ── AudioTrack Properties Tests ──


class TestAudioTrack:
    """Tests for AudioTrack dataclass properties."""

    def _make_track(self, codec: str = "eac3", **kwargs) -> AudioTrack:
        defaults = dict(
            index=1,
            stream_index=0,
            codec=codec,
            codec_long="Test Codec",
            language_code="eng",
            language_name="English",
            channels=2,
            channel_layout="stereo",
            sample_rate=48000,
            bit_rate=128000,
            title="",
            duration=100.0,
            is_default=False,
            is_forced=False,
        )
        defaults.update(kwargs)
        return AudioTrack(**defaults)

    def test_file_extension_eac3(self) -> None:
        track = self._make_track("eac3")
        assert track.file_extension == ".eac3"

    def test_file_extension_ac3(self) -> None:
        track = self._make_track("ac3")
        assert track.file_extension == ".ac3"

    def test_file_extension_aac(self) -> None:
        track = self._make_track("aac")
        assert track.file_extension == ".aac"

    def test_file_extension_mp3(self) -> None:
        track = self._make_track("mp3")
        assert track.file_extension == ".mp3"

    def test_file_extension_flac(self) -> None:
        track = self._make_track("flac")
        assert track.file_extension == ".flac"

    def test_file_extension_opus(self) -> None:
        track = self._make_track("opus")
        assert track.file_extension == ".opus"

    def test_file_extension_dts(self) -> None:
        track = self._make_track("dts")
        assert track.file_extension == ".dts"

    def test_file_extension_unknown_falls_back_to_mka(self) -> None:
        track = self._make_track("some_weird_codec")
        assert track.file_extension == ".mka"

    def test_display_name(self) -> None:
        track = self._make_track(
            language_name="Hindi",
            codec="eac3",
            channel_layout="stereo",
            bit_rate=128000,
            title="Hindi DDP 2.0",
            is_default=True,
        )
        display = track.display_name
        assert "Hindi" in display
        assert "EAC3" in display
        assert "128kbps" in display
        assert "(Default)" in display


# ── Output Path Building Tests ──


class TestBuildOutputPath:
    """Tests for output path building."""

    def _make_file_info(self, name: str = "movie.mkv") -> FileInfo:
        return FileInfo(
            path=Path(f"/test/{name}"),
            format_name="matroska",
            duration=100.0,
            size=1_000_000,
        )

    def _make_track(self, lang: str = "eng", codec: str = "eac3") -> AudioTrack:
        return AudioTrack(
            index=1,
            stream_index=0,
            codec=codec,
            codec_long="Test",
            language_code=lang,
            language_name=get_language_name(lang),
            channels=2,
            channel_layout="stereo",
            sample_rate=48000,
            bit_rate=128000,
            title="",
            duration=100.0,
            is_default=False,
            is_forced=False,
        )

    def test_copy_mode_output_path(self) -> None:
        fi = self._make_file_info()
        track = self._make_track("hin", "eac3")
        path = build_output_path(fi, track, Path("/output"), ExtractionMode.COPY)
        assert path == Path("/output/movie.hin.0.eac3")

    def test_convert_mode_output_path(self) -> None:
        fi = self._make_file_info()
        track = self._make_track("eng", "eac3")
        path = build_output_path(
            fi, track, Path("/output"), ExtractionMode.CONVERT, ConvertFormat.MP3
        )
        assert path == Path("/output/movie.eng.0.mp3")

    def test_aac_convert_extension(self) -> None:
        fi = self._make_file_info()
        track = self._make_track("tam", "eac3")
        path = build_output_path(
            fi, track, Path("/output"), ExtractionMode.CONVERT, ConvertFormat.AAC
        )
        assert path.suffix == ".m4a"

    def test_und_language_in_path(self) -> None:
        fi = self._make_file_info()
        track = self._make_track("und", "aac")
        path = build_output_path(fi, track, Path("/output"), ExtractionMode.COPY)
        assert "unknown" in str(path)


# ── File Exists Handling Tests ──


class TestHandleExistingFile:
    """Tests for existing file handling."""

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.eac3"
        final, skip = handle_existing_file(path, FileExistsAction.OVERWRITE)
        assert final == path
        assert skip is False

    def test_overwrite(self, tmp_path: Path) -> None:
        path = tmp_path / "existing.eac3"
        path.touch()
        final, skip = handle_existing_file(path, FileExistsAction.OVERWRITE)
        assert final == path
        assert skip is False

    def test_skip(self, tmp_path: Path) -> None:
        path = tmp_path / "existing.eac3"
        path.touch()
        final, skip = handle_existing_file(path, FileExistsAction.SKIP)
        assert final == path
        assert skip is True

    def test_rename(self, tmp_path: Path) -> None:
        path = tmp_path / "existing.eac3"
        path.touch()
        final, skip = handle_existing_file(path, FileExistsAction.RENAME)
        assert final != path
        assert final.stem.endswith("_1")
        assert skip is False

    def test_rename_multiple(self, tmp_path: Path) -> None:
        path = tmp_path / "existing.eac3"
        path.touch()
        (tmp_path / "existing_1.eac3").touch()
        final, skip = handle_existing_file(path, FileExistsAction.RENAME)
        assert final.stem.endswith("_2")


# ── Convert Format Tests ──


class TestConvertFormat:
    """Tests for ConvertFormat enum."""

    def test_mp3_extension(self) -> None:
        assert ConvertFormat.MP3.extension == ".mp3"

    def test_aac_extension(self) -> None:
        assert ConvertFormat.AAC.extension == ".m4a"

    def test_flac_extension(self) -> None:
        assert ConvertFormat.FLAC.extension == ".flac"

    def test_opus_extension(self) -> None:
        assert ConvertFormat.OPUS.extension == ".opus"

    def test_wav_extension(self) -> None:
        assert ConvertFormat.WAV.extension == ".wav"

    def test_ffmpeg_codecs(self) -> None:
        assert ConvertFormat.MP3.ffmpeg_codec == "libmp3lame"
        assert ConvertFormat.AAC.ffmpeg_codec == "aac"
        assert ConvertFormat.FLAC.ffmpeg_codec == "flac"
        assert ConvertFormat.OPUS.ffmpeg_codec == "libopus"
        assert ConvertFormat.WAV.ffmpeg_codec == "pcm_s16le"


# ── Integration Test: Generate Test MKV ──


class TestWithRealMKV:
    """Integration tests using a real (generated) MKV file."""

    @pytest.fixture
    def test_mkv(self, tmp_path: Path) -> Path:
        """Generate a small multi-audio test MKV using ffmpeg."""
        mkv_path = tmp_path / "test_multi_audio.mkv"

        # Generate a 2-second MKV with 3 audio tracks (different languages)
        cmd = [
            "ffmpeg", "-y",
            # Silent audio sources
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=660:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
            # Map all inputs
            "-map", "0:a", "-map", "1:a", "-map", "2:a",
            # Set codecs
            "-c:a", "aac",
            # Set metadata
            "-metadata:s:a:0", "language=hin",
            "-metadata:s:a:0", "title=Hindi AAC",
            "-metadata:s:a:1", "language=tam",
            "-metadata:s:a:1", "title=Tamil AAC",
            "-metadata:s:a:2", "language=jpn",
            "-metadata:s:a:2", "title=Japanese AAC",
            str(mkv_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            pytest.skip(f"Could not generate test MKV: {result.stderr}")

        return mkv_path

    def test_probe_real_file(self, test_mkv: Path) -> None:
        from mkv_audio_extractor.core.probe import probe_file

        file_info = probe_file(test_mkv)
        assert file_info.has_audio
        assert len(file_info.audio_tracks) == 3

        langs = [t.language_code for t in file_info.audio_tracks]
        assert "hin" in langs
        assert "tam" in langs
        assert "jpn" in langs

    def test_extract_copy_mode(self, test_mkv: Path, tmp_path: Path) -> None:
        from mkv_audio_extractor.core.probe import probe_file

        file_info = probe_file(test_mkv)
        track = file_info.audio_tracks[0]  # Hindi

        output_dir = tmp_path / "output"
        output_path = build_output_path(file_info, track, output_dir, ExtractionMode.COPY)

        task = ExtractionTask(
            file_info=file_info,
            track=track,
            output_path=output_path,
            mode=ExtractionMode.COPY,
        )

        extractor = Extractor()
        results = extractor.extract_tracks([task])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output_path is not None
        assert results[0].output_path.exists()
        assert results[0].output_path.stat().st_size > 0

    def test_extract_convert_mp3(self, test_mkv: Path, tmp_path: Path) -> None:
        from mkv_audio_extractor.core.probe import probe_file

        file_info = probe_file(test_mkv)
        track = file_info.audio_tracks[1]  # Tamil

        output_dir = tmp_path / "output_mp3"
        output_path = build_output_path(
            file_info, track, output_dir,
            ExtractionMode.CONVERT, ConvertFormat.MP3,
        )

        task = ExtractionTask(
            file_info=file_info,
            track=track,
            output_path=output_path,
            mode=ExtractionMode.CONVERT,
            convert_format=ConvertFormat.MP3,
            bitrate="128k",
        )

        extractor = Extractor()
        results = extractor.extract_tracks([task])

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output_path.suffix == ".mp3"

    def test_extract_multiple_tracks(self, test_mkv: Path, tmp_path: Path) -> None:
        from mkv_audio_extractor.core.probe import probe_file

        file_info = probe_file(test_mkv)
        output_dir = tmp_path / "output_batch"

        tasks = []
        for track in file_info.audio_tracks:
            output_path = build_output_path(file_info, track, output_dir, ExtractionMode.COPY)
            tasks.append(ExtractionTask(
                file_info=file_info,
                track=track,
                output_path=output_path,
                mode=ExtractionMode.COPY,
            ))

        extractor = Extractor()
        results = extractor.extract_tracks(tasks)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_cancel_extraction(self, test_mkv: Path, tmp_path: Path) -> None:
        from mkv_audio_extractor.core.probe import probe_file

        file_info = probe_file(test_mkv)
        output_dir = tmp_path / "output_cancel"

        tasks = []
        for track in file_info.audio_tracks:
            output_path = build_output_path(file_info, track, output_dir, ExtractionMode.COPY)
            tasks.append(ExtractionTask(
                file_info=file_info,
                track=track,
                output_path=output_path,
                mode=ExtractionMode.COPY,
            ))

        extractor = Extractor()
        # Cancel immediately
        extractor.cancel()
        results = extractor.extract_tracks(tasks)

        # All should be marked as cancelled
        assert all(not r.success for r in results)
