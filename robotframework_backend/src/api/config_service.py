import os
import json
from typing import Dict, Any, Tuple, List

import yaml

from src.core.settings import settings


def _resolve_path(rel_path: str) -> Tuple[str, str]:
    base = settings.CONFIG_DIR
    abs_path = os.path.abspath(os.path.join(base, rel_path))
    if not abs_path.startswith(os.path.abspath(base)):
        raise ValueError("Path traversal not allowed")
    ext = os.path.splitext(abs_path)[1].lower()
    return abs_path, ext


# PUBLIC_INTERFACE
def read_config(rel_path: str) -> Dict[str, Any]:
    """Read a YAML or JSON config file from CONFIG_DIR."""
    abs_path, ext = _resolve_path(rel_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Config not found: {rel_path}")
    with open(abs_path, "r", encoding="utf-8") as f:
        text = f.read()
    if ext in [".yaml", ".yml"]:
        return yaml.safe_load(text) or {}
    if ext == ".json":
        return json.loads(text or "{}")
    raise ValueError("Unsupported config format; use .yaml/.yml or .json")


# PUBLIC_INTERFACE
def write_config(rel_path: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """Write a YAML or JSON config file to CONFIG_DIR."""
    abs_path, ext = _resolve_path(rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    if ext in [".yaml", ".yml"]:
        with open(abs_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(content or {}, f, sort_keys=False, allow_unicode=True)
    elif ext == ".json":
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(content or {}, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError("Unsupported config format; use .yaml/.yml or .json")
    return content


# PUBLIC_INTERFACE
def list_config_folders() -> List[str]:
    """List subfolders under CONFIG_DIR (non-recursive)."""
    base = settings.CONFIG_DIR
    try:
        entries = os.listdir(base)
    except FileNotFoundError:
        return []
    folders: List[str] = []
    for e in entries:
        p = os.path.join(base, e)
        if os.path.isdir(p):
            folders.append(e)
    return sorted(folders)
