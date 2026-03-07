#!/usr/bin/env python3
"""
WelcomeEye auth/down-channel listener.

What it does:
1) Optional login via /auth/...;jus_duplex=up (XML command "login")
2) Keeps session cookies
3) Subscribes to /auth/...;jus_duplex=down in long-poll loop
4) Prints each event as JSON (and optional raw payload)

Use only on devices/accounts you own or are authorized to test.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import re
import ssl
import sys
import time
import xml.etree.ElementTree as et
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


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


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def build_login_xml(
    account: str,
    password: str,
    auth_type: int,
    auth_code: str,
    ip_region_id: int,
    client_id: str,
    client_type: int,
    oem: str,
    app: str,
) -> str:
    # Mirrors the app request shape used by UserAuthRequestHelper.getLoginReq(...)
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
        f"<id>{client_id}</id>"
        f"<type>{client_type}</type>"
        f"<oem>{oem}</oem>"
        f"<app>{app}</app>"
        "</client>"
        "</header>"
        "<content>"
        f"<account>{account}</account>"
        f"<password>{password}</password>"
        f"<auth-type>{auth_type}</auth-type>"
        f"<auth-code>{auth_code}</auth-code>"
        f"<ip-region-id>{ip_region_id}</ip-region-id>"
        "</content>"
        "</envelope>"
    )


def parse_set_cookie(headers: Dict[str, str]) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    raw = headers.get("set-cookie")
    if not raw:
        return cookies
    sc = SimpleCookie()
    sc.load(raw)
    for k, morsel in sc.items():
        cookies[k] = morsel.value
    return cookies


def merge_cookie_header(cookies: Dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def request_once(
    scheme: str,
    host: str,
    port: int,
    path: str,
    method: str,
    body: str,
    headers: Dict[str, str],
    timeout_s: int,
    insecure: bool,
) -> Tuple[int, Dict[str, str], str]:
    conn: http.client.HTTPConnection
    if scheme == "https":
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection(host, port, timeout=timeout_s, context=ctx)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout_s)

    try:
        payload = body.encode("utf-8") if body else None
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw_headers = {k.lower(): v for k, v in resp.getheaders()}
        raw_body = resp.read().decode("utf-8", errors="replace")
        return resp.status, raw_headers, raw_body
    finally:
        conn.close()


def xml_to_dict(node: et.Element) -> Any:
    children = list(node)
    if not children:
        return (node.text or "").strip()
    out: Dict[str, Any] = {}
    for child in children:
        value = xml_to_dict(child)
        if child.tag in out:
            if not isinstance(out[child.tag], list):
                out[child.tag] = [out[child.tag]]
            out[child.tag].append(value)
        else:
            out[child.tag] = value
    return out


def parse_login_result(login_xml: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        root = et.fromstring(login_xml)
    except Exception:
        return None, None

    result = root.findtext("./header/result")
    session_id = root.findtext("./header/session/id")
    try:
        return (int(result) if result is not None else None, session_id)
    except ValueError:
        return None, session_id


def parse_event_payload(payload: str) -> Dict[str, Any]:
    s = payload.strip()
    if not s:
        return {"format": "empty", "data": None}

    if s.startswith("{") or s.startswith("["):
        try:
            data = json.loads(s)
            return {"format": "json", "data": data}
        except Exception:
            return {"format": "text", "data": s}

    if s.startswith("<"):
        try:
            root = et.fromstring(s)
            return {"format": "xml", "data": {root.tag: xml_to_dict(root)}}
        except Exception:
            return {"format": "text", "data": s}

    return {"format": "text", "data": s}


def extract_command(event_data: Any) -> Optional[str]:
    if isinstance(event_data, dict):
        # Most common: envelope -> header -> command
        envelope = event_data.get("envelope")
        if isinstance(envelope, dict):
            header = envelope.get("header")
            if isinstance(header, dict):
                cmd = header.get("command")
                if isinstance(cmd, str) and cmd:
                    return cmd
        for k, v in event_data.items():
            if k == "command" and isinstance(v, str):
                return v
            cmd = extract_command(v)
            if cmd:
                return cmd
    elif isinstance(event_data, list):
        for item in event_data:
            cmd = extract_command(item)
            if cmd:
                return cmd
    return None


CALL_KEYWORDS = (
    "call",
    "ring",
    "doorbell",
    "visitor",
    "intercom",
    "incoming",
    "alarm",
)


def is_call_like(payload: str, command: Optional[str]) -> bool:
    hay = (command or "") + " " + payload
    hay = hay.lower()
    return any(k in hay for k in CALL_KEYWORDS)


def print_event_json(
    status: int,
    payload: str,
    print_raw: bool,
) -> None:
    parsed = parse_event_payload(payload)
    cmd = extract_command(parsed["data"])
    call_like = is_call_like(payload, cmd)
    out = {
        "ts": utc_now_iso(),
        "http_status": status,
        "format": parsed["format"],
        "command": cmd,
        "call_like": call_like,
        "event_class": "call_candidate" if call_like else "other",
        "data": parsed["data"],
    }
    if not print_raw:
        out.pop("data")
    print(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Subscribe to WelcomeEye auth down-channel and print events as JSON."
    )
    p.add_argument("--base-url", required=True, help="e.g. https://auth.example.com:443/")
    p.add_argument("--mode", choices=["user", "third", "deli", "free"], default="user")
    p.add_argument("--account", default="", help="Account for login command")
    p.add_argument("--password", default="", help="Password for login command")
    p.add_argument("--auth-type", type=int, default=0, help="Login auth-type")
    p.add_argument("--auth-code", default="", help="Login auth-code")
    p.add_argument("--ip-region-id", type=int, default=0)
    p.add_argument("--client-id", default="python-listener")
    p.add_argument("--client-type", type=int, default=0)
    p.add_argument("--oem", default="python")
    p.add_argument("--app", default="0")
    p.add_argument(
        "--cookie",
        default="",
        help='Existing cookie string, e.g. "JSESSIONID=...; path=/". If set, login is skipped.',
    )
    p.add_argument("--read-timeout", type=int, default=45, help="Down-channel request timeout in seconds")
    p.add_argument("--retry-delay", type=float, default=1.0, help="Delay before reconnect")
    p.add_argument("--max-events", type=int, default=0, help="Stop after N events (0 = infinite)")
    p.add_argument("--print-raw", action="store_true", help="Include parsed payload data in output JSON")
    p.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    args = p.parse_args()

    parsed = urlparse(args.base_url)
    if parsed.scheme not in ("http", "https"):
        print("base-url must start with http:// or https://", file=sys.stderr)
        return 2

    host = parsed.hostname
    if not host:
        print("base-url host missing", file=sys.stderr)
        return 2
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    up_path = UP_PATH_BY_MODE[args.mode]
    down_path = DOWN_PATH_BY_MODE[args.mode]

    cookies: Dict[str, str] = {}
    if args.cookie:
        sc = SimpleCookie()
        sc.load(args.cookie)
        for k, morsel in sc.items():
            cookies[k] = morsel.value

    if not cookies:
        if args.mode != "free" and (not args.account or not args.password):
            print("account/password required unless --cookie is provided", file=sys.stderr)
            return 2
        login_xml = build_login_xml(
            account=args.account,
            password=args.password,
            auth_type=args.auth_type,
            auth_code=args.auth_code,
            ip_region_id=args.ip_region_id,
            client_id=args.client_id,
            client_type=args.client_type,
            oem=args.oem,
            app=args.app,
        )
        login_headers = {
            "Content-Type": "application/xml;charset=utf-8",
            "Accept": "*/*",
            "Connection": "close",
        }
        status, resp_headers, resp_body = request_once(
            scheme=parsed.scheme,
            host=host,
            port=port,
            path=up_path,
            method="POST",
            body=login_xml,
            headers=login_headers,
            timeout_s=15,
            insecure=args.insecure,
        )
        cookies.update(parse_set_cookie(resp_headers))
        result, session_id = parse_login_result(resp_body)
        print(
            json.dumps(
                {
                    "ts": utc_now_iso(),
                    "phase": "login",
                    "http_status": status,
                    "result": result,
                    "session_id": session_id,
                    "cookies": list(cookies.keys()),
                },
                ensure_ascii=False,
            )
        )
        sys.stdout.flush()
        if status != 200 or (result is not None and result != 0):
            print("login failed, stopping", file=sys.stderr)
            return 1

    event_count = 0
    while True:
        headers = {
            "Accept": "*/*",
            "Connection": "close",
        }
        cookie_header = merge_cookie_header(cookies)
        if cookie_header:
            headers["Cookie"] = cookie_header

        try:
            status, resp_headers, body = request_once(
                scheme=parsed.scheme,
                host=host,
                port=port,
                path=down_path,
                method="GET",
                body="",
                headers=headers,
                timeout_s=args.read_timeout,
                insecure=args.insecure,
            )
        except TimeoutError:
            continue
        except Exception as exc:
            print(json.dumps({"ts": utc_now_iso(), "phase": "down", "error": str(exc)}))
            sys.stdout.flush()
            time.sleep(args.retry_delay)
            continue

        new_cookies = parse_set_cookie(resp_headers)
        if new_cookies:
            cookies.update(new_cookies)

        if status == 200:
            if body.strip():
                print_event_json(status=status, payload=body, print_raw=args.print_raw)
                event_count += 1
        else:
            print(
                json.dumps(
                    {
                        "ts": utc_now_iso(),
                        "phase": "down",
                        "http_status": status,
                        "note": "non-200 response",
                        "body": body[:500],
                    },
                    ensure_ascii=False,
                )
            )
            sys.stdout.flush()

            if status in (401, 403, 404):
                return 1

        if args.max_events > 0 and event_count >= args.max_events:
            return 0

        time.sleep(args.retry_delay)


if __name__ == "__main__":
    raise SystemExit(main())
