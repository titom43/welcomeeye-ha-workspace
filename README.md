# WelcomeEye Local

<p align="center">
  <img src="assets/logo.svg" alt="WelcomeEye Local logo" width="160">
</p>

<p align="center">
  Local control for WelcomeEye intercoms from Home Assistant.
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=titom43&repository=welcomeeye-ha-workspace&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open this repository in HACS">
  </a>
  <a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=welcomeeye">
    <img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up WelcomeEye Local">
  </a>
</p>

## What it does

- Opens the **latch** and the **gate** through the local device API.
- Supports direct LAN control without an Android bridge.
- Exposes simple Home Assistant entities and a door opening service.

Current local scope:

- `lock_number=1` -> latch
- `lock_number=2` -> gate

## Installation

### HACS

1. Open the HACS button above.
2. Add this repository as an **Integration**.
3. Install **WelcomeEye Local**.
4. Restart Home Assistant.
5. Add the integration from `Settings -> Devices & Services`.

### Manual

1. Copy `custom_components/welcomeeye` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings -> Devices & Services`.

## Configuration

Recommended local defaults:

- `scheme=https`
- `cgi_port=443`
- `username=adminapp2`
- `security=username`

Password fields accept either:

- the raw device code you chose on the monitor
- or the already encoded 64-character SHA-256 value

## Entities

- Button: `Open Latch`
- Button: `Open Gate`
- Sensor: `Last Event Type`
- Sensor: `Last Unlock Method`
- Sensor: `Last Badge ID`

## Service

Service name:

- `welcomeeye.open_door`

Optional service fields:

- `entry_id`
- `door`
- `lock_number`

## Notes

- Local unlock uses the device XML API on `https://<device_host>:443/tdkcgi`.
- Badge names are not currently exposed by the payloads we observed.
- The integration is designed to stay usable with only the data needed for Home Assistant.

## Support

- Issues: [GitHub Issues](https://github.com/titom43/welcomeeye-ha-workspace/issues)
- Documentation: [Repository](https://github.com/titom43/welcomeeye-ha-workspace)
