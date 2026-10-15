"""Chargement des scénarios JSON depuis le dossier `scenarios/`."""

import json
from pathlib import Path

from game.models import Scenario

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
DEFAULT_SCENARIO = "manoir_valmont"


def list_scenarios() -> list[str]:
    return sorted(path.stem for path in SCENARIOS_DIR.glob("*.json"))


def load_scenario(name: str = DEFAULT_SCENARIO) -> Scenario:
    path = SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scénario introuvable : {name}. Disponibles : {list_scenarios()}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Scenario.model_validate(data)
