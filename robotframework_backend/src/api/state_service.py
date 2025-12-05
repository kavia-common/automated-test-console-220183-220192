from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class _StateStore:
    """In-memory state store for UI lock and sync state."""
    locked: bool = False
    owner: Optional[str] = None
    state: Dict[str, Any] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_state = _StateStore()


# PUBLIC_INTERFACE
async def set_ui_lock(locked: bool, owner: Optional[str] = None) -> Dict[str, Any]:
    """Set the UI lock in a thread-safe manner."""
    async with _state.lock:
        _state.locked = locked
        _state.owner = owner
        return {"locked": _state.locked, "owner": _state.owner}


# PUBLIC_INTERFACE
async def sync_state(new_state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge provided state into the store in a thread-safe manner."""
    async with _state.lock:
        _state.state.update(new_state or {})
        return dict(_state.state)


# PUBLIC_INTERFACE
async def get_state() -> Dict[str, Any]:
    """Return a copy of the current state."""
    async with _state.lock:
        return dict(_state.state)


# PUBLIC_INTERFACE
async def get_lock_info() -> Dict[str, Any]:
    """Return current lock information."""
    async with _state.lock:
        return {"locked": _state.locked, "owner": _state.owner}
