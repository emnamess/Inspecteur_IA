"""Agent Maître du jeu : génère un scénario complet et cohérent.

La sortie est contrainte au schéma JSON du modèle `Scenario` (sorties structurées),
puis validée par Pydantic, y compris les règles de cohérence (un seul coupable,
indices tous placés...). En cas d'échec, l'erreur est renvoyée au LLM pour qu'il corrige.
"""

import json
import random
from pathlib import Path

from pydantic import ValidationError

from agents.llm import LLM, LLMError
from game.models import Scenario
from game.scenario import SCENARIOS_DIR

GENERATED_DIR = SCENARIOS_DIR / "generated"

SETTINGS = [
    "un manoir isolé sur la lande bretonne",
    "un train de nuit entre Paris et Venise",
    "un palace de la Côte d'Azur dans les années 1930",
    "une abbaye transformée en hôtel dans les Alpes",
    "un paquebot transatlantique",
    "un vignoble bordelais pendant les vendanges",
]
WEAPONS = ["un poison", "une arme blanche", "un objet contondant", "une chute provoquée", "un étranglement"]

SYSTEM_PROMPT = """Tu es le Maître du jeu d'un jeu d'enquête policière en français. Tu écris des \
scénarios de meurtre classiques (style Agatha Christie), cohérents et solubles par déduction.

Contraintes :
- Exactement 4 suspects, dont exactement 1 coupable (is_guilty = true), et solution.guilty = son id.
- 5 pièces. La victime est trouvée dans l'une d'elles (victim.location = id de cette pièce).
- 6 à 9 indices ; chaque indice est placé dans exactement une pièce (rooms[].clues).
- Les identifiants sont courts, en minuscules, sans accents ni espaces (ex. "bibliotheque", "majordome").
- Chaque suspect a une personnalité marquée, un alibi, au moins un secret et 3 à 5 faits vrais (knows).
- Chaque innocent cache un secret qui en fait une fausse piste crédible.
- `lies` liste les seuls points sur lesquels un suspect a le droit de mentir. Le coupable ment sur \
son alibi et sur ce qui le relie au crime.
- `timeline` est la vérité complète, heure par heure, cohérente avec tous les alibis, faits et indices.
- Le coupable doit pouvoir être démasqué en croisant au moins 3 indices et un témoignage.
- `intro` est un court texte d'ambiance qui ne révèle rien de la solution."""


class GameMaster:
    def __init__(self, llm: LLM):
        self.llm = llm

    def generate(self, seed: int, max_attempts: int = 3) -> Scenario:
        rng = random.Random(seed)  # même seed = même consigne = scénario reproductible (avec le cache)
        request = (
            f"Écris un nouveau scénario. Cadre : {rng.choice(SETTINGS)}. "
            f"Arme du crime : {rng.choice(WEAPONS)}. Numéro de scénario : {seed}."
        )
        messages = [{"role": "user", "content": request}]

        for _ in range(max_attempts):
            try:
                return self.llm.generate_json(SYSTEM_PROMPT, messages, Scenario, effort="high")
            except ValidationError as exc:
                correction = f"Ta proposition précédente était incohérente : {exc}. Corrige ces erreurs."
                messages = [{"role": "user", "content": f"{request}\n\n{correction}"}]
        raise LLMError(f"Le Maître du jeu n'a pas produit de scénario cohérent en {max_attempts} essais.")


def generated_scenario(seed: int, game_master: GameMaster) -> Scenario:
    """Renvoie le scénario de ce seed : depuis le cache disque s'il existe, sinon généré puis sauvé."""
    path: Path = GENERATED_DIR / f"seed_{seed}.json"
    if path.exists():
        return Scenario.model_validate_json(path.read_text(encoding="utf-8"))

    scenario = game_master.generate(seed)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scenario.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return scenario
