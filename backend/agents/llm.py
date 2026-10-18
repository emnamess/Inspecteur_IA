"""Accès au LLM, isolé derrière une petite interface.

Les agents ne connaissent que `LLM.generate` (texte libre) et `LLM.generate_json`
(sortie structurée validée par Pydantic). On peut donc changer de fournisseur
(Gemini, Claude) ou utiliser un faux LLM dans les tests, sans toucher aux agents.
Le fournisseur se choisit avec la variable LLM_PROVIDER du fichier .env.
"""

import os
import time
from typing import Literal, Protocol, TypeVar

import anthropic
import httpx
import httpx2
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel

from game import GameError

load_dotenv()

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODELS = {"gemini": "gemini-3.8-flash", "anthropic": "claude-opus-5-5"}
DEFAULT_GEMINI_FALLBACKS = "gemini-3.6-flash,gemini-3.5-flash-lite"  # chacun a son propre quota

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
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS["anthropic"]
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


class GeminiLLM:
    """Implémentation avec le SDK officiel Google (`google-genai`), utilisable gratuitement.

    - `effort` est traduit en `thinking_level` : la profondeur de réflexion du modèle. Les suspects
      (effort « low ») réfléchissent au minimum : pour du dialogue, c'est bien plus rapide et suffisant.
    - Sorties structurées : Gemini reçoit le schéma JSON du modèle Pydantic, puis on valide
      nous-mêmes la réponse (une incohérence lève une ValidationError, comme avec Claude).
    - Chaîne de modèles : si un modèle est surchargé (503), trop lent (TIMEOUT_SECONDS) ou a
      épuisé son quota du jour (429), on passe tout de suite au suivant (GEMINI_FALLBACK_MODELS).
      L'offre gratuite limite en effet chaque modèle à quelques requêtes par jour.
    - Un 429 « par minute » (attente courte) est simplement réessayé après la pause demandée.
    """

    THINKING = {"low": "MINIMAL", "medium": "LOW", "high": "HIGH"}
    TIMEOUT_SECONDS = {"low": 45, "medium": 60, "high": 300}  # le Maître du jeu écrit un long scénario
    TIMEOUTS = (httpx.TimeoutException, httpx2.TimeoutException)
    MAX_RETRIES = 8
    MAX_WAIT_SECONDS = 60  # au-delà, on n'attend pas : on change de modèle

    def __init__(self, model: str | None = None, max_tokens: int = 8000):
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS["gemini"]
        fallbacks = os.getenv("GEMINI_FALLBACK_MODELS", DEFAULT_GEMINI_FALLBACKS)
        self.models = list(dict.fromkeys([self.model, *filter(None, fallbacks.split(","))]))
        self.max_tokens = max_tokens
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:  # créé à la demande : on peut lancer le jeu sans clé pour les tests
            try:
                self._client = genai.Client()  # lit GEMINI_API_KEY dans l'environnement
            except ValueError as exc:
                raise LLMError("Aucune clé API : ajoutez GEMINI_API_KEY dans le fichier .env.") from exc
        return self._client

    def generate(self, system: str, messages: list[dict], effort: Effort = "low") -> str:
        return self._call(system, messages, effort)

    def generate_json(self, system: str, messages: list[dict], schema: type[T], effort: Effort = "low") -> T:
        text = self._call(
            system, messages, effort, response_mime_type="application/json", response_schema=schema
        )
        return schema.model_validate_json(text)

    def _call(self, system: str, messages: list[dict], effort: Effort, **extra) -> str:
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self.max_tokens,
            thinking_config=genai_types.ThinkingConfig(thinking_level=self.THINKING[effort]),
            # attempts=1 : on gère nous-mêmes les nouvelles tentatives et le modèle de secours.
            http_options=genai_types.HttpOptions(
                timeout=self.TIMEOUT_SECONDS[effort] * 1000,
                retry_options=genai_types.HttpRetryOptions(attempts=1),
            ),
            **extra,
        )
        # Gemini appelle « model » le rôle que Claude appelle « assistant ».
        contents = [
            genai_types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[genai_types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]

        models = self.models
        current = 0  # indice du modèle utilisé dans `models`
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=models[current], contents=contents, config=config
                )
                break
            except genai_errors.ClientError as exc:
                if exc.code == 400 and "Thinking level" in str(exc.message):
                    # Tous les modèles n'acceptent pas MINIMAL : on remonte d'un cran pour ce modèle.
                    config = config.model_copy(
                        update={"thinking_config": genai_types.ThinkingConfig(thinking_level="LOW")}
                    )
                    continue
                if exc.code == 429:
                    wait = _retry_delay_seconds(exc)
                    if wait is not None and wait <= self.MAX_WAIT_SECONDS and attempt < self.MAX_RETRIES - 1:
                        time.sleep(wait)  # quota par minute : la pause demandée est courte
                        continue
                    if current < len(models) - 1:
                        current += 1  # quota du jour épuisé pour ce modèle : on passe au suivant
                        continue
                    raise LLMError(
                        "Quota gratuit du jour épuisé pour tous les modèles Gemini. "
                        "Il se renouvelle chaque jour (vers 9h, heure de Paris)."
                    ) from exc
                if exc.code in (400, 401, 403) and "API key" in str(exc):
                    raise LLMError(
                        "Clé API invalide : vérifiez GEMINI_API_KEY dans le fichier .env."
                    ) from exc
                raise LLMError(f"Erreur de l'API Gemini ({exc.code}) : {exc.message}") from exc
            except (genai_errors.ServerError, *self.TIMEOUTS) as exc:
                if current < len(models) - 1:
                    current += 1  # modèle surchargé : on passe tout de suite au modèle de secours
                    continue
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(5)
                    continue
                raise LLMError("L'API Gemini est surchargée ou trop lente, réessayez plus tard.") from exc

        if not response.text:  # réponse bloquée par un filtre de sécurité, ou vide
            raise LLMError("Le LLM a refusé de répondre à cette question.")
        return response.text.strip()


def _retry_delay_seconds(exc: genai_errors.APIError) -> float | None:
    """Lit la pause demandée par Google dans une erreur 429 (ex. « 34s »), si elle est fournie."""
    details = exc.details.get("error", {}).get("details", []) if isinstance(exc.details, dict) else []
    for detail in details:
        delay = detail.get("retryDelay")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


def default_llm(model: str | None = None, max_tokens: int | None = None) -> LLM:
    """Crée le LLM choisi par LLM_PROVIDER (« gemini » par défaut, ou « anthropic »)."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"LLM_PROVIDER inconnu : {provider}. Valeurs possibles : {list(DEFAULT_MODELS)}")
    cls = GeminiLLM if provider == "gemini" else ClaudeLLM
    return cls(model, max_tokens) if max_tokens else cls(model)
