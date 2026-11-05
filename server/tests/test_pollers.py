from flypaper.flights import DETAIL_FIELDS
from flypaper.pollers import carry_over_details


def aircraft(**overrides):
    data = {"registration": "RA-73182", "origin": "LED", "dest": "OVB",
            "origin_city": "", "dest_city": "", **{field: "" for field in DETAIL_FIELDS}}
    return {**data, **overrides}


def test_details_are_carried_over_for_the_same_aircraft():
    previous = aircraft(model_name="Airbus A320-214", origin_city="Saint Petersburg", dest_city="Novosibirsk")
    selected = carry_over_details(aircraft(), previous)
    assert selected["model_name"] == "Airbus A320-214"
    assert selected["origin_city"] == "Saint Petersburg"
    assert selected["dest_city"] == "Novosibirsk"


def test_cities_are_not_carried_over_after_route_change():
    previous = aircraft(dest_city="Novosibirsk")
    assert carry_over_details(aircraft(dest="SVO"), previous)["dest_city"] == ""


def test_other_aircraft_keeps_its_own_data():
    previous = aircraft(model_name="Airbus A320-214")
    assert carry_over_details(aircraft(registration="TC-LSA"), previous)["model_name"] == ""


def test_nothing_to_merge():
    assert carry_over_details(None, aircraft()) is None
    assert carry_over_details(aircraft(), None) == aircraft()
