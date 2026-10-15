"""Accès au LLM, isolé derrière une petite interface.

Les agents ne connaissent que `LLM.generate` (texte libre) et `LLM.generate_json`
(sortie structurée validée par Pydantic). On peut donc remplacer Claude par un
faux LLM dans les tests, ou par un autre fournisseur, sans toucher aux agents.
"""

import os
from typing import Literal, Protocol, TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from game import GameError

load_dotenv()

DEFAULT_MODEL = "claude-opus-5-5"

Effort = Literal["low", "medium", "high"]
T = TypeVar("T", bound=BaseModel)


class LLMError(GameError):
    """Le LLM n'a pas pu répondre (clé absente, réseau, refus...)."""


class LLM(Protocol):
    def generate(self, system: str, messages: list[dict], effort: Effort = "low") -> str: ...

    def generate_json(
        self, system: str, messages: list[dict], schema: type[T], effort: Effort = "low"
    ) -> T: ...


class ClaudeLLM:
    """Implémentation avec le SDK officiel Anthropic.

    - `effort` règle la profondeur de réflexion (et donc le coût et la latence). Sur les
      modèles Claude récents, il remplace la température, que l'API n'accepte plus.
    - `fallbacks="default"` : si le modèle refuse une requête (ex. faux positif d'un filtre
      de sécurité sur une histoire de meurtre), l'API relance automatiquement sur un autre modèle.
    """

    BETAS = ["server-side-fallback-2026-07-01"]

    def __init__(self, model: str | None = None, max_tokens: int = 4000):
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:  # créé à la demande : on peut lancer le jeu sans clé pour les tests
            self._client = anthropic.Anthropic()
        return self._client

    def generate(self, system: str, messages: list[dict], effort: Effort = "low") -> str:
        response = self._call(
            self.client.beta.messages.create, system=system, messages=messages, effort=effort
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()

    def generate_json(self, system: str, messages: list[dict], schema: type[T], effort: Effort = "low") -> T:
        response = self._call(
            self.client.beta.messages.parse,
            system=system,
            messages=messages,
            effort=effort,
            output_format=schema,
        )
        if response.parsed_output is None:
            raise LLMError("Le LLM n'a pas renvoyé de JSON valide.")
        return response.parsed_output

    def _call(self, method, *, system: str, messages: list[dict], effort: Effort, **extra):
        try:
            response = method(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                output_config={"effort": effort},
                betas=self.BETAS,
                fallbacks="default",
                **extra,
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError("Clé API invalide : vérifiez ANTHROPIC_API_KEY dans le fichier .env.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Trop de requêtes vers le LLM, réessayez dans un instant.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Erreur de l'API LLM ({exc.status_code}) : {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Impossible de joindre l'API LLM (connexion réseau).") from exc
        except TypeError as exc:
            if "authentication" not in str(exc):  # le SDK lève une TypeError quand aucune clé n'est trouvée
                raise
            raise LLMError("Aucune clé API : ajoutez ANTHROPIC_API_KEY dans le fichier .env.") from exc

        if response.stop_reason == "refusal":
            raise LLMError("Le LLM a refusé de répondre à cette question.")
        return response
