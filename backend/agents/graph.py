"""Orchestration des agents avec LangGraph.

    question → [suspect] → [vérificateur] → OK : on renvoie la réponse
                   ↑              │
                   └── KO ────────┘  (avec les problèmes en feedback, au plus MAX_ATTEMPTS fois)

Le graphe rend la boucle de correction explicite : chaque nœud est une étape,
l'état circule entre les nœuds, et une arête conditionnelle décide de la suite.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.suspect import SuspectAgent
from agents.verifier import Verdict, Verifier
from game import Answer, Exchange, Scenario
from game.models import Suspect

MAX_ATTEMPTS = 3


class InterrogationState(TypedDict, total=False):
    scenario: Scenario
    suspect: Suspect
    question: str
    history: list[Exchange]
    answer: str
    verdict: Verdict | None
    attempts: int
    feedback: list[str]


class InterrogationGraph:
    """Implémente l'interface `Interrogator` du moteur : Suspect + Vérificateur (optionnel)."""

    def __init__(
        self, suspect_agent: SuspectAgent, verifier: Verifier | None, max_attempts: int = MAX_ATTEMPTS
    ):
        self.suspect_agent = suspect_agent
        self.verifier = verifier
        self.max_attempts = max_attempts
        self.graph = self._build()

    def _build(self):
        graph = StateGraph(InterrogationState)
        graph.add_node("suspect", self._suspect_node)
        graph.add_edge(START, "suspect")
        if self.verifier is None:  # mode « sans Vérificateur », utilisé par l'évaluation
            graph.add_edge("suspect", END)
        else:
            graph.add_node("verifier", self._verifier_node)
            graph.add_edge("suspect", "verifier")
            graph.add_conditional_edges("verifier", self._route, {"retry": "suspect", "done": END})
        return graph.compile()

    def _suspect_node(self, state: InterrogationState) -> InterrogationState:
        text = self.suspect_agent.generate(
            state["scenario"], state["suspect"], state["question"], state["history"], state.get("feedback")
        )
        return {"answer": text, "attempts": state.get("attempts", 0) + 1}

    def _verifier_node(self, state: InterrogationState) -> InterrogationState:
        verdict = self.verifier.check(
            state["scenario"], state["suspect"], state["question"], state["answer"], state["history"]
        )
        return {"verdict": verdict, "feedback": verdict.issues}

    def _route(self, state: InterrogationState) -> str:
        if state["verdict"].ok or state["attempts"] >= self.max_attempts:
            return "done"
        return "retry"

    def answer(self, scenario: Scenario, suspect: Suspect, question: str, history: list[Exchange]) -> Answer:
        final = self.graph.invoke(
            {"scenario": scenario, "suspect": suspect, "question": question, "history": history}
        )
        verdict: Verdict | None = final.get("verdict")
        text = final["answer"]

        if verdict is not None and verdict.leak:
            # Dernier filet de sécurité : une fuite de la solution n'atteint jamais le joueur.
            text = f"{suspect.name} vous fixe longuement, puis détourne le regard sans répondre."

        self.suspect_agent.remember(suspect, question, text)
        return Answer(
            text=text,
            verified=verdict.ok if verdict is not None else False,
            attempts=final["attempts"],
            issues=verdict.issues if verdict is not None else [],
        )
