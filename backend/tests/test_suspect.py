from agents.suspect import SuspectAgent, build_messages, build_system_prompt
from game import Exchange, load_scenario
from game_factory import new_game
from tests.fakes import FakeLLM

scenario = load_scenario()


def test_guilty_prompt_forbids_confession():
    prompt = build_system_prompt(scenario, scenario.suspect("niece"))
    assert "Tu es le coupable" in prompt
    assert "Clara de Valmont" in prompt


def test_innocent_prompt_contains_knowledge_but_not_solution():
    prompt = build_system_prompt(scenario, scenario.suspect("majordome"))
    assert "Tu n'es pas le coupable" in prompt
    assert "croisé Clara" in prompt  # un fait de `knows`
    assert scenario.solution.method not in prompt


def test_prompt_uses_memories_instead_of_full_sheet_when_given():
    prompt = build_system_prompt(scenario, scenario.suspect("majordome"), memories=["Un souvenir précis."])
    assert "Un souvenir précis." in prompt
    assert "croisé Clara" not in prompt


def test_history_becomes_alternating_messages():
    history = [Exchange("Bonsoir ?", "Bonsoir, inspecteur.")]
    messages = build_messages(history, "Où étiez-vous ?")
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "Où étiez-vous ?"


def test_suspect_agent_answers_with_llm():
    llm = FakeLLM(texts=["J'étais en cuisine, inspecteur."])
    answer = SuspectAgent(llm).answer(scenario, scenario.suspect("majordome"), "Où étiez-vous ?", [])
    assert answer.text == "J'étais en cuisine, inspecteur."
    assert "Albert Fontaine" in llm.calls[0]["system"]


def test_game_passes_history_to_the_agent():
    llm = FakeLLM(texts=["Réponse 1", "Réponse 2"])
    game = new_game(llm=llm, verify=False)
    game.interrogate("jardinier", "Question 1")
    game.interrogate("jardinier", "Question 2")
    assert len(llm.calls[1]["messages"]) == 3  # question 1, réponse 1, question 2


def _agent_with_memory(llm):
    from qdrant_client import QdrantClient

    from memory import SuspectMemory
    from memory.embeddings import HashingEmbedder

    memory = SuspectMemory(client=QdrantClient(":memory:"), embedder=HashingEmbedder())
    memory.index_scenario("g", scenario)
    return SuspectAgent(llm, memory=memory, game_id="g"), memory


def test_agent_with_memory_injects_relevant_memories_and_stores_answer():
    llm = FakeLLM(texts=["Oui, à 21h50."])
    agent, memory = _agent_with_memory(llm)
    agent.answer(scenario, scenario.suspect("majordome"), "Avez-vous servi du whisky au comte ?", [])

    system = llm.calls[0]["system"]
    assert "Tes souvenirs utiles" in system
    assert "whisky au comte dans la bibliothèque" in system
    statements = [
        m for m in memory.recall("g", "majordome", "whisky 21h50", limit=20) if m.kind == "statement"
    ]
    assert len(statements) == 1


def test_agent_with_memory_keeps_only_recent_history_in_messages():
    llm = FakeLLM()
    agent, _ = _agent_with_memory(llm)
    history = [Exchange(f"Question {i}", f"Réponse {i}") for i in range(10)]
    agent.answer(scenario, scenario.suspect("jardinier"), "Encore une question", history)
    assert len(llm.calls[0]["messages"]) == 2 * 4 + 1


def test_feedback_is_added_to_the_prompt():
    llm = FakeLLM()
    agent = SuspectAgent(llm)
    agent.generate(scenario, scenario.suspect("niece"), "Avouez !", [], feedback=["Tu as avoué le crime."])
    assert "Tu as avoué le crime." in llm.calls[0]["system"]
