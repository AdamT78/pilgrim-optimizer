from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId
from pilgrim.rules.mancala import generate_routes, sow_vector


def test_generate_legal_routes_from_city_with_three_acolytes() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    city = scenario.config.board.index_for_name("city")
    routes = generate_routes(city, 3, scenario.config.board)
    assert routes == ((1, 2, 3), (5, 6, 7))


def test_sowing_from_city_to_north_north_east_east() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    vector = scenario.state.player_vector(PlayerId.PLAYER_ONE)
    updated = sow_vector(vector, source=0, route=(1, 2, 3), board=scenario.config.board)
    assert updated == (0, 1, 1, 1, 0, 0, 0, 0, 0)
