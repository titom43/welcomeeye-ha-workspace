from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import WelcomeEyeClient
from .const import DATA_RUNTIME, SIGNAL_EVENT, CONF_POLL_INTERVAL_MIN, CONF_AUTH_ACCOUNT, CONF_AUTH_PASSWORD
from .parser import parse_alarm_history_item

_LOGGER = logging.getLogger(__name__)


class WelcomeEyeRuntime:
    def __init__(self, hass: HomeAssistant, entry_id: str, client: WelcomeEyeClient, config: dict[str, Any]) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.client = client
        self.config = config
        self._alarm_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._refresh_event = asyncio.Event()
        self.last_event: dict[str, Any] | None = None
        self.last_open_result: dict[str, Any] | None = None
        self._last_alarm_id: str | None = None

    async def async_start(self) -> None:
        if self._alarm_task and not self._alarm_task.done():
            return
        
        # Don't start polling if cloud info is missing
        if not self.config.get(CONF_AUTH_ACCOUNT) or not self.config.get(CONF_AUTH_PASSWORD):
            _LOGGER.info("Cloud Watcher disabled: missing credentials")
            return

        self._stop.clear()
        self._alarm_task = self.hass.async_create_task(self._run_alarm_poll(), name=f"welcomeeye_alarm_{self.entry_id}")

    async def async_stop(self) -> None:
        self._stop.set()
        self._refresh_event.set() # Unblock task if it was waiting
        if self._alarm_task:
            self._alarm_task.cancel()
            try:
                await self._alarm_task
            except asyncio.CancelledError:
                pass
            self._alarm_task = None

    async def async_refresh(self) -> None:
        """Trigger a manual poll."""
        _LOGGER.debug("Manual refresh requested")
        self._refresh_event.set()

    async def async_open_door(self, door: int | None = None, lock_number: int | None = None) -> dict[str, Any]:
        result = await self.client.open_door(door=door, lock_number=lock_number)
        self.last_open_result = result
        if result.get("ok"):
            self.last_event = {
                "event_type": "unlock",
                "event_code": 63,
                "alarm_state": 4,
                "unlock_method": "app_or_remote",
                "badge_id": None,
                "command": "set.device.opendoor",
                "lock_number": lock_number or self.config.get("lock_number", 1),
                "alarm_info": str(lock_number or self.config.get("lock_number", 1)),
                "raw": result.get("response", ""),
            }
        async_dispatcher_send(self.hass, SIGNAL_EVENT.format(entry_id=self.entry_id))
        return result

    async def _run_alarm_poll(self) -> None:
        initialized = False
        _LOGGER.debug("Starting alarm poll loop")
        
        # Initial login attempt
        try:
            if await self.client.login_auth():
                await self.client.login_alarm()
        except Exception as exc:
            _LOGGER.error("Initial cloud login failed: %s", exc)

        while not self._stop.is_set():
            poll_min = self.config.get(CONF_POLL_INTERVAL_MIN, 5)
            wait_seconds = poll_min * 60 if poll_min > 0 else 3600
            
            try:
                _LOGGER.debug("Querying alarm list...")
                items = await self.client.query_alarm_list(page_num=0, page_line_num=15)
                
                if not items:
                    _LOGGER.debug("Alarm query empty, trying re-login")
                    await self.client.login_auth()
                    await self.client.login_alarm()
                    # Si c'est toujours vide après re-login, on attend un peu
                    try:
                        await asyncio.wait_for(self._refresh_event.wait(), timeout=30)
                        self._refresh_event.clear()
                    except asyncio.TimeoutError:
                        pass
                    continue

                latest = items[0]
                latest_id = latest.get("id") or latest.get("alarmid")
                latest_time = latest.get("time")
                
                # Check if this was a manual refresh
                is_manual = self._refresh_event.is_set()
                
                # We detect a change if ID or Time is different
                has_changed = (latest_id != self._last_alarm_id) or (latest_time != self.config.get("_last_time"))
                
                if not initialized:
                    self._last_alarm_id = latest_id
                    self.config["_last_time"] = latest_time
                    initialized = True
                    self.last_event = parse_alarm_history_item(latest)
                    async_dispatcher_send(self.hass, SIGNAL_EVENT.format(entry_id=self.entry_id))
                    _LOGGER.debug("Watcher initialized with ID %s at %s", latest_id, latest_time)
                elif has_changed or is_manual:
                    self._last_alarm_id = latest_id
                    self.config["_last_time"] = latest_time
                    parsed = parse_alarm_history_item(latest)
                    _LOGGER.debug("Event update (manual=%s, changed=%s): %s", is_manual, has_changed, parsed)
                    self.last_event = parsed
                    async_dispatcher_send(self.hass, SIGNAL_EVENT.format(entry_id=self.entry_id))

                self._refresh_event.clear()
                
                # Wait for next poll or manual refresh
                try:
                    if poll_min > 0:
                        _LOGGER.debug("Waiting %s seconds for next poll", wait_seconds)
                        await asyncio.wait_for(self._refresh_event.wait(), timeout=wait_seconds)
                    else:
                        _LOGGER.debug("Waiting for manual refresh (poll_min=0)")
                        await self._refresh_event.wait()
                    
                    self._refresh_event.clear()
                    _LOGGER.debug("Polling triggered by refresh event")
                except asyncio.TimeoutError:
                    pass

            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                _LOGGER.exception("Alarm poll loop error: %s", exc)
                await asyncio.sleep(60)


def get_runtime(hass: HomeAssistant, entry_id: str) -> WelcomeEyeRuntime:
    return hass.data[DATA_RUNTIME][entry_id]
