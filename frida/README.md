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

Run the TLS/debug monitor when checking MITM trust or suspected pinning:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_tls_debug.js
```

Run the active TLS bypass when you want the app to accept the MITM certificate path:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_tls_bypass.js
```

Run the combined pairing/full monitor when you want one single Frida session for:

- TLS bypass
- service resolution
- signup/account creation
- bind/device token requests
- down-channel payload capture

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_pairing_full.js
```

Run the event monitor when you want to focus on:

- incoming ring / visitor call
- down-channel unlock events
- badge / RFID events
- distinguishing `gache` (`door=1`) from `portail` (`door=2`)

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_event_monitor.js
```

Run the full event monitor when you want the same event capture but without breaking cloud auth under MITM:

- TLS bypass
- certificate pinning bypass
- incoming ring / visitor call
- unlock events and badge events
- distinguishing `gache` from `portail`

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_event_full.js
```

Run the live control monitor when you want hooks aligned to the exact phone build (`1.0.123.3(2)`) and focused on the real unlock path used from the live preview:

- TLS bypass
- certificate pinning bypass
- preview unlock chain (`PreviewPresenter` -> `PreviewModel` -> `QvPlayerCore`)
- HTTP / IoT unlock paths (`HttpDeviceManager`, `QvDeviceSDK`, `QvIotControlManager`, `QvBaseIotControl`)
- alarm history entries for unlocks / badge (`event=63`)

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_live_control_full.js
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

If you want a cleaner log focused only on field events, use instead:

```bash
cd /Users/tsouvign/Documents/Playground/welcomeeye-ha-workspace
mkdir -p logs
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_event_monitor.js | tee logs/event_monitor_$(date +%Y%m%d_%H%M%S).log
```

Watch for these tags:

- `event.ring`
- `event.unlock`
- `event.unlock_portail`
- `event.unlock_gache`
- `event.badge`
- `device.openLock`
- `device.openLock_portail`

If the app forces a re-login or loses its session while mitmproxy is active, use this version instead:

```bash
cd /Users/tsouvign/Documents/Playground/welcomeeye-ha-workspace
mkdir -p logs
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_event_full.js | tee logs/event_full_$(date +%Y%m%d_%H%M%S).log
```

If you need the exact-build version that follows the live preview unlock path and tries to surface badge activity from alarm history:

```bash
cd /Users/tsouvign/Documents/Playground/welcomeeye-ha-workspace
mkdir -p logs
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_live_control_full.js | tee logs/live_control_full_$(date +%Y%m%d_%H%M%S).log
```

Watch for these tags:

- `preview.presenter.unlock`
- `preview.presenter.startUnlock`
- `preview.model.unlock`
- `playercore.unlock`
- `http.deviceUnlock`
- `iot.deviceUnlock`
- `iot.sendSimpleData`
- `alarm.unlockHistory`
- `alarm.badge`

### 3. During MITM / TLS validation

Run:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_tls_debug.js
```

This helps confirm:

- whether `CertificatePinner.check(...)` is ever called
- whether auth/down-channel uses a custom CA path
- which trust managers are installed into `SSLContext`
- whether the app is using "allow all" hostname verification or a custom CA/truststore path

If you see `tls.certificatePinner.check`, we have explicit OkHttp pinning on that path.
If you only see `tls.initSSL2`, `tls.createBuilder2WithCA`, and a `serverCAPath`, the failure is more likely due to a custom truststore than classic pinning.

### 4. During MITM / active TLS bypass

Run:

```bash
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_tls_bypass.js
```

This script attempts to neutralize the most common Android TLS checks:

- injects a permissive `X509TrustManager`
- forces hostname verification to return `true`
- bypasses `okhttp3.CertificatePinner.check(...)`
- bypasses Conscrypt `TrustManagerImpl.verifyChain(...)`
- re-applies permissive hostname verification on the app's custom OkHttp builders

Recommended test flow:

```bash
mitmweb --ssl-insecure -m wireguard@51823 --web-host 0.0.0.0
```

Then in another terminal:

```bash
cd /Users/tsouvign/Documents/Playground/welcomeeye-ha-workspace
mkdir -p logs
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_tls_bypass.js | tee logs/tls_bypass_$(date +%Y%m%d_%H%M%S).log
```

If the bypass works, you should start seeing `/auth/user` traffic in mitmproxy instead of stopping after `/mst/query`.

### 5. Recommended single-script pairing run

Use this when you want the simplest workflow:

```bash
mitmweb --ssl-insecure -m wireguard@51823 --web-host 0.0.0.0
```

Then:

```bash
cd /Users/tsouvign/Documents/Playground/welcomeeye-ha-workspace
mkdir -p logs
frida -U -f com.extel.philipsdoorconnect -l frida/welcomeeye_pairing_full.js | tee logs/pairing_full_$(date +%Y%m%d_%H%M%S).log
```

This is the preferred script for:

- sending registration code
- account creation
- observing `downchannel.changeService`
- observing `account-register` request construction
- bypassing TLS/pinning on `qvcloud.net`

## High-value outputs to keep

- `auth_base_url`
- `device_host`
- `cgi_port`
- `username`
- `hs_device`
- `dataEncodeKey`
- `open_password`
- any payload that contains `badge`, `rfid`, `card`, `unlock`, `opendoor`
- any TLS logs containing `certificatePinner`, `serverCAPath`, `initSSL2`, `checkServerTrusted`
