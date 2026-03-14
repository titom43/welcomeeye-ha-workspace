#!/usr/bin/env python3
"""
Open WelcomeEye door latch via /tdkcgi with app-like Digest auth.

Authorized testing only.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import ssl
import sys
import xml.etree.ElementTree as et
from typing import Dict, Tuple


def md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def encode_device_password(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) >= 64:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_www_authenticate(header_value: str) -> Dict[str, str]:
    # Accept both "Digest realm=..." and fragments split by commas.
    v = (header_value or "").strip()
    if v.lower().startswith("digest "):
        v = v[7:].strip()
    out: Dict[str, str] = {}
    for part in [p.strip() for p in v.split(",") if p.strip()]:
        if "=" not in part:
            continue
        k, val = part.split("=", 1)
        out[k.strip()] = val.strip().strip('"')
    if "realm" in out and "Digest realm" not in out:
        out["Digest realm"] = out["realm"]
    return out


def build_digest_auth(
    *,
    username: str,
    password: str,
    data_encode_key: str,
    challenge: Dict[str, str],
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
        raise ValueError("Missing realm/nonce/opaque/qop in WWW-Authenticate challenge")

    if is_hs_device:
        a1_raw = f"{username}:{realm}:{password}"
    else:
        a1_raw = f"{username}:{realm}:{data_encode_key}"

    response = md5_hex(
        f"{md5_hex(a1_raw)}:{nonce}:{nc}:{cnonce}:{qop}:{md5_hex(f'{method}:{uri}')}"
    )

    return (
        f'Digest username="{username}",realm="{realm}",nonce="{nonce}",'
        f'uri="{uri}",algorithm=MD5,response="{response}",opaque="{opaque}",'
        f'qop={qop},nc={nc},cnonce="{cnonce}"'
    )


def build_open_door_xml(
    *,
    username: str,
    device_password: str,
    door: int,
    open_password: str,
    security: str,
) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        f"<security>{security}</security>"
        f"<username>{username}</username>"
        f"<password>{device_password}</password>"
        "</header>"
        "<body>"
        "<command>set.device.opendoor</command>"
        "<content>"
        f"<door>{door}</door>"
        f"<password>{open_password}</password>"
        "</content>"
        "</body>"
        "</envelope>"
    )


def request(
    conn: http.client.HTTPConnection,
    *,
    path: str,
    body: str,
    authorization: str = "",
) -> Tuple[int, Dict[str, str], str]:
    headers = {
        "Content-Type": "application/xml;charset=utf-8",
        "Accept": "*/*",
    }
    if authorization:
        headers["Authorization"] = authorization
    conn.request("POST", path, body=body.encode("utf-8"), headers=headers)
    resp = conn.getresponse()
    text = resp.read().decode("utf-8", errors="replace")
    return resp.status, {k: v for k, v in resp.getheaders()}, text


def parse_cgi_error(xml_text: str) -> str:
    try:
        root = et.fromstring(xml_text)
    except Exception:
        return ""
    # Expected path in analyzed app response model:
    # envelope/body/error
    err = root.findtext("./body/error")
    return (err or "").strip()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Open latch with app-like Digest auth and XML command set.device.opendoor"
    )
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--scheme", choices=["http", "https"], default="http")
    p.add_argument("--path", default="/tdkcgi")
    p.add_argument("--insecure", action="store_true", help="Disable TLS verification (https only)")

    p.add_argument("--username", required=True, help="Device CGI username")
    p.add_argument("--device-password", required=True, help="Device CGI password, raw or already SHA-256 encoded")
    p.add_argument("--data-encode-key", default="", help="Needed for non-HS digest formula")
    p.add_argument("--hs-device", action="store_true", help="Use HS digest formula username:realm:password")
    p.add_argument("--security", default="username", help="Header security value (default: username)")

    p.add_argument("--door", type=int, default=1, help="Latch index")
    p.add_argument("--open-password", default="", help="Open password, raw or already SHA-256 encoded; defaults to --device-password")
    p.add_argument("--dry-run", action="store_true", help="Print XML only")
    args = p.parse_args()

    encoded_device_password = encode_device_password(args.device_password)
    encoded_open_password = encode_device_password(args.open_password or args.device_password)

    xml = build_open_door_xml(
        username=args.username,
        device_password=encoded_device_password,
        door=args.door,
        open_password=encoded_open_password,
        security=args.security,
    )
    print("=== XML command ===")
    print(xml)
    print()
    if args.dry_run:
        return 0

    if args.scheme == "https":
        ctx = ssl.create_default_context()
        if args.insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            args.host, args.port, timeout=10, context=ctx
        )
    else:
        conn = http.client.HTTPConnection(args.host, args.port, timeout=10)

    try:
        st1, h1, b1 = request(conn, path=args.path, body=xml, authorization="")
        print(f"=== First response: HTTP {st1} ===")
        print("=== First response headers ===")
        for k, v in h1.items():
            print(f"{k}: {v}")
        print()
        print(b1[:1200])
        print()

        err = parse_cgi_error(b1)
        if st1 != 401 and err != "401":
            if st1 == 200 and err == "0":
                print("Door command accepted (error=0).")
                return 0
            print("No digest challenge (401) received. Stopping.")
            return 1

        challenge = parse_www_authenticate(h1.get("WWW-Authenticate", ""))
        auth = build_digest_auth(
            username=args.username,
            password=encoded_device_password,
            data_encode_key=args.data_encode_key,
            challenge=challenge,
            is_hs_device=args.hs_device,
            uri=args.path,
        )

        print("=== Authorization used ===")
        print(auth)
        print()

        st2, _h2, b2 = request(conn, path=args.path, body=xml, authorization=auth)
        print(f"=== Second response: HTTP {st2} ===")
        print(b2[:1200])
        print()
        err2 = parse_cgi_error(b2)
        if st2 == 200 and err2 == "0":
            print("Door command accepted (error=0).")
            return 0
        print(f"Door command not confirmed (http={st2}, error={err2!r}).")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
