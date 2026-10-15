import os

import pytest
from qdrant_client import QdrantClient

from game import load_scenario
from memory import SuspectMemory
from memory.embeddings import HashingEmbedder, Model2VecEmbedder

scenario = load_scenario()


@pytest.fixture
def memory() -> SuspectMemory:
    return SuspectMemory(client=QdrantClient(":memory:"), embedder=HashingEmbedder())


def test_index_scenario_stores_facts_and_secrets(memory):
    count = memory.index_scenario("partie1", scenario)
    expected = sum(len(s.knows) + len(s.secrets) for s in scenario.suspects)
    assert count == expected


def test_recall_only_returns_memories_of_that_suspect_and_game(memory):
    memory.index_scenario("partie1", scenario)
    memory.index_scenario("partie2", scenario)
    found = memory.recall("partie1", "majordome", "whisky", limit=50)
    majordome = scenario.suspect("majordome")
    assert len(found) == len(majordome.knows) + len(majordome.secrets)
    assert {m.text for m in found} <= set(majordome.knows + majordome.secrets)


def test_recall_ranks_relevant_memory_first(memory):
    memory.index_scenario("partie1", scenario)
    found = memory.recall("partie1", "majordome", "Avez-vous servi du whisky au comte ?")
    assert "whisky" in found[0].text


def test_statements_are_remembered(memory):
    memory.index_scenario("partie1", scenario)
    memory.remember_statement("partie1", "jardinier", "Aimez-vous les rosiers ?", "Je déteste les rosiers.")
    found = memory.recall("partie1", "jardinier", "rosiers", limit=1)
    assert found[0].kind == "statement"
    assert "Je déteste les rosiers" in found[0].as_prompt_line()


def test_forget_game(memory):
    memory.index_scenario("partie1", scenario)
    memory.forget_game("partie1")
    assert memory.recall("partie1", "majordome", "whisky") == []


@pytest.mark.skipif(not os.getenv("RUN_SLOW"), reason="télécharge le modèle d'embeddings (RUN_SLOW=1)")
def test_semantic_recall_without_shared_words():
    memory = SuspectMemory(client=QdrantClient(":memory:"), embedder=Model2VecEmbedder())
    memory.index_scenario("partie1", scenario)
    found = memory.recall("partie1", "medecin", "Qu'avez-vous remarqué sur le corps ?", limit=2)
    assert any("arsenic" in m.text for m in found)
