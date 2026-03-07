from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AUTH_MODES,
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
    CONF_ENABLE_DOWNCHANNEL,
    CONF_HS_DEVICE,
    CONF_IP_REGION_ID,
    CONF_NAME,
    CONF_OPEN_PASSWORD,
    CONF_READ_TIMEOUT,
    CONF_SCHEME,
    CONF_SECURITY,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_AUTH_MODE,
    DEFAULT_AUTH_TYPE,
    DEFAULT_CGI_PORT,
    DEFAULT_DOOR,
    DEFAULT_ENABLE_DOWNCHANNEL,
    DEFAULT_IP_REGION_ID,
    DEFAULT_NAME,
    DEFAULT_READ_TIMEOUT,
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
            vol.Required(CONF_CGI_PORT, default=defaults.get(CONF_CGI_PORT, DEFAULT_CGI_PORT)): int,
            vol.Required(CONF_SCHEME, default=defaults.get(CONF_SCHEME, DEFAULT_SCHEME)): vol.In(
                ["http", "https"]
            ),
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_DEVICE_PASSWORD, default=defaults.get(CONF_DEVICE_PASSWORD, "")): str,
            vol.Optional(CONF_DATA_ENCODE_KEY, default=defaults.get(CONF_DATA_ENCODE_KEY, "")): str,
            vol.Required(CONF_HS_DEVICE, default=defaults.get(CONF_HS_DEVICE, False)): bool,
            vol.Required(CONF_SECURITY, default=defaults.get(CONF_SECURITY, DEFAULT_SECURITY)): str,
            vol.Required(CONF_DOOR, default=defaults.get(CONF_DOOR, DEFAULT_DOOR)): int,
            vol.Optional(CONF_OPEN_PASSWORD, default=defaults.get(CONF_OPEN_PASSWORD, "")): str,
            vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)): bool,
            vol.Required(
                CONF_ENABLE_DOWNCHANNEL,
                default=defaults.get(CONF_ENABLE_DOWNCHANNEL, DEFAULT_ENABLE_DOWNCHANNEL),
            ): bool,
            vol.Optional(CONF_AUTH_BASE_URL, default=defaults.get(CONF_AUTH_BASE_URL, "")): str,
            vol.Required(CONF_AUTH_MODE, default=defaults.get(CONF_AUTH_MODE, DEFAULT_AUTH_MODE)): vol.In(
                AUTH_MODES
            ),
            vol.Optional(CONF_AUTH_ACCOUNT, default=defaults.get(CONF_AUTH_ACCOUNT, "")): str,
            vol.Optional(CONF_AUTH_PASSWORD, default=defaults.get(CONF_AUTH_PASSWORD, "")): str,
            vol.Required(CONF_AUTH_TYPE, default=defaults.get(CONF_AUTH_TYPE, DEFAULT_AUTH_TYPE)): int,
            vol.Optional(CONF_AUTH_CODE, default=defaults.get(CONF_AUTH_CODE, "")): str,
            vol.Required(CONF_IP_REGION_ID, default=defaults.get(CONF_IP_REGION_ID, DEFAULT_IP_REGION_ID)): int,
            vol.Required(CONF_READ_TIMEOUT, default=defaults.get(CONF_READ_TIMEOUT, DEFAULT_READ_TIMEOUT)): int,
        }
    )


def _validate(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data[CONF_CGI_PORT] <= 0:
        errors[CONF_CGI_PORT] = "invalid_port"
    if data[CONF_DOOR] <= 0:
        errors[CONF_DOOR] = "invalid_door"
    if data[CONF_READ_TIMEOUT] < 5:
        errors[CONF_READ_TIMEOUT] = "invalid_timeout"
    if data[CONF_ENABLE_DOWNCHANNEL]:
        if not data.get(CONF_AUTH_BASE_URL):
            errors[CONF_AUTH_BASE_URL] = "required"
        if data.get(CONF_AUTH_MODE) != "free" and (
            not data.get(CONF_AUTH_ACCOUNT) or not data.get(CONF_AUTH_PASSWORD)
        ):
            errors["base"] = "auth_credentials_required"
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
                self.hass.config_entries.async_update_entry(self._config_entry, data=user_input)
                return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
