import pytest

from agents import game_master
from agents.game_master import GameMaster, generated_scenario
from agents.llm import LLMError
from game import load_scenario
from game_factory import new_game
from tests.fakes import FakeLLM

valid = load_scenario().model_dump()


def _invalid() -> dict:
    data = load_scenario().model_dump()
    data["solution"]["guilty"] = "majordome"  # ne correspond pas au suspect marqué coupable
    return data


def test_generates_a_valid_scenario():
    llm = FakeLLM(objects=[valid])
    scenario = GameMaster(llm).generate(seed=1)
    assert scenario.solution.guilty == "niece"
    assert "Cadre :" in llm.calls[0]["messages"][0]["content"]


def test_retries_with_validation_error_as_feedback():
    llm = FakeLLM(objects=[_invalid(), valid])
    GameMaster(llm).generate(seed=1)
    assert "incohérente" in llm.calls[1]["messages"][0]["content"]


def test_gives_up_after_max_attempts():
    llm = FakeLLM(objects=[_invalid()] * 3)
    with pytest.raises(LLMError):
        GameMaster(llm).generate(seed=1)


def test_same_seed_gives_same_request():
    llm = FakeLLM(objects=[valid, valid])
    GameMaster(llm).generate(seed=42)
    GameMaster(llm).generate(seed=42)
    assert llm.calls[0]["messages"] == llm.calls[1]["messages"]


def test_generated_scenarios_are_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(game_master, "GENERATED_DIR", tmp_path)
    llm = FakeLLM(objects=[valid])
    generated_scenario(7, GameMaster(llm))
    generated_scenario(7, GameMaster(llm))  # 2e appel : lu depuis le disque, pas de nouvel appel LLM
    assert len(llm.calls) == 1
    assert (tmp_path / "seed_7.json").exists()


def test_new_game_with_seed_uses_the_game_master(tmp_path, monkeypatch):
    monkeypatch.setattr(game_master, "GENERATED_DIR", tmp_path)
    game = new_game(seed=3, llm=FakeLLM(objects=[valid]))
    assert game.scenario.title == "Meurtre au manoir de Valmont"
