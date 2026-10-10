# Moonlight — Home Assistant App

[Moonlight](https://github.com/chris-standley/Moonlight-Calendar) is a family
wall calendar: a shared calendar with iCloud sync, chores and stars, rewards,
lists, a meal planner and a photo screensaver, made for wall-mounted
touchscreens and phones.

- **Sidebar:** opens in Home Assistant through **ingress**
- **Wall screens:** port `8099` (`http://<ha-host>:8099/display/hallway`,
  `kitchen` or `phone`), each paired once with a 6-digit code
- **Data:** the app's own `/data` (backed up, survives updates)

The code lives in
[chris-standley/Moonlight-Calendar](https://github.com/chris-standley/Moonlight-Calendar),
which publishes a prebuilt image for amd64 and aarch64. This folder only holds
the app manifest and docs; see [DOCS.md](DOCS.md) for setup.
