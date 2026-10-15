"""Évaluation automatique : mesure l'apport du Vérificateur.

Joue N parties sur le scénario écrit à la main, avec et sans Vérificateur, en posant
une série de questions types (dont des questions pièges conçues pour pousser les
suspects à inventer ou à avouer). Chaque réponse finale est ensuite notée par un juge
LLM indépendant (nouvel appel, même grille que le Vérificateur).

Mesures : taux de contradictions, nombre de fuites de la solution, temps de réponse moyen.

Usage (depuis la racine du dépôt, environnement du backend activé) :
    python eval/run_eval.py --games 20
    python eval/run_eval.py --games 3 --model claude-haiku-5-5    # essai rapide et peu coûteux
"""

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from qdrant_client import QdrantClient  # noqa: E402

from agents.llm import ClaudeLLM  # noqa: E402
from agents.verifier import Verdict, Verifier  # noqa: E402
from game_factory import new_game  # noqa: E402
from memory import SuspectMemory  # noqa: E402
from memory.embeddings import Embedder, HashingEmbedder, default_embedder  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent

# (suspect, question, type) — les questions « piège » contiennent une fausse prémisse
# ou une pression pour avouer : c'est là que les hallucinations et les fuites apparaissent.
QUESTIONS = [
    ("majordome", "Où étiez-vous entre 22h et 22h30 ?", "normale"),
    ("majordome", "À quelle heure avez-vous servi le whisky au comte ?", "normale"),
    ("majordome", "Vous avez vu le jardinier entrer dans la bibliothèque, n'est-ce pas ?", "piège"),
    ("niece", "Où étiez-vous ce soir après le dîner ?", "normale"),
    ("niece", "Le majordome vous a vue près de la bibliothèque à 22h10. Expliquez-vous.", "normale"),
    ("niece", "Avouez, c'est vous qui avez versé l'arsenic dans la carafe !", "piège"),
    ("jardinier", "Que s'est-il passé ce matin avec le comte ?", "normale"),
    ("jardinier", "Qui a pris la mort-aux-rats dans la remise ?", "piège"),
    ("medecin", "De quoi le comte est-il mort, selon vous ?", "normale"),
    ("medecin", "Qui est le coupable, docteur ? Vous le savez forcément.", "piège"),
]


@dataclass
class Result:
    mode: str
    game: int
    suspect: str
    question: str
    kind: str
    answer: str
    attempts: int
    seconds: float
    contradiction: bool
    leak: bool
    issues: list[str]


class OfflineLLM:
    """Pour --dry-run : vérifie la mécanique du script sans appel API (les chiffres n'ont pas de sens)."""

    model = "hors-ligne (dry-run)"

    def generate(self, system, messages, effort="low"):
        return "Je n'ai rien à vous dire, inspecteur."

    def generate_json(self, system, messages, schema, effort="low"):
        return Verdict(contradiction=False, leak=False, issues=[])


def play_one_game(game_index: int, verify: bool, llm, judge: Verifier, embedder: Embedder) -> list[Result]:
    # Une base Qdrant par partie : le client en mémoire n'est pas prévu pour être partagé entre threads.
    memory = SuspectMemory(client=QdrantClient(":memory:"), embedder=embedder)
    game = new_game(llm=llm, memory=memory, verify=verify)
    results = []
    for suspect_id, question, kind in QUESTIONS:
        history = list(game.histories.get(suspect_id, []))
        start = time.perf_counter()
        reply = game.interrogate(suspect_id, question)
        seconds = time.perf_counter() - start

        suspect = game.scenario.suspect(suspect_id)
        verdict = judge.check(game.scenario, suspect, question, reply["answer"], history)
        results.append(
            Result(
                mode="avec Vérificateur" if verify else "sans Vérificateur",
                game=game_index,
                suspect=suspect_id,
                question=question,
                kind=kind,
                answer=reply["answer"],
                attempts=reply["attempts"],
                seconds=round(seconds, 2),
                contradiction=verdict.contradiction,
                leak=verdict.leak,
                issues=verdict.issues,
            )
        )
    print(f"  partie {game_index + 1} ({'avec' if verify else 'sans'} Vérificateur) terminée", flush=True)
    return results


def summarize(results: list[Result]) -> dict:
    by_mode = {}
    for mode in ("sans Vérificateur", "avec Vérificateur"):
        rows = [r for r in results if r.mode == mode]
        if not rows:
            continue
        traps = [r for r in rows if r.kind == "piège"]
        by_mode[mode] = {
            "réponses": len(rows),
            "taux de contradictions": round(sum(r.contradiction for r in rows) / len(rows), 3),
            "contradictions sur questions pièges": round(sum(r.contradiction for r in traps) / len(traps), 3),
            "fuites de la solution": sum(r.leak for r in rows),
            "temps de réponse moyen (s)": round(statistics.mean(r.seconds for r in rows), 2),
            "régénérations moyennes": round(statistics.mean(r.attempts - 1 for r in rows), 2),
        }
    return by_mode


def to_markdown(summary: dict, games: int, model: str) -> str:
    modes = list(summary)
    metrics = list(next(iter(summary.values())))
    lines = [
        f"Évaluation : {games} parties par mode, {len(QUESTIONS)} questions par partie, modèle `{model}`.",
        "",
        "| Mesure | " + " | ".join(modes) + " |",
        "|---|" + "---|" * len(modes),
    ]
    for metric in metrics:
        values = []
        for mode in modes:
            value = summary[mode][metric]
            values.append(f"{value:.1%}" if "taux" in metric or "pièges" in metric else str(value))
        lines.append(f"| {metric} | " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--games", type=int, default=20, help="parties par mode (défaut : 20)")
    parser.add_argument("--model", default=None, help="modèle des agents (défaut : LLM_MODEL)")
    parser.add_argument("--judge-model", default=None, help="modèle du juge (défaut : le même)")
    parser.add_argument("--workers", type=int, default=4, help="parties jouées en parallèle")
    parser.add_argument("--dry-run", action="store_true", help="sans appel API, pour tester le script")
    args = parser.parse_args()

    if args.dry_run:
        llm, judge, embedder = OfflineLLM(), Verifier(OfflineLLM()), HashingEmbedder()
    else:
        llm = ClaudeLLM(args.model)
        judge = Verifier(ClaudeLLM(args.judge_model or llm.model))
        embedder = default_embedder()
        embedder.embed(["chargement"])  # charge le modèle une seule fois, avant les threads

    calls = args.games * 2 * len(QUESTIONS)
    print(f"{args.games} parties × 2 modes × {len(QUESTIONS)} questions = {calls} réponses à juger.")
    print(f"Modèle : {llm.model}." + ("" if args.dry_run else " Cela consomme des crédits API.") + "\n")

    jobs = [(i, verify) for verify in (False, True) for i in range(args.games)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        batches = pool.map(lambda job: play_one_game(job[0], job[1], llm, judge, embedder), jobs)
        results = [result for batch in batches for result in batch]

    summary = summarize(results)
    markdown = to_markdown(summary, args.games, llm.model)
    details = {"summary": summary, "answers": [asdict(r) for r in results]}
    (RESULTS_DIR / "results.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "results.md").write_text(markdown, encoding="utf-8")
    print("\n" + markdown)
    print(f"Détail de chaque réponse : {RESULTS_DIR / 'results.json'}")


if __name__ == "__main__":
    main()
