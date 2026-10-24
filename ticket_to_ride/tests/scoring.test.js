// Scoring tests. Run through pytest (tests/test_scoring_js.py), which writes
// the maps to $TTR_MAPS in the shape the page receives them.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { scoreGame } = require("../app/ticket_to_ride/static/scoring.js");

const load = (id) => JSON.parse(fs.readFileSync(path.join(process.env.TTR_MAPS, `${id}.json`), "utf8"));
const usa = load("usa");
const europe = load("europe");

function rid(map, a, b, lane = 0) {
  const r = map.routes.find((r) => ((r.a === a && r.b === b) || (r.a === b && r.b === a)) && (!lane || r.lane === lane));
  if (!r) throw new Error(`no route ${a}-${b}`);
  return r.id;
}
const player = (result, color) => result.players.find((p) => p.color === color);

test("route points and trains", () => {
  const game = {
    players: [{ color: "red" }],
    routes: {
      [rid(usa, "Denver", "Santa Fe")]: "red", // 2 -> 2
      [rid(usa, "Seattle", "Helena")]: "red", // 6 -> 15
      [rid(usa, "Atlanta", "Nashville")]: "red", // 1 -> 1
    },
  };
  const p = player(scoreGame(usa, game), "red");
  assert.equal(p.route_points, 18);
  assert.equal(p.trains_used, 9);
  assert.equal(p.trains_left, 36);
});

test("tickets completed and failed", () => {
  const game = {
    players: [{
      color: "blue",
      tickets: [
        { a: "Denver", b: "El Paso", points: 4 },
        { a: "Kansas City", b: "Houston", points: 5 },
      ],
    }],
    routes: { [rid(usa, "Denver", "Santa Fe")]: "blue", [rid(usa, "Santa Fe", "El Paso")]: "blue" },
  };
  const p = player(scoreGame(usa, game), "blue");
  assert.deepEqual(p.tickets.map((t) => t.completed), [true, false]);
  assert.equal(p.ticket_points, -1);
  assert.equal(p.tickets_completed, 1);
});

test("a ticket connected through a long chain", () => {
  const chain = ["Los Angeles", "El Paso", "Dallas", "Little Rock", "Nashville", "Raleigh", "Washington", "New York"];
  const routes = {};
  for (let i = 1; i < chain.length; i++) routes[rid(usa, chain[i - 1], chain[i])] = "green";
  const game = { players: [{ color: "green", tickets: [{ a: "New York", b: "Los Angeles", points: 21 }] }], routes };
  assert.equal(player(scoreGame(usa, game), "green").ticket_points, 21);
});

test("longest route counts loops and ties all score", () => {
  const red = ["Denver", "Santa Fe", "El Paso", "Phoenix", "Denver"]; // loop: 2+2+3+5 = 12
  const game = { players: [{ color: "red" }, { color: "green" }, { color: "blue" }], routes: {} };
  for (let i = 1; i < red.length; i++) game.routes[rid(usa, red[i - 1], red[i])] = "red";
  game.routes[rid(usa, "Seattle", "Helena")] = "green";
  game.routes[rid(usa, "Helena", "Duluth")] = "green";
  game.routes[rid(usa, "Miami", "New Orleans")] = "blue";
  const result = scoreGame(usa, game);
  assert.equal(player(result, "red").longest_path, 12);
  assert.equal(player(result, "green").longest_path, 12);
  assert.equal(player(result, "red").longest_bonus, 10);
  assert.equal(player(result, "green").longest_bonus, 10);
  assert.equal(player(result, "blue").longest_bonus, 0);
});

test("longest route takes the best branch", () => {
  // A "T": Duluth-Chicago(3), Chicago-Pittsburgh(3), Chicago-Omaha(4), Omaha-Denver(4)
  const routes = {
    [rid(usa, "Chicago", "Duluth")]: "red",
    [rid(usa, "Chicago", "Pittsburgh", 1)]: "red",
    [rid(usa, "Chicago", "Omaha")]: "red",
    [rid(usa, "Omaha", "Denver")]: "red",
  };
  const p = player(scoreGame(usa, { players: [{ color: "red" }], routes }), "red");
  assert.equal(p.longest_path, 11);
  assert.equal(p.longest_path_routes.length, 3);
});

test("longest route is quick for a tangled network", () => {
  const pairs = [
    ["Kansas City", "Omaha", 1], ["Omaha", "Duluth", 1], ["Kansas City", "Oklahoma City", 1],
    ["Oklahoma City", "Dallas", 1], ["Dallas", "Houston", 1], ["Kansas City", "Saint Louis", 1],
    ["Saint Louis", "Little Rock"], ["Little Rock", "Dallas"], ["Little Rock", "Oklahoma City"],
    ["Saint Louis", "Nashville"], ["Nashville", "Atlanta"], ["Atlanta", "Raleigh", 1],
    ["Raleigh", "Washington", 1], ["Washington", "Pittsburgh"], ["Pittsburgh", "Raleigh"],
    ["Pittsburgh", "Nashville"], ["Raleigh", "Nashville"], ["Atlanta", "Charleston"], ["Charleston", "Raleigh"],
  ];
  const routes = Object.fromEntries(pairs.map(([a, b, lane]) => [rid(usa, a, b, lane), "red"]));
  const started = Date.now();
  const p = player(scoreGame(usa, { players: [{ color: "red" }], routes }), "red");
  assert.ok(p.longest_path > 25);
  assert.ok(Date.now() - started < 2000);
});

test("warnings for double routes", () => {
  const game = {
    players: [{ color: "red" }, { color: "blue" }],
    routes: { [rid(usa, "Boston", "New York", 1)]: "red", [rid(usa, "Boston", "New York", 2)]: "blue" },
  };
  assert.ok(scoreGame(usa, game).warnings.some((w) => w.includes("fewer than 4")));
  game.routes = { [rid(usa, "Boston", "New York", 1)]: "red", [rid(usa, "Boston", "New York", 2)]: "red" };
  assert.ok(scoreGame(usa, game).warnings.some((w) => w.includes("both lanes")));
});

test("ranking breaks ties on completed tickets", () => {
  const game = {
    players: [{ color: "blue" }, { color: "red", tickets: [{ a: "Denver", b: "Santa Fe", points: 0 }] }],
    routes: { [rid(usa, "Denver", "Santa Fe")]: "red", [rid(usa, "Las Vegas", "Los Angeles")]: "blue" },
  };
  const result = scoreGame(usa, game);
  assert.deepEqual(result.players.map((p) => p.color), ["red", "blue"]);
  assert.deepEqual(result.players.map((p) => p.rank), [1, 2]);
});

test("equal players share a rank", () => {
  const game = {
    players: [{ color: "blue" }, { color: "red" }],
    routes: { [rid(usa, "Denver", "Santa Fe")]: "red", [rid(usa, "Las Vegas", "Los Angeles")]: "blue" },
  };
  assert.deepEqual(scoreGame(usa, game).players.map((p) => p.rank), [1, 1]);
});

test("Europe stations: unused points and borrowing a route", () => {
  const game = {
    players: [
      { color: "red", tickets: [{ a: "Paris", b: "Wien", points: 8 }], stations: ["Munchen"] },
      { color: "blue", stations: [] },
    ],
    routes: {
      [rid(europe, "Paris", "Frankfurt", 1)]: "red",
      [rid(europe, "Frankfurt", "Munchen")]: "red",
      [rid(europe, "Munchen", "Wien")]: "blue", // red borrows this with the Munchen station
    },
  };
  const result = scoreGame(europe, game);
  const red = player(result, "red");
  const blue = player(result, "blue");
  assert.equal(red.tickets[0].completed, true);
  assert.deepEqual(red.borrowed_routes, [rid(europe, "Munchen", "Wien")]);
  assert.equal(red.station_points, 8); // two unused
  assert.equal(blue.station_points, 12);
  // The borrowed route doesn't count for red's longest path or route points.
  assert.equal(red.longest_path, 5);
  assert.equal(red.route_points, 4 + 2);
});

test("Europe: a station only borrows one route", () => {
  // Red needs two of blue's routes through Munchen; one station isn't enough.
  const game = {
    players: [
      { color: "red", tickets: [{ a: "Frankfurt", b: "Wien", points: 8 }], stations: ["Munchen"] },
      { color: "blue" },
    ],
    routes: { [rid(europe, "Frankfurt", "Munchen")]: "blue", [rid(europe, "Munchen", "Wien")]: "blue" },
  };
  assert.equal(player(scoreGame(europe, game), "red").tickets[0].completed, false);
  // Two stations can borrow one route each.
  game.players[0].stations = ["Munchen", "Frankfurt"];
  const red = player(scoreGame(europe, game), "red");
  assert.equal(red.tickets[0].completed, true);
  assert.equal(red.borrowed_routes.length, 2);
  assert.equal(red.station_points, 4);
});

test("Europe: an eight-car route is worth 21", () => {
  const game = { players: [{ color: "green" }], routes: { [rid(europe, "Stockholm", "Petrograd")]: "green" } };
  assert.equal(player(scoreGame(europe, game), "green").route_points, 21);
});

test("unknown routes and cities are ignored", () => {
  const game = {
    players: [{ color: "red", tickets: [{ a: "Atlantis", b: "Denver", points: 5 }] }],
    routes: { "nowhere-somewhere": "red" },
  };
  const p = player(scoreGame(usa, game), "red");
  assert.equal(p.route_points, 0);
  assert.deepEqual(p.tickets, []);
});
