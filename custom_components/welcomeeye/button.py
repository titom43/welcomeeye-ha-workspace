from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME
from .coordinator import get_runtime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = get_runtime(hass, entry.entry_id)
    async_add_entities(
        [
            WelcomeEyeOpenLockButton(entry, runtime, lock_number=1, suffix="gache", name="Open Latch", icon="mdi:door-open"),
            WelcomeEyeOpenLockButton(entry, runtime, lock_number=2, suffix="portail", name="Open Gate", icon="mdi:gate-open"),
        ]
    )


class WelcomeEyeOpenLockButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime, *, lock_number: int, suffix: str, name: str, icon: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._lock_number = lock_number
        self._attr_name = name
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
