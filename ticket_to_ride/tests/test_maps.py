from ticket_to_ride.maps import all_maps, get_map


def test_maps_load():
    maps = all_maps()
    assert set(maps) >= {"usa", "europe"}
    usa, europe = maps["usa"], maps["europe"]
    assert (len(usa.cities), len(usa.routes), len(usa.tickets)) == (36, 100, 30)
    assert (len(europe.cities), len(europe.routes), len(europe.tickets)) == (47, 101, 46)
    assert sum(t.long for t in europe.tickets.values()) == 6
    assert europe.stations == 3 and usa.stations == 0
    for m in maps.values():
        for r in m.routes.values():
            assert r.length in m.route_points, r
        for t in m.tickets.values():
            assert t.a != t.b


def test_double_routes_get_lanes():
    usa = get_map("usa")
    assert usa.routes["boston-new_york-1"].color == "yellow"
    assert usa.routes["boston-new_york-2"].color == "red"
    assert usa.routes["denver-santa_fe"].lane == 0


def test_city_aliases():
    usa, europe = get_map("usa"), get_map("europe")
    assert usa.city("St. Louis") == "Saint Louis"
    assert usa.city("sault ste marie") == "Sault St. Marie"
    assert usa.city("STOCKHOLM") is None
    assert europe.city("München") == "Munchen"
    assert europe.city("Moscow") == "Moskva"
    assert europe.city("stockholm") == "Stockholm"
    assert usa.city("Atlantis") is None


def test_find_ticket_either_way_round():
    usa = get_map("usa")
    assert usa.find_ticket("El Paso", "Denver").points == 4
    assert usa.find_ticket("Denver", "Boston") is None
