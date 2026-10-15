import type { Verdict } from "../types";

export function VerdictScreen({ verdict, onRestart }: { verdict: Verdict; onRestart: () => void }) {
  const { solution } = verdict;
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 px-4 py-12">
      <p className={`text-sm uppercase tracking-[0.3em] ${verdict.correct ? "text-emerald-400" : "text-red-400"}`}>
        {verdict.correct ? "Affaire résolue" : "Affaire classée… à tort"}
      </p>
      <h1 className="font-serif text-4xl text-amber-100">{verdict.message}</h1>

      <div className="space-y-4 rounded-xl border border-stone-800 bg-stone-900/60 p-5 text-stone-300">
        <p>
          <span className="font-medium text-amber-200">Coupable : </span>
          {solution.guilty_name}
        </p>
        <p>
          <span className="font-medium text-amber-200">Mobile : </span>
          {solution.motive}
        </p>
        <p>
          <span className="font-medium text-amber-200">Méthode : </span>
          {solution.method}
        </p>
        <p className="text-sm text-stone-500">
          Indices découverts : {verdict.clues_found} / {verdict.clues_total}
        </p>
      </div>

      <button
        onClick={onRestart}
        className="self-start rounded-lg bg-amber-600 px-5 py-3 font-semibold text-stone-950 hover:bg-amber-500"
      >
        Nouvelle enquête
      </button>
    </main>
  );
}
