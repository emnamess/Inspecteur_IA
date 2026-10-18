# 🕵️ Inspecteur IA

**Un jeu d'enquête policière où chaque suspect est un agent IA**, exposé par un **serveur MCP** : on y joue depuis l'interface web… ou directement depuis Claude Desktop ou VS Code.

Un meurtre a eu lieu au manoir de Valmont. Vous fouillez les pièces, interrogez les quatre suspects en langage naturel, confrontez leurs versions, puis accusez un coupable. Chaque suspect a sa personnalité, ses secrets et sa mémoire ; le coupable ment, et les innocents cachent eux aussi quelque chose. Un **agent Vérificateur** contrôle chaque réponse pour empêcher le LLM d'inventer des faits ou de révéler la solution.

![Démo d'une partie : fouille des pièces, interrogatoire des suspects, accusation](docs/demo.gif)

## Ce que montre le projet

| Compétence | Où |
|---|---|
| **Serveur MCP** | [backend/mcp_server.py](backend/mcp_server.py) : 7 outils (`start_game`, `inspect_room`, `interrogate`, `accuse`…) |
| **Multi-agents** | Maître du jeu, Suspects, Vérificateur, orchestrés avec **LangGraph** ([backend/agents/graph.py](backend/agents/graph.py)) |
| **RAG / base vectorielle** | Mémoire de chaque suspect dans **Qdrant** ([backend/memory/store.py](backend/memory/store.py)) |
| **Fiabilité des LLM** | Vérificateur + boucle de régénération + sorties structurées validées par Pydantic + [évaluation](eval/run_eval.py) |
| **Full-stack** | API **FastAPI** + front **React / TypeScript / Tailwind** |
| **Industrialisation** | Docker Compose, 51 tests pytest (sans clé API), CI GitHub Actions |

## Architecture

```
┌──────────────────┐     ┌──────────────────┐
│ Front React/TS   │     │ Client MCP       │
│ (plan, carnet,   │     │ (Claude Desktop, │
│  interrogatoire) │     │  VS Code…)       │
└────────┬─────────┘     └────────┬─────────┘
         │ REST                   │ MCP (stdio)
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│ api.py (FastAPI) │     │ mcp_server.py    │   deux « portes d'entrée »…
└────────┬─────────┘     └────────┬─────────┘
         └──────────┬─────────────┘
                    ▼
        ┌───────────────────────┐
        │ game/ : moteur de jeu │   …sur une seule logique de jeu
        └───────────┬───────────┘
                    │ Interrogator (injecté)
                    ▼
        ┌───────────────────────────────────────────┐
        │ agents/ (LangGraph)                       │
        │   question → Suspect → Vérificateur ─┐    │
        │                 ▲          KO        │    │
        │                 └────────────────────┘    │
        │   Maître du jeu (génère les scénarios)    │
        └──────┬──────────────────────────┬─────────┘
               ▼                          ▼
        ┌─────────────┐            ┌─────────────┐
        │ Qdrant      │            │ API du LLM  │
        │ (mémoire)   │            │  (Gemini)   │
        └─────────────┘            └─────────────┘
```

**Principe clé : la logique du jeu est écrite une seule fois**, dans `game/`. Le moteur ne connaît pas le LLM : il reçoit un `Interrogator` (l'interface « fais répondre ce suspect »). Le serveur MCP et l'API FastAPI ne font que traduire leur protocole vers les méthodes du moteur. Résultat : le moteur se teste sans LLM, et ajouter une troisième interface (CLI, Discord…) ne demanderait aucune règle de jeu en plus.

### Le chemin d'une question

1. Le joueur demande au majordome *« Avez-vous apporté quelque chose au comte ? »*
2. **RAG** : la question est transformée en vecteur (embedding), et Qdrant renvoie les souvenirs du majordome les plus proches. Ici, *« À 21h50, il a servi un verre de whisky au comte… »*, même sans mot en commun.
3. **Agent Suspect** : le LLM reçoit la personnalité, l'alibi, les mensonges autorisés, ces souvenirs et les derniers échanges, puis répond dans son rôle.
4. **Agent Vérificateur** : un second appel, qui connaît toute la vérité (chronologie, solution), renvoie un verdict structuré `{contradiction, leak, issues}`.
5. **LangGraph** : si le verdict est KO, on revient au Suspect avec les problèmes en feedback (3 essais maximum). Une fuite de la solution n'atteint jamais le joueur.
6. La réponse finale est mémorisée dans Qdrant : le suspect restera cohérent plus tard.

## Démarrage rapide

**Prérequis :** Python 3.11+, Node 22+, une clé API **Gemini gratuite** ([Google AI Studio](https://aistudio.google.com/apikey)).

```bash
cp .env.example .env            # puis renseignez GEMINI_API_KEY
```

Le projet fonctionne aussi avec Claude : `LLM_PROVIDER=anthropic` et `ANTHROPIC_API_KEY` dans `.env`.

### Back-end

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux : source .venv/bin/activate)
pip install -r requirements-dev.txt
pytest                          # 51 tests, aucune clé nécessaire
uvicorn api:app --reload        # API sur http://localhost:8000 (docs : /docs)
```

Au premier lancement, le modèle d'embeddings multilingue (~500 Mo) est téléchargé depuis Hugging Face.

### Front-end

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Raccourci (Windows) : `npm start` dans `frontend/` lance l'API **et** le front en une seule commande.

### Tout en Docker

```bash
docker compose up --build       # http://localhost:8080 (front) — Qdrant en serveur, persistant
```

## Jouer via MCP

**MCP Inspector** (pour tester les outils à la main) :

```bash
npx @modelcontextprotocol/inspector backend/.venv/Scripts/python.exe backend/mcp_server.py
```

**VS Code (Copilot, mode agent)** : la configuration est déjà dans [.vscode/mcp.json](.vscode/mcp.json). Il suffit de démarrer le serveur depuis ce fichier.

**Claude Desktop** : ajoutez ceci dans `claude_desktop_config.json` (en adaptant les chemins) :

```json
{
  "mcpServers": {
    "inspecteur-ia": {
      "command": "C:\\chemin\\vers\\Inspecteur_IA\\backend\\.venv\\Scripts\\python.exe",
      "args": ["C:\\chemin\\vers\\Inspecteur_IA\\backend\\mcp_server.py"]
    }
  }
}
```

Puis : *« Lance une partie d'Inspecteur IA, fouille la bibliothèque et interroge le majordome. »*

## Évaluation

[eval/run_eval.py](eval/run_eval.py) joue N parties **avec et sans Vérificateur**, en posant 10 questions types, dont 4 **questions pièges** : une fausse prémisse (*« Vous avez vu le jardinier entrer dans la bibliothèque, n'est-ce pas ? »*) ou une pression pour avouer. Chaque réponse finale est notée par un juge LLM indépendant.

```bash
python eval/run_eval.py --games 20 --workers 1                  # mesure complète
python eval/run_eval.py --games 3 --workers 1                   # essai rapide
python eval/run_eval.py --games 1 --dry-run                     # vérifie le script, sans API
```

Le script mesure, pour chaque mode :

- le **taux de contradictions** : réponses qui contredisent le scénario ou inventent un fait, en particulier sur les questions pièges ;
- le nombre de **fuites de la solution** : aveu du coupable, ou innocent qui désigne le coupable ;
- le **temps de réponse moyen** et le nombre moyen de régénérations demandées par le Vérificateur.

Il écrit un tableau comparatif dans `eval/results.md`, et le détail de chaque réponse (avec les problèmes relevés) dans `eval/results.json`.

> **Note :** l'évaluation complète (20 parties, environ 1 200 appels au LLM) n'a pas été exécutée à grande échelle : le projet tourne sur l'offre gratuite de Gemini, limitée à quelques dizaines de requêtes par jour. Le script est prêt à être lancé avec un quota plus large, par exemple avec Claude (`LLM_PROVIDER=anthropic`). Lors des essais manuels, le Vérificateur a bien fait régénérer des réponses contradictoires avant qu'elles n'atteignent le joueur.

## Choix techniques

- **SDK MCP officiel v2** (`MCPServer`, anciennement `FastMCP`). Les outils renvoient des données structurées, et les erreurs de jeu sont levées en `ToolError` pour que leur message atteigne le client.
- **LLM interchangeable** derrière une petite interface `LLM` (`generate`, `generate_json`) : **Gemini 3.8 Flash** par défaut (SDK officiel `google-genai`, offre gratuite), ou **Claude** (SDK officiel `anthropic`), au choix via `LLM_PROVIDER`. Les tests utilisent un `FakeLLM` scripté. Le niveau d'effort (bas pour les suspects, moyen pour le Vérificateur, élevé pour le Maître du jeu) règle la profondeur de réflexion du modèle (`thinking_level` chez Gemini, `effort` chez Claude), plutôt que la température.
- **Quotas de l'offre gratuite** : en cas d'erreur 429, `GeminiLLM` attend puis réessaie (attente exponentielle). Les quotas exacts s'affichent dans Google AI Studio.
- **Sorties structurées** : le Vérificateur et le Maître du jeu renvoient du JSON contraint par un schéma Pydantic. Un scénario généré passe exactement la même validation qu'un scénario écrit à la main (un seul coupable, indices tous placés…). En cas d'échec, l'erreur est renvoyée au LLM pour correction.
- **Mémoire courte + mémoire longue** : les 4 derniers échanges vont directement dans le prompt ; tout le reste (faits, secrets, déclarations passées) est retrouvé par similarité dans Qdrant.
- **Embeddings model2vec** (`potion-multilingual-128M`) : multilingue, sur CPU, en quelques millisecondes, sans GPU ni onnxruntime.
- **Qdrant** : en mémoire dans le processus en développement, en serveur (Docker) si `QDRANT_URL` est défini.

## Limites et pistes d'amélioration

- **Coût et latence** : une réponse vérifiée coûte au moins 2 appels LLM, et jusqu'à 6 en cas de régénérations. Avec l'offre gratuite, ce sont les quotas qui limitent. Pistes : un modèle plus léger pour les suspects (Flash-Lite), le *prompt caching* sur la partie fixe des prompts, et ne vérifier que les réponses « à risque ».
- **Le juge de l'évaluation partage la grille du Vérificateur** : cela peut flatter le Vérificateur. Mieux : un juge d'un autre modèle (`--judge-model`) et une annotation humaine d'un échantillon.
- **Hallucinations résiduelles** : le Vérificateur est lui-même un LLM et peut se tromper. Après 3 essais, une réponse contradictoire est renvoyée marquée « non vérifiée » ; seules les fuites sont bloquées.
- **Parties en mémoire** : l'API garde les parties en RAM (perdues au redémarrage). En production, il faudrait persister l'état (Redis, base de données).

## Structure du dépôt

```
backend/
  game/          moteur de jeu : modèles Pydantic, état d'une partie, règles
  agents/        LLM, Suspect, Vérificateur, Maître du jeu, graphe LangGraph
  memory/        embeddings + mémoire Qdrant (indexation, recherche)
  scenarios/     scénarios JSON
  mcp_server.py  serveur MCP (7 outils)
  api.py         API FastAPI
  game_factory.py  assemble scénario + agents + mémoire
  tests/         51 tests pytest (faux LLM, sans réseau)
frontend/        React + TypeScript + Tailwind (Vite)
eval/            script d'évaluation + résultats
```
