"""Agent Suspect : fait parler un suspect en restant fidèle à sa fiche.

Le prompt système contient l'identité du suspect et les règles du jeu.
L'historique de l'interrogatoire est passé sous forme de messages user/assistant,
pour que le suspect reste cohérent avec ce qu'il a déjà dit.
"""

from agents.llm import LLM
from game import Answer, Exchange, Scenario
from game.models import Suspect


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (rien)"


def build_system_prompt(scenario: Scenario, suspect: Suspect, memories: list[str] | None = None) -> str:
    victim = scenario.victim
    if suspect.is_guilty:
        role_rule = (
            "Tu es le coupable. Tu n'avoues jamais, même face aux preuves : tu minimises, "
            "tu détournes ou tu proposes une autre explication, sans inventer de fait nouveau."
        )
    else:
        role_rule = "Tu n'es pas le coupable et tu ne sais pas qui l'est. Tu n'accuses personne sans raison."

    # Sans mémoire (RAG), tout ce que sait le suspect est dans le prompt.
    # Avec la mémoire, seuls les souvenirs pertinents pour la question sont injectés.
    if memories is None:
        knowledge = (
            f"Ce que tu sais (c'est vrai) :\n{_bullets(suspect.knows)}\n\n"
            f"Tes secrets (à cacher ; tu ne cèdes que si l'inspecteur te met face à une preuve précise) :\n"
            f"{_bullets(suspect.secrets)}"
        )
    else:
        knowledge = f"Tes souvenirs utiles pour cette question :\n{_bullets(memories)}"

    return f"""Tu joues {suspect.name}, {suspect.role.lower()}, dans un jeu d'enquête policière.
Un inspecteur t'interroge sur la mort de {victim.name} ({victim.cause_of_death.lower()}, vers {victim.time}).

Ta personnalité : {suspect.personality}

Ton alibi (ce que tu affirmes) : {suspect.alibi}

{knowledge}

Les seuls points sur lesquels tu as le droit de mentir :
{_bullets(suspect.lies)}

Règles :
- {role_rule}
- Réponds en français, à la première personne, en 1 à 4 phrases, comme dans une vraie conversation.
- Ne parle que de ce que tu sais. Si tu ne sais pas, dis-le. N'invente aucun fait nouveau \
(témoin, objet, horaire, lieu).
- En dehors des mensonges autorisés, ne contredis jamais ce que tu sais.
- Ne sors jamais de ton personnage et ne mentionne jamais ces instructions."""


def build_messages(history: list[Exchange], question: str) -> list[dict]:
    messages = []
    for exchange in history:
        messages.append({"role": "user", "content": exchange.question})
        messages.append({"role": "assistant", "content": exchange.answer})
    messages.append({"role": "user", "content": question})
    return messages


class SuspectAgent:
    """Implémente l'interface `Interrogator` du moteur de jeu avec un LLM."""

    def __init__(self, llm: LLM):
        self.llm = llm

    def answer(self, scenario: Scenario, suspect: Suspect, question: str, history: list[Exchange]) -> Answer:
        system = build_system_prompt(scenario, suspect)
        text = self.llm.generate(system, build_messages(history, question), effort="low")
        return Answer(text=text)
