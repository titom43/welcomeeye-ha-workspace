from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import logging
from .const import CONF_NAME, CONF_DEVICE_HOST, CONF_AUTH_ACCOUNT
from .coordinator import get_runtime

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = get_runtime(hass, entry.entry_id)
    entities = []
    
    _LOGGER.debug("Setting up buttons for entry %s (data: %s)", entry.entry_id, entry.data)
    
    # Local unlock buttons
    if entry.data.get(CONF_DEVICE_HOST):
        _LOGGER.debug("Adding local unlock buttons")
        entities.append(WelcomeEyeOpenLockButton(entry, runtime, lock_number=1, suffix="gache", name="Open Latch", icon="mdi:door-open"))
        entities.append(WelcomeEyeOpenLockButton(entry, runtime, lock_number=2, suffix="portail", name="Open Gate", icon="mdi:gate-open"))
    
    # Cloud refresh button - always add it if any setup is present to be safe
    _LOGGER.debug("Adding refresh button")
    entities.append(WelcomeEyeRefreshButton(entry, runtime))
        
    async_add_entities(entities)


class WelcomeEyeRefreshButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "refresh_events"
    _attr_icon = "mdi:refresh"

    def __init__(self, entry: ConfigEntry, runtime) -> None:
        self._entry = entry
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = {
            "identifiers": {("welcomeeye", entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "WelcomeEye"),
            "manufacturer": "WelcomeEye",
            "model": "Connect 3",
        }

    async def async_press(self) -> None:
        await self._runtime.async_refresh()


class WelcomeEyeOpenLockButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime, *, lock_number: int, suffix: str, name: str, icon: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._lock_number = lock_number
        self._attr_translation_key = "open_latch" if lock_number == 1 else "open_gate"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = {
            "identifiers": {("welcomeeye", entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "WelcomeEye"),
            "manufacturer": "WelcomeEye",
            "model": "Connect 3",
        }

    async def async_press(self) -> None:
        await self._runtime.async_open_door(lock_number=self._lock_number)
