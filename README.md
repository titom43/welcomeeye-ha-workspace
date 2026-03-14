# WelcomeEye HA Workspace

This repository now contains:

- Standalone reverse-engineering/testing scripts
- A full Home Assistant custom integration (HACS-ready): `custom_components/welcomeeye`

## HACS Integration

### Install

1. Add this private repo as a custom repository in HACS (category: `Integration`).
2. Install `WelcomeEye Local`.
3. Restart Home Assistant.
4. Go to `Settings -> Devices & Services -> Add Integration -> WelcomeEye Local`.

### Parameters requested at install

- Local LAN control:
  - `device_host`, `cgi_port`, `scheme`
  - recommended local defaults:
    - `scheme=https`
    - `cgi_port=443`
    - `username=adminapp2`
    - `security=username`
  - `device_password`
    - local auth password used in the XML header
    - on this device it is the 64-char auth code
  - `door`
    - usually `1`
  - `lock_number`
    - `1 = gâche`
    - `2 = portail`
  - `open_password`
    - door unlock password used in the command content
    - on this device it is the same 64-char auth code
  - `verify_ssl`
- Optional down-channel listener:
  - `enable_downchannel`
  - `auth_base_url`, `alarm_base_url`, `auth_mode`
  - `auth_account`, `auth_password` (except free mode)
  - `auth_type`, `auth_code`, `ip_region_id`, `read_timeout`
  - `alarm_base_url` can be left empty if your auth host follows the usual
    `shi-XX-sec.qvcloud.net` pattern; the integration will derive
    `https://shi-(XX+1)-sec.qvcloud.net:4443/UserAlarm`

### Entities and service

- Buttons:
  - `Open Latch`
  - `Open Gate`
- Sensors:
  - `Last Event Type`
  - `Last Unlock Method`
  - `Last Badge ID`
- Service:
  - `welcomeeye.open_door`
  - optional fields: `entry_id`, `door`, `lock_number`

### Local opening path

The integration now tries the local XML API first:

- `POST https://<device_host>:443/tdkcgi`
- XML auth in the envelope header
- no Android bridge required

If that local path does not answer as expected, the integration keeps the previous digest path as a fallback.

### Badge unlock info

The integration now combines:

- local LAN opening on `443`
- optional cloud event polling from `UserAlarm`

Reliable event mappings observed on this device:

- `event=19`, `alarmState=1` -> ring
- `event=63`, `alarmState=4` -> app/remote unlock
- `event=63`, `alarmState=5` -> badge unlock

Current limitation:
- the app/cloud payloads observed so far do not expose the badge name (`Alice`, etc.),
  so `Last Badge ID` will usually stay empty even when the unlock method is correctly
  classified as `badge`.

## Utility Scripts

- `welcomeeye_auth_endpoint_finder_macos.py`
- `welcomeeye_downchannel_listener.py`
- `welcomeeye_httpauthen_sim.py`
- `welcomeeye_open_door.py`
