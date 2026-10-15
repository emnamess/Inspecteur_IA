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
    game = new_game(llm=llm)
    game.interrogate("jardinier", "Question 1")
    game.interrogate("jardinier", "Question 2")
    assert len(llm.calls[1]["messages"]) == 3  # question 1, réponse 1, question 2
