# Changelog

## 0.1.2

- Fewer similar photos. Similar shots are now matched by their colours and
  layout as well as fine detail, so reframed or zoomed shots of the same thing
  are stacked, not just bursts. Albums also skip a photo when they already have
  one of the same scene from around the same time, so they show a range of
  moments instead of repeats. Album sizes are unchanged.
- New **Similar photo filtering** option: light, normal (default) or strong.
- Fixed album names calling a day someone's birthday when it isn't: a party or
  a cake no longer makes the AI (or the template) name it after a birthday.
- Photos are analysed again once after this update, to measure what they look
  like.

## 0.1.1

- **Immich IP address** option: connect to Immich by IP while keeping its
  hostname, for when Home Assistant can't look the hostname up. HTTPS
  certificate checks keep working.
- **Verify HTTPS certificate** option, to allow self-signed certificates.
- If the Immich URL can't be reached, the app now falls back to the Immich app
  on this Home Assistant, and the log says why the URL failed (hostname not
  found, certificate not accepted, nothing listening) and what to try.

## 0.1.0

- First release. Finds trips, days out, holidays, birthdays and unusually busy
  days in Immich and makes an album for each, with a friendly name (optionally
  polished by Home Assistant's AI).
- Leaves out screenshots, receipts and paperwork, and photos of jobs around the
  house.
- Stacks near-identical shots with the best one on top: most people facing the
  camera with their eyes open, then the sharpest.
- Collections that grow each year: holiday seasons (*Christmas through the
  years*), birthdays, holidays in a country (*Holidays in Norway*) and repeat
  visits to an area (*Trips to the Lake District*).
- Dry run, and a one-switch undo that removes everything it made.
