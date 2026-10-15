"""Mémoire des suspects dans Qdrant (base vectorielle).

Chaque souvenir est un point Qdrant : un vecteur (l'embedding du texte) et un
payload (partie, suspect, type, texte). Pour répondre à une question, on cherche
les souvenirs du suspect les plus proches de la question : c'est le « R » de RAG
(Retrieval), avant l'injection dans le prompt (Augmented Generation).
"""

import os
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from game.models import Scenario
from memory.embeddings import Embedder, default_embedder

COLLECTION = "suspect_memory"

KIND_LABELS = {
    "fact": "fait",
    "secret": "secret à cacher",
    "statement": "ce que tu as déjà déclaré",
}


@dataclass
class Memory:
    text: str
    kind: str
    score: float

    def as_prompt_line(self) -> str:
        return f"[{KIND_LABELS.get(self.kind, self.kind)}] {self.text}"


def default_client() -> QdrantClient:
    """Serveur Qdrant si QDRANT_URL est défini (Docker), sinon Qdrant en mémoire dans le processus."""
    url = os.getenv("QDRANT_URL")
    return QdrantClient(url=url) if url else QdrantClient(":memory:")


def _is_server(client: QdrantClient) -> bool:
    return client.init_options.get("url") is not None


class SuspectMemory:
    def __init__(self, client: QdrantClient | None = None, embedder: Embedder | None = None):
        self.client = client or default_client()
        self.embedder = embedder or default_embedder()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(COLLECTION):
            return
        self.client.create_collection(
            COLLECTION,
            vectors_config=models.VectorParams(size=self.embedder.dim, distance=models.Distance.COSINE),
        )
        # Index sur les champs filtrés : accélère la recherche (inutile en mode local, en mémoire).
        if _is_server(self.client):
            for field_name in ("game_id", "suspect_id"):
                self.client.create_payload_index(COLLECTION, field_name, models.PayloadSchemaType.KEYWORD)

    def index_scenario(self, game_id: str, scenario: Scenario) -> int:
        """Indexe les faits et secrets de chaque suspect. Renvoie le nombre de souvenirs."""
        entries = [
            (suspect.id, kind, text)
            for suspect in scenario.suspects
            for kind, texts in (("fact", suspect.knows), ("secret", suspect.secrets))
            for text in texts
        ]
        self._add(game_id, entries)
        return len(entries)

    def remember_statement(self, game_id: str, suspect_id: str, question: str, answer: str) -> None:
        text = f"L'inspecteur m'a demandé « {question} » ; j'ai répondu : « {answer} »"
        self._add(game_id, [(suspect_id, "statement", text)])

    def recall(self, game_id: str, suspect_id: str, query: str, limit: int = 5) -> list[Memory]:
        [query_vector] = self.embedder.embed([query])
        result = self.client.query_points(
            COLLECTION,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(key="game_id", match=models.MatchValue(value=game_id)),
                    models.FieldCondition(key="suspect_id", match=models.MatchValue(value=suspect_id)),
                ]
            ),
            limit=limit,
        )
        return [
            Memory(text=point.payload["text"], kind=point.payload["kind"], score=point.score)
            for point in result.points
        ]

    def forget_game(self, game_id: str) -> None:
        self.client.delete(
            COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="game_id", match=models.MatchValue(value=game_id))]
                )
            ),
        )

    def _add(self, game_id: str, entries: list[tuple[str, str, str]]) -> None:
        if not entries:
            return
        vectors = self.embedder.embed([text for _, _, text in entries])
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"game_id": game_id, "suspect_id": suspect_id, "kind": kind, "text": text},
            )
            for (suspect_id, kind, text), vector in zip(entries, vectors, strict=True)
        ]
        self.client.upsert(COLLECTION, points=points)
