"""Modèle de données d'un scénario, validé avec Pydantic.

Pydantic vérifie les types champ par champ, puis `Scenario.check_consistency`
vérifie les liens entre les parties (un indice cité existe, un seul coupable...).
Un scénario écrit à la main ou généré par le Maître du jeu passe par la même validation.
"""

from pydantic import BaseModel, Field, model_validator


class Victim(BaseModel):
    name: str
    cause_of_death: str
    time: str = Field(description="Heure du décès, format HH:MM")
    location: str = Field(description="Identifiant de la pièce où le corps a été trouvé")


class Room(BaseModel):
    id: str
    name: str
    description: str
    clues: list[str] = Field(default_factory=list, description="Identifiants des indices présents")


class Suspect(BaseModel):
    id: str
    name: str
    role: str = Field(description="Rôle public : majordome, nièce...")
    description: str = Field(description="Présentation publique, visible par le joueur")
    personality: str
    alibi: str = Field(description="Ce que le suspect affirme avoir fait au moment du crime")
    secrets: list[str] = Field(default_factory=list, description="Ce que le suspect cache")
    knows: list[str] = Field(default_factory=list, description="Faits vrais que le suspect connaît")
    lies: list[str] = Field(
        default_factory=list,
        description="Mensonges autorisés : seuls points sur lesquels le suspect peut mentir",
    )
    is_guilty: bool = False


class Clue(BaseModel):
    id: str
    name: str
    description: str
    points_to: str = Field(description="Ce que l'indice suggère (pour le joueur attentif)")


class TimelineEvent(BaseModel):
    time: str
    event: str


class Solution(BaseModel):
    guilty: str = Field(description="Identifiant du suspect coupable")
    motive: str
    method: str


class Scenario(BaseModel):
    title: str
    intro: str = Field(description="Texte d'ambiance lu au début de la partie")
    victim: Victim
    rooms: list[Room]
    suspects: list[Suspect]
    clues: list[Clue]
    timeline: list[TimelineEvent] = Field(
        description="Vérité chronologique : sert au Vérificateur, jamais montrée au joueur"
    )
    solution: Solution

    @model_validator(mode="after")
    def check_consistency(self) -> "Scenario":
        room_ids = [room.id for room in self.rooms]
        suspect_ids = [suspect.id for suspect in self.suspects]
        clue_ids = [clue.id for clue in self.clues]

        for label, ids in (("pièce", room_ids), ("suspect", suspect_ids), ("indice", clue_ids)):
            if len(ids) != len(set(ids)):
                raise ValueError(f"Identifiants de {label} en double : {ids}")

        if self.victim.location not in room_ids:
            raise ValueError(f"Lieu du crime inconnu : {self.victim.location}")

        for room in self.rooms:
            for clue_id in room.clues:
                if clue_id not in clue_ids:
                    raise ValueError(f"La pièce '{room.id}' cite un indice inconnu : {clue_id}")

        placed = {clue_id for room in self.rooms for clue_id in room.clues}
        unplaced = set(clue_ids) - placed
        if unplaced:
            raise ValueError(f"Indices placés dans aucune pièce : {sorted(unplaced)}")

        guilty = [suspect.id for suspect in self.suspects if suspect.is_guilty]
        if len(guilty) != 1:
            raise ValueError(f"Il faut exactement un coupable, trouvé : {guilty}")
        if self.solution.guilty != guilty[0]:
            raise ValueError("solution.guilty ne correspond pas au suspect marqué is_guilty")

        return self

    def suspect(self, suspect_id: str) -> Suspect | None:
        return next((s for s in self.suspects if s.id == suspect_id), None)

    def room(self, room_id: str) -> Room | None:
        return next((r for r in self.rooms if r.id == room_id), None)

    def clue(self, clue_id: str) -> Clue | None:
        return next((c for c in self.clues if c.id == clue_id), None)
