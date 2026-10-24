# Disclaimer

**This is an unofficial, community-maintained collection of Home Assistant apps.
It is NOT affiliated with, endorsed by, sponsored by, or supported by any of the
projects whose software it packages.**

Each app in this repository simply **wraps an official, unmodified upstream
Docker image** so it can be installed and managed as a Home Assistant app. This
project does **not** modify or redistribute the upstream software itself.

## Channels DVR apps

- Not affiliated with, endorsed by, or supported by **Fancy Bits, LLC** or the
  Channels team.
- "Channels", "Channels DVR", and related names and logos are trademarks of
  their respective owners (Fancy Bits, LLC), used only to describe what the app
  runs. No trademark ownership or endorsement is claimed or implied.
- Wraps the official `fancybits/channels-dvr` image. The Channels DVR server
  binary is downloaded by that image at runtime, directly from Fancy Bits.
- For official support: <https://getchannels.com> and
  <https://community.getchannels.com>.

## Jellyfin apps

- Not affiliated with, endorsed by, or supported by the **Jellyfin project**.
- "Jellyfin" and related names and logos are trademarks of their respective
  owners, used only to describe what the app runs. No trademark ownership or
  endorsement is claimed or implied.
- Wraps the official `jellyfin/jellyfin` image.
- For official support: <https://jellyfin.org> and
  <https://forum.jellyfin.org>.

## Immich Memories app

- Not affiliated with, endorsed by, or supported by the **Immich project** or
  FUTO.
- "Immich" and related names and logos are trademarks of their respective
  owners, used only to describe what the app works with. No trademark ownership
  or endorsement is claimed or implied.
- This app is original code that talks to your own Immich server through
  Immich's public API; it does not package or modify Immich. It uses OpenCV's
  YuNet face detection model (MIT licence), downloaded when the app is built.

## Ticket to Ride Scorer app

- Not affiliated with, endorsed by, or supported by **Days of Wonder** or
  **Asmodee**.
- "Ticket to Ride" is a trademark of Days of Wonder, used only to describe the
  game this app helps score. No trademark ownership or endorsement is claimed or
  implied.
- This app is original code. It doesn't include artwork from the game: its map
  is a simple diagram of city names and route lengths, used to add up scores.
  You need your own copy of the game to play.

## General

- This project is not affiliated with or endorsed by Home Assistant / the Open
  Home Foundation.
- The packaged software is subject to its own license and terms of service; your
  use of it is governed by those terms, not by this project.
- These apps are provided "as is", without warranty of any kind. Use at your own
  risk.
