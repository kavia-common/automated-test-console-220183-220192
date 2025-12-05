import os
import json
import yaml

from src.api.config_service import read_config, write_config, list_config_folders
from src.core.settings import settings


def test_write_and_read_yaml_config(tmp_path):
    rel = "envs/sample.yaml"
    path = os.path.join(settings.CONFIG_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    content = {"a": 1, "b": {"x": True}}
    write_config(rel, content)
    # ensure file exists
    assert os.path.exists(path)

    # also ensure YAML content on disk is valid
    with open(path, "r", encoding="utf-8") as f:
        data_on_disk = yaml.safe_load(f)
    assert data_on_disk == content

    # read via service
    loaded = read_config(rel)
    assert loaded == content


def test_write_and_read_json_config():
    rel = "profiles/sample.json"
    path = os.path.join(settings.CONFIG_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    content = {"name": "demo", "list": [1, 2, 3]}
    write_config(rel, content)

    with open(path, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk == content

    loaded = read_config(rel)
    assert loaded == content


def test_list_config_folders_empty_and_nonempty(tmp_path, monkeypatch):
    """
    Ensure the test does not depend on prior tests by isolating CONFIG_DIR.
    First assert empty list, then create envs/profiles and assert sorted list.
    """
    # Point CONFIG_DIR to a fresh temporary folder
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path), raising=False)

    # Initially empty -> []
    folders = list_config_folders()
    assert folders == []

    # Create folders under the isolated CONFIG_DIR
    os.makedirs(os.path.join(settings.CONFIG_DIR, "envs"), exist_ok=True)
    os.makedirs(os.path.join(settings.CONFIG_DIR, "profiles"), exist_ok=True)

    folders = list_config_folders()
    # Expect sorted order
    assert folders == ["envs", "profiles"]


def test_read_unsupported_extension_raises():
    rel = "bad.ext"
    path = os.path.join(settings.CONFIG_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("whatever")
    try:
        read_config(rel)
        assert False, "read_config should have raised for unsupported extension"
    except ValueError as e:
        assert "Unsupported config format" in str(e)
