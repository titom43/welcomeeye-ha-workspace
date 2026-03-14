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


def _md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _encode_device_password(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) >= 64:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _build_login_xml(config: dict[str, Any]) -> str:
    client_id = config.get("client_id", "003-4123-09f95ff624058e33")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        "<flag>tdkcloud</flag>"
        "<version>v1.13</version>"
        "<command>login</command>"
        "<seq>0</seq>"
        "<session></session>"
        "<user-data></user-data>"
        "<client>"
        f"<id>{client_id}</id>"
        "<type>3</type>"
        "<oem>G0123,A0058,G0058</oem>"
        "<app>4123</app>"
        "</client>"
        "</header>"
        "<content>"
        f"<account>{config.get(CONF_AUTH_ACCOUNT, '')}</account>"
        f"<password>{config.get(CONF_AUTH_PASSWORD, '')}</password>"
        f"<auth-type>{config.get(CONF_AUTH_TYPE, 0)}</auth-type>"
        f"<auth-code>{config.get(CONF_AUTH_CODE, '')}</auth-code>"
        f"<ip-region-id>{config.get(CONF_IP_REGION_ID, 0)}</ip-region-id>"
        "</content>"
        "</envelope>"
    )


def _build_alarm_login_xml(
    config: dict[str, Any],
    session_id: str,
    account_id: str,
    auth_server_host: str,
    auth_token: str,
) -> str:
    client_id = config.get("client_id", "003-4123-09f95ff624058e33")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        '<content class="com.quvii.qvweb.Alarm.bean.request.AlarmLoginReqContent">'
        "<account>"
        f"<authserver>{auth_server_host}</authserver>"
        f"<id>{account_id}</id>"
        "</account>"
        "<client>"
        "<appid>4123</appid>"
        f"<id>{client_id}</id>"
        "<notifylang>French</notifylang>"
        "<oemid>ha</oemid>"
        "<timezone>GMT+01:00</timezone>"
        f"<token>{config.get(CONF_AUTH_CODE, auth_token)}</token>"
        "<tokentype>1</tokentype>"
        "<type>3</type>"
        "</client>"
        "</content>"
        "<header>"
        "<command>client-login</command>"
        "<flag>tdkcloud</flag>"
        "<seq>0</seq>"
        f"<session>{session_id}</session>"
        "</header>"
        "</envelope>"
    )


def _build_alarm_list_xml(config: dict[str, Any], session_id: str, page_num: int = 0, page_line_num: int = 15, max_id: str = "0") -> str:
    uid = config.get(CONF_AUTH_CODE, "")
    devid_xml = f"<devid><id>{uid}</id></devid>" if uid else "<devid><id></id></devid>"
    
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        '<content class="com.quvii.qvweb.Alarm.bean.request.AlarmListQueryReqContent">'
        "<filter>"
        f"{devid_xml}"
        "<event><type></type></event>"
        "<peroid/>"
        "</filter>"
        f"<maxid>{max_id}</maxid>"
        f"<pagelinenum>{page_line_num}</pagelinenum>"
        f"<pageno>{page_num}</pageno>"
        "</content>"
        "<header>"
        "<command>client-query-recordlist</command>"
        "<flag>tdkcloud</flag>"
        "<seq>0</seq>"
        f"<session>{session_id}</session>"
        "</header>"
        "</envelope>"
    )


def _candidate_alarm_bases(auth_base_url: str) -> list[str]:
    import re
    parsed = urlparse(auth_base_url.rstrip('/'))
    host = parsed.hostname or ""
    m = re.match(r"^(shi-)(\d+)(-sec\.qvcloud\.net)$", host)
    if not m:
        return []
    n = int(m.group(2))
    prefix = m.group(1)
    suffix = m.group(3)
    offsets = [0, 1, -1, 2, -2, 3, -3]
    out: list[str] = []
    for off in offsets:
        cand_n = n + off
        if cand_n <= 0:
            continue
        out.append(f"{parsed.scheme}://{prefix}{cand_n}{suffix}:4443")
    return out


def _build_open_door_xml(
    config: dict[str, Any],
    *,
    door: int | None = None,
    lock_number: int | None = None,
) -> str:
    door_value = door if door is not None else config.get(CONF_DOOR, 1)
    lock_value = lock_number if lock_number is not None else config.get(CONF_LOCK_NUMBER, 1)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        f"<security>{config.get(CONF_SECURITY, 'username')}</security>"
        f"<username>{config.get(CONF_USERNAME, 'adminapp2')}</username>"
        f"<password>{config.get(CONF_DEVICE_PASSWORD, '')}</password>"
        "</header>"
        "<body>"
        "<command>set.device.opendoor</command>"
        "<content>"
        f"<door>{door_value}</door>"
        f"<locknumber>{lock_value}</locknumber>"
        f"<password>{config.get(CONF_OPEN_PASSWORD, '')}</password>"
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
    door_value = door if door is not None else config.get(CONF_DOOR, 1)
    lock_value = lock_number if lock_number is not None else config.get(CONF_LOCK_NUMBER, 1)
    header_password = _encode_device_password(config.get(CONF_DEVICE_PASSWORD) or config.get(CONF_OPEN_PASSWORD, ""))
    open_password = _encode_device_password(config.get(CONF_OPEN_PASSWORD) or config.get(CONF_DEVICE_PASSWORD, ""))
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


class WelcomeEyeClient:
    def __init__(self, session: ClientSession, config: dict[str, Any]) -> None:
        self._session = session
        self._config = config
        self._cookies: dict[str, str] = {}
        self._auth_session_id: str | None = None
        self._alarm_session_id: str | None = None
        self._account_id: str | None = None
        self._auth_token: str | None = None
        self._dynamic_auth_base: str | None = None
        self._dynamic_alarm_base: str | None = None
        self._auth_server_host: str | None = None

    @property
    def _ssl(self) -> bool:
        return self._config.get(CONF_VERIFY_SSL, False)

    @property
    def _cgi_base(self) -> str:
        scheme = self._config.get(CONF_SCHEME, "https")
        host = self._config.get(CONF_DEVICE_HOST, "127.0.0.1")
        port = self._config.get(CONF_CGI_PORT, 443)
        return f"{scheme}://{host}:{port}"

    def _auth_base(self) -> str | None:
        if self._dynamic_auth_base:
            return self._dynamic_auth_base
        raw = self._config.get(CONF_AUTH_BASE_URL) or ""
        if not raw:
            return None
        return raw.rstrip("/")

    def _alarm_base(self) -> str | None:
        if self._dynamic_alarm_base:
            return self._dynamic_alarm_base
        explicit = (self._config.get(CONF_ALARM_BASE_URL) or "").strip()
        if explicit:
            return explicit.rstrip("/")
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
        local_xml_payload = _build_local_open_door_xml(self._config, door=door, lock_number=lock_number)
        try:
            local = await self._request("POST", url, data=local_xml_payload, headers=headers, timeout=12)
            local_body = await local.text()
            local_error = _parse_cgi_error(local_body)
            if local.status == 200 and local_error == "0":
                return {"ok": True, "http_status": local.status, "cgi_error": local_error, "method": "local_xml"}
        except Exception as exc:
            _LOGGER.debug("Local XML open_door failed: %s", exc)
        return {"ok": False, "method": "failed"}

    async def login_auth(self) -> bool:
        mode = self._config.get(CONF_AUTH_MODE, "user")
        account = self._config.get(CONF_AUTH_ACCOUNT)
        password = self._config.get(CONF_AUTH_PASSWORD)
        if not account or not password:
            return False

        # SHA256 Hashing
        if len(password) != 64:
            password = hashlib.sha256(password.encode("utf-8")).hexdigest()

        temp_config = dict(self._config)
        temp_config[CONF_AUTH_PASSWORD] = password

        bases_to_try = []
        if self._dynamic_auth_base: bases_to_try.append(self._dynamic_auth_base)
        if self._auth_base(): bases_to_try.append(self._auth_base())
        
        seeds = [
            "https://shi-19-sec.qvcloud.net",
            "https://shi-19-sec.qvcloud.net:4443",
            "https://shi-27-sec.qvcloud.net",
            "https://api-sec.qvcloud.net",
        ]
        for seed in seeds:
            if seed not in bases_to_try: bases_to_try.append(seed)

        path = UP_PATH_BY_MODE.get(mode, "/auth/user;jus_duplex=up")
        payload = _build_login_xml(temp_config)
        headers = {
            "Content-Type": "application/xml;charset=utf-8",
            "Accept": "*/*",
            "User-Agent": "okhttp/3.12.13",
            "Accept-Encoding": "gzip",
            "Accept-Language": "fr-FR",
            "Connection": "Keep-Alive",
        }

        for base in bases_to_try:
            url = f"{base.rstrip('/')}{path}"
            try:
                resp = await self._request("POST", url, data=payload, headers=headers, timeout=10)
                body = await resp.text()
                if resp.status != 200: continue
                root = ET.fromstring(body)
                res = root.findtext("./header/result")
                if res != "0":
                    _LOGGER.info("Cloud login rejected by %s (Error %s)", base, res)
                    continue
                self._cookies.clear()
                for cookie in resp.cookies.values(): self._cookies[cookie.key] = cookie.value
                self._auth_session_id = root.findtext("./header/session/id") or root.findtext("./header/session")
                content = root.find("./content")
                if content is not None:
                    self._account_id = (content.findtext("account-id") or "").strip()
                    self._auth_token = (content.findtext("token") or "").strip()
                self._dynamic_auth_base = base
                self._auth_server_host = urlparse(base).hostname
                _LOGGER.info("Successfully logged in to WelcomeEye Cloud via %s", base)
                return True
            except Exception: continue
        return False

    async def login_alarm(self) -> bool:
        auth_base = self._auth_base()
        if not auth_base or not self._auth_session_id or not self._account_id:
            return False
        candidates = []
        if self._alarm_base(): candidates.append(self._alarm_base())
        candidates.extend(_candidate_alarm_bases(auth_base))
        auth_server_host = self._auth_server_host or urlparse(auth_base).hostname or ""
        headers = {
            "Content-Type": "application/xml;charset=utf-8",
            "Accept": "*/*",
            "User-Agent": "okhttp/3.12.13",
            "Accept-Encoding": "gzip",
            "Accept-Language": "fr-FR",
            "Connection": "Keep-Alive",
        }
        if self._cookies: headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        for candidate in candidates:
            url = candidate.rstrip("/")
            if "/UserAlarm" not in url: url = f"{url}/UserAlarm"
            payload = _build_alarm_login_xml(self._config, self._auth_session_id, self._account_id, auth_server_host, self._auth_token or "")
            try:
                resp = await self._request("POST", url, data=payload, headers=headers, timeout=10)
                body = await resp.text()
                if resp.status == 200:
                    root = ET.fromstring(body)
                    if root.findtext("./header/result") == "0":
                        self._alarm_session_id = root.findtext("./header/session/id") or root.findtext("./header/session")
                        self._dynamic_alarm_base = candidate
                        return True
            except Exception: continue
        return False

    async def query_alarm_list(self, *, page_num: int = 0, page_line_num: int = 15, max_id: str = "0") -> list[dict[str, Any]]:
        base = self._dynamic_alarm_base or self._alarm_base()
        if not base: return []
        url = base.rstrip("/")
        if "/UserAlarm" not in url: url = f"{url}/UserAlarm"
        headers = {
            "Content-Type": "application/xml;charset=utf-8",
            "Accept": "*/*",
            "User-Agent": "okhttp/3.12.13",
            "Accept-Encoding": "gzip",
            "Accept-Language": "fr-FR",
            "Connection": "Keep-Alive",
        }
        if self._cookies: headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        session_id = self._alarm_session_id or self._auth_session_id or ""
        payload = _build_alarm_list_xml(self._config, session_id, page_num=page_num, page_line_num=page_line_num, max_id=max_id)
        try:
            resp = await self._request("POST", url, data=payload, headers=headers, timeout=15)
            body = await resp.text()
            if resp.status != 200: return []
            root = ET.fromstring(body)
            if root.findtext("./header/result") not in (None, "", "0"): return []
            items = []
            for node in root.findall(".//record/data") or root.findall(".//record/alarmList/data"):
                items.append({
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
                })
            return items
        except Exception: return []
