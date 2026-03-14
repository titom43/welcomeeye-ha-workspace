from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from aiohttp import ClientResponse, ClientSession

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
    CONF_HS_DEVICE,
    CONF_IP_REGION_ID,
    CONF_OPEN_PASSWORD,
    CONF_READ_TIMEOUT,
    CONF_SCHEME,
    CONF_SECURITY,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

_LOGGER = logging.getLogger(__name__)

UP_PATH_BY_MODE = {
    "user": "/auth/user;jus_duplex=up",
    "third": "/auth/user;jus_duplex=up",
    "deli": "/auth/user/deli;jus_duplex=up",
    "free": "/auth/nologin;jus_duplex=up",
}
DOWN_PATH_BY_MODE = {
    "user": "/auth/user;jus_duplex=down",
    "third": "/auth/user;jus_duplex=down",
    "deli": "/auth/user/deli;jus_duplex=down",
    "free": "/auth/nologin;jus_duplex=down",
}


def _md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _parse_challenge(www_authenticate: str) -> dict[str, str]:
    value = (www_authenticate or "").strip()
    if value.lower().startswith("digest "):
        value = value[7:].strip()
    out: dict[str, str] = {}
    for part in [p.strip() for p in value.split(",") if p.strip()]:
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        out[key.strip()] = val.strip().strip('"')
    if "realm" in out and "Digest realm" not in out:
        out["Digest realm"] = out["realm"]
    return out


def _build_digest_authorization(
    *,
    username: str,
    password: str,
    data_encode_key: str,
    challenge: dict[str, str],
    is_hs_device: bool,
    uri: str = "/tdkcgi",
    method: str = "POST",
    nc: str = "nc00001",
    cnonce: str = "suiji",
) -> str:
    realm = challenge.get("Digest realm") or challenge.get("realm", "")
    nonce = challenge.get("nonce", "")
    opaque = challenge.get("opaque", "")
    qop = challenge.get("qop", "")
    if not (realm and nonce and opaque and qop):
        raise ValueError("Digest challenge missing realm/nonce/opaque/qop")

    if is_hs_device:
        a1 = f"{username}:{realm}:{password}"
    else:
        a1 = f"{username}:{realm}:{data_encode_key}"

    response = _md5_hex(
        f"{_md5_hex(a1)}:{nonce}:{nc}:{cnonce}:{qop}:{_md5_hex(f'{method}:{uri}')}"
    )
    return (
        f'Digest username="{username}",realm="{realm}",nonce="{nonce}",'
        f'uri="{uri}",algorithm=MD5,response="{response}",opaque="{opaque}",'
        f'qop={qop},nc={nc},cnonce="{cnonce}"'
    )


def _build_open_door_xml(
    config: dict[str, Any],
    *,
    door: int | None = None,
    lock_number: int | None = None,
) -> str:
    door_value = door if door is not None else config[CONF_DOOR]
    lock_value = lock_number if lock_number is not None else config.get(CONF_LOCK_NUMBER, 1)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        f"<security>{config[CONF_SECURITY]}</security>"
        f"<username>{config[CONF_USERNAME]}</username>"
        f"<password>{config[CONF_DEVICE_PASSWORD]}</password>"
        "</header>"
        "<body>"
        "<command>set.device.opendoor</command>"
        "<content>"
        f"<door>{door_value}</door>"
        f"<locknumber>{lock_value}</locknumber>"
        f"<password>{config[CONF_OPEN_PASSWORD]}</password>"
        "</content>"
        "</body>"
        "</envelope>"
    )


def _build_local_open_door_xml(
    config: dict[str, Any],
    *,
    door: int | None = None,
    lock_number: int | None = None,
) -> str:
    door_value = door if door is not None else config[CONF_DOOR]
    lock_value = lock_number if lock_number is not None else config.get(CONF_LOCK_NUMBER, 1)
    header_password = config.get(CONF_DEVICE_PASSWORD) or config.get(CONF_OPEN_PASSWORD, "")
    open_password = config.get(CONF_OPEN_PASSWORD) or header_password
    username = config.get(CONF_USERNAME) or "adminapp2"
    security = config.get(CONF_SECURITY, "username")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        f"<security>{security}</security>"
        f"<username>{username}</username>"
        f"<password>{header_password}</password>"
        "<passwordencode>1</passwordencode>"
        "</header>"
        "<body>"
        "<command>set.device.opendoor</command>"
        "<content>"
        f"<door>{door_value}</door>"
        f"<locknumber>{lock_value}</locknumber>"
        f"<password>{open_password}</password>"
        "</content>"
        "</body>"
        "</envelope>"
    )


def _parse_cgi_error(xml_body: str) -> str | None:
    try:
        root = ET.fromstring(xml_body)
    except Exception:
        return None
    err = root.findtext("./body/error")
    if err is None:
        return None
    return err.strip()


def _build_login_xml(config: dict[str, Any]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        "<flag>tdkcloud</flag>"
        "<version></version>"
        "<command>login</command>"
        "<seq>0</seq>"
        "<session></session>"
        "<user-data></user-data>"
        "<client>"
        "<id>ha-welcomeeye</id>"
        "<type>0</type>"
        "<oem>ha</oem>"
        "<app>0</app>"
        "</client>"
        "</header>"
        "<content>"
        f"<account>{config[CONF_AUTH_ACCOUNT]}</account>"
        f"<password>{config[CONF_AUTH_PASSWORD]}</password>"
        f"<auth-type>{config[CONF_AUTH_TYPE]}</auth-type>"
        f"<auth-code>{config[CONF_AUTH_CODE]}</auth-code>"
        f"<ip-region-id>{config[CONF_IP_REGION_ID]}</ip-region-id>"
        "</content>"
        "</envelope>"
    )


class WelcomeEyeClient:
    def __init__(self, session: ClientSession, config: dict[str, Any]) -> None:
        self._session = session
        self._config = config
        self._cookies: dict[str, str] = {}
        self._auth_session_id: str | None = None

    @property
    def _ssl(self) -> bool:
        return self._config[CONF_VERIFY_SSL]

    @property
    def _cgi_base(self) -> str:
        scheme = self._config[CONF_SCHEME]
        host = self._config[CONF_DEVICE_HOST]
        port = self._config[CONF_CGI_PORT]
        return f"{scheme}://{host}:{port}"

    def _auth_base(self) -> str | None:
        raw = self._config.get(CONF_AUTH_BASE_URL) or ""
        if not raw:
            return None
        parsed = urlparse(raw)
        if not parsed.scheme:
            return None
        return raw.rstrip("/")

    def _alarm_base(self) -> str | None:
        explicit = (self._config.get(CONF_ALARM_BASE_URL) or "").strip()
        if explicit:
            return explicit.rstrip("/")

        auth_base = self._auth_base()
        if not auth_base:
            return None

        parsed = urlparse(auth_base)
        if not parsed.scheme or not parsed.hostname:
            return None

        host = parsed.hostname
        host_match = re.match(r"^(shi-)(\d+)(-sec\.qvcloud\.net)$", host)
        if host_match:
            host = f"{host_match.group(1)}{int(host_match.group(2)) + 1}{host_match.group(3)}"
            return f"{parsed.scheme}://{host}:4443/UserAlarm"

        return None

    async def _request(
        self,
        method: str,
        url: str,
        *,
        data: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ClientResponse:
        kwargs: dict[str, Any] = {"ssl": self._ssl}
        if timeout is not None:
            kwargs["timeout"] = timeout
        return await self._session.request(method, url, data=data, headers=headers, **kwargs)

    async def open_door(self, door: int | None = None, lock_number: int | None = None) -> dict[str, Any]:
        path = "/tdkcgi"
        url = f"{self._cgi_base}{path}"
        headers = {"Content-Type": "application/xml;charset=utf-8", "Accept": "*/*"}

        # Preferred local/LAN path: XML auth in the envelope header, no HTTP digest.
        local_xml_payload = _build_local_open_door_xml(
            self._config,
            door=door,
            lock_number=lock_number,
        )
        local = await self._request("POST", url, data=local_xml_payload, headers=headers, timeout=12)
        local_body = await local.text()
        local_error = _parse_cgi_error(local_body)
        if local.status == 200 and local_error == "0":
            return {
                "ok": True,
                "http_status": local.status,
                "cgi_error": local_error,
                "response": local_body[:4000],
                "method": "local_xml",
            }
        if local_error not in {"401", None, ""}:
            return {
                "ok": False,
                "http_status": local.status,
                "cgi_error": local_error,
                "response": local_body[:4000],
                "method": "local_xml",
            }

        # Fallback for older digest-based setups kept for compatibility.
        xml_payload = _build_open_door_xml(self._config, door=door, lock_number=lock_number)
        first = await self._request("POST", url, data=xml_payload, headers=headers, timeout=12)
        first_body = await first.text()
        first_error = _parse_cgi_error(first_body)
        if first.status != 401:
            return {
                "ok": first.status == 200 and first_error == "0",
                "http_status": first.status,
                "cgi_error": first_error,
                "response": first_body[:4000],
                "method": "digest_fallback",
            }

        challenge = _parse_challenge(first.headers.get("WWW-Authenticate", ""))
        auth_header = _build_digest_authorization(
            username=self._config[CONF_USERNAME],
            password=self._config[CONF_DEVICE_PASSWORD],
            data_encode_key=self._config[CONF_DATA_ENCODE_KEY],
            challenge=challenge,
            is_hs_device=self._config[CONF_HS_DEVICE],
            uri=path,
        )
        second_headers = dict(headers)
        second_headers["Authorization"] = auth_header
        second = await self._request("POST", url, data=xml_payload, headers=second_headers, timeout=12)
        second_body = await second.text()
        error = _parse_cgi_error(second_body)
        return {
            "ok": second.status == 200 and error == "0",
            "http_status": second.status,
            "cgi_error": error,
            "response": second_body[:4000],
            "method": "digest_fallback",
        }

    async def login_auth(self) -> bool:
        base = self._auth_base()
        mode = self._config.get(CONF_AUTH_MODE)
        if not base or mode not in AUTH_MODES:
            return False
        if mode != "free" and (
            not self._config.get(CONF_AUTH_ACCOUNT) or not self._config.get(CONF_AUTH_PASSWORD)
        ):
            return False

        path = UP_PATH_BY_MODE[mode]
        url = f"{base}{path}"
        payload = _build_login_xml(self._config)
        headers = {"Content-Type": "application/xml;charset=utf-8", "Accept": "*/*"}
        resp = await self._request("POST", url, data=payload, headers=headers, timeout=15)
        body = await resp.text()
        if resp.status != 200:
            _LOGGER.warning("Auth login failed status=%s body=%s", resp.status, body[:300])
            return False

        self._cookies.clear()
        for cookie in resp.cookies.values():
            self._cookies[cookie.key] = cookie.value
        self._auth_session_id = self._parse_auth_session_id(body)
        return True

    def _parse_auth_session_id(self, body: str) -> str | None:
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return None
        session_id = root.findtext("./header/session/id")
        if session_id:
            return session_id.strip()
        session_text = root.findtext("./header/session")
        if session_text:
            return session_text.strip()
        return None

    def _build_alarm_list_xml(self, *, page_num: int = 0, page_line_num: int = 15, max_id: str = "") -> str:
        session_xml = f"<session>{self._auth_session_id}</session>" if self._auth_session_id else "<session></session>"
        filter_xml = ""
        configured_device_id = self._config.get("device_uid") or self._config.get("device_cid")
        if configured_device_id:
            filter_xml = (
                "<filter>"
                "<devid>"
                f"<id>{configured_device_id}</id>"
                "</devid>"
                "</filter>"
            )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<envelope>"
            "<header>"
            "<flag>tdkcloud</flag>"
            f"{session_xml}"
            "<command>client-query-recordlist</command>"
            "<seq>0</seq>"
            "</header>"
            "<content>"
            f"<maxid>{max_id}</maxid>"
            f"<pageno>{page_num}</pageno>"
            f"<pagelinenum>{page_line_num}</pagelinenum>"
            f"{filter_xml}"
            "</content>"
            "</envelope>"
        )

    async def query_alarm_list(self, *, page_num: int = 0, page_line_num: int = 15, max_id: str = "") -> list[dict[str, Any]]:
        base = self._alarm_base()
        if not base:
            return []
        headers = {"Content-Type": "application/xml;charset=utf-8", "Accept": "*/*"}
        if self._cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        payload = self._build_alarm_list_xml(page_num=page_num, page_line_num=page_line_num, max_id=max_id)
        resp = await self._request("POST", base, data=payload, headers=headers, timeout=15)
        body = await resp.text()
        if resp.status != 200:
            _LOGGER.debug("Alarm list query failed status=%s body=%s", resp.status, body[:300])
            return []
        return self._parse_alarm_list_response(body)

    def _parse_alarm_list_response(self, body: str) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []
        result = root.findtext("./header/result")
        if result not in (None, "", "0"):
            return []
        items: list[dict[str, Any]] = []
        for node in root.findall(".//record/alarmList/data"):
            items.append(
                {
                    "id": (node.findtext("id") or "").strip(),
                    "alarmid": (node.findtext("alarmid") or "").strip(),
                    "devid": (node.findtext("devid") or "").strip(),
                    "event": (node.findtext("event") or "").strip(),
                    "alarmstate": (node.findtext("alarmstate") or "").strip(),
                    "alarminfo": (node.findtext("alarminfo") or "").strip(),
                    "alarmsource": (node.findtext("alarmsource") or "").strip(),
                    "alarmsourcename": (node.findtext("alarmsourcename") or "").strip(),
                    "time": (node.findtext("time") or "").strip(),
                    "msgsavetype": (node.findtext("msgsavetype") or "").strip(),
                    "msgstate": (node.findtext("msgstate") or "").strip(),
                }
            )
        return items

    async def poll_downchannel_once(self) -> tuple[int, str]:
        base = self._auth_base()
        mode = self._config.get(CONF_AUTH_MODE)
        if not base or mode not in AUTH_MODES:
            return 0, ""
        path = DOWN_PATH_BY_MODE[mode]
        url = f"{base}{path}"
        headers = {"Accept": "*/*"}
        if self._cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        timeout = self._config.get(CONF_READ_TIMEOUT, 45)
        resp = await self._request("GET", url, headers=headers, timeout=timeout)
        body = await resp.text()
        for cookie in resp.cookies.values():
            self._cookies[cookie.key] = cookie.value
        return resp.status, body
