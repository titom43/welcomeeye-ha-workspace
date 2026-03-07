from __future__ import annotations

from datetime import UTC, datetime
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

CALL_KEYWORDS = ("call", "ring", "doorbell", "intercom", "visitor")
UNLOCK_KEYWORDS = ("unlock", "open", "opendoor", "latch", "door_open")
BADGE_KEYWORDS = ("badge", "rfid", "card", "nfc", "tag", "ic")

BADGE_ID_RE = re.compile(r"(?:badge|card|rfid|tag|nfc)[^0-9a-zA-Z]{0,8}([0-9A-Fa-f]{4,32})")


def _xml_to_obj(node: ET.Element) -> Any:
    children = list(node)
    if not children:
        return (node.text or "").strip()
    out: dict[str, Any] = {}
    for child in children:
        value = _xml_to_obj(child)
        if child.tag in out:
            if not isinstance(out[child.tag], list):
                out[child.tag] = [out[child.tag]]
            out[child.tag].append(value)
        else:
            out[child.tag] = value
    return out


def _extract_command(data: Any) -> str | None:
    if isinstance(data, dict):
        if "command" in data and isinstance(data["command"], str):
            return data["command"]
        for value in data.values():
            cmd = _extract_command(value)
            if cmd:
                return cmd
    if isinstance(data, list):
        for item in data:
            cmd = _extract_command(item)
            if cmd:
                return cmd
    return None


def _as_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False)


def parse_downchannel_payload(payload: str) -> dict[str, Any]:
    raw = payload.strip()
    data: Any = raw
    parsed_format = "text"
    if not raw:
        data = None
        parsed_format = "empty"
    elif raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
            parsed_format = "json"
        except Exception:
            parsed_format = "text"
    elif raw.startswith("<"):
        try:
            root = ET.fromstring(raw)
            data = {root.tag: _xml_to_obj(root)}
            parsed_format = "xml"
        except Exception:
            parsed_format = "text"

    command = _extract_command(data)
    hay = f"{_as_text(data)} {command or ''}".lower()

    event_type = "other"
    unlock_method = "unknown"
    badge_id = None

    if any(k in hay for k in CALL_KEYWORDS):
        event_type = "call"
    if any(k in hay for k in UNLOCK_KEYWORDS):
        event_type = "unlock"
    if any(k in hay for k in BADGE_KEYWORDS):
        if event_type == "unlock":
            unlock_method = "badge"
        event_type = "badge" if event_type == "other" else event_type

    badge_match = BADGE_ID_RE.search(hay)
    if badge_match:
        badge_id = badge_match.group(1)
        unlock_method = "badge"
        if event_type == "other":
            event_type = "badge"

    if event_type == "unlock" and unlock_method == "unknown":
        unlock_method = "app_or_remote"

    return {
        "ts": datetime.now(UTC).isoformat(),
        "format": parsed_format,
        "event_type": event_type,
        "command": command,
        "unlock_method": unlock_method,
        "badge_id": badge_id,
        "raw": raw,
        "data": data,
    }
