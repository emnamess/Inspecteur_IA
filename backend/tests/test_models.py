import pytest
from pydantic import ValidationError

from game.models import Scenario
from game.scenario import list_scenarios, load_scenario


def test_handwritten_scenario_is_valid():
    scenario = load_scenario()
    assert len(scenario.suspects) == 4
    assert scenario.suspect(scenario.solution.guilty).is_guilty


def test_all_scenarios_are_valid():
    for name in list_scenarios():
        load_scenario(name)


def _raw() -> dict:
    return load_scenario().model_dump()


def test_rejects_unknown_clue_in_room():
    data = _raw()
    data["rooms"][0]["clues"].append("indice_fantome")
    with pytest.raises(ValidationError, match="indice inconnu"):
        Scenario.model_validate(data)


def test_rejects_two_culprits():
    data = _raw()
    for suspect in data["suspects"]:
        suspect["is_guilty"] = True
    with pytest.raises(ValidationError, match="exactement un coupable"):
        Scenario.model_validate(data)


def test_rejects_solution_not_matching_culprit():
    data = _raw()
    innocent = next(s["id"] for s in data["suspects"] if not s["is_guilty"])
    data["solution"]["guilty"] = innocent
    with pytest.raises(ValidationError, match="solution.guilty"):
        Scenario.model_validate(data)


def test_rejects_unplaced_clue():
    data = _raw()
    data["rooms"][0]["clues"] = []
    with pytest.raises(ValidationError, match="placés dans aucune pièce"):
        Scenario.model_validate(data)
