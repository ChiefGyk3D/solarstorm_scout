"""The thin config layer: legacy switches and which networks are on."""

from solarstorm_scout import config


def test_legacy_flags_fill_the_new_names(monkeypatch):
    monkeypatch.setenv('BLUESKY_ENABLED', 'true')
    monkeypatch.setenv('MASTODON_ENABLED', 'false')
    config.apply_legacy_keys()
    assert config.enabled_platforms() == ['bluesky']


def test_explicit_new_name_wins_over_legacy(monkeypatch):
    monkeypatch.setenv('BLUESKY_ENABLED', 'true')
    monkeypatch.setenv('BLUESKY_ENABLE_POSTING', 'false')
    config.apply_legacy_keys()
    assert config.enabled_platforms() == []


def test_posting_order_is_fixed(monkeypatch):
    monkeypatch.setenv('MASTODON_ENABLE_POSTING', 'yes')
    monkeypatch.setenv('BLUESKY_ENABLE_POSTING', '1')
    assert config.enabled_platforms() == ['bluesky', 'mastodon']


def test_load_without_env_file_is_fine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert config.load(str(tmp_path / '.env')) is False
