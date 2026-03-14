from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AUTH_MODES,
    CONF_ALARM_BASE_URL,
    CONF_AUTH_ACCOUNT,
    CONF_AUTH_BASE_URL,
    CONF_AUTH_CODE,
    CONF_AUTH_MODE,
    CONF_AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_CGI_PORT,
    CONF_DATA_ENCODE_KEY,
    CONF_DEVICE_HOST,
    CONF_DEVICE_PASSWORD,
    CONF_DOOR,
    CONF_LOCK_NUMBER,
    CONF_ENABLE_DOWNCHANNEL,
    CONF_HS_DEVICE,
    CONF_IP_REGION_ID,
    CONF_NAME,
    CONF_OPEN_PASSWORD,
    CONF_READ_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_SCHEME,
    CONF_SECURITY,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_AUTH_MODE,
    DEFAULT_AUTH_TYPE,
    DEFAULT_CGI_PORT,
    DEFAULT_DOOR,
    DEFAULT_LOCK_NUMBER,
    DEFAULT_ENABLE_DOWNCHANNEL,
    DEFAULT_IP_REGION_ID,
    DEFAULT_NAME,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCHEME,
    DEFAULT_SECURITY,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_DEVICE_HOST, default=defaults.get(CONF_DEVICE_HOST, "")): str,
            vol.Required(CONF_DEVICE_PASSWORD, default=defaults.get(CONF_DEVICE_PASSWORD, "")): str,
            vol.Optional(CONF_AUTH_ACCOUNT, default=defaults.get(CONF_AUTH_ACCOUNT, "")): str,
            vol.Optional(CONF_AUTH_PASSWORD, default=defaults.get(CONF_AUTH_PASSWORD, "")): str,
            vol.Optional(CONF_AUTH_CODE, default=defaults.get(CONF_AUTH_CODE, "")): str, # CID / Intercom ID
            vol.Required(CONF_POLL_INTERVAL_MIN, default=defaults.get(CONF_POLL_INTERVAL_MIN, 5)): int,
        }
    )


def _validate(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    
    # Fill in technical defaults if not present (internal use)
    data.setdefault(CONF_CGI_PORT, DEFAULT_CGI_PORT)
    data.setdefault(CONF_SCHEME, DEFAULT_SCHEME)
    data.setdefault(CONF_USERNAME, "adminapp2")
    data.setdefault(CONF_SECURITY, DEFAULT_SECURITY)
    data.setdefault(CONF_DOOR, DEFAULT_DOOR)
    data.setdefault(CONF_LOCK_NUMBER, DEFAULT_LOCK_NUMBER)
    data.setdefault(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    data.setdefault(CONF_AUTH_BASE_URL, "https://shi-1-sec.qvcloud.net:4443")
    data.setdefault(CONF_AUTH_MODE, DEFAULT_AUTH_MODE)
    data.setdefault(CONF_AUTH_TYPE, DEFAULT_AUTH_TYPE)
    data.setdefault(CONF_IP_REGION_ID, DEFAULT_IP_REGION_ID)
    data.setdefault(CONF_READ_TIMEOUT, DEFAULT_READ_TIMEOUT)
    data.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    data.setdefault(CONF_HS_DEVICE, True)

    if not data.get(CONF_DEVICE_HOST):
        errors[CONF_DEVICE_HOST] = "required"
    
    # If cloud email is provided, password and CID are recommended
    if data.get(CONF_AUTH_ACCOUNT):
        if not data.get(CONF_AUTH_PASSWORD):
            errors[CONF_AUTH_PASSWORD] = "required"
    return errors


class WelcomeEyeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                await self.async_set_unique_id(f"{user_input[CONF_DEVICE_HOST]}:{user_input[CONF_CGI_PORT]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "WelcomeEyeOptionsFlow":
        return WelcomeEyeOptionsFlow(config_entry)


class WelcomeEyeOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        current = dict(self._config_entry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                new_data = {**self._config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
                return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
