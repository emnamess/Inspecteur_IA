from mcp.server.mcpserver import MCPServer

# Création du serveur : le nom est celui que verront les clients MCP
mcp = MCPServer("Inspecteur IA")

# Pièces du manoir, écrites en dur pour l'étape 1 (le JSON viendra à l'étape 2)
ROOMS = {
    "bibliotheque": "Une pièce sombre remplie de livres. Un verre brisé traîne près du fauteuil.",
    "cuisine": "Une grande cuisine encore chaude. Une fiole vide dépasse de la poubelle.",
    "salon": "Un salon luxueux. La cheminée fume encore et une lettre à moitié brûlée y repose.",
}


@mcp.tool()
def list_rooms() -> list[str]:
    """Liste les identifiants des pièces du manoir que l'inspecteur peut fouiller.

    À appeler avant `inspect_room` pour connaître les valeurs valides du paramètre `room`.
    """
    return list(ROOMS.keys())


@mcp.tool()
def inspect_room(room: str) -> str:
    """Fouille une pièce du manoir et renvoie sa description.

    Args:
        room: identifiant de la pièce, tel que renvoyé par `list_rooms` (ex. "bibliotheque").
    """
    if room not in ROOMS:
        return f"Pièce inconnue : '{room}'. Pièces valides : {', '.join(ROOMS)}."
    return ROOMS[room]


if __name__ == "__main__":
    mcp.run()  # par défaut en "stdio" : le client lance ce script et lui parle via l'entrée/sortie standard
