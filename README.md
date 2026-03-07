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

- Device CGI:
  - `device_host`, `cgi_port`, `scheme`
  - `username`, `device_password`
  - `hs_device` (on/off)
  - `data_encode_key` (needed for non-HS digest mode)
  - `security`, `door`, `open_password`
  - `verify_ssl`
- Optional down-channel listener:
  - `enable_downchannel`
  - `auth_base_url`, `auth_mode`
  - `auth_account`, `auth_password` (except free mode)
  - `auth_type`, `auth_code`, `ip_region_id`, `read_timeout`

### Entities and service

- Button:
  - `Open Door`
- Sensors:
  - `Last Event Type`
  - `Last Unlock Method`
  - `Last Badge ID`
- Service:
  - `welcomeeye.open_door`
  - optional fields: `entry_id`, `door`

### Badge unlock info

The integration parses down-channel payloads and attempts to detect:

- call/ring events
- unlock events
- badge/RFID/card events and badge IDs

Important:
- badge identification depends on what your model/firmware actually sends in payload.
- if badge metadata is present, `Last Badge ID` and `Last Unlock Method=badge` will update.
- if payload does not include explicit badge info, unlock remains classified as `app_or_remote`/`unknown`.

## Utility Scripts

- `welcomeeye_auth_endpoint_finder_macos.py`
- `welcomeeye_downchannel_listener.py`
- `welcomeeye_httpauthen_sim.py`
- `welcomeeye_open_door.py`
