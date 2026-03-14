from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, CONF_DEVICE_HOST
from .coordinator import get_runtime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    if not entry.data.get(CONF_DEVICE_HOST):
        return

    runtime = get_runtime(hass, entry.entry_id)
    async_add_entities(
        [
            WelcomeEyeLock(entry, runtime, lock_number=1, suffix="latch", name="Latch", icon="mdi:door-open"),
            WelcomeEyeLock(entry, runtime, lock_number=2, suffix="gate", name="Gate", icon="mdi:gate-open"),
        ]
    )


class WelcomeEyeLock(LockEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime, *, lock_number: int, suffix: str, name: str, icon: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._lock_number = lock_number
        self._attr_translation_key = "open_latch" if lock_number == 1 else "open_gate"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_lock_{suffix}"
        self._attr_device_info = {
            "identifiers": {("welcomeeye", entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "WelcomeEye"),
            "manufacturer": "WelcomeEye",
            "model": "Connect 3",
        }
        self._is_locked = True
        self._unlock_task: asyncio.Task | None = None

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self._runtime.async_open_door(lock_number=self._lock_number)
        
        # Temporary unlock state to simulate the impulse
        self._is_locked = False
        self.async_write_ha_state()

        if self._unlock_task:
            self._unlock_task.cancel()
            
        self._unlock_task = self.hass.async_create_task(self._async_auto_relock())

    async def _async_auto_relock(self) -> None:
        """Automatically re-lock after a short delay."""
        try:
            await asyncio.sleep(2)
            self._is_locked = True
            self.async_write_ha_state()
        except asyncio.CancelledError:
            pass
        finally:
            self._unlock_task = None

    async def async_lock(self, **kwargs: Any) -> None:
        """Locking is not supported by hardware, just update state."""
        self._is_locked = True
        self.async_write_ha_state()
