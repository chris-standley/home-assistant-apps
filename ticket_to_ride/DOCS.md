# Ticket to Ride Scorer

Work out the final scores of a game of Ticket to Ride from your phone. You take
a photo of the finished board and of each player's destination tickets; Home
Assistant's AI reads them, you check and fix what it read, and the app adds up
the scores.

## Setup

1. **An AI that can see photos.** Photos are read by an AI Task entity, so you
   need an AI integration set up in Home Assistant (for example Anthropic,
   OpenAI or Google Generative AI) with a model that accepts images. Set it as
   the default under **Settings → System → General → AI suggestions**, or name
   the entity in this app's **AI Task entity** option.
   Without one, the app still works: you tap the routes in by hand.
2. **Install and start this app.** It appears in the sidebar as
   **Ticket to Ride**. On iPhone, open it from the Home Assistant Companion app.

## Scoring a game

1. **Players:** pick the map and tick each player's train colour. Names are
   optional.
2. **Board:** tap **Photograph the board** and take one photo from straight
   above, with the whole board in frame and no glare. After a short wait the
   claimed routes appear on the map in each player's colour.
   - **Check it.** Under the map is each player's train count and how many
     cars they should have left over (45 minus the cars on the board). Ask each
     player to count their leftover cars: if a number doesn't match, a route is
     wrong.
   - **Fix it.** Pick a colour and tap a route to give it to that player; tap
     it again (or use **Clear**) to empty it. **+** zooms in.
   - **Europe stations:** tap **Stations** (tap again to switch player), then
     tap a city to place or remove that player's station.
3. **Tickets:** for each player, lay their tickets face up (completed and not)
   and tap **Photograph … tickets**. Each ticket shows ✓ if its cities are
   joined by that player's trains and ✗ if not. Add a missing ticket from the
   list, change its points, or remove one with ×. Tickets from expansions can
   be added with **Another ticket**.
4. **Scores:** everyone's total, ranked, with a breakdown. Warnings appear at
   the top for things that break the rules (such as one player on both lanes of
   a double route).

Your game is kept on the phone, so closing the page or locking the phone loses
nothing. **New game** keeps the players and clears the rest.

## How scores are worked out

| | USA | Europe |
| --- | --- | --- |
| Route of 1 / 2 / 3 / 4 / 5 / 6 / 8 cars | 1 / 2 / 4 / 7 / 10 / 15 / — | 1 / 2 / 4 / 7 / — / 15 / 21 |
| Ticket | + points if completed, − points if not | same |
| Longest continuous path | +10 | +10 (European Express) |
| Each station not placed | — | +4 |

- **Longest path** counts train cars along a single path that uses each route
  once (it may pass through a city more than once). Everyone tied for the
  longest gets the bonus.
- **Stations** (Europe): each placed station lets its owner use one route of
  another player's into that city for their tickets. The app picks the routes
  that give the best ticket score. Borrowed routes don't count towards the
  longest path.
- **Ties** are broken by most completed tickets, then (Europe) fewest stations
  placed, then the longest-path bonus.

Scoring runs in the page on your phone. Once the page has loaded, you can keep
scoring by hand even if the connection to Home Assistant drops; only reading
photos needs Home Assistant.

## Options

| Option | |
| --- | --- |
| **AI Task entity** | The AI that reads photos, e.g. `ai_task.claude_ai_task`. Leave empty for Home Assistant's default. |
| **Log level** | `debug` also logs the AI's answer for each photo, which helps when it misreads. |

### Opening it outside Home Assistant

Through Home Assistant (the sidebar or the Companion app) you're signed in and
it works away from home. To use it straight from Safari on your network, for
example to save it to your iPhone's home screen, set a port for `8099/tcp` on
the app's **Network** settings and open `http://homeassistant.local:<port>/`.
That address has **no login**, so only do this on a network you trust.

## Privacy

Photos are sent to whichever AI your AI Task entity uses. They are saved to
`/media/ticket_to_ride/` only while the AI reads them, then deleted.

## Adding a map

Each map is a JSON file in `app/ticket_to_ride/maps/` listing its cities (with
positions for drawing), routes (one entry per lane: cities, length, colour, and
optionally `tunnel` or `ferry`), tickets, and scoring rules (`route_points`,
`longest_route_bonus`, `stations`, `station_points`). Copy `usa.json` and
change it; the app picks it up automatically. The map data was entered by
hand, so if anything doesn't match your board, please open an issue.
