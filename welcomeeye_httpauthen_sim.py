#!/usr/bin/env python3
"""
Simulate WelcomeEye Connect 3 open-door CGI call and Digest Authorization.

For authorized testing on your own device only.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import re
import ssl
import sys
from typing import Dict, Tuple


def md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def parse_kv_header(header_value: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not header_value:
        return out

    parts = [p.strip() for p in header_value.split(",") if p.strip()]
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip().strip('"')

    # Keep compatibility with app parsing behavior where first key can be "Digest realm".
    if "realm" in out and "Digest realm" not in out:
        out["Digest realm"] = out["realm"]
    return out


def parse_digest_challenge(www_authenticate: str) -> Dict[str, str]:
    # Example: Digest realm="...", nonce="...", opaque="...", qop="auth"
    challenge = www_authenticate.strip()
    if challenge.lower().startswith("digest "):
        challenge = challenge[7:].strip()
    parsed = parse_kv_header(challenge)
    if "realm" in parsed and "Digest realm" not in parsed:
        parsed["Digest realm"] = parsed["realm"]
    return parsed


def build_digest_authorization(
    username: str,
    password: str,
    data_encode_key: str,
    challenge: Dict[str, str],
    *,
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

    if not all([realm, nonce, opaque, qop]):
        raise ValueError(
            "Challenge incomplete: realm/nonce/opaque/qop are required to mimic app behavior."
        )

    # App logic:
    # HS: A1 raw = username:realm:password
    # Non-HS: A1 raw = username:realm:dataEncodeKey
    if is_hs_device:
        a1_raw = f"{username}:{realm}:{password}"
    else:
        a1_raw = f"{username}:{realm}:{data_encode_key}"

    ha1 = md5_hex(a1_raw)
    ha2 = md5_hex(f"{method}:{uri}")
    response = md5_hex(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")

    return (
        f'Digest username="{username}",realm="{realm}",nonce="{nonce}",'
        f'uri="{uri}",algorithm=MD5,response="{response}",opaque="{opaque}",'
        f'qop={qop},nc={nc},cnonce="{cnonce}"'
    )


def build_open_door_xml(username: str, device_password: str, door: int, open_password: str) -> str:
    # Matches the expected XML command envelope used by app CGI calls.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope>"
        "<header>"
        "<security>username</security>"
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


def request_once(
    conn: http.client.HTTPConnection,
    path: str,
    xml_body: str,
    authorization: str | None = None,
) -> Tuple[int, Dict[str, str], str]:
    headers = {
        "Content-Type": "application/xml;charset=utf-8",
        "Accept": "*/*",
    }
    if authorization:
        headers["Authorization"] = authorization

    conn.request("POST", path, body=xml_body.encode("utf-8"), headers=headers)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", errors="replace")
    resp_headers = {k: v for k, v in resp.getheaders()}
    return resp.status, resp_headers, body


def parse_digest_authorization(header_value: str) -> Dict[str, str]:
    val = header_value.strip()
    if val.lower().startswith("digest "):
        val = val[7:].strip()
    return parse_kv_header(val)


def compare_auth_headers(expected: str, observed: str) -> str:
    exp = parse_digest_authorization(expected)
    obs = parse_digest_authorization(observed)
    keys = sorted(set(exp.keys()) | set(obs.keys()))
    lines = []
    for k in keys:
        ev = exp.get(k)
        ov = obs.get(k)
        if ev == ov:
            lines.append(f"[OK]   {k}: {ev}")
        else:
            lines.append(f"[DIFF] {k}: expected={ev!r} observed={ov!r}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Simulate WelcomeEye /tdkcgi set.device.opendoor with app-like Digest auth."
    )
    p.add_argument("--host", required=True, help="Device IP/hostname or relay IP")
    p.add_argument("--port", type=int, required=True, help="CGI port")
    p.add_argument("--scheme", choices=["http", "https"], default="http")
    p.add_argument("--path", default="/tdkcgi")

    p.add_argument("--username", required=True, help="Device username used by app")
    p.add_argument("--device-password", required=True, help="Device account password")
    p.add_argument("--data-encode-key", default="", help="dataEncodeKey (non-HS mode)")
    p.add_argument("--hs-device", action="store_true", help="Use HS A1 formula username:realm:password")

    p.add_argument("--door", type=int, default=1)
    p.add_argument("--open-password", default="", help="Password used in <content><password> for opendoor")

    p.add_argument(
        "--challenge",
        default="",
        help='Manual WWW-Authenticate Digest challenge (e.g. \'Digest realm="x", nonce="y", ...\')',
    )
    p.add_argument("--observed-auth", default="", help="Observed Authorization header to compare against")
    p.add_argument("--dry-run", action="store_true", help="Do not send network requests")
    p.add_argument("--insecure", action="store_true", help="Disable TLS cert verification for https")
    args = p.parse_args()

    xml_body = build_open_door_xml(
        username=args.username,
        device_password=args.device_password,
        door=args.door,
        open_password=args.open_password,
    )

    print("=== XML Body (set.device.opendoor) ===")
    print(xml_body)
    print()

    challenge_dict: Dict[str, str] = {}
    auth_header = ""

    if args.challenge:
        challenge_dict = parse_digest_challenge(args.challenge)
        auth_header = build_digest_authorization(
            username=args.username,
            password=args.device_password,
            data_encode_key=args.data_encode_key,
            challenge=challenge_dict,
            is_hs_device=args.hs_device,
            uri=args.path,
            method="POST",
        )
        print("=== Authorization (from provided challenge) ===")
        print(auth_header)
        print()

    if args.observed_auth:
        if not auth_header:
            print("No generated Authorization yet (missing --challenge), comparison skipped.", file=sys.stderr)
        else:
            print("=== Comparison With Observed Authorization ===")
            print(compare_auth_headers(auth_header, args.observed_auth))
            print()

    if args.dry_run:
        return 0

    if args.scheme == "https":
        ctx = ssl.create_default_context()
        if args.insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(args.host, args.port, context=ctx, timeout=10)
    else:
        conn = http.client.HTTPConnection(args.host, args.port, timeout=10)

    try:
        # First request without Authorization, to fetch digest challenge if needed.
        status1, headers1, body1 = request_once(conn, args.path, xml_body, authorization=None)
        print(f"=== First Response ===\nHTTP {status1}")
        print("WWW-Authenticate:", headers1.get("WWW-Authenticate", ""))
        print(body1[:1000])
        print()

        if status1 == 401:
            challenge_header = headers1.get("WWW-Authenticate", "")
            challenge_dict = parse_digest_challenge(challenge_header)
            auth_header = build_digest_authorization(
                username=args.username,
                password=args.device_password,
                data_encode_key=args.data_encode_key,
                challenge=challenge_dict,
                is_hs_device=args.hs_device,
                uri=args.path,
                method="POST",
            )
            print("=== Generated Authorization (retry) ===")
            print(auth_header)
            print()

            if args.observed_auth:
                print("=== Comparison With Observed Authorization ===")
                print(compare_auth_headers(auth_header, args.observed_auth))
                print()

            status2, headers2, body2 = request_once(conn, args.path, xml_body, authorization=auth_header)
            print(f"=== Second Response ===\nHTTP {status2}")
            print(body2[:1000])
            print()
        else:
            print("No 401 challenge on first request; digest retry not triggered.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
