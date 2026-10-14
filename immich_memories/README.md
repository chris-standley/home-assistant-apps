# Immich Memories — Home Assistant App

Apple Photos style **memories** for [Immich](https://immich.app/). Once a day
it looks through your Immich library, finds the moments worth remembering, and
makes an album for each one with a friendly name, such as
*Mediterranean trip 2024*, *Walk in the Lake District with Emma*,
*Christmas 2023* or *Jack's 5th birthday*.

- **Finds:** trips and days out (away from Home Assistant's home location),
  holidays (Christmas, Easter, public holidays...), birthdays of people Immich
  knows, and days with an unusual burst of photos.
- **Picks the best photos:** favours people (face recognition), scenery and
  landmarks (smart search), favourites and sharp, well-exposed shots, spread
  across the whole event.
- **Leaves out clutter:** screenshots, receipts and paperwork, and photos of
  jobs around the house.
- **Stacks near-identical shots** in Immich, with the best on top: the one
  where most people are facing the camera with their eyes open, then the
  sharpest.
- **Names albums** from Immich's places, people and dates, optionally polished
  by whatever AI you've set up in Home Assistant.
- **Easy to undo:** albums are marked as made by this app, and one switch
  removes them all.

See [DOCS.md](DOCS.md) for setup and options.

> **Unofficial:** this is a community app and is **not affiliated with,
> endorsed by, or supported by the Immich project**. It talks to your own
> Immich server through Immich's public API. See
> [../DISCLAIMER.md](../DISCLAIMER.md).
