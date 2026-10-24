# Ticket to Ride Scorer — Home Assistant App

Final scores for the board game **Ticket to Ride**, from your phone. At the end
of a game, photograph the board and each player's destination tickets; the app
reads them with Home Assistant's AI, shows you what it saw so you can fix
anything, and adds up everyone's score.

- **Routes:** the train cars on each route, with a per-player train count to
  check against the cars left over.
- **Tickets:** whether each ticket's two cities are joined by the player's
  trains, plus or minus its points.
- **Longest route** bonus (ties all score it), and on Europe, unused
  **stations** and the routes they borrow.
- **USA** and **Europe** maps. Maps are data files, so more can be added.
- **No AI? No problem:** tap the routes in and pick tickets from a list.
- Works in the Home Assistant Companion app on iPhone, through ingress.

See [DOCS.md](DOCS.md) for setup and how to use it.

> **Unofficial:** this is a fan-made scoring aid and is **not affiliated with,
> endorsed by, or supported by Days of Wonder or Asmodee**. Ticket to Ride is a
> trademark of Days of Wonder. See [../DISCLAIMER.md](../DISCLAIMER.md).
