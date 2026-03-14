#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any


def xml_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dt%H:%M:%Sz')


def build_header(username: str, password: str) -> str:
    return (
        '<header>'
        '<security>username</security>'
        f'<username>{username}</username>'
        f'<password>{password}</password>'
        '<passwordencode>1</passwordencode>'
        '</header>'
    )


def build_device_status(username: str, password: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<envelope>'
        f'{build_header(username, password)}'
        '<body><command>get.device.status</command><content></content></body>'
        '</envelope>'
    )


def build_record_alarm(username: str, password: str, channel: int, timestamp: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<envelope>'
        f'{build_header(username, password)}'
        '<body>'
        '<command>get.record.alarmrecord</command>'
        '<content><record>'
        '<filetype>all</filetype>'
        '<stream>all</stream>'
        '<occurtype>all</occurtype>'
        f'<channel>{channel}</channel>'
        f'<timestamp>{timestamp}</timestamp>'
        '</record></content>'
        '</body>'
        '</envelope>'
    )


def post(host: str, port: int, body: str) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection(host, port, timeout=5, context=ctx)
    try:
        conn.request(
            'POST',
            '/tdkcgi',
            body=body.encode('utf-8'),
            headers={'Content-Type': 'application/xml; charset=utf-8'},
        )
        resp = conn.getresponse()
        return resp.read().decode('utf-8', errors='replace')
    finally:
        conn.close()


def get_text(root: ET.Element, path: str, default: str = '') -> str:
    value = root.findtext(path)
    return (value or default).strip()


def parse_device_status(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    return {
        'error': get_text(root, './body/error'),
        'calling': get_text(root, './body/content/devicestatus/calling'),
        'lockstatus': get_text(root, './body/content/devicestatus/lockstatus'),
        'vionoff': get_text(root, './body/content/vionoff/value'),
        'datetime': get_text(root, './body/content/time/datatime'),
    }


def summarize_alarmrecord(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    error = get_text(root, './body/error')
    content = root.find('./body/content')
    if content is None:
        return {'error': error, 'summary': 'no-content'}

    # Keep this generic: many firmware variants shape alarmrecord differently.
    items: list[dict[str, str]] = []
    for node in content.iter():
        if node is content:
            continue
        children = list(node)
        if not children:
            continue
        leafs = {child.tag: (child.text or '').strip() for child in children if len(list(child)) == 0}
        if leafs and any(v for v in leafs.values()):
            items.append({'tag': node.tag, **leafs})

    digest = hashlib.sha256(xml_text.encode('utf-8')).hexdigest()[:12]
    preview = items[:5]
    return {
        'error': error,
        'digest': digest,
        'items': preview,
        'item_count': len(items),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Watch local WelcomeEye status + alarmrecord changes during a ring')
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=443)
    parser.add_argument('--username', default='adminapp2')
    parser.add_argument('--password', required=True)
    parser.add_argument('--channel', type=int, default=1)
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--duration', type=float, default=45.0)
    parser.add_argument('--lookback', type=float, default=120.0, help='Seconds back for get.record.alarmrecord timestamp window')
    args = parser.parse_args()

    end = time.time() + args.duration
    last_status = None
    last_alarm_digest = None

    while time.time() < end:
        now = datetime.now(timezone.utc)
        status_body = build_device_status(args.username, args.password)
        alarm_body = build_record_alarm(args.username, args.password, args.channel, xml_time(now - timedelta(seconds=args.lookback)))

        try:
            status_snap = parse_device_status(post(args.host, args.port, status_body))
            if status_snap != last_status:
                print({'type': 'device-status', **status_snap})
                sys.stdout.flush()
                last_status = status_snap
        except Exception as exc:
            print({'type': 'device-status', 'error': str(exc)})
            sys.stdout.flush()

        try:
            alarm_snap = summarize_alarmrecord(post(args.host, args.port, alarm_body))
            if alarm_snap.get('digest') != last_alarm_digest:
                print({'type': 'alarmrecord', **alarm_snap})
                sys.stdout.flush()
                last_alarm_digest = alarm_snap.get('digest')
        except Exception as exc:
            print({'type': 'alarmrecord', 'error': str(exc)})
            sys.stdout.flush()

        time.sleep(args.interval)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
