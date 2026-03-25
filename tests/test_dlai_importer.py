"""Tests for src/dlai_importer.py — TDD suite."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.dlai_importer import (
    DLAIImporter,
    DLAIImporterConfig,
    ImportResult,
    load_dlai_importer_from_config,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = DLAIImporterConfig(output_dir="output/imports")


def make_video_file(tmp_path: Path, name: str = "lecture.mp4") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00\x01\x02")  # dummy bytes
    return p


def make_srt_file(tmp_path: Path, name: str = "lecture.srt") -> Path:
    p = tmp_path / name
    p.write_text(
        "1\n00:00:00,000 --> 00:00:03,500\nHello world\n\n"
        "2\n00:00:03,500 --> 00:00:07,000\nSecond line\n",
        encoding="utf-8",
    )
    return p


def make_vtt_file(tmp_path: Path, name: str = "lecture.vtt") -> Path:
    p = tmp_path / name
    p.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:03.500\nHello world\n\n"
        "00:00:03.500 --> 00:00:07.000\nSecond line\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# TestImportResult
# ---------------------------------------------------------------------------

class TestImportResult:
    def test_fields_exist(self):
        r = ImportResult(
            video_path="/out/lecture.mp4",
            subtitle_path="/out/lecture.srt",
            subtitle_was_converted=False,
            original_video_path="/src/lecture.mp4",
            original_subtitle_path="/src/lecture.srt",
        )
        assert r.video_path == "/out/lecture.mp4"
        assert r.subtitle_path == "/out/lecture.srt"
        assert r.subtitle_was_converted is False
        assert r.original_video_path == "/src/lecture.mp4"
        assert r.original_subtitle_path == "/src/lecture.srt"


# ---------------------------------------------------------------------------
# TestDLAIImporterConfig
# ---------------------------------------------------------------------------

class TestDLAIImporterConfig:
    def test_default_output_dir(self):
        cfg = DLAIImporterConfig()
        assert cfg.output_dir == "output/imports"

    def test_custom_output_dir(self):
        cfg = DLAIImporterConfig(output_dir="/custom/path")
        assert cfg.output_dir == "/custom/path"


# ---------------------------------------------------------------------------
# TestValidateVideo
# ---------------------------------------------------------------------------

class TestValidateVideo:
    def test_mp4_accepted(self, tmp_path):
        p = make_video_file(tmp_path, "v.mp4")
        importer = DLAIImporter(DEFAULT_CONFIG)
        importer._validate_video(str(p))  # should not raise

    def test_webm_accepted(self, tmp_path):
        p = make_video_file(tmp_path, "v.webm")
        importer = DLAIImporter(DEFAULT_CONFIG)
        importer._validate_video(str(p))

    def test_mkv_accepted(self, tmp_path):
        p = make_video_file(tmp_path, "v.mkv")
        importer = DLAIImporter(DEFAULT_CONFIG)
        importer._validate_video(str(p))

    def test_invalid_extension_raises(self, tmp_path):
        p = make_video_file(tmp_path, "v.avi")
        importer = DLAIImporter(DEFAULT_CONFIG)
        with pytest.raises(ValueError, match="Unsupported video format"):
            importer._validate_video(str(p))

    def test_missing_file_raises(self, tmp_path):
        missing = str(tmp_path / "ghost.mp4")
        importer = DLAIImporter(DEFAULT_CONFIG)
        with pytest.raises(FileNotFoundError):
            importer._validate_video(missing)


# ---------------------------------------------------------------------------
# TestValidateSubtitle
# ---------------------------------------------------------------------------

class TestValidateSubtitle:
    def test_srt_accepted(self, tmp_path):
        p = make_srt_file(tmp_path)
        DLAIImporter(DEFAULT_CONFIG)._validate_subtitle(str(p))

    def test_vtt_accepted(self, tmp_path):
        p = make_vtt_file(tmp_path)
        DLAIImporter(DEFAULT_CONFIG)._validate_subtitle(str(p))

    def test_invalid_extension_raises(self, tmp_path):
        p = tmp_path / "sub.ass"
        p.write_text("content")
        with pytest.raises(ValueError, match="Unsupported subtitle format"):
            DLAIImporter(DEFAULT_CONFIG)._validate_subtitle(str(p))

    def test_missing_file_raises(self, tmp_path):
        missing = str(tmp_path / "ghost.srt")
        with pytest.raises(FileNotFoundError):
            DLAIImporter(DEFAULT_CONFIG)._validate_subtitle(missing)


# ---------------------------------------------------------------------------
# TestImportSrtFile
# ---------------------------------------------------------------------------

class TestImportSrtFile:
    def test_returns_import_result(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        cfg = DLAIImporterConfig(output_dir=out_dir)
        result = DLAIImporter(cfg).import_files(str(video), str(sub))
        assert isinstance(result, ImportResult)

    def test_video_path_is_in_output_dir(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(sub))
        assert result.video_path.startswith(out_dir)

    def test_subtitle_path_is_in_output_dir(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(sub))
        assert result.subtitle_path.startswith(out_dir)

    def test_was_converted_false_for_srt(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(sub))
        assert result.subtitle_was_converted is False

    def test_original_paths_preserved(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(sub))
        assert result.original_video_path == str(video)
        assert result.original_subtitle_path == str(sub)


# ---------------------------------------------------------------------------
# TestImportVttFile
# ---------------------------------------------------------------------------

class TestImportVttFile:
    def test_was_converted_true_for_vtt(self, tmp_path):
        video = make_video_file(tmp_path)
        vtt = make_vtt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(vtt))
        assert result.subtitle_was_converted is True

    def test_output_subtitle_has_srt_extension(self, tmp_path):
        video = make_video_file(tmp_path)
        vtt = make_vtt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(vtt))
        assert result.subtitle_path.endswith(".srt")

    def test_srt_file_exists_on_disk(self, tmp_path):
        video = make_video_file(tmp_path)
        vtt = make_vtt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(vtt))
        assert Path(result.subtitle_path).exists()

    def test_original_subtitle_path_is_vtt(self, tmp_path):
        video = make_video_file(tmp_path)
        vtt = make_vtt_file(tmp_path)
        out_dir = str(tmp_path / "out")
        result = DLAIImporter(DLAIImporterConfig(out_dir)).import_files(str(video), str(vtt))
        assert result.original_subtitle_path == str(vtt)
        assert result.original_subtitle_path.endswith(".vtt")

    def test_no_vtt_file_in_output_dir(self, tmp_path):
        """Only the converted SRT should end up in output, not the raw VTT."""
        video = make_video_file(tmp_path)
        vtt = make_vtt_file(tmp_path)
        out_dir = tmp_path / "out"
        DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(vtt))
        vtt_files = list(out_dir.glob("*.vtt"))
        assert len(vtt_files) == 0


# ---------------------------------------------------------------------------
# TestVttConversionContent
# ---------------------------------------------------------------------------

class TestVttConversionContent:
    def _convert(self, tmp_path: Path) -> str:
        vtt = make_vtt_file(tmp_path)
        srt_out = str(tmp_path / "out.srt")
        DLAIImporter(DEFAULT_CONFIG)._convert_vtt_to_srt(str(vtt), srt_out)
        return Path(srt_out).read_text(encoding="utf-8")

    def test_timestamps_use_commas(self, tmp_path):
        content = self._convert(tmp_path)
        # SRT format uses comma: 00:00:00,000
        assert "," in content
        assert "00:00:00,000" in content

    def test_index_numbers_present(self, tmp_path):
        content = self._convert(tmp_path)
        lines = content.strip().split("\n")
        # First non-empty line should be "1"
        assert lines[0].strip() == "1"

    def test_text_preserved(self, tmp_path):
        content = self._convert(tmp_path)
        assert "Hello world" in content
        assert "Second line" in content

    def test_two_entries_converted(self, tmp_path):
        content = self._convert(tmp_path)
        # Count entries by counting lines that are purely a digit
        index_lines = [l for l in content.strip().split("\n") if re.match(r"^\d+$", l.strip())]
        assert len(index_lines) == 2


# ---------------------------------------------------------------------------
# TestOutputDirCreated
# ---------------------------------------------------------------------------

class TestOutputDirCreated:
    def test_output_dir_created_if_not_exists(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = tmp_path / "brand" / "new" / "dir"
        DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(sub))
        assert out_dir.exists()

    def test_nested_output_dir_created(self, tmp_path):
        video = make_video_file(tmp_path)
        vtt = make_vtt_file(tmp_path)
        out_dir = tmp_path / "a" / "b" / "c"
        DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(vtt))
        assert out_dir.exists()


# ---------------------------------------------------------------------------
# TestFileCopied
# ---------------------------------------------------------------------------

class TestFileCopied:
    def test_video_file_exists_in_output_dir(self, tmp_path):
        video = make_video_file(tmp_path, "my_lecture.mp4")
        sub = make_srt_file(tmp_path)
        out_dir = tmp_path / "out"
        result = DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(sub))
        assert Path(result.video_path).exists()

    def test_video_filename_preserved(self, tmp_path):
        video = make_video_file(tmp_path, "my_lecture.mp4")
        sub = make_srt_file(tmp_path)
        out_dir = tmp_path / "out"
        result = DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(sub))
        assert Path(result.video_path).name == "my_lecture.mp4"

    def test_subtitle_file_exists_in_output_dir(self, tmp_path):
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path, "my_subs.srt")
        out_dir = tmp_path / "out"
        result = DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(sub))
        assert Path(result.subtitle_path).exists()

    def test_original_files_not_deleted(self, tmp_path):
        """Source files must still exist after import (copy, not move)."""
        video = make_video_file(tmp_path)
        sub = make_srt_file(tmp_path)
        out_dir = tmp_path / "out"
        DLAIImporter(DLAIImporterConfig(str(out_dir))).import_files(str(video), str(sub))
        assert video.exists()
        assert sub.exists()


# ---------------------------------------------------------------------------
# TestLoadFromConfig
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_output_dir_from_yaml(self):
        importer = load_dlai_importer_from_config("config/config.yaml")
        assert importer.config.output_dir == "output/imports"

    def test_output_dir_override(self):
        importer = load_dlai_importer_from_config(
            "config/config.yaml", output_dir="/custom/imports"
        )
        assert importer.config.output_dir == "/custom/imports"

    def test_missing_imports_section_uses_default(self, tmp_path):
        cfg_path = tmp_path / "minimal.yaml"
        cfg_path.write_text("app:\n  log_level: INFO\n", encoding="utf-8")
        importer = load_dlai_importer_from_config(str(cfg_path))
        assert importer.config.output_dir == "output/imports"
