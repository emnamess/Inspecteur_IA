"""API REST (FastAPI) pour le front React : la deuxième porte d'entrée sur le même moteur.

Comme le serveur MCP, elle n'a aucune règle de jeu : elle traduit HTTP <-> méthodes de `Game`.
Différence : plusieurs joueurs peuvent jouer en même temps, chacun avec sa partie (`game_id`).

Lancement : uvicorn api:app --reload
"""

from collections import OrderedDict
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agents.llm import LLMError
from game import Game, GameError
from game_factory import new_game, shared_memory

MAX_GAMES = 200  # parties gardées en mémoire ; au-delà, les plus anciennes sont oubliées

app = FastAPI(title="Inspecteur IA", description="Jeu d'enquête où chaque suspect est un agent IA.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # serveur de développement Vite
    allow_methods=["*"],
    allow_headers=["*"],
)

games: OrderedDict[str, Game] = OrderedDict()


class NewGameRequest(BaseModel):
    seed: int | None = Field(default=None, description="Absent : scénario écrit à la main")


class InterrogateRequest(BaseModel):
    suspect: str
    question: str = Field(min_length=1, max_length=500)


class AccuseRequest(BaseModel):
    suspect: str
    reasoning: str = Field(default="", max_length=2000)


@app.exception_handler(GameError)
def game_error_handler(request: Request, exc: GameError) -> JSONResponse:
    status = 503 if isinstance(exc, LLMError) else 400
    return JSONResponse(status_code=status, content={"detail": str(exc)})


def get_game_factory() -> Callable[..., Game]:
    """Dépendance FastAPI : remplacée dans les tests par une fabrique avec un faux LLM."""
    return new_game


def get_game(game_id: str) -> Game:
    game = games.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable. Lancez une nouvelle partie.")
    return game


CurrentGame = Annotated[Game, Depends(get_game)]
GameFactory = Annotated[Callable[..., Game], Depends(get_game_factory)]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/games")
def create_game(body: NewGameRequest, factory: GameFactory) -> dict[str, Any]:
    game = factory(seed=body.seed)
    games[game.id] = game
    while len(games) > MAX_GAMES:
        old_id, _ = games.popitem(last=False)
        shared_memory().forget_game(old_id)
    return game.start_info()


@app.get("/api/games/{game_id}/rooms")
def list_rooms(game: CurrentGame) -> list[dict[str, Any]]:
    return game.list_rooms()


@app.post("/api/games/{game_id}/rooms/{room_id}/inspect")
def inspect_room(room_id: str, game: CurrentGame) -> dict[str, Any]:
    return game.inspect_room(room_id)


@app.get("/api/games/{game_id}/suspects")
def list_suspects(game: CurrentGame) -> list[dict[str, Any]]:
    return game.list_suspects()


# `def` et non `async def` : l'appel au LLM est bloquant, FastAPI l'exécute dans un thread.
@app.post("/api/games/{game_id}/interrogate")
def interrogate(body: InterrogateRequest, game: CurrentGame) -> dict[str, Any]:
    return game.interrogate(body.suspect, body.question)


@app.get("/api/games/{game_id}/clues")
def get_clues(game: CurrentGame) -> list[dict[str, Any]]:
    return game.get_clues()


@app.post("/api/games/{game_id}/accuse")
def accuse(body: AccuseRequest, game: CurrentGame) -> dict[str, Any]:
    return game.accuse(body.suspect, body.reasoning)
