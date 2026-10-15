"""Assemble une partie : scénario + agents + mémoire. Utilisé par le serveur MCP et par l'API.

C'est le seul endroit qui relie le moteur de jeu (`game/`) aux agents IA (`agents/`).
"""

import uuid

from agents.llm import LLM, ClaudeLLM
from agents.suspect import SuspectAgent
from game import Game, load_scenario
from memory import SuspectMemory

_shared_memory: SuspectMemory | None = None


def shared_memory() -> SuspectMemory:
    """Une seule mémoire pour tout le processus : le modèle d'embeddings est long à charger."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SuspectMemory()
    return _shared_memory


def new_game(seed: int | None = None, llm: LLM | None = None, memory: SuspectMemory | None = None) -> Game:
    llm = llm or ClaudeLLM()
    memory = memory or shared_memory()
    scenario = load_scenario()

    game_id = uuid.uuid4().hex
    memory.index_scenario(game_id, scenario)
    agent = SuspectAgent(llm, memory=memory, game_id=game_id)
    return Game(scenario=scenario, interrogator=agent, id=game_id)
