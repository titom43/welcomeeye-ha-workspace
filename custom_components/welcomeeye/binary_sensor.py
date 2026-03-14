from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import CONF_NAME, SIGNAL_EVENT, CONF_AUTH_ACCOUNT
from .coordinator import WelcomeEyeRuntime, get_runtime

# Durée pendant laquelle le capteur de sonnette reste actif après un événement
RING_DURATION = 10


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    if not entry.data.get(CONF_AUTH_ACCOUNT):
        return

    runtime = get_runtime(hass, entry.entry_id)
    async_add_entities([WelcomeEyeDoorbellSensor(entry, runtime)])


class WelcomeEyeDoorbellSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SOUND
    _attr_translation_key = "doorbell"

    def __init__(self, entry: ConfigEntry, runtime: WelcomeEyeRuntime) -> None:
        self._entry = entry
        self._runtime = runtime
        self._is_on = False
        self._attr_unique_id = f"{entry.entry_id}_doorbell"
        self._attr_device_info = {
            "identifiers": {("welcomeeye", entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "WelcomeEye"),
            "manufacturer": "WelcomeEye",
            "model": "Connect 3",
        }
        self._off_timer = None

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_EVENT.format(entry_id=self._entry.entry_id),
                self._handle_runtime_update,
            )
        )

    @callback
    def _handle_runtime_update(self) -> None:
        if not self._runtime.last_event:
            return

        event_type = self._runtime.last_event.get("event_type")
        
        # On active la sonnette si l'événement est de type 'ring'
        if event_type == "ring":
            self._is_on = True
            self.async_write_ha_state()

            if self._off_timer:
                self._off_timer()
            
            @callback
            def _turn_off(_: Any) -> None:
                self._is_on = False
                self._off_timer = None
                self.async_write_ha_state()

            self._off_timer = async_call_later(self.hass, RING_DURATION, _turn_off)
