import stat

import pytest

from minecraft_ia.config import ConfigError, ensure_token, load_config, read_secret


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_and_relative_paths(tmp_path):
    cfg = load_config(write(tmp_path / "config.toml", 'kb_path = "kb"\ndb_path = "data/brain.sqlite3"\n'))
    assert cfg.kb_path == tmp_path / "kb"
    assert cfg.db_path == tmp_path / "data/brain.sqlite3"
    assert cfg.model == "gemini-3.8-flash"
    assert cfg.thinking_level == "high"
    assert cfg.host == "127.0.0.1"
    assert cfg.questions_per_player_per_day > 0 and cfg.llm_calls_per_day > 0


@pytest.mark.parametrize(
    "line", ['host = "0.0.0.0"', 'thinking_level = "max"', "questions_per_player_per_day = 0", "unknown_key = 1"]
)
def test_rejects_unsafe_or_invalid_values(tmp_path, line):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path / "config.toml", f'kb_path = "kb"\ndb_path = "b.sqlite3"\n{line}\n'))


def test_missing_required_key(tmp_path):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path / "config.toml", 'kb_path = "kb"\n'))


def test_read_secret_strips_and_refuses_empty(tmp_path):
    assert read_secret(write(tmp_path / "k", "abc\n")) == "abc"
    with pytest.raises(ConfigError):
        read_secret(write(tmp_path / "empty", "\n"))
    with pytest.raises(ConfigError):
        read_secret(tmp_path / "absent")


def test_ensure_token_creates_private_file_once(tmp_path):
    path = tmp_path / "sub" / "brain-token"
    token = ensure_token(path)
    assert len(token) >= 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert ensure_token(path) == token
