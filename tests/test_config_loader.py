import pytest
import os
import tempfile
import textwrap

from src.config_loader import Config, load_config, ConfigValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_YAML = textwrap.dedent("""\
    ollama:
      base_url: http://localhost:11434
      model: llama3
    tts:
      voice: vi_VN-vivos-medium
      speed: 1.0
    app:
      language: vi
    """)

MISSING_REQUIRED_YAML = textwrap.dedent("""\
    tts:
      voice: vi_VN-vivos-medium
    """)


@pytest.fixture
def valid_yaml_file(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(VALID_YAML)
    return str(f)


@pytest.fixture
def missing_required_yaml_file(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(MISSING_REQUIRED_YAML)
    return str(f)


# ---------------------------------------------------------------------------
# Tests: đọc file yaml hợp lệ
# ---------------------------------------------------------------------------

class TestLoadValidConfig:
    def test_returns_config_object(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert isinstance(cfg, Config)

    def test_access_nested_key_via_dot_notation(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.ollama.base_url == "http://localhost:11434"

    def test_access_nested_key_via_get(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.get("ollama.model") == "llama3"

    def test_access_top_level_key(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.get("app.language") == "vi"

    def test_numeric_value(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.tts.speed == 1.0


# ---------------------------------------------------------------------------
# Tests: file không tồn tại
# ---------------------------------------------------------------------------

class TestMissingFile:
    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_error_message_contains_path(self):
        path = "/no/such/file.yaml"
        with pytest.raises(FileNotFoundError, match=path):
            load_config(path)


# ---------------------------------------------------------------------------
# Tests: key thiếu / giá trị mặc định
# ---------------------------------------------------------------------------

class TestMissingKeys:
    def test_get_missing_key_returns_default(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.get("ollama.timeout", default=30) == 30

    def test_get_missing_key_returns_none_by_default(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.get("nonexistent.key") is None

    def test_get_missing_top_level_key(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        assert cfg.get("database.host", default="localhost") == "localhost"

    def test_dot_access_missing_key_raises_attribute_error(self, valid_yaml_file):
        cfg = load_config(valid_yaml_file)
        with pytest.raises(AttributeError):
            _ = cfg.nonexistent_section.some_key


# ---------------------------------------------------------------------------
# Tests: validation các giá trị bắt buộc
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_config_passes_validation(self, valid_yaml_file):
        cfg = load_config(
            valid_yaml_file,
            required_keys=["ollama.base_url", "ollama.model", "tts.voice"],
        )
        assert cfg is not None

    def test_missing_required_key_raises_validation_error(self, missing_required_yaml_file):
        with pytest.raises(ConfigValidationError):
            load_config(
                missing_required_yaml_file,
                required_keys=["ollama.base_url"],
            )

    def test_validation_error_names_missing_key(self, missing_required_yaml_file):
        with pytest.raises(ConfigValidationError, match="ollama.base_url"):
            load_config(
                missing_required_yaml_file,
                required_keys=["ollama.base_url"],
            )

    def test_multiple_missing_keys_all_reported(self, missing_required_yaml_file):
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(
                missing_required_yaml_file,
                required_keys=["ollama.base_url", "ollama.model"],
            )
        msg = str(exc_info.value)
        assert "ollama.base_url" in msg
        assert "ollama.model" in msg
