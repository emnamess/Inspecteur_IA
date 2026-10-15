"""Teste le serveur MCP comme le ferait un vrai client (connexion en mémoire, sans sous-processus)."""

import asyncio

from mcp import Client

import mcp_server


def _run(coro):
    return asyncio.run(coro)


async def _call(client: Client, tool: str, args: dict | None = None):
    return await client.call_tool(tool, args or {})


def test_exposes_the_seven_tools():
    async def scenario():
        async with Client(mcp_server.mcp) as client:
            tools = await client.list_tools()
            return {tool.name: tool.description for tool in tools.tools}

    tools = _run(scenario())
    assert set(tools) == {
        "start_game",
        "list_rooms",
        "inspect_room",
        "list_suspects",
        "interrogate",
        "get_clues",
        "accuse",
    }
    assert all(description for description in tools.values()), "chaque outil doit avoir une docstring"


def test_full_game_through_mcp():
    async def scenario():
        async with Client(mcp_server.mcp) as client:
            start = await _call(client, "start_game")
            room = await _call(client, "inspect_room", {"room": "chambre_clara"})
            clues = await _call(client, "get_clues")
            verdict = await _call(client, "accuse", {"suspect": "niece", "reasoning": "Bottines boueuses."})
            return start, room, clues, verdict

    start, room, clues, verdict = _run(scenario())
    assert start.structured_content["title"] == "Meurtre au manoir de Valmont"
    assert "bottines_boueuses" in room.structured_content["new_clues"]
    assert len(clues.structured_content["result"]) == 2
    assert verdict.structured_content["correct"] is True


def test_game_errors_are_reported_to_the_client():
    async def scenario():
        async with Client(mcp_server.mcp) as client:
            await _call(client, "start_game")
            return await _call(client, "inspect_room", {"room": "grenier"})

    result = _run(scenario())
    assert result.is_error
    assert "Pièces valides" in result.content[0].text
