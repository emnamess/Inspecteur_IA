"""Assemble une partie : scénario + agents. Utilisé par le serveur MCP et par l'API.

C'est le seul endroit qui relie le moteur de jeu (`game/`) aux agents IA (`agents/`).
"""

from agents.llm import LLM, ClaudeLLM
from agents.suspect import SuspectAgent
from game import Game, load_scenario


def new_game(seed: int | None = None, llm: LLM | None = None) -> Game:
    llm = llm or ClaudeLLM()
    return Game(scenario=load_scenario(), interrogator=SuspectAgent(llm))
