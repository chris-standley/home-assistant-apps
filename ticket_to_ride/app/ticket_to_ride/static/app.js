// Ticket to Ride scorer: the page. Plain JavaScript, no build step.
// The current game lives in localStorage so a reload (or the phone locking)
// doesn't lose it. Scoring happens in the page; the server only serves the
// maps and passes photos to Home Assistant's AI.
(() => {
  "use strict";

  const PLAYER_HEX = { red: "#d62828", blue: "#1d6fd8", green: "#2a9d3a", yellow: "#f2c014", black: "#222222" };
  const ROUTE_HEX = {
    red: "#e04848", blue: "#3d7fe0", green: "#45a85a", yellow: "#f0cd3a", black: "#3a3a3a",
    white: "#f7f7f2", orange: "#f08a24", pink: "#e872b4", gray: "#a39d94",
  };
  const STORE = "ttr-game-v1";
  const $ = (sel) => document.querySelector(sel);
  const el = (tag, attrs = {}, ...kids) => {
    const node = tag.startsWith("svg:")
      ? document.createElementNS("http://www.w3.org/2000/svg", tag.slice(4))
      : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "on") for (const [ev, fn] of Object.entries(v)) node.addEventListener(ev, fn);
      else if (k === "text") node.textContent = v;
      else if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v);
    }
    for (const kid of kids) if (kid !== null && kid !== undefined) node.append(kid);
    return node;
  };

  let maps = [];
  let map = null; // full map JSON for the current game
  let status = { ai: false };
  let result = null; // last score from the server
  let brush = null; // colour being painted, "erase", or "station"
  let stationColor = null;
  let ticketPlayer = null;
  let zoom = 1;
  let game = load();

  function blankGame(mapId = "usa", players) {
    return {
      map: mapId,
      players: players || [
        { color: "red", name: "", tickets: [], stations: [] },
        { color: "blue", name: "", tickets: [], stations: [] },
      ],
      routes: {},
      step: "players",
    };
  }
  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE));
      if (saved && saved.players) return saved;
    } catch (e) { /* private browsing or corrupt: start fresh */ }
    return blankGame();
  }
  function save() {
    try { localStorage.setItem(STORE, JSON.stringify(game)); } catch (e) { /* ignore */ }
  }
  const playerName = (p) => p.name || p.color[0].toUpperCase() + p.color.slice(1);
  const findPlayer = (color) => game.players.find((p) => p.color === color);

  // -- server ---------------------------------------------------------------

  async function api(path, opts = {}) {
    const resp = await fetch(path, opts);
    let data = null;
    try { data = await resp.json(); } catch (e) { /* not JSON */ }
    if (!resp.ok) throw new Error((data && data.error) || `Something went wrong (HTTP ${resp.status}).`);
    return data;
  }

  // Scoring runs right here on the phone (scoring.js), so it's instant and
  // works without a connection once the page has loaded.
  function changed() {
    save();
    rescore();
  }
  function rescore() {
    if (!map) return;
    result = TTRScoring.scoreGame(map, game);
    renderCounts();
    renderTickets();
    renderScores();
    drawLongest();
  }

  // Shrink a photo before upload: phones take 12MP+ images, the AI needs far less.
  async function shrink(file, maxDim = 2048) {
    let source;
    try {
      source = await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (e) {
      source = await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error("That file isn't a photo this browser can open."));
        img.src = URL.createObjectURL(file);
      });
    }
    const w = source.width, h = source.height;
    const scale = Math.min(1, maxDim / Math.max(w, h));
    const canvas = el("canvas", { width: Math.round(w * scale), height: Math.round(h * scale) });
    canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
  }

  async function sendPhoto(file, path, message) {
    busy(message);
    try {
      const blob = await shrink(file);
      return await api(path, { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob });
    } finally {
      busy(null);
    }
  }

  function busy(text) {
    $("#busy").hidden = !text;
    if (text) $("#busy-text").textContent = text;
  }
  let toastTimer = null;
  function toast(text, ms = 5000) {
    const t = $("#toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, ms);
  }

  // -- steps ----------------------------------------------------------------

  function go(step) {
    if (step !== "players" && game.players.length < 1) {
      toast("Pick at least one player first.");
      step = "players";
    }
    game.step = step;
    save();
    document.querySelectorAll(".step").forEach((s) => s.classList.toggle("on", s.id === `step-${step}`));
    document.querySelectorAll("#steps button").forEach((b) => b.classList.toggle("on", b.dataset.step === step));
    if (step === "board") renderBoard();
    if (step === "tickets") renderTickets();
    window.scrollTo(0, 0);
  }

  // -- players --------------------------------------------------------------

  function renderPlayers() {
    const choice = $("#map-choice");
    choice.replaceChildren(
      ...maps.map((m) =>
        el("label", {},
          el("input", {
            type: "radio", name: "map", value: m.id, checked: m.id === game.map,
            on: { change: () => switchMap(m.id) },
          }),
          m.name)
      )
    );
    const list = $("#player-list");
    list.replaceChildren(
      ...map.player_colors.map((color) => {
        const p = findPlayer(color);
        const row = el("div", { class: "player-row" + (p ? "" : " off") });
        const swatch = el("span", {
          class: "swatch", style: `background:${PLAYER_HEX[color]}`, role: "checkbox",
          "aria-checked": p ? "true" : "false", "aria-label": color, text: p ? "✓" : "",
          on: { click: () => togglePlayer(color) },
        });
        const name = el("input", {
          type: "text", placeholder: color[0].toUpperCase() + color.slice(1), value: p ? p.name : "",
          autocomplete: "off", autocapitalize: "words",
          on: {
            focus: () => { if (!findPlayer(color)) togglePlayer(color, true); },
            input: (e) => { const q = findPlayer(color); if (q) { q.name = e.target.value; changed(); } },
          },
        });
        row.append(swatch, name);
        return row;
      })
    );
  }

  function togglePlayer(color, keepFocus) {
    const i = game.players.findIndex((p) => p.color === color);
    if (i >= 0) {
      game.players.splice(i, 1);
      for (const [rid, c] of Object.entries(game.routes)) if (c === color) delete game.routes[rid];
    } else {
      game.players.push({ color, name: "", tickets: [], stations: [] });
      game.players.sort((a, b) => map.player_colors.indexOf(a.color) - map.player_colors.indexOf(b.color));
    }
    changed();
    if (!keepFocus) renderPlayers();
    else document.querySelectorAll(".player-row").forEach((row, idx) => {
      const c = map.player_colors[idx];
      row.classList.toggle("off", !findPlayer(c));
      row.querySelector(".swatch").textContent = findPlayer(c) ? "✓" : "";
    });
  }

  async function switchMap(id) {
    if (id === game.map) return;
    const hasWork = Object.keys(game.routes).length || game.players.some((p) => p.tickets.length);
    if (hasWork && !confirm("Switch map? The routes and tickets entered so far will be cleared.")) {
      renderPlayers();
      return;
    }
    game = blankGame(id, game.players.map((p) => ({ color: p.color, name: p.name, tickets: [], stations: [] })));
    await loadMap(id);
    renderPlayers();
    changed();
  }

  async function loadMap(id) {
    map = await api(`api/maps/${encodeURIComponent(id)}`);
    map.routeById = Object.fromEntries(map.routes.map((r) => [r.id, r]));
    game.players = game.players.filter((p) => map.player_colors.includes(p.color));
    drawn = null;
  }

  // -- board ----------------------------------------------------------------

  let drawn = null; // map id the SVG was drawn for

  function renderBoard() {
    const hint = $("#board-hint");
    hint.textContent = status.ai
      ? "Take the photo from straight above, with the whole board in frame. Then check it: pick a colour and tap a route to fix it."
      : "Pick a colour, then tap each route that player claimed. Tap again to clear it.";
    if (!brush || (brush !== "erase" && brush !== "station" && !findPlayer(brush))) brush = game.players[0]?.color || "erase";
    if (!stationColor || !findPlayer(stationColor)) stationColor = game.players[0]?.color;
    renderPalette();
    if (drawn !== map.id) drawMap();
    paintRoutes();
    renderCounts();
  }

  function renderPalette() {
    const pal = $("#palette");
    const items = game.players.map((p) =>
      el("button", { class: brush === p.color ? "on" : "", on: { click: () => { brush = p.color; renderPalette(); } } },
        el("span", { class: "swatch", style: `background:${PLAYER_HEX[p.color]}` }),
        playerName(p))
    );
    items.push(
      el("button", { class: "eraser" + (brush === "erase" ? " on" : ""), on: { click: () => { brush = "erase"; renderPalette(); } } },
        el("span", { class: "swatch", text: "✕" }), "Clear")
    );
    if (map.stations) {
      items.push(
        el("button", {
          class: "station" + (brush === "station" ? " on" : ""),
          on: { click: () => {
            if (brush === "station") {
              // Tap again to cycle whose stations you're placing.
              const i = game.players.findIndex((p) => p.color === stationColor);
              stationColor = game.players[(i + 1) % game.players.length].color;
            }
            brush = "station";
            renderPalette();
          } },
        },
        el("span", { class: "swatch", text: "⌂", style: brush === "station" ? `color:${PLAYER_HEX[stationColor]}` : "" }),
        brush === "station" ? `${playerName(findPlayer(stationColor))}'s stations` : "Stations")
      );
    }
    pal.replaceChildren(...items);
  }

  function laneOffset(r) {
    return r.lane === 0 ? 0 : r.lane === 1 ? -5.5 : 5.5;
  }

  function routeGeometry(r) {
    const [x1, y1] = map.cities[r.a];
    const [x2, y2] = map.cities[r.b];
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy);
    const ux = dx / len, uy = dy / len;
    const off = laneOffset(r);
    const nx = -uy * off, ny = ux * off;
    const pad = 10;
    return {
      x1: x1 + ux * pad + nx, y1: y1 + uy * pad + ny,
      x2: x2 - ux * pad + nx, y2: y2 - uy * pad + ny,
      len: len - pad * 2,
    };
  }

  function drawMap() {
    const svg = $("#map");
    const [w, h] = map.size;
    svg.setAttribute("viewBox", `-10 -10 ${w + 20} ${h + 20}`);
    svg.replaceChildren();
    const longest = el("svg:g", { id: "longest-layer" });
    const tracks = el("svg:g");
    const hits = el("svg:g");
    for (const r of map.routes) {
      const g = routeGeometry(r);
      const gap = 2.5;
      const seg = (g.len - gap * (r.length - 1)) / r.length;
      tracks.append(el("svg:line", {
        class: "track", id: `t-${r.id}`, x1: g.x1, y1: g.y1, x2: g.x2, y2: g.y2,
        "stroke-dasharray": `${seg} ${gap}`,
      }));
      if (r.kind === "ferry") {
        const mx = (g.x1 + g.x2) / 2, my = (g.y1 + g.y2) / 2;
        tracks.append(el("svg:circle", { cx: mx, cy: my, r: 3, fill: "#fff", stroke: "#333", "stroke-width": 1, "pointer-events": "none" }));
      }
      const hit = el("svg:line", {
        class: "hit", x1: g.x1, y1: g.y1, x2: g.x2, y2: g.y2,
        on: { click: () => tapRoute(r.id) },
      });
      hit.append(el("svg:title", { text: `${r.a} – ${r.b} (${r.length}${r.kind ? ", " + r.kind : ""})` }));
      hits.append(hit);
    }
    const cities = el("svg:g");
    const stations = el("svg:g", { id: "station-layer" });
    for (const [name, [x, y]] of Object.entries(map.cities)) {
      cities.append(el("svg:circle", { class: "city", cx: x, cy: y, r: 7 }));
      const anchor = x > map.size[0] - 90 ? "end" : x < 70 ? "start" : "middle";
      cities.append(el("svg:text", { class: "label", x, y: y - 11, "text-anchor": anchor, text: name }));
      cities.append(el("svg:circle", { class: "city-hit", cx: x, cy: y, r: 16, on: { click: () => tapCity(name) } }));
    }
    svg.append(longest, tracks, hits, cities, stations);
    drawn = map.id;
    applyZoom();
  }

  function paintRoutes() {
    for (const r of map.routes) {
      const line = document.getElementById(`t-${r.id}`);
      if (!line) continue;
      const owner = game.routes[r.id];
      if (owner) {
        line.setAttribute("stroke", PLAYER_HEX[owner]);
        line.setAttribute("stroke-width", 9);
        line.setAttribute("opacity", 1);
      } else {
        line.setAttribute("stroke", ROUTE_HEX[r.color] || "#999");
        line.setAttribute("stroke-width", 5);
        line.setAttribute("opacity", r.color === "white" ? 1 : 0.55);
      }
    }
    const layer = document.getElementById("station-layer");
    if (layer) {
      layer.replaceChildren();
      const placed = {};
      for (const p of game.players) {
        for (const city of p.stations || []) {
          const n = (placed[city] = (placed[city] || 0) + 1) - 1;
          const [x, y] = map.cities[city];
          const sx = x + 9 + n * 12, sy = y + 4;
          layer.append(el("svg:path", {
            d: `M${sx} ${sy} l6 -6 l6 6 v7 h-12 z`, fill: PLAYER_HEX[p.color], stroke: "#fff", "stroke-width": 1.5,
            "pointer-events": "none",
          }));
        }
      }
    }
  }

  function drawLongest() {
    const layer = document.getElementById("longest-layer");
    if (!layer || !result) return;
    layer.replaceChildren();
    for (const p of result.players) {
      if (!p.longest_bonus) continue;
      for (const rid of p.longest_path_routes) {
        const r = map.routeById[rid];
        if (!r) continue;
        const g = routeGeometry(r);
        layer.append(el("svg:line", { class: "longest", x1: g.x1, y1: g.y1, x2: g.x2, y2: g.y2 }));
      }
    }
  }

  function tapRoute(rid) {
    if (brush === "station") {
      toast("Tap a city to place a station. Pick a colour to mark routes.");
      return;
    }
    const r = map.routeById[rid];
    if (brush === "erase" || game.routes[rid] === brush) {
      delete game.routes[rid];
    } else {
      // A player can only own one lane of a double route.
      for (const other of map.routes) {
        if (other.id !== rid && other.lane && r.lane &&
            ((other.a === r.a && other.b === r.b) || (other.a === r.b && other.b === r.a)) &&
            game.routes[other.id] === brush) {
          delete game.routes[other.id];
        }
      }
      game.routes[rid] = brush;
    }
    paintRoutes();
    changed();
  }

  function tapCity(city) {
    if (brush !== "station" || !map.stations) return;
    const p = findPlayer(stationColor);
    if (!p) return;
    p.stations = p.stations || [];
    const i = p.stations.indexOf(city);
    if (i >= 0) p.stations.splice(i, 1);
    else if (p.stations.length >= map.stations) {
      toast(`${playerName(p)} only has ${map.stations} stations. Tap one of theirs to remove it.`);
      return;
    } else p.stations.push(city);
    paintRoutes();
    changed();
  }

  function applyZoom() {
    $("#map").style.width = `${zoom * 100}%`;
  }

  function renderCounts() {
    const box = $("#train-counts");
    if (!map) return;
    const byColor = Object.fromEntries((result?.players || []).map((p) => [p.color, p]));
    box.replaceChildren(
      ...game.players.map((p) => {
        const s = byColor[p.color];
        const used = s ? s.trains_used : 0;
        const left = map.trains_per_player - used;
        const extra = map.stations ? ` · ${(p.stations || []).length}/${map.stations} stations` : "";
        return el("div", { class: "count" },
          el("span", { class: "swatch", style: `background:${PLAYER_HEX[p.color]}` }),
          el("div", {},
            el("b", { text: `${playerName(p)}: ${used} trains` }),
            el("small", { text: `${left} should be left over${extra}` })));
      })
    );
  }

  async function boardPhoto(file) {
    const players = game.players.map((p) => p.color).join(",");
    let data;
    try {
      data = await sendPhoto(file, `api/read-board?map=${game.map}&players=${players}`,
        "Reading the board… this can take up to a minute.");
    } catch (e) {
      toast(e.message, 8000);
      return;
    }
    game.routes = data.routes || {};
    if (map.stations) for (const p of game.players) p.stations = (data.stations || {})[p.color] || [];
    paintRoutes();
    changed();
    const n = Object.keys(game.routes).length;
    toast(`Found ${n} claimed route${n === 1 ? "" : "s"}. Check the trains left over against each count below, and tap any route that's wrong.`, 9000);
  }

  // -- tickets --------------------------------------------------------------

  function renderTickets() {
    if (!map) return;
    if (!ticketPlayer || !findPlayer(ticketPlayer)) ticketPlayer = game.players[0]?.color;
    const p = findPlayer(ticketPlayer);
    $("#ticket-tabs").replaceChildren(
      ...game.players.map((q) =>
        el("button", { class: q.color === ticketPlayer ? "on" : "", on: { click: () => { ticketPlayer = q.color; renderTickets(); } } },
          el("span", { class: "swatch", style: `background:${PLAYER_HEX[q.color]}` }),
          `${playerName(q)} (${q.tickets.length})`))
    );
    if (!p) return;
    $("#ticket-photo-label").textContent = `Photograph ${playerName(p)}'s tickets`;

    const scored = result?.players.find((s) => s.color === p.color);
    const list = $("#ticket-list");
    if (!p.tickets.length) {
      list.replaceChildren(el("li", { class: "empty", text: "No tickets yet." }));
    } else {
      list.replaceChildren(
        ...p.tickets.map((t, i) => {
          const s = scored?.tickets.find((x) => x.a === t.a && x.b === t.b);
          const done = s ? s.completed : null;
          return el("li", { class: done === null ? "" : done ? "done" : "missed" },
            el("span", { class: "status", text: done === null ? "…" : done ? "✓" : "✗" }),
            el("span", { class: "name" }, `${t.a} – ${t.b}`,
              el("small", { text: done === null ? "" : done ? `Connected: +${t.points}` : `Not connected: −${t.points}` })),
            el("input", {
              type: "number", min: 0, max: 40, value: t.points, inputmode: "numeric", "aria-label": "Points",
              on: { change: (e) => { t.points = Math.max(0, parseInt(e.target.value, 10) || 0); changed(); } },
            }),
            el("button", { class: "remove", "aria-label": "Remove", text: "×", on: { click: () => { p.tickets.splice(i, 1); changed(); renderTickets(); } } }));
        })
      );
    }
    renderTicketSelect();
  }

  function renderTicketSelect() {
    const sel = $("#ticket-select");
    if (sel.dataset.map !== map.id) {
      const sorted = [...map.tickets].sort((x, y) => `${x.a} ${x.b}`.localeCompare(`${y.a} ${y.b}`));
      sel.replaceChildren(
        el("option", { value: "", text: "Add a ticket…" }),
        ...sorted.map((t) => el("option", { value: t.id, text: `${t.a} – ${t.b} (${t.points})${t.long ? " long" : ""}` })),
        el("option", { value: "custom", text: "Another ticket (expansion)…" })
      );
      const cities = Object.keys(map.cities).sort();
      for (const id of ["#custom-a", "#custom-b"]) {
        $(id).replaceChildren(el("option", { value: "", text: "City" }), ...cities.map((c) => el("option", { value: c, text: c })));
      }
      sel.dataset.map = map.id;
    }
    sel.value = "";
  }

  function addTicket(t) {
    const p = findPlayer(ticketPlayer);
    if (!p) return;
    if (p.tickets.some((x) => (x.a === t.a && x.b === t.b) || (x.a === t.b && x.b === t.a))) {
      toast(`${playerName(p)} already has ${t.a} – ${t.b}.`);
      return;
    }
    p.tickets.push({ a: t.a, b: t.b, points: t.points });
    changed();
    renderTickets();
  }

  async function ticketPhoto(file) {
    const p = findPlayer(ticketPlayer);
    if (!p) return;
    let data;
    try {
      data = await sendPhoto(file, `api/read-tickets?map=${game.map}`, `Reading ${playerName(p)}'s tickets…`);
    } catch (e) {
      toast(e.message, 8000);
      return;
    }
    const found = data.tickets || [];
    let added = 0;
    for (const t of found) {
      if (!p.tickets.some((x) => (x.a === t.a && x.b === t.b) || (x.a === t.b && x.b === t.a))) {
        p.tickets.push({ a: t.a, b: t.b, points: t.points });
        added++;
      }
    }
    changed();
    renderTickets();
    toast(found.length
      ? `Added ${added} ticket${added === 1 ? "" : "s"}. Check them against the cards, and fix any points.`
      : "Couldn't see any tickets. Try a closer photo, or add them from the list.", 7000);
  }

  // -- scores ---------------------------------------------------------------

  function renderScores() {
    if (!result) return;
    $("#warnings").replaceChildren(...result.warnings.map((w) => el("li", { text: w })));
    const name = result.longest_route_name;
    $("#score-list").replaceChildren(
      ...result.players.map((s) => {
        const sign = (n) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0");
        const rows = [
          ["Routes", `${s.routes} routes, ${s.trains_used} trains`, s.route_points],
          ["Tickets", `${s.tickets_completed} of ${s.tickets.length} completed`, s.ticket_points],
        ];
        if (map.stations) {
          rows.push(["Stations kept", `${map.stations - s.stations_used} unused` +
            (s.borrowed_routes.length ? `; borrowed ${s.borrowed_routes.map((id) => {
              const r = map.routeById[id];
              return r ? `${r.a}–${r.b}` : id;
            }).join(", ")}` : ""), s.station_points]);
        }
        rows.push([name, `longest path ${s.longest_path}`, s.longest_bonus]);
        const table = el("table", {});
        for (const [label, detail, pts] of rows) {
          table.append(el("tr", {}, el("td", { text: label }), el("td", { text: sign(pts) })));
          table.append(el("tr", { class: "detail" }, el("td", { colspan: 2, text: detail })));
        }
        const missed = s.tickets.filter((t) => !t.completed);
        if (missed.length) {
          table.append(el("tr", { class: "detail" }, el("td", { colspan: 2, text: `Missed: ${missed.map((t) => `${t.a}–${t.b}`).join(", ")}` })));
        }
        return el("li", { class: "score" + (s.rank === 1 ? " first" : "") },
          el("div", { class: "score-head" },
            el("span", { class: "rank", text: `${s.rank}.` }),
            el("span", { class: "swatch", style: `background:${PLAYER_HEX[s.color]}` }),
            el("span", { class: "who", text: s.name }),
            el("span", { class: "total", text: s.total })),
          table);
      })
    );
  }

  // -- start ----------------------------------------------------------------

  function wire() {
    document.querySelectorAll("#steps button").forEach((b) => b.addEventListener("click", () => go(b.dataset.step)));
    document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => go(b.dataset.goto)));
    $("#board-photo").addEventListener("change", (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) boardPhoto(f); });
    $("#ticket-photo").addEventListener("change", (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) ticketPhoto(f); });
    $("#zoom-in").addEventListener("click", () => { zoom = Math.min(3, zoom + 0.5); applyZoom(); });
    $("#zoom-out").addEventListener("click", () => { zoom = Math.max(1, zoom - 0.5); applyZoom(); });
    $("#clear-board").addEventListener("click", () => {
      if (!confirm("Clear every route on the board?")) return;
      game.routes = {};
      for (const p of game.players) p.stations = [];
      paintRoutes();
      changed();
    });
    $("#ticket-select").addEventListener("change", (e) => {
      const v = e.target.value;
      $("#custom-ticket").hidden = v !== "custom";
      if (!v || v === "custom") return;
      const t = map.tickets.find((x) => x.id === v);
      if (t) addTicket(t);
    });
    $("#custom-add").addEventListener("click", () => {
      const a = $("#custom-a").value, b = $("#custom-b").value;
      const points = parseInt($("#custom-points").value, 10) || 0;
      if (!a || !b || a === b) { toast("Pick two different cities."); return; }
      addTicket({ a, b, points });
      $("#custom-ticket").hidden = true;
      $("#custom-points").value = "";
    });
    $("#new-game").addEventListener("click", () => {
      if (!confirm("Start a new game? The same players stay; the board and tickets are cleared.")) return;
      game = blankGame(game.map, game.players.map((p) => ({ color: p.color, name: p.name, tickets: [], stations: [] })));
      result = null;
      changed();
      go("players");
      renderPlayers();
    });
  }

  async function start() {
    wire();
    try {
      [maps, status] = await Promise.all([api("api/maps"), api("api/status").catch(() => ({ ai: false }))]);
      if (!maps.some((m) => m.id === game.map)) game = blankGame(maps[0].id);
      await loadMap(game.map);
    } catch (e) {
      toast(`Couldn't load the maps: ${e.message}`, 15000);
      return;
    }
    document.body.classList.toggle("no-ai", !status.ai);
    renderPlayers();
    go(game.step || "players");
    rescore();
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  }

  start();
})();
