"""Faux LLM pour les tests : réponses scriptées, aucun appel réseau, aucune clé nécessaire."""

from pydantic import BaseModel


class FakeLLM:
    """Renvoie les réponses prévues, dans l'ordre, et enregistre les appels reçus."""

    def __init__(self, texts: list[str] | None = None, objects: list[BaseModel] | None = None):
        self.texts = list(texts or [])
        self.objects = list(objects or [])
        self.calls: list[dict] = []

    def generate(self, system, messages, effort="low"):
        self.calls.append({"kind": "text", "system": system, "messages": messages})
        return self.texts.pop(0) if self.texts else "Je n'ai rien à ajouter, inspecteur."

    def generate_json(self, system, messages, schema, effort="low"):
        self.calls.append({"kind": "json", "system": system, "messages": messages, "schema": schema})
        if not self.objects:
            raise AssertionError(f"FakeLLM : aucune réponse JSON prévue pour {schema.__name__}")
        obj = self.objects.pop(0)
        return obj if isinstance(obj, schema) else schema.model_validate(obj)
