import pytest
from fastapi.testclient import TestClient

import api
from agents.llm import LLMError
from agents.verifier import Verdict
from game_factory import new_game
from tests.fakes import FakeLLM

OK = Verdict(contradiction=False, leak=False, issues=[])


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM(texts=["J'étais en cuisine, inspecteur."], objects=[OK])


@pytest.fixture
def client(llm):
    api.app.dependency_overrides[api.get_game_factory] = lambda: lambda seed=None: new_game(seed, llm=llm)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()
    api.games.clear()


def _start(client) -> str:
    response = client.post("/api/games", json={})
    assert response.status_code == 200
    return response.json()["game_id"]


def test_full_game_over_http(client):
    game_id = _start(client)
    room = client.post(f"/api/games/{game_id}/rooms/bibliotheque/inspect").json()
    assert room["new_clues"] == ["verre_brise", "carafe_whisky"]

    answer = client.post(
        f"/api/games/{game_id}/interrogate", json={"suspect": "majordome", "question": "Où étiez-vous ?"}
    ).json()
    assert answer["answer"] == "J'étais en cuisine, inspecteur."
    assert answer["verified"] is True

    assert len(client.get(f"/api/games/{game_id}/clues").json()) == 2
    verdict = client.post(
        f"/api/games/{game_id}/accuse", json={"suspect": "niece", "reasoning": "..."}
    ).json()
    assert verdict["correct"] is True


def test_games_are_independent(client):
    first, second = _start(client), _start(client)
    client.post(f"/api/games/{first}/rooms/salon/inspect")
    assert client.get(f"/api/games/{second}/clues").json() == []


def test_game_errors_become_400(client):
    game_id = _start(client)
    response = client.post(f"/api/games/{game_id}/rooms/grenier/inspect")
    assert response.status_code == 400
    assert "Pièces valides" in response.json()["detail"]


def test_unknown_game_is_404(client):
    assert client.get("/api/games/inconnue/rooms").status_code == 404


def test_llm_errors_become_503(client, llm, monkeypatch):
    game_id = _start(client)

    def broken(*args, **kwargs):
        raise LLMError("Aucune clé API.")

    monkeypatch.setattr(llm, "generate", broken)
    response = client.post(
        f"/api/games/{game_id}/interrogate", json={"suspect": "majordome", "question": "?"}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Aucune clé API."
