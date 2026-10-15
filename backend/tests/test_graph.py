from qdrant_client import QdrantClient

from agents.graph import InterrogationGraph
from agents.suspect import SuspectAgent
from agents.verifier import Verdict, Verifier, build_verifier_prompt
from game import load_scenario
from memory import SuspectMemory
from memory.embeddings import HashingEmbedder
from tests.fakes import FakeLLM

scenario = load_scenario()
OK = Verdict(contradiction=False, leak=False, issues=[])


def _graph(llm: FakeLLM, verify: bool = True, max_attempts: int = 3):
    memory = SuspectMemory(client=QdrantClient(":memory:"), embedder=HashingEmbedder())
    memory.index_scenario("g", scenario)
    agent = SuspectAgent(llm, memory=memory, game_id="g")
    return InterrogationGraph(agent, Verifier(llm) if verify else None, max_attempts), memory


def _statements(memory: SuspectMemory, suspect_id: str) -> list[str]:
    found = memory.recall("g", suspect_id, "inspecteur demandé répondu", limit=50)
    return [m.text for m in found if m.kind == "statement"]


def test_verifier_knows_the_whole_truth():
    prompt = build_verifier_prompt(scenario, scenario.suspect("majordome"))
    assert scenario.solution.method in prompt
    assert "Mensonges autorisés" in prompt


def test_accepted_answer_is_returned_after_one_attempt():
    llm = FakeLLM(texts=["J'étais en cuisine."], objects=[OK])
    graph, memory = _graph(llm)
    answer = graph.answer(scenario, scenario.suspect("majordome"), "Où étiez-vous ?", [])
    assert (answer.text, answer.verified, answer.attempts) == ("J'étais en cuisine.", True, 1)
    assert len(_statements(memory, "majordome")) == 1


def test_rejected_answer_is_regenerated_with_feedback():
    bad = Verdict(contradiction=True, leak=False, issues=["Tu as dit avoir vu le jardinier : c'est inventé."])
    llm = FakeLLM(texts=["J'ai vu le jardinier.", "Je n'ai vu personne."], objects=[bad, OK])
    graph, memory = _graph(llm)
    answer = graph.answer(scenario, scenario.suspect("medecin"), "Avez-vous vu quelqu'un ?", [])

    assert answer.text == "Je n'ai vu personne."
    assert answer.attempts == 2 and answer.verified
    second_suspect_call = [c for c in llm.calls if c["kind"] == "text"][1]
    assert "c'est inventé" in second_suspect_call["system"]
    assert len(_statements(memory, "medecin")) == 1  # seule la réponse finale est mémorisée


def test_leak_never_reaches_the_player():
    leak = Verdict(contradiction=False, leak=True, issues=["Tu as avoué le crime."])
    llm = FakeLLM(texts=["C'est moi qui l'ai empoisonné."] * 2, objects=[leak, leak])
    graph, _ = _graph(llm, max_attempts=2)
    answer = graph.answer(scenario, scenario.suspect("niece"), "Avouez !", [])

    assert "empoisonné" not in answer.text
    assert answer.attempts == 2 and not answer.verified


def test_without_verifier_the_first_answer_is_returned():
    llm = FakeLLM(texts=["Réponse brute."])
    graph, _ = _graph(llm, verify=False)
    answer = graph.answer(scenario, scenario.suspect("jardinier"), "Où étiez-vous ?", [])
    assert (answer.text, answer.attempts, answer.verified) == ("Réponse brute.", 1, False)
    assert all(call["kind"] == "text" for call in llm.calls)
