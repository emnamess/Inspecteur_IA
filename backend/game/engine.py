"""Moteur de jeu : l'état d'une partie et ses règles.

Toute la logique du jeu est ici, écrite une seule fois. Le serveur MCP et l'API
FastAPI ne font qu'appeler ces méthodes. Les réponses des suspects sont
déléguées à un `Interrogator` injecté, ce qui garde le moteur indépendant du LLM.
"""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from game.models import Scenario, Suspect


class GameError(ValueError):
    """Action impossible (pièce inconnue, partie terminée...). Le message est destiné au joueur."""


@dataclass
class Exchange:
    question: str
    answer: str


@dataclass
class Answer:
    text: str
    verified: bool = True
    attempts: int = 1
    issues: list[str] = field(default_factory=list)


class Interrogator(Protocol):
    def answer(
        self, scenario: Scenario, suspect: Suspect, question: str, history: list[Exchange]
    ) -> Answer: ...


class AlibiInterrogator:
    """Interrogateur hors-ligne, sans LLM : le suspect répète son alibi. Utile pour les tests."""

    def answer(self, scenario: Scenario, suspect: Suspect, question: str, history: list[Exchange]) -> Answer:
        return Answer(text=suspect.alibi)


@dataclass
class Game:
    scenario: Scenario
    interrogator: Interrogator
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    discovered_clues: dict[str, str] = field(default_factory=dict)  # id de l'indice -> id de la pièce
    visited_rooms: list[str] = field(default_factory=list)
    histories: dict[str, list[Exchange]] = field(default_factory=dict)
    verdict: dict | None = None

    @property
    def finished(self) -> bool:
        return self.verdict is not None

    def start_info(self) -> dict:
        victim = self.scenario.victim
        return {
            "game_id": self.id,
            "title": self.scenario.title,
            "intro": self.scenario.intro,
            "victim": {
                "name": victim.name,
                "cause_of_death": victim.cause_of_death,
                "time": victim.time,
                "location": victim.location,
            },
            "rooms": self.list_rooms(),
            "suspects": self.list_suspects(),
        }

    def list_rooms(self) -> list[dict]:
        return [
            {"id": room.id, "name": room.name, "visited": room.id in self.visited_rooms}
            for room in self.scenario.rooms
        ]

    def inspect_room(self, room_id: str) -> dict:
        self._ensure_running()
        room = self.scenario.room(room_id)
        if room is None:
            valid = ", ".join(r.id for r in self.scenario.rooms)
            raise GameError(f"Pièce inconnue : '{room_id}'. Pièces valides : {valid}.")

        if room.id not in self.visited_rooms:
            self.visited_rooms.append(room.id)

        clues, new_clues = [], []
        for clue_id in room.clues:
            clue = self.scenario.clue(clue_id)
            clues.append({"id": clue.id, "name": clue.name, "description": clue.description})
            if clue_id not in self.discovered_clues:
                self.discovered_clues[clue_id] = room.id
                new_clues.append(clue_id)

        return {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "clues": clues,
            "new_clues": new_clues,
        }

    def list_suspects(self) -> list[dict]:
        return [
            {"id": s.id, "name": s.name, "role": s.role, "description": s.description}
            for s in self.scenario.suspects
        ]

    def interrogate(self, suspect_id: str, question: str) -> dict:
        self._ensure_running()
        suspect = self._get_suspect(suspect_id)
        question = question.strip()
        if not question:
            raise GameError("La question est vide.")

        history = self.histories.setdefault(suspect.id, [])
        answer = self.interrogator.answer(self.scenario, suspect, question, list(history))
        history.append(Exchange(question=question, answer=answer.text))

        return {
            "suspect": suspect.id,
            "name": suspect.name,
            "question": question,
            "answer": answer.text,
            "verified": answer.verified,
            "attempts": answer.attempts,
        }

    def get_clues(self) -> list[dict]:
        notebook = []
        for clue_id, room_id in self.discovered_clues.items():
            clue = self.scenario.clue(clue_id)
            notebook.append(
                {
                    "id": clue.id,
                    "name": clue.name,
                    "description": clue.description,
                    "analysis": clue.points_to,
                    "found_in": room_id,
                }
            )
        return notebook

    def accuse(self, suspect_id: str, reasoning: str) -> dict:
        self._ensure_running()
        suspect = self._get_suspect(suspect_id)
        solution = self.scenario.solution
        guilty = self.scenario.suspect(solution.guilty)
        correct = suspect.id == guilty.id

        if correct:
            message = f"Bravo, inspecteur ! {guilty.name} est bien coupable."
        else:
            message = (
                f"Erreur judiciaire : {suspect.name} est innocent(e). Le vrai coupable était {guilty.name}."
            )

        self.verdict = {
            "correct": correct,
            "accused": suspect.id,
            "reasoning": reasoning,
            "message": message,
            "solution": {
                "guilty": guilty.id,
                "guilty_name": guilty.name,
                "motive": solution.motive,
                "method": solution.method,
            },
            "clues_found": len(self.discovered_clues),
            "clues_total": len(self.scenario.clues),
        }
        return self.verdict

    def _get_suspect(self, suspect_id: str) -> Suspect:
        suspect = self.scenario.suspect(suspect_id)
        if suspect is None:
            valid = ", ".join(s.id for s in self.scenario.suspects)
            raise GameError(f"Suspect inconnu : '{suspect_id}'. Suspects valides : {valid}.")
        return suspect

    def _ensure_running(self) -> None:
        if self.finished:
            raise GameError("La partie est terminée. Lancez une nouvelle partie avec start_game.")
