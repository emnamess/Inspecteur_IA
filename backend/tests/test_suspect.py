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


def test_llm_provider_is_chosen_from_environment(monkeypatch):
    from agents.llm import ClaudeLLM, GeminiLLM, default_llm

    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(default_llm(), GeminiLLM)  # gratuit par défaut
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert isinstance(default_llm(), ClaudeLLM)
    assert default_llm(max_tokens=16000).max_tokens == 16000


def test_gemini_receives_roles_and_validates_json(monkeypatch):
    from types import SimpleNamespace

    from agents.llm import GeminiLLM
    from agents.verifier import Verdict

    sent = {}

    def fake_generate_content(model, contents, config):
        sent.update(contents=contents, config=config)
        return SimpleNamespace(text='{"contradiction": false, "leak": true, "issues": ["Aveu."]}')

    llm = GeminiLLM(model="gemini-test")
    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "R1"},
        {"role": "user", "content": "Q2"},
    ]
    verdict = llm.generate_json("système", messages, Verdict, effort="medium")

    assert verdict.leak and verdict.issues == ["Aveu."]
    assert [c.role for c in sent["contents"]] == ["user", "model", "user"]
    assert sent["config"].system_instruction == "système"


def test_gemini_switches_to_fallback_model_when_overloaded(monkeypatch):
    from types import SimpleNamespace

    from google.genai import errors

    from agents.llm import GeminiLLM

    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    used = []

    def fake_generate_content(model, contents, config):
        used.append(model)
        if model == "principal":
            raise errors.ServerError(503, {"error": {"message": "high demand", "status": "UNAVAILABLE"}})
        return SimpleNamespace(text="Réponse du modèle de secours")

    llm = GeminiLLM(model="principal")
    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    assert llm.generate("système", [{"role": "user", "content": "Q"}]) == "Réponse du modèle de secours"
    assert used == ["principal", "gemini-3.6-flash"]


def test_gemini_raises_thinking_level_when_minimal_is_not_supported():
    from types import SimpleNamespace

    from google.genai import errors

    from agents.llm import GeminiLLM

    levels = []

    def fake_generate_content(model, contents, config):
        levels.append(config.thinking_config.thinking_level)
        if config.thinking_config.thinking_level == "MINIMAL":
            raise errors.ClientError(400, {"error": {"message": "Thinking level MINIMAL is not supported"}})
        return SimpleNamespace(text="Réponse")

    llm = GeminiLLM(model="principal")
    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    assert llm.generate("système", [{"role": "user", "content": "Q"}], effort="low") == "Réponse"
    assert [str(level) for level in levels][-1].endswith("LOW")


def test_gemini_moves_to_next_model_when_daily_quota_is_exhausted(monkeypatch):
    from types import SimpleNamespace

    import pytest
    from google.genai import errors

    from agents.llm import GeminiLLM, LLMError

    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "secours")
    daily = {"error": {"message": "quota", "details": [{"retryDelay": "34959s"}]}}
    used = []

    def exhausted(model, contents, config):
        used.append(model)
        raise errors.ClientError(429, daily)

    llm = GeminiLLM(model="principal")
    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=exhausted))
    with pytest.raises(LLMError, match="Quota gratuit du jour"):
        llm.generate("système", [{"role": "user", "content": "Q"}])
    assert used == ["principal", "secours"]  # aucune attente : on change de modèle puis on abandonne
