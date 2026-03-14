# WelcomeEye Local

<p align="center">
  <img src="assets/logo.svg" alt="WelcomeEye Local logo" width="160">
</p>

<p align="center">
  Local control and cloud event monitoring for WelcomeEye Connect 3 intercoms from Home Assistant.
</p>

## Features

- **Local Unlock**: Open the **latch** (gâche) and the **gate** (portail) directly via the local device API. No cloud latency for opening.
- **Cloud Watcher**: Monitor events (doorbell rings, badge unlocks, app unlocks) via a robust polling mechanism.
- **Dedicated Entities**: 
    - Binary Sensor for the doorbell.
    - Buttons for opening latch and gate.
    - Sensor for the last event type, unlock method, and badge ID.
    - Manual refresh button to trigger an instant event check.

## Installation

### HACS (Recommended)

1. Add this repository as a **Custom Repository** in HACS (Integration category).
2. Install **WelcomeEye Local**.
3. Restart Home Assistant.
4. Go to `Settings -> Devices & Services -> Add Integration` and search for **WelcomeEye**.

## Configuration

The setup is simplified to the essentials:

- **Intercom IP**: Local IP address of your monitor.
- **Local Code**: The 6-digit code you configured on the monitor screen.
- **Cloud Email & Password**: Your Philips WelcomeEye app credentials (optional, enables the Watcher).
- **Intercom ID / CID**: The unique ID of your intercom (found in the app settings, e.g., `2502uvs...`).
- **Poll Frequency**: How often to check for events (in minutes, set to 0 to disable automatic polling).

## Entities

- **Binary Sensor**: `Doorbell` (turns on for 10 seconds when someone rings).
- **Button**: `Open Latch` (Gâche).
- **Button**: `Open Gate` (Portail).
- **Button**: `Refresh Events` (Manual poll).
- **Sensor**: `Last Event Type`.
- **Sensor**: `Last Unlock Method`.
- **Sensor**: `Last Badge ID`.

## Notes

- Opening is done locally via the XML API on `/tdkcgi`.
- Event monitoring (Watcher) requires cloud credentials and uses a polling strategy for better stability than long-polling.
- The integration is designed to be 100% focused on Home Assistant needs, keeping technical complexity hidden.

## Support

- Issues: [GitHub Issues](https://github.com/titom43/welcomeeye-ha-workspace/issues)
