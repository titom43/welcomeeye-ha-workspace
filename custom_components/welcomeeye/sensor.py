from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, SIGNAL_EVENT
from .coordinator import WelcomeEyeRuntime, get_runtime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = get_runtime(hass, entry.entry_id)
    async_add_entities(
        [
            WelcomeEyeEventTypeSensor(entry, runtime),
            WelcomeEyeUnlockMethodSensor(entry, runtime),
            WelcomeEyeBadgeIdSensor(entry, runtime),
        ]
    )


class _BaseWelcomeEyeSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime: WelcomeEyeRuntime) -> None:
        self._entry = entry
        self._runtime = runtime
        self._remove_dispatcher: Callable[[], None] | None = None
        self._attr_device_info = {
            "identifiers": {("welcomeeye", entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "WelcomeEye"),
            "manufacturer": "WelcomeEye",
            "model": "Connect 3",
        }

    async def async_added_to_hass(self) -> None:
        self._remove_dispatcher = async_dispatcher_connect(
            self.hass,
            SIGNAL_EVENT.format(entry_id=self._entry.entry_id),
            self._handle_runtime_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_dispatcher:
            self._remove_dispatcher()
            self._remove_dispatcher = None

    def _handle_runtime_update(self) -> None:
        self.async_write_ha_state()


class WelcomeEyeEventTypeSensor(_BaseWelcomeEyeSensor):
    _attr_name = "Last Event Type"

    def __init__(self, entry: ConfigEntry, runtime: WelcomeEyeRuntime) -> None:
        super().__init__(entry, runtime)
        self._attr_unique_id = f"{entry.entry_id}_last_event_type"

    @property
    def native_value(self) -> str | None:
        if not self._runtime.last_event:
            return None
        return self._runtime.last_event.get("event_type")

    @property
    def extra_state_attributes(self) -> dict:
        if not self._runtime.last_event:
            return {}
        event = self._runtime.last_event
        return {
            "command": event.get("command"),
            "unlock_method": event.get("unlock_method"),
            "badge_id": event.get("badge_id"),
            "raw": event.get("raw"),
        }


class WelcomeEyeUnlockMethodSensor(_BaseWelcomeEyeSensor):
    _attr_name = "Last Unlock Method"

    def __init__(self, entry: ConfigEntry, runtime: WelcomeEyeRuntime) -> None:
        super().__init__(entry, runtime)
        self._attr_unique_id = f"{entry.entry_id}_last_unlock_method"

    @property
    def native_value(self) -> str | None:
        if not self._runtime.last_event:
            return None
        return self._runtime.last_event.get("unlock_method")


class WelcomeEyeBadgeIdSensor(_BaseWelcomeEyeSensor):
    _attr_name = "Last Badge ID"

    def __init__(self, entry: ConfigEntry, runtime: WelcomeEyeRuntime) -> None:
        super().__init__(entry, runtime)
        self._attr_unique_id = f"{entry.entry_id}_last_badge_id"

    @property
    def native_value(self) -> str | None:
        if not self._runtime.last_event:
            return None
        return self._runtime.last_event.get("badge_id")
