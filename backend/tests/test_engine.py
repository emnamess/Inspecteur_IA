import pytest

from game import Game, GameError, load_scenario
from game.engine import AlibiInterrogator


@pytest.fixture
def game() -> Game:
    return Game(scenario=load_scenario(), interrogator=AlibiInterrogator())


def test_start_info_hides_solution(game):
    info = game.start_info()
    assert info["victim"]["name"] == "Comte Édouard de Valmont"
    assert "solution" not in info
    assert all("is_guilty" not in suspect for suspect in info["suspects"])


def test_inspect_room_reveals_clues_once(game):
    first = game.inspect_room("bibliotheque")
    assert first["new_clues"] == ["verre_brise", "carafe_whisky"]
    second = game.inspect_room("bibliotheque")
    assert second["new_clues"] == []
    assert [clue["id"] for clue in game.get_clues()] == ["verre_brise", "carafe_whisky"]


def test_inspect_unknown_room_lists_valid_rooms(game):
    with pytest.raises(GameError, match="bibliotheque"):
        game.inspect_room("grenier")


def test_interrogate_keeps_history(game):
    result = game.interrogate("majordome", "Où étiez-vous à 22h ?")
    assert result["answer"].startswith("J'étais en cuisine")
    assert len(game.histories["majordome"]) == 1


def test_interrogate_rejects_empty_question(game):
    with pytest.raises(GameError):
        game.interrogate("majordome", "   ")


def test_correct_accusation_wins_and_ends_game(game):
    verdict = game.accuse("niece", "Les bottines boueuses contredisent son alibi.")
    assert verdict["correct"] is True
    assert verdict["solution"]["guilty"] == "niece"
    with pytest.raises(GameError, match="terminée"):
        game.inspect_room("salon")


def test_wrong_accusation_reveals_solution(game):
    verdict = game.accuse("jardinier", "Il a été renvoyé.")
    assert verdict["correct"] is False
    assert verdict["solution"]["guilty_name"] == "Clara de Valmont"
