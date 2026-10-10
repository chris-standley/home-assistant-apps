# Chris's Home Assistant Apps

A Home Assistant apps repository that wraps **official** upstream Docker images
so they can be installed and managed as Home Assistant apps — currently
**Channels DVR** and **Jellyfin**, each with an Intel/AMD and an NVIDIA variant —
plus my own **Moonlight** family wall calendar.

> ## ⚠️ Unofficial — not affiliated with the upstream projects
>
> **This is an unofficial, community project.** It is **not affiliated with,
> endorsed by, or supported by** Fancy Bits / Channels, the Jellyfin project, or
> Home Assistant / the Open Home Foundation. Each app wraps an **official,
> unmodified** upstream image; it does not modify or redistribute their software.
> All trademarks belong to their respective owners. See
> [DISCLAIMER.md](DISCLAIMER.md) for the full statement.

## Apps

Each app comes in two GPU variants — install the **one** that matches your
hardware. (The two variants of the same app both bind the same port, so don't
run both at once.)

| App | Intel / AMD (VA-API) | NVIDIA (NVENC) | Port |
| --- | --- | --- | --- |
| **Channels DVR** — live TV DVR from HDHomeRun / TV Everywhere | [`channels_dvr`](./channels_dvr) | [`channels_dvr_nvidia`](./channels_dvr_nvidia) | `8089` |
| **Jellyfin** — free software media system | [`jellyfin`](./jellyfin) | [`jellyfin_nvidia`](./jellyfin_nvidia) | `8096` |

| App | Folder | Port |
| --- | --- | --- |
| **Moonlight** — family wall calendar, chores, lists and meals ([source](https://github.com/chris-standley/Moonlight-Calendar)) | [`moonlight`](./moonlight) | `8091` |

> **Which GPU variant?** *Quick Sync* is Intel-only; AMD uses its VCN encoder.
> On Linux both are reached through the same `/dev/dri` render node, so the
> **Intel / AMD** variant covers both — pick it unless you have an NVIDIA GPU.
> NVIDIA (NVENC) needs a host with the NVIDIA driver installed (generally a
> **Supervised** install, not Home Assistant OS).

Notable differences between the two apps:

- **Channels DVR** needs **host networking** for HDHomeRun tuner discovery, so
  it can't use ingress — reach it on the LAN at `:8089` (or via Channels' own
  remote access). The Channels server self-updates itself at runtime.
- **Jellyfin** runs on the bridge network and supports subpaths, so it enables
  **ingress** — authenticated remote access through Home Assistant, no exposed
  port. Jellyfin does not self-update; the image update is the server update.

## Installing this repository

> The repository must be **public** on GitHub — Home Assistant clones it
> anonymously. (Private repos aren't supported via the Store UI; use the local
> app method below instead.)

1. In Home Assistant: **Settings → Apps → App Store**.
2. Open the ⋮ menu (top-right) → **Repositories**.
3. Add this repository's URL:

   ```
   https://github.com/chris-standley/home-assistant-apps
   ```

4. The apps above will appear in the store, ready to install.

[![Open your Home Assistant instance and show the add app repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fchris-standley%2Fhome-assistant-apps)

### Local install (no public GitHub repo needed)

Copy an app folder (e.g. `channels_dvr/` or `jellyfin/`) into the `/addons`
directory on your Home Assistant host (via the Samba or SSH app). It will appear
under **Local apps** in the store.

## How updates work

Every app **pins its base image by digest** for reproducible builds, and a
scheduled GitHub Action — [`.github/workflows/update-base-image.yml`](.github/workflows/update-base-image.yml) —
checks each upstream image daily. When a digest changes it re-pins the
Dockerfile, bumps that app's `version`, and prepends a `CHANGELOG.md` entry, so
Home Assistant surfaces an **Update** (with a note) on its own — no manual
version bumping. You can also **Run workflow** manually from the **Actions** tab,
or use **Rebuild** on an app's Info page to rebuild from the pinned digest.

**Moonlight** is different: its code lives in
[chris-standley/Moonlight-Calendar](https://github.com/chris-standley/Moonlight-Calendar),
which publishes a prebuilt image per architecture. Its `config.yaml` points at
that image, so nothing is built on the Home Assistant host. A second workflow,
[`.github/workflows/sync-moonlight.yml`](.github/workflows/sync-moonlight.yml),
checks every few hours and, once a new version's images are published, copies
Moonlight's manifest and docs into `moonlight/` and adds a changelog entry, so
the update shows up in Home Assistant.

Beyond the base image:

- **Channels DVR** also self-updates its server binary at runtime (the image is
  just a bootstrapper), so it stays current between base-image updates.
- **Jellyfin** does not self-update — the base-image update *is* the server
  update, which makes the automation above the primary update path.

## Recommended two-drive storage layout

These apps are designed for a Home Assistant host with **two drives**, and they
**share the media disk**:

| Drive | Holds | How it's used |
| ----- | ----- | ------------- |
| **Drive 1 — data disk** | HA config/DB, app configs, **Channels' & Jellyfin's databases** | The default HAOS data disk (`/mnt/data`). Small, fast, backed up. |
| **Drive 2 — media disk** | **Channels recordings** + **Jellyfin media library** | HAOS `/media` folder, moved to the second disk. Bulk storage. |

Each app splits the same way:

- **Config/database →** the app's `addon_config` directory on the **data disk
  (drive 1)**. Small, backed up. (Channels: `/channels-dvr`; Jellyfin:
  `/config`.)
- **Bulk media →** the Home Assistant **`/media`** share on **drive 2**.
  Channels writes recordings there; Jellyfin reads its libraries from there. You
  can even point a Jellyfin library at the Channels recordings (e.g.
  `/media/TV`).

### Setting it up in Home Assistant OS

1. Attach the second drive to the host.
2. **Settings → System → Storage** — HAOS (10.2+ / Core 2023.6+) lets you move
   the **media** folder onto the second disk. Select the new drive for media.
   (This moves only `/media`; config/DB/apps stay on the data disk.)
3. Install the apps. Their media automatically uses `/media` → now on drive 2;
   their databases stay on drive 1 via `addon_config`.

## Repository layout

```
.
├── repository.yaml          # Repository metadata (name, url, maintainer)
├── README.md                # This file
├── DISCLAIMER.md            # Full non-affiliation / trademark statement
├── .github/workflows/       # CI: auto-update each app's base image digest + version; sync Moonlight
├── channels_dvr/            # Channels DVR — Intel / AMD (VA-API)
├── channels_dvr_nvidia/     # Channels DVR — NVIDIA (NVENC)
├── jellyfin/                # Jellyfin — Intel / AMD (VA-API)
├── jellyfin_nvidia/         # Jellyfin — NVIDIA (NVENC)
└── moonlight/               # Moonlight — prebuilt image from chris-standley/Moonlight-Calendar
```

Each app folder contains: `config.yaml` (manifest), `Dockerfile` (wraps the
digest-pinned official image), `README.md`, `DOCS.md`, and `CHANGELOG.md`.
`moonlight/` has no `Dockerfile`: its manifest names a prebuilt image instead.

### Optional assets

Home Assistant shows default artwork if none is provided. To brand an app, drop
these PNGs into its folder:

- `icon.png` — 128×128 (square) app icon
- `logo.png` — ~250×100 store logo

## Disclaimer

Unofficial community project; not affiliated with or endorsed by Fancy Bits /
Channels, the Jellyfin project, or Home Assistant / the Open Home Foundation.
See [DISCLAIMER.md](DISCLAIMER.md).
