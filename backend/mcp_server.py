"""Serveur MCP : expose le jeu sous forme d'outils utilisables par un LLM.

Ce fichier ne contient aucune règle du jeu : chaque outil appelle le moteur (`game/`).
Les docstrings sont importantes : c'est ce que le LLM du client lit pour choisir l'outil.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from game import Game, GameError
from game_factory import new_game, shared_memory

mcp = MCPServer(
    "Inspecteur IA",
    instructions=(
        "Jeu d'enquête policière. Le joueur est l'inspecteur. Commence par start_game, "
        "fouille les pièces, interroge les suspects, puis accuse un coupable avec accuse."
    ),
)

# Un serveur MCP en stdio sert un seul joueur : une seule partie en cours suffit.
_current_game: Game | None = None


def _play(action: str, *args: Any) -> Any:
    """Appelle une action du moteur. Les erreurs de jeu deviennent des `ToolError` :
    le SDK MCP ne transmet au client que le message de ce type d'erreur."""
    if _current_game is None:
        raise ToolError("Aucune partie en cours. Appelle d'abord l'outil start_game.")
    try:
        return getattr(_current_game, action)(*args)
    except GameError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def start_game(seed: int | None = None) -> dict[str, Any]:
    """Lance une nouvelle partie d'enquête et renvoie le contexte de départ.

    Renvoie le texte d'introduction, la victime, la liste des pièces et des suspects.
    À appeler en premier. Relancer l'outil abandonne la partie en cours.

    Args:
        seed: optionnel. Absent : le scénario écrit à la main. Un nombre : un nouveau scénario
            généré par le Maître du jeu (le même nombre redonne le même scénario).
    """
    global _current_game
    if _current_game is not None:
        shared_memory().forget_game(_current_game.id)
    _current_game = new_game(seed)
    return _current_game.start_info()


@mcp.tool()
def list_rooms() -> list[dict[str, Any]]:
    """Liste les pièces du manoir (identifiant, nom, déjà fouillée ou non).

    À appeler pour connaître les valeurs valides du paramètre `room` de `inspect_room`.
    """
    return _play("list_rooms")


@mcp.tool()
def inspect_room(room: str) -> dict[str, Any]:
    """Fouille une pièce : renvoie sa description et les indices qui s'y trouvent.

    Les indices trouvés sont ajoutés au carnet de l'inspecteur (voir `get_clues`).

    Args:
        room: identifiant de la pièce, tel que renvoyé par `list_rooms` (ex. "bibliotheque").
    """
    return _play("inspect_room", room)


@mcp.tool()
def list_suspects() -> list[dict[str, Any]]:
    """Liste les suspects : identifiant, nom, rôle et courte description.

    À appeler pour connaître les valeurs valides du paramètre `suspect`
    de `interrogate` et `accuse`.
    """
    return _play("list_suspects")


@mcp.tool()
def interrogate(suspect: str, question: str) -> dict[str, Any]:
    """Pose une question à un suspect, qui répond en restant dans son personnage.

    Les suspects peuvent mentir ou cacher des secrets : confrontez leurs réponses
    aux indices et aux autres témoignages. Chaque suspect se souvient de ses réponses.

    Args:
        suspect: identifiant du suspect, tel que renvoyé par `list_suspects` (ex. "majordome").
        question: la question, en langage naturel (ex. "Où étiez-vous à 22h ?").
    """
    return _play("interrogate", suspect, question)


@mcp.tool()
def get_clues() -> list[dict[str, Any]]:
    """Renvoie le carnet de l'inspecteur : les indices découverts jusqu'ici, avec leur analyse."""
    return _play("get_clues")


@mcp.tool()
def accuse(suspect: str, reasoning: str) -> dict[str, Any]:
    """Accuse un suspect et termine la partie. Action définitive !

    Renvoie si l'accusation est juste, ainsi que la solution complète (coupable, mobile, méthode).

    Args:
        suspect: identifiant du suspect accusé (voir `list_suspects`).
        reasoning: le raisonnement de l'inspecteur (mobile, moyen, indices, contradictions).
    """
    return _play("accuse", suspect, reasoning)


if __name__ == "__main__":
    mcp.run()  # transport "stdio" : le client lance ce script et lui parle via stdin/stdout
