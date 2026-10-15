import os

# Les tests n'utilisent ni le vrai modèle d'embeddings (long à charger) ni un serveur Qdrant.
os.environ["EMBEDDER"] = "hashing"
os.environ.pop("QDRANT_URL", None)
