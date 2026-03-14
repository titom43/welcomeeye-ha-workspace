from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import WelcomeEyeClient
from .const import CONF_ENABLE_DOWNCHANNEL, DATA_RUNTIME, SIGNAL_EVENT
from .parser import parse_downchannel_payload

_LOGGER = logging.getLogger(__name__)


class WelcomeEyeRuntime:
    def __init__(self, hass: HomeAssistant, entry_id: str, client: WelcomeEyeClient, config: dict[str, Any]) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.client = client
        self.config = config
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.last_event: dict[str, Any] | None = None
        self.last_open_result: dict[str, Any] | None = None

    async def async_start(self) -> None:
        if not self.config.get(CONF_ENABLE_DOWNCHANNEL):
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = self.hass.async_create_task(self._run_downchannel(), name=f"welcomeeye_down_{self.entry_id}")

    async def async_stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def async_open_door(self, door: int | None = None, lock_number: int | None = None) -> dict[str, Any]:
        result = await self.client.open_door(door=door, lock_number=lock_number)
        self.last_open_result = result
        if result.get("ok"):
            self.last_event = {
                "event_type": "unlock",
                "unlock_method": "app_or_remote",
                "badge_id": None,
                "command": "set.device.opendoor",
                "lock_number": lock_number or self.config.get("lock_number", 1),
                "raw": result.get("response", ""),
            }
        async_dispatcher_send(self.hass, SIGNAL_EVENT.format(entry_id=self.entry_id))
        return result

    async def _run_downchannel(self) -> None:
        while not self._stop.is_set():
            try:
                if not await self.client.login_auth():
                    await asyncio.sleep(3)
                    continue
                while not self._stop.is_set():
                    status, body = await self.client.poll_downchannel_once()
                    if status == 200 and body.strip():
                        self.last_event = parse_downchannel_payload(body)
                        async_dispatcher_send(self.hass, SIGNAL_EVENT.format(entry_id=self.entry_id))
                    elif status in (401, 403, 404):
                        _LOGGER.warning("Down-channel returned %s, re-login required", status)
                        break
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("Down-channel loop error: %s", exc, exc_info=True)
                await asyncio.sleep(2)


def get_runtime(hass: HomeAssistant, entry_id: str) -> WelcomeEyeRuntime:
    return hass.data[DATA_RUNTIME][entry_id]
