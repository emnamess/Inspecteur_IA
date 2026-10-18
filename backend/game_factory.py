"""Assemble une partie : scénario + agents + mémoire. Utilisé par le serveur MCP et par l'API.

C'est le seul endroit qui relie le moteur de jeu (`game/`) aux agents IA (`agents/`).
"""

import uuid

from agents.game_master import GameMaster, generated_scenario
from agents.graph import InterrogationGraph
from agents.llm import LLM, default_llm
from agents.suspect import SuspectAgent
from agents.verifier import Verifier
from game import Game, load_scenario
from memory import SuspectMemory

_shared_memory: SuspectMemory | None = None


def shared_memory() -> SuspectMemory:
    """Une seule mémoire pour tout le processus : le modèle d'embeddings est long à charger."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SuspectMemory()
    return _shared_memory


def new_game(
    seed: int | None = None,
    llm: LLM | None = None,
    memory: SuspectMemory | None = None,
    verify: bool = True,
) -> Game:
    """Crée une partie. Sans seed : le scénario écrit à la main. Avec seed : un scénario généré.

    `verify=False` désactive le Vérificateur (utile pour mesurer son apport dans l'évaluation).
    """
    memory = memory or shared_memory()

    if seed is None:
        scenario = load_scenario()
    else:
        game_master_llm = llm or default_llm(max_tokens=16000)  # un scénario complet est long
        scenario = generated_scenario(seed, GameMaster(game_master_llm))

    llm = llm or default_llm()

    game_id = uuid.uuid4().hex
    memory.index_scenario(game_id, scenario)
    suspect_agent = SuspectAgent(llm, memory=memory, game_id=game_id)
    interrogator = InterrogationGraph(suspect_agent, Verifier(llm) if verify else None)
    return Game(scenario=scenario, interrogator=interrogator, id=game_id)
