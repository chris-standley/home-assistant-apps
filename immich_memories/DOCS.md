# Immich Memories

Apple Photos style memories for [Immich](https://immich.app/). Once a day this
app looks through your Immich library, finds trips, days out, holidays,
birthdays and busy days, picks the best photos from each and makes an album
with a friendly name.

It works with the Immich server you already run as an app on this Home
Assistant (or any Immich server it can reach), through Immich's API. Your photos
are never modified or moved; the app only creates albums and stacks.

## Setup

1. **In Immich**, make sure **Machine Learning** is on, with **Facial
   Recognition** and **Smart Search** enabled (Administration → Settings →
   Machine Learning), and that the jobs have run on your library. Name the
   people you want to appear in album titles, and add birthdays to see
   birthday memories.
2. **Create an API key** in Immich: your avatar → **Account Settings → API
   Keys → New API Key**. Give it these permissions (or **all**):
   `asset.read`, `asset.view`, `album.create`, `album.read`, `album.update`,
   `album.delete`, `albumAsset.create`, `stack.create`, `stack.delete`,
   `person.read`, `user.read`.
   The albums are created in that user's library.
3. **Install this app**, paste the key into **Immich API key** on the
   **Configuration** tab, and start it.
4. Check the **Log** tab. The first run looks at your whole library and makes
   up to 20 albums, newest first; the rest follow on later runs. To see what it
   would do first, turn on **Dry run**.

### Finding Immich

Leave **Immich URL** empty and the app looks for an Immich app on this Home
Assistant and connects to it directly. If it can't find it (the log says
so), enter Immich's address, for example `http://homeassistant.local:2283`, or
the app's hostname from its **Info** page, e.g. `http://abc123-immich:2283`.

## How it decides

**Events**

| Memory | When |
| --- | --- |
| Trip | Two or more days with most photos taken further than *Home radius* from Home Assistant's home (Settings → System → General). Short gaps without photos are bridged. |
| Day out | One such day. |
| Holiday | Christmas (24–26 Dec), New Year's Eve, Easter weekend, Halloween, Mother's and Father's Day, Bonfire Night (UK), and your country's public holidays, at home. A trip over Christmas becomes *Christmas in …*. |
| Birthday | The birthday of someone Immich knows (with a birth date set), when they're in at least three photos that day. |
| Busy day | A day with at least *Photos needed for a busy day*, and *Busy day factor* times the usual number for the weeks around it. |

Each needs a minimum number of photos (see the options). Events from the last
two days are left until the next run, in case they're still going on.

**Leaving out clutter**

- **Screenshots:** file names like *Screenshot…*, PNGs and images at exact
  phone/monitor screen sizes with no camera information, and images Immich's
  smart search says look like screenshots.
- **Receipts, paperwork and household jobs:** images smart search says look
  like receipts, letters, forms, labels, whiteboards or DIY jobs (pipes,
  wiring, damp walls...), **unless someone is in the photo**.

**Choosing photos**

Near-identical photos (bursts, Immich's duplicate detection, or shots taken a
minute apart that look the same) are grouped. In each group the app looks at
Immich's preview of every shot and picks the best:

1. **People:** faces are found with OpenCV's YuNet face detector. For each face
   it checks whether the person is **facing the camera** (from where the nose
   sits between the eyes) and whether their **eyes are open**. The shot where
   the most people are looking at the camera with their eyes open wins, then
   the one with the **sharpest faces**, then smiles.
2. **No people:** the sharpest, best exposed shot.
3. A **favourite** or higher **star rating** always wins.

If **Stack similar photos** is on, the group becomes an Immich stack with that
photo on top, so the timeline shows only the best one.

Then each moment is scored, favouring favourites, named people, people facing
the camera, scenery, landmarks and sunsets (smart search), and sharp,
well-exposed photos. The album gets a spread of the best across the whole event
(up to *Most photos per album*), and the best one becomes its cover.

**Names**

A name is always built from Immich's data: the main place (city, region,
country, or an area such as *Mediterranean* when a trip spans several
countries), named people who are in many of the photos, the holiday, and what
smart search says the photos show (beach, hiking, snow, a cruise ship...). For
example *Trip to Rome 2024*, *Walk in Ambleside with Emma*, *Christmas 2024*.

With **AI album names** on, the app then asks Home Assistant's AI to polish
it, giving it the same facts plus a day-by-day itinerary for trips. This is
how *Ambleside, Grasmere and Keswick* can become *the Lake District*, or a
port-a-day trip *a Mediterranean cruise*. It uses, in order:

1. **AI Task** (`ai_task.generate_data`, Home Assistant 2025.8 or later): your
   default AI Task entity (Settings → System → General → AI suggestions), or
   the one in **AI Task entity**.
2. The **Conversation agent** you name, e.g. `conversation.chatgpt` or
   `conversation.ollama`.

If neither answers, or the answer doesn't look like a title, the template name
is used. Facts sent to the AI are place names, first names, dates and scene
words, never photos. If your AI runs in the cloud, those facts go to that
provider.

Every album's description ends with *Made by Immich Memories*.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| Immich URL | *(find it)* | Immich's address, if it can't be found automatically. |
| Immich API key | | Required. See Setup. |
| Daily run time | `03:30` | When to look for new memories, in Home Assistant's time zone. |
| Run when started | on | Also run as soon as the app starts. |
| Dry run | off | Log what it would make without changing anything. |
| AI album names | on | Polish names with Home Assistant's AI. |
| AI Task entity | *(default)* | Which AI Task entity to use; `none` to skip AI Task. |
| Conversation agent | | A conversation agent to use if AI Task isn't available. |
| Stack similar photos | on | Stack near-identical shots with the best on top. |
| Most photos per album | `50` | Albums get about 4×√(photos) photos, up to this. |
| Most new albums per run | `20` | Spreads a big first run over several days. `0` = no limit. |
| Photos needed for a trip or day out | `15` | |
| Photos needed for a holiday or birthday | `10` | |
| Photos needed for a busy day | `25` | |
| Busy day factor | `3` | How many times busier than usual a day must be. |
| Home radius (km) | `40` | Further than this from home counts as away. |
| Holiday country / region | *(Home Assistant's)* | e.g. `GB` and `ENG`. |
| Leave out of names | | People never named in titles, usually yourself. |
| Earliest date | | Ignore photos before this date (`YYYY-MM-DD`). |
| Remove created albums | off | Undo (see below). |

## Undo and changes

- **Delete an album** you don't like in Immich and it won't be made again.
- **Remove created albums:** turn it on and restart the app to delete every
  album and stack it made (your photos stay where they are). It then stops;
  turn it off again to start over.
- The app remembers what it has made in its own storage, so reruns only add
  new memories.

## Notes

- Albums are owned by the user whose API key you use, and aren't shared.
- Analysing photos downloads Immich's preview of each photo in an event once
  (the results are cached), so the first run on a big library takes a while.
- Smart search ranks photos but doesn't say how alike they are, so the app
  treats the closest few percent of the library to each description as a
  match. If a receipt or screenshot slips through, archive it in Immich:
  archived photos are always skipped.

## Support

Issues: https://github.com/chris-standley/home-assistant-apps/issues
