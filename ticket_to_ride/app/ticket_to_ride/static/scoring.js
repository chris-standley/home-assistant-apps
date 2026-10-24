// Final scoring for a game of Ticket to Ride. Runs in the browser (on the
// phone, no server needed) and under Node for the tests.
//
// A game is plain JSON:
//
//   {
//     map: "usa",
//     players: [
//       { color: "red", name: "Chris",
//         tickets: [{ a: "Denver", b: "El Paso", points: 4 }],
//         stations: ["Wien"] }                 // Europe only
//     ],
//     routes: { "denver-santa_fe": "red", ... } // route id -> player colour
//   }
//
// and the map is what /api/maps/<id> returns. Each player scores their claimed
// routes, plus or minus each destination ticket depending on whether its two
// cities are joined by their own trains, plus the longest-route bonus. On maps
// with train stations, each unused station is worth points, and each placed
// station lets its owner borrow one other player's route into that city for
// their tickets (we pick the routes that score best).
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.TTRScoring = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const titleCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const other = (r, city) => (city === r.a ? r.b : r.a);
  const samePair = (r, s) => (r.a === s.a && r.b === s.b) || (r.a === s.b && r.b === s.a);

  function connected(edges, a, b) {
    if (a === b) return true;
    const adj = new Map();
    for (const [x, y] of edges) {
      if (!adj.has(x)) adj.set(x, new Set());
      if (!adj.has(y)) adj.set(y, new Set());
      adj.get(x).add(y);
      adj.get(y).add(x);
    }
    const seen = new Set([a]);
    const stack = [a];
    while (stack.length) {
      const city = stack.pop();
      for (const next of adj.get(city) || []) {
        if (next === b) return true;
        if (!seen.has(next)) {
          seen.add(next);
          stack.push(next);
        }
      }
    }
    return false;
  }

  // The longest continuous path through these routes, using each route once.
  // Cities may be visited more than once (loops count). Players own at most
  // ~45 cars, so an exhaustive search is quick.
  function longestPath(routes) {
    const adj = new Map();
    for (const r of routes) {
      if (!adj.has(r.a)) adj.set(r.a, []);
      if (!adj.has(r.b)) adj.set(r.b, []);
      adj.get(r.a).push(r);
      adj.get(r.b).push(r);
    }
    let bestLen = 0;
    let bestPath = [];
    const used = new Set();
    const path = [];
    function walk(city, length) {
      if (length > bestLen) {
        bestLen = length;
        bestPath = path.slice();
      }
      for (const r of adj.get(city) || []) {
        if (used.has(r.id)) continue;
        used.add(r.id);
        path.push(r.id);
        walk(other(r, city), length + r.length);
        path.pop();
        used.delete(r.id);
      }
    }
    for (const city of adj.keys()) walk(city, 0);
    return { length: bestLen, routes: bestPath };
  }

  function ticketResults(edges, tickets) {
    return tickets.map((t) => ({ a: t.a, b: t.b, points: t.points, completed: connected(edges, t.a, t.b) }));
  }
  const ticketTotal = (results) => results.reduce((sum, t) => sum + (t.completed ? t.points : -t.points), 0);

  // Every combination of one choice from each list.
  function product(lists) {
    return lists.reduce((acc, list) => acc.flatMap((combo) => list.map((x) => combo.concat([x]))), [[]]);
  }

  function scoreGame(map, game) {
    const routeById = {};
    for (const r of map.routes) routeById[r.id] = r;
    const owners = {};
    for (const [rid, color] of Object.entries(game.routes || {})) if (routeById[rid] && color) owners[rid] = color;
    const players = game.players || [];
    const colors = players.map((p) => p.color);
    const stationsAllowed = map.stations || 0;
    const points = (len) => map.route_points[String(len)] || 0;
    const warnings = [];

    // Sanity checks the page can show next to the board.
    for (const [rid, color] of Object.entries(owners)) {
      if (!colors.includes(color)) {
        const r = routeById[rid];
        warnings.push(`${r.a}–${r.b} is marked ${color}, who isn't playing.`);
      }
    }
    const claimedLanes = Object.keys(owners).map((id) => routeById[id]).filter((r) => r.lane);
    const pairsDone = new Set();
    for (const r of claimedLanes) {
      const key = [r.a, r.b].sort().join("|");
      if (pairsDone.has(key)) continue;
      pairsDone.add(key);
      const lanes = claimedLanes.filter((s) => samePair(r, s));
      if (lanes.length < 2) continue;
      const [a, b] = [r.a, r.b].sort();
      if (new Set(lanes.map((s) => owners[s.id])).size === 1) {
        warnings.push(`${titleCase(owners[r.id])} has both lanes of ${a}–${b}; a player can only claim one.`);
      } else if (players.length < (map.double_routes_min_players || 4)) {
        warnings.push(
          `Both lanes of ${a}–${b} are claimed, but with fewer than ${map.double_routes_min_players || 4} ` +
            "players only one lane can be used."
        );
      }
    }

    const cities = map.cities || {};
    const results = players.map((p) => {
      const color = p.color;
      const name = p.name || titleCase(color);
      const mine = Object.entries(owners).filter(([, c]) => c === color).map(([id]) => routeById[id]);
      const routePoints = mine.reduce((s, r) => s + points(r.length), 0);
      const trainsUsed = mine.reduce((s, r) => s + r.length, 0);
      if (trainsUsed > map.trains_per_player) {
        warnings.push(`${name} has ${trainsUsed} train cars on the board, but only ${map.trains_per_player} in the box.`);
      }

      const edges = mine.map((r) => [r.a, r.b]);
      const tickets = (p.tickets || [])
        .filter((t) => cities[t.a] && cities[t.b])
        .map((t) => ({ a: t.a, b: t.b, points: Math.max(0, parseInt(t.points, 10) || 0) }));
      const stations = [...new Set((p.stations || []).filter((c) => cities[c]))].slice(0, stationsAllowed);

      let results = ticketResults(edges, tickets);
      let borrowed = [];
      if (stations.length && tickets.length) {
        // Each station may borrow one route of another player's into its city.
        const options = stations.map((city) => [null].concat(
          map.routes.filter((r) => (r.a === city || r.b === city) && owners[r.id] && owners[r.id] !== color)
        ));
        let best = ticketTotal(results);
        for (const combo of product(options)) {
          const extra = combo.filter(Boolean);
          if (!extra.length) continue;
          const trial = ticketResults(edges.concat(extra.map((r) => [r.a, r.b])), tickets);
          const total = ticketTotal(trial);
          if (total > best) {
            best = total;
            results = trial;
            borrowed = extra.map((r) => r.id);
          }
        }
      }

      const longest = longestPath(mine);
      const unusedStations = Math.max(0, stationsAllowed - stations.length);
      return {
        color,
        name,
        routes: mine.length,
        trains_used: trainsUsed,
        trains_left: map.trains_per_player - trainsUsed,
        route_points: routePoints,
        tickets: results,
        ticket_points: ticketTotal(results),
        tickets_completed: results.filter((t) => t.completed).length,
        stations_used: stations.length,
        station_points: unusedStations * (map.station_points || 0),
        borrowed_routes: borrowed,
        longest_path: longest.length,
        longest_path_routes: longest.routes,
        longest_bonus: 0,
      };
    });

    const top = Math.max(0, ...results.map((r) => r.longest_path));
    if (top > 0) for (const r of results) if (r.longest_path === top) r.longest_bonus = map.longest_route_bonus; // ties all score it
    for (const r of results) r.total = r.route_points + r.ticket_points + r.station_points + r.longest_bonus;

    // Official tie-breaks: most completed tickets, then (Europe) fewest
    // stations used, then the longest-route bonus.
    const key = (r) =>
      stationsAllowed
        ? [r.total, r.tickets_completed, -r.stations_used, r.longest_bonus]
        : [r.total, r.tickets_completed, r.longest_bonus];
    const cmp = (x, y) => {
      const a = key(x), b = key(y);
      for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return b[i] - a[i];
      return 0;
    };
    const ranked = results.slice().sort(cmp);
    ranked.forEach((r, i) => {
      r.rank = i > 0 && cmp(r, ranked[i - 1]) === 0 ? ranked[i - 1].rank : i + 1;
    });

    return { players: ranked, warnings, longest_route_name: map.longest_route_name };
  }

  return { scoreGame, longestPath, connected };
});
