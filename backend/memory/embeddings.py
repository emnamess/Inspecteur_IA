"""Embeddings : transformer un texte en vecteur pour la recherche par similarité.

Deux textes de sens proche donnent des vecteurs proches (cosinus élevé), même
sans mot en commun : « Qui a apporté la boisson ? » est proche de
« J'ai servi le whisky au comte ».
"""

import hashlib
import math
import os
import re
from functools import cached_property
from typing import Protocol

DEFAULT_EMBEDDING_MODEL = "minishlab/potion-multilingual-128M"


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Model2VecEmbedder:
    """Modèle d'embeddings multilingue local (model2vec : embeddings statiques, numpy seul).

    Choisi car il tourne sur CPU sans GPU ni onnxruntime, en quelques millisecondes,
    et gère le français. Le modèle (~500 Mo) est téléchargé une fois depuis Hugging Face.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    @cached_property
    def model(self):
        from model2vec import StaticModel  # import tardif : chargement lent, inutile dans les tests

        return StaticModel.from_pretrained(self.model_name)

    @property
    def dim(self) -> int:
        return self.model.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()


class HashingEmbedder:
    """Embedder lexical minimal (sac de mots haché), sans dépendance ni téléchargement.

    Il ne capte que les mots en commun, pas le sens : il sert aux tests et au mode hors-ligne.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in re.findall(r"\w{3,}", text.lower()):
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def default_embedder() -> Embedder:
    if os.getenv("EMBEDDER", "model2vec") == "hashing":
        return HashingEmbedder()
    return Model2VecEmbedder()
