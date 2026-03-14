#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ssl
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import http.client


def now_xml() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dt%H:%M:%Sz')


def encode_device_password(value: str) -> str:
    raw = (value or '').strip()
    if len(raw) >= 64:
        return raw
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def build_header(username: str, password: str, security: str = 'username', passwordencode: str = '1') -> str:
    return (
        '<header>'
        f'<security>{security}</security>'
        f'<username>{username}</username>'
        f'<password>{password}</password>'
        f'<passwordencode>{passwordencode}</passwordencode>'
        '</header>'
    )


def build_envelope(command: str, content_xml: str, username: str, password: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<envelope>'
        f'{build_header(username, password)}'
        '<body>'
        f'<command>{command}</command>'
        f'{content_xml}'
        '</body>'
        '</envelope>'
    )


def content_empty() -> str:
    return '<content></content>'


def content_unlock(lock: int, door: int, unlock_password: str) -> str:
    return (
        '<content>'
        f'<door>{door}</door>'
        f'<locknumber>{lock}</locknumber>'
        f'<password>{unlock_password}</password>'
        '</content>'
    )


def content_record_alarm(channel: int, timestamp: str) -> str:
    return (
        '<content>'
        '<record>'
        '<filetype>all</filetype>'
        '<stream>all</stream>'
        '<occurtype>all</occurtype>'
        f'<channel>{channel}</channel>'
        f'<timestamp>{timestamp}</timestamp>'
        '</record>'
        '</content>'
    )


def content_record_session(channel: int, start_time: str, end_time: str) -> str:
    return (
        '<content>'
        '<record>'
        '<filetype>all</filetype>'
        '<occurtype>all</occurtype>'
        f'<channels>{channel}</channels>'
        f'<starttime>{start_time}</starttime>'
        f'<endtime>{end_time}</endtime>'
        '<stream>all</stream>'
        '</record>'
        '</content>'
    )


def content_record_message(record_id: str) -> str:
    return (
        '<content>'
        '<record>'
        f'<id>{record_id}</id>'
        '</record>'
        '</content>'
    )


def post_xml(host: str, port: int, body: str, insecure: bool = True) -> tuple[int, dict[str, str], str]:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection(host, port, timeout=8, context=ctx)
    try:
        conn.request(
            'POST',
            '/tdkcgi',
            body=body.encode('utf-8'),
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Accept': '*/*'},
        )
        resp = conn.getresponse()
        text = resp.read().decode('utf-8', errors='replace')
        return resp.status, {k: v for k, v in resp.getheaders()}, text
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description='Probe WelcomeEye local XML API on /tdkcgi')
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, default=443)
    p.add_argument('--username', default='adminapp2')
    p.add_argument('--password', required=True, help='Local auth password, raw or already SHA-256 encoded')
    p.add_argument('--unlock-password', default=None, help='Unlock password, raw or already SHA-256 encoded; defaults to --password')
    p.add_argument('--probe', required=True, choices=['device-status', 'live-status', 'system-status', 'record-alarm', 'record-session', 'record-message', 'unlock-gache', 'unlock-portail'])
    p.add_argument('--channel', type=int, default=1)
    p.add_argument('--timestamp', default=None)
    p.add_argument('--end-timestamp', default=None)
    p.add_argument('--record-id', default=None)
    args = p.parse_args()

    encoded_password = encode_device_password(args.password)
    unlock_password = encode_device_password(args.unlock_password or args.password)
    ts = args.timestamp or now_xml()

    if args.probe == 'device-status':
        command, content = 'get.device.status', content_empty()
    elif args.probe == 'live-status':
        command, content = 'get.live.status', content_empty()
    elif args.probe == 'system-status':
        command, content = 'get.system.status', content_empty()
    elif args.probe == 'record-alarm':
        command, content = 'get.record.alarmrecord', content_record_alarm(args.channel, ts)
    elif args.probe == 'record-session':
        end_ts = args.end_timestamp or ts
        command, content = 'get.record.session', content_record_session(args.channel, ts, end_ts)
    elif args.probe == 'record-message':
        if not args.record_id:
            raise SystemExit('--record-id is required for record-message')
        command, content = 'get.record.message', content_record_message(args.record_id)
    elif args.probe == 'unlock-gache':
        command, content = 'set.device.opendoor', content_unlock(1, args.channel, unlock_password)
    elif args.probe == 'unlock-portail':
        command, content = 'set.device.opendoor', content_unlock(2, args.channel, unlock_password)
    else:
        raise SystemExit('unsupported probe')

    xml = build_envelope(command, content, args.username, encoded_password)
    print('=== REQUEST ===')
    print(xml)
    print()
    status, headers, text = post_xml(args.host, args.port, xml)
    print(f'=== RESPONSE HTTP {status} ===')
    for k, v in headers.items():
        print(f'{k}: {v}')
    print()
    print(text)
    try:
        root = ET.fromstring(text)
        err = root.findtext('./body/error')
        if err is not None:
            print(f'\n=== CGI ERROR {err} ===')
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
