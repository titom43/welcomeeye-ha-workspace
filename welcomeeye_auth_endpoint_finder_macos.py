#!/usr/bin/env python3
"""
Find WelcomeEye auth endpoint(s) on macOS.

Methods:
1) adb-prefs: extract cached SERVICE_URL from Android app shared prefs
2) capture: sniff traffic with tshark and detect auth up/down requests

Use only on devices/accounts you own or are authorized to test.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as et
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


DEFAULT_PACKAGE = "com.extel.philipsdoorconnect"

AUTH_PATH_RE = re.compile(r"/auth/(?:user|nologin)(?:/deli)?;jus_duplex=(?:up|down)")


def run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        print(f"[ERROR] Missing required binary: {name}", file=sys.stderr)
        sys.exit(2)


def parse_service_urls_from_prefs_xml(xml_text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        root = et.fromstring(xml_text)
    except Exception as exc:
        raise RuntimeError(f"Unable to parse shared prefs XML: {exc}") from exc

    # <string name="su_<group>_<type>">https://host:port/</string>
    for string_node in root.findall("string"):
        name = string_node.attrib.get("name", "")
        if name.startswith("su_"):
            out[name] = (string_node.text or "").strip()
    return out


def adb_read_shared_prefs(package: str) -> str:
    require_binary("adb")

    # First attempt: run-as (works on debuggable builds or rooted contexts)
    cmd = [
        "adb",
        "shell",
        "run-as",
        package,
        "cat",
        "shared_prefs/save.xml",
    ]
    cp = run(cmd)
    if cp.returncode == 0 and cp.stdout.strip():
        return cp.stdout

    # Fallback: direct path (likely requires root)
    cmd2 = [
        "adb",
        "shell",
        "cat",
        f"/data/data/{package}/shared_prefs/save.xml",
    ]
    cp2 = run(cmd2)
    if cp2.returncode == 0 and cp2.stdout.strip() and "permission denied" not in cp2.stdout.lower():
        return cp2.stdout

    details = "\n".join(
        [
            "run-as stderr:\n" + (cp.stderr.strip() or "(empty)"),
            "direct cat stderr:\n" + (cp2.stderr.strip() or "(empty)"),
            "direct cat stdout:\n" + (cp2.stdout.strip() or "(empty)"),
        ]
    )
    raise RuntimeError(
        "Unable to read app shared_prefs/save.xml via adb. "
        "You may need a debuggable app build, root, or backup-based extraction.\n"
        + details
    )


def do_adb_prefs(package: str) -> int:
    xml_text = adb_read_shared_prefs(package)
    urls = parse_service_urls_from_prefs_xml(xml_text)
    if not urls:
        print("[WARN] No SERVICE_URL keys found (keys starting with 'su_').")
        return 1

    print("SERVICE_URL entries found:")
    for key in sorted(urls.keys()):
        print(f"{key} = {urls[key]}")

    # Help identify auth service type=0 convention
    auth_candidates = {k: v for k, v in urls.items() if k.endswith("_0")}
    if auth_candidates:
        print("\nLikely AUTH candidates (type 0):")
        for key in sorted(auth_candidates.keys()):
            print(f"{key} = {auth_candidates[key]}")
    return 0


def parse_tshark_lines(lines: Iterable[str]) -> Tuple[Set[str], Set[str], Dict[str, Set[str]]]:
    """
    Returns:
    - cleartext_urls: full URLs with path seen in HTTP
    - tls_sni_hosts: SNI hostnames seen in TLS ClientHello
    - ip_hits: map ip -> set(hints)
    """
    cleartext_urls: Set[str] = set()
    tls_sni_hosts: Set[str] = set()
    ip_hits: Dict[str, Set[str]] = defaultdict(set)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # Format from tshark fields output:
        # frame.time_epoch \t ip.dst \t http.host \t http.request.uri \t tls.sni
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        _ts, ip_dst, http_host, http_uri, tls_sni = parts[:5]

        if http_host and http_uri and AUTH_PATH_RE.search(http_uri):
            cleartext_urls.add(f"http://{http_host}{http_uri}")
            if ip_dst:
                ip_hits[ip_dst].add(f"http:{http_host}{http_uri}")

        if tls_sni:
            tls_sni_hosts.add(tls_sni)
            if ip_dst:
                ip_hits[ip_dst].add(f"tls-sni:{tls_sni}")

    return cleartext_urls, tls_sni_hosts, ip_hits


def do_capture(interface: str, duration: int, auth_only: bool) -> int:
    require_binary("tshark")

    # We capture HTTP URI/Host and TLS SNI. HTTPS path is not visible without MITM.
    # Using -a duration ensures clean stop.
    display_filter = "http.request or tls.handshake.extensions_server_name"
    if auth_only:
        display_filter = (
            '(http.request.uri contains "jus_duplex=up" or '
            'http.request.uri contains "jus_duplex=down" or '
            'tls.handshake.extensions_server_name)'
        )

    cmd = [
        "tshark",
        "-l",
        "-i",
        interface,
        "-a",
        f"duration:{duration}",
        "-Y",
        display_filter,
        "-T",
        "fields",
        "-e",
        "frame.time_epoch",
        "-e",
        "ip.dst",
        "-e",
        "http.host",
        "-e",
        "http.request.uri",
        "-e",
        "tls.handshake.extensions_server_name",
        "-E",
        "separator=\t",
    ]

    print(f"[INFO] Running: {' '.join(cmd)}")
    print("[INFO] Trigger login / app open / incoming call during capture.")
    cp = run(cmd)
    if cp.returncode != 0:
        print(cp.stderr.strip() or cp.stdout.strip(), file=sys.stderr)
        return 1

    cleartext_urls, tls_sni_hosts, ip_hits = parse_tshark_lines(cp.stdout.splitlines())

    print("\n=== Cleartext auth URLs (definitive) ===")
    if cleartext_urls:
        for u in sorted(cleartext_urls):
            print(u)
    else:
        print("(none seen; traffic may be HTTPS)")

    print("\n=== TLS SNI hosts (candidates) ===")
    if tls_sni_hosts:
        for h in sorted(tls_sni_hosts):
            print(h)
    else:
        print("(none seen)")

    print("\n=== Destination IP hints ===")
    if ip_hits:
        for ip in sorted(ip_hits.keys()):
            hints = ", ".join(sorted(ip_hits[ip]))
            print(f"{ip} -> {hints}")
    else:
        print("(none)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find WelcomeEye auth endpoint on macOS via adb prefs or tshark capture."
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_adb = sub.add_parser("adb-prefs", help="Read app shared_prefs/save.xml and extract SERVICE_URL.")
    p_adb.add_argument("--package", default=DEFAULT_PACKAGE, help="Android package name.")

    p_cap = sub.add_parser("capture", help="Sniff traffic with tshark and detect auth endpoints.")
    p_cap.add_argument("--interface", default="en0", help="Network interface (e.g., en0, en1).")
    p_cap.add_argument("--duration", type=int, default=40, help="Capture duration in seconds.")
    p_cap.add_argument(
        "--all-http",
        action="store_true",
        help="Wider filter (all HTTP requests + TLS SNI), not only auth path candidates.",
    )

    args = parser.parse_args()
    if args.mode == "adb-prefs":
        return do_adb_prefs(package=args.package)
    if args.mode == "capture":
        return do_capture(interface=args.interface, duration=args.duration, auth_only=not args.all_http)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
