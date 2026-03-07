# WelcomeEye HA Workspace

Scripts in this workspace:

- `welcomeeye_auth_endpoint_finder_macos.py`:
  - Find auth endpoint(s) on macOS via:
    - `adb-prefs` (extract `SERVICE_URL` from app shared prefs)
    - `capture` (tshark sniff of auth up/down candidates)
- `welcomeeye_downchannel_listener.py`:
  - Login to auth server (optional) and subscribe to `...;jus_duplex=down`
  - Print events as JSON
- `welcomeeye_httpauthen_sim.py`:
  - Reproduce device Digest auth header generation (`/tdkcgi`)
  - Compare generated `Authorization` with intercepted one
- `welcomeeye_open_door.py`:
  - Trigger `set.device.opendoor` with app-like 401 challenge -> Digest retry flow

## Quick Start

```bash
# 1) Find auth endpoint (from phone/app cache)
python3 welcomeeye_auth_endpoint_finder_macos.py adb-prefs

# 2) Listen down-channel events (calls/rings candidates)
python3 welcomeeye_downchannel_listener.py --base-url "https://<auth_host>:<auth_port>/" --mode user --account "<account>" --password "<password>" --print-raw --insecure

# 3) Trigger door open command (authorized device only)
python3 welcomeeye_open_door.py --host <device_ip> --port <cgi_port> --scheme http --username <user> --device-password <pwd> --data-encode-key <key> --door 1 --open-password <open_pwd>
```
