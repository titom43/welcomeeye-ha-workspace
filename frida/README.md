# Frida Scripts

These scripts are intended to run against the Android app during:

- pairing / onboarding
- first successful login
- incoming calls / unlock events
- app-triggered door opening

Package assumed:

- `com.extel.philipsdoorconnect`

## Typical usage

Spawn the app and attach the pairing monitor:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_pairing_monitor.js
```

Attach to a running app for runtime events:

```bash
frida -U -n PhilipsDoorConnect -l frida/welcomeeye_runtime_monitor.js
```

If the process name differs on your phone, list processes first:

```bash
frida-ps -Uai | rg -i "philips|extel|door|welcome"
```

## What to run when

### 1. During pairing / first installation

Run:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_pairing_monitor.js
```

This should help capture:

- auth service URL (`changeService`)
- bind requests (`device-bind`, `device-bind-hs`)
- dynamic password / token flow
- device properties and flags
- `dataEncodeKey` accesses when they happen

### 2. During normal use / validation

Run:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_runtime_monitor.js
```

This should help capture:

- `requestUrl` / auth endpoint changes
- raw down-channel payloads
- digest auth generation inputs
- exact `set.device.opendoor` parameters
- badge / unlock payloads if emitted

## High-value outputs to keep

- `auth_base_url`
- `device_host`
- `cgi_port`
- `username`
- `hs_device`
- `dataEncodeKey`
- `open_password`
- any payload that contains `badge`, `rfid`, `card`, `unlock`, `opendoor`
