"""Agent Vérificateur : contrôle chaque réponse d'un suspect avant qu'elle n'atteigne le joueur.

Contrairement au suspect, il connaît toute la vérité (chronologie, fiche complète,
solution). Il renvoie un verdict structuré (JSON validé par Pydantic) plutôt que du
texte libre : le graphe peut ainsi décider automatiquement d'accepter ou de régénérer.
"""

from pydantic import BaseModel, Field

from agents.llm import LLM
from game import Exchange, Scenario
from game.models import Suspect


class Verdict(BaseModel):
    contradiction: bool = Field(
        description="La réponse contredit les faits du scénario hors mensonges autorisés, "
        "invente un fait important, ou contredit une déclaration précédente du suspect."
    )
    leak: bool = Field(
        description="La réponse révèle la solution : aveu du coupable, méthode ou mobile du crime, "
        "ou un innocent qui désigne le coupable sans le savoir."
    )
    issues: list[str] = Field(description="Problèmes précis constatés, vide si la réponse est correcte.")

    @property
    def ok(self) -> bool:
        return not (self.contradiction or self.leak)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (aucun)"


def build_verifier_prompt(scenario: Scenario, suspect: Suspect) -> str:
    timeline = "\n".join(f"- {event.time} : {event.event}" for event in scenario.timeline)
    solution = scenario.solution
    status = "COUPABLE" if suspect.is_guilty else "innocent"
    return f"""Tu es le Vérificateur d'un jeu d'enquête policière. Tu contrôles la réponse d'un suspect \
joué par une IA, pour garantir qu'elle reste fidèle au scénario.

LA VÉRITÉ (chronologie réelle) :
{timeline}

SOLUTION : coupable = {solution.guilty}. Mobile : {solution.motive} Méthode : {solution.method}

FICHE DU SUSPECT : {suspect.name} ({suspect.role}), {status}.
Alibi affiché : {suspect.alibi}
Ce qu'il sait :
{_bullets(suspect.knows)}
Ses secrets :
{_bullets(suspect.secrets)}
Mensonges autorisés (ne sont PAS des contradictions) :
{_bullets(suspect.lies)}

Critères :
1. contradiction = vrai si la réponse affirme quelque chose de faux par rapport à la vérité ou à ce que \
le suspect sait, SAUF si c'est un mensonge autorisé ; ou si elle invente un fait important absent du \
scénario (témoin, objet, horaire, lieu, événement) ; ou si elle contredit une réponse précédente du suspect.
2. leak = vrai si le coupable avoue ou décrit sa méthode ou son mobile ; ou si un innocent désigne \
le coupable ou révèle la solution sans que cela fasse partie de ce qu'il sait.
3. Ne signale PAS : une réponse vague, évasive, émotive ou un refus de répondre ; un mensonge autorisé ; \
un secret avoué par un innocent (c'est permis) ; un fait vrai que le suspect connaît.
Dans `issues`, décris chaque problème en une phrase, adressée au suspect (« Tu as affirmé... »)."""


def build_verifier_message(question: str, answer: str, history: list[Exchange]) -> str:
    previous = "\n".join(f"Q : {e.question}\nR : {e.answer}" for e in history) or "(aucune)"
    return f"""Réponses précédentes du suspect :
{previous}

Question de l'inspecteur : {question}
Réponse à vérifier : {answer}"""


class Verifier:
    def __init__(self, llm: LLM):
        self.llm = llm

    def check(
        self, scenario: Scenario, suspect: Suspect, question: str, answer: str, history: list[Exchange]
    ) -> Verdict:
        system = build_verifier_prompt(scenario, suspect)
        message = build_verifier_message(question, answer, history)
        return self.llm.generate_json(
            system, [{"role": "user", "content": message}], Verdict, effort="medium"
        )
