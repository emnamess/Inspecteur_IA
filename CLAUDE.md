# Inspecteur IA — Brief du projet

> À placer à la racine du dépôt (ou à copier dans `CLAUDE.md`) pour que Claude Code ait tout le contexte.

## 1. Le concept

Un jeu d'enquête policière dans lequel **chaque suspect est un agent IA**.

Un meurtre a eu lieu dans un manoir. Le joueur incarne l'inspecteur : il fouille les pièces, interroge les suspects en langage naturel, confronte leurs versions, puis accuse un coupable.

* Un **agent Maître du jeu** crée le scénario : la victime, 4 suspects, le coupable, les indices et les alibis.
* Chaque **agent Suspect** a sa personnalité, ses secrets et sa propre mémoire. Le coupable ment, et les innocents peuvent cacher d'autres secrets.
* Un **agent Vérificateur** contrôle chaque réponse d'un suspect pour s'assurer qu'elle ne contredit pas les faits du scénario. C'est lui qui empêche le LLM d'inventer n'importe quoi.
* Tout le jeu est exposé par un **serveur MCP**. On peut donc y jouer depuis l'interface web du projet, mais aussi depuis n'importe quel client MCP (Claude Desktop, VS Code / Copilot).

**Objectif du projet :** montrer en une démo de 30 secondes que je sais construire un serveur MCP, orchestrer plusieurs agents, faire du RAG, fiabiliser les sorties d'un LLM et livrer une application full-stack propre.

## 2. Ce que le projet doit démontrer (pour les recruteurs)


| Compétence                 | Où elle apparaît dans le projet                                  |
| --------------------------- | ------------------------------------------------------------------ |
| Serveur MCP                 | Outils`inspect_room`,`interrogate`,`get_clues`,`accuse`…          |
| IA agentique / multi-agents | Maître du jeu, Suspects, Vérificateur orchestrés avec LangGraph |
| RAG / base vectorielle      | Mémoire de chaque suspect + faits du scénario dans Qdrant        |
| Fiabilité des LLM          | Vérificateur + évaluation automatique (taux de contradictions)   |
| Full-stack                  | Back FastAPI + front React/TypeScript (Tailwind)                   |
| Industrialisation           | Docker, docker-compose, tests (pytest), CI GitHub Actions          |

## 3. Architecture

```
┌──────────────────┐     ┌──────────────────┐
│ Front React/TS   │     │ Client MCP        │
│ (plan, carnet,   │     │ (Claude Desktop,  │
│  chat)           │     │  VS Code…)        │
└────────┬─────────┘     └────────┬─────────┘
         │ REST                    │ MCP
         ▼                         ▼
┌─────────────────────────────────────────────┐
│ Back-end Python                              │
│  - API FastAPI (pour le front)               │
│  - Serveur MCP (mêmes fonctions du jeu)      │
│  - Moteur de jeu (état de la partie)         │
│  - Agents LangGraph :                        │
│      Maître du jeu → Suspects → Vérificateur │
└───────┬─────────────────────────┬───────────┘
        ▼                         ▼
   ┌─────────┐              ┌──────────┐
   │ Qdrant  │              │ API LLM  │
   │ mémoire │              │          │
   └─────────┘              └──────────┘
```

**Principe clé :** la logique du jeu est écrite **une seule fois** (dans `game/`). L'API FastAPI et le serveur MCP sont deux « portes d'entrée » qui appellent les mêmes fonctions.

## 4. Les outils MCP


| Outil           | Paramètres           | Rôle                                                                            |
| --------------- | --------------------- | -------------------------------------------------------------------------------- |
| `start_game`    | `seed?`               | Lance une partie (scénario fixe ou généré) et renvoie le contexte de départ |
| `list_rooms`    | —                    | Liste les pièces du manoir                                                      |
| `inspect_room`  | `room`                | Décrit la pièce et révèle les indices qui s'y trouvent                       |
| `list_suspects` | —                    | Nom, rôle et courte description de chaque suspect                               |
| `interrogate`   | `suspect`,`question`  | Le suspect répond (via son agent), puis le Vérificateur contrôle la réponse  |
| `get_clues`     | —                    | Carnet de l'inspecteur : indices découverts jusqu'ici                           |
| `accuse`        | `suspect`,`reasoning` | Fin de partie : victoire ou échec, avec la solution                             |

Chaque outil a une **docstring claire**, parce que c'est elle que le LLM lit pour décider quand l'utiliser.

## 5. Le scénario (modèle de données)

Le scénario est un fichier JSON. Il est d'abord écrit à la main, puis généré par le Maître du jeu.

```json
{
  "victim": { "name": "...", "cause_of_death": "...", "time": "22:30" },
  "rooms": [
    { "id": "bibliotheque", "description": "...", "clues": ["verre_brise"] }
  ],
  "suspects": [
    {
      "id": "majordome",
      "name": "...",
      "personality": "nerveux, très poli",
      "alibi": "...",
      "secrets": ["..."],
      "is_guilty": false,
      "knows": ["faits que ce suspect connaît"]
    }
  ],
  "clues": [
    { "id": "verre_brise", "description": "...", "points_to": "..." }
  ],
  "solution": { "guilty": "...", "motive": "...", "method": "..." }
}
```

**Règle importante :** un suspect ne doit jamais révéler la `solution`, et ne peut parler que de ce qui figure dans `knows`. Le coupable peut mentir, mais seulement sur les points prévus.

## 6. Les agents

1. **Maître du jeu.** Génère un scénario cohérent au format JSON ci-dessus, validé avec Pydantic.
2. **Suspect** (une instance par suspect). Son prompt contient la personnalité, l'alibi, les secrets et ce qu'il sait. Il récupère dans Qdrant les éléments de sa mémoire qui sont pertinents pour la question posée (RAG), puis répond.
3. **Vérificateur.** Reçoit la réponse du suspect et les faits du scénario. Il détecte toute contradiction non prévue ou toute fuite de la solution. Si la réponse pose problème, il la fait régénérer.

Orchestration avec **LangGraph** : `question → Suspect → Vérificateur → (OK : renvoyer | KO : régénérer)`.

## 7. Évaluation

Un script `eval/run_eval.py` joue automatiquement environ 20 parties avec des questions types, puis mesure :

* le **taux de contradictions** avec et sans Vérificateur ;
* le nombre de **fuites de la solution** ;
* le temps de réponse moyen.

Les résultats vont dans le README. C'est la partie la plus convaincante pour les postes IA, notamment au CEA.

## 8. Stack technique

* **Back :** Python 3.11+, SDK MCP officiel v2 (`mcp`, classe `MCPServer`, ex-FastMCP), FastAPI, LangGraph, Pydantic, pytest
* **IA :** Claude (SDK officiel `anthropic`), Qdrant pour la mémoire vectorielle, embeddings `model2vec`
* **Front :** React + TypeScript + Vite + Tailwind CSS
* **Infra :** Docker, docker-compose (back + front + Qdrant), GitHub Actions (lint + tests)

## 9. Structure du dépôt

```
inspecteur-ia/
├── backend/
│   ├── game/          # moteur de jeu : état, règles, chargement du scénario
│   ├── agents/        # maître du jeu, suspect, vérificateur, graphe LangGraph
│   ├── memory/        # accès Qdrant (indexation + recherche)
│   ├── mcp_server.py  # serveur MCP (expose les outils)
│   ├── api.py         # API FastAPI (pour le front)
│   ├── scenarios/     # scénarios JSON
│   └── tests/
├── frontend/          # React + TS + Tailwind
├── eval/              # script d'évaluation + résultats
├── docker-compose.yml
├── .github/workflows/ci.yml
└── README.md          # schéma, démo GIF, installation, résultats d'éval
```

## 10. Plan par étapes (1 semaine)


| Étape | Livrable                                                                    | Ce que je dois comprendre                       |
| ------ | --------------------------------------------------------------------------- | ----------------------------------------------- |
| 1      | Serveur MCP minimal +`list_rooms`/`inspect_room`, testé avec MCP Inspector | Client / serveur / outil, rôle de la docstring |
| 2      | Scénario JSON écrit à la main + moteur de jeu + les 7 outils             | État d'une partie, validation Pydantic         |
| 3      | Un suspect qui répond via le LLM                                           | Prompt système, contexte, température         |
| 4      | Mémoire des suspects dans Qdrant (RAG)                                     | Embeddings, recherche par similarité           |
| 5      | Vérificateur + 4 suspects orchestrés avec LangGraph                       | Graphe d'agents, boucle de correction           |
| 6      | API FastAPI + front React simple                                            | Séparer la logique du jeu des interfaces       |
| 7      | Évaluation, Docker, CI, README + GIF, mise en ligne GitHub                 | Mesurer la fiabilité d'un LLM                  |

**Version minimum présentable :** étapes 1 à 5 + README. Le front soigné et l'évaluation complète peuvent suivre.

## 11. Règles de travail pour Claude Code (mode apprentissage)

Je veux **comprendre** chaque partie du projet, pas seulement l'obtenir.

1. Avance **une étape à la fois**, selon le plan de la section 10. Ne code pas plusieurs étapes d'un coup.
2. Avant chaque étape, explique en quelques lignes **le concept** et **ce que tu vas faire**.
3. Après chaque étape, explique **les choix importants** (pourquoi cette structure, cette librairie, ce prompt), ainsi que **comment tester** moi-même.
4. Garde un code **simple et lisible**, avec des noms clairs et des commentaires seulement là où c'est utile.
5. Fais un **commit Git par étape**, avec un message clair.
6. À la fin de chaque étape, pose-moi **1 ou 2 questions de compréhension** comme on pourrait me les poser en entretien.

## 12. Pour l'entretien : ce que je dois savoir expliquer

* Qu'est-ce que MCP, et quelle est la différence avec une simple API REST ?
* Pourquoi la logique du jeu est séparée du serveur MCP et de l'API.
* Comment fonctionne le RAG dans le projet (embeddings, recherche, injection dans le prompt).
* Pourquoi un Vérificateur, et ce que montrent les résultats de l'évaluation.
* Les limites du projet et ce que j'améliorerais (coût, latence, hallucinations restantes).
