import { useState } from "react";

interface Props {
  onStart: (seed?: number) => void;
  loading: boolean;
  error: string | null;
}

export function StartScreen({ onStart, loading, error }: Props) {
  const [useGenerated, setUseGenerated] = useState(false);
  const [seed, setSeed] = useState("1");

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-8 px-4 py-12">
      <div>
        <p className="text-sm uppercase tracking-[0.3em] text-amber-500">Jeu d'enquête</p>
        <h1 className="mt-2 font-serif text-5xl text-amber-100">Inspecteur IA</h1>
        <p className="mt-4 text-stone-400">
          Un meurtre, quatre suspects. Chacun est un agent IA avec sa personnalité, ses secrets et sa mémoire. Fouillez,
          interrogez, confrontez… puis accusez.
        </p>
      </div>

      <div className="space-y-4 rounded-xl border border-stone-800 bg-stone-900/60 p-5">
        <label className="flex items-center gap-3 text-sm text-stone-300">
          <input type="checkbox" checked={useGenerated} onChange={(e) => setUseGenerated(e.target.checked)} />
          Scénario généré par le Maître du jeu (plus lent)
        </label>
        {useGenerated && (
          <label className="flex items-center gap-3 text-sm text-stone-400">
            Numéro de scénario
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              className="w-24 rounded-md border border-stone-700 bg-stone-950 px-2 py-1 text-stone-100"
            />
          </label>
        )}
        <button
          onClick={() => onStart(useGenerated ? Number(seed) : undefined)}
          disabled={loading}
          className="w-full rounded-lg bg-amber-600 px-4 py-3 font-semibold text-stone-950 hover:bg-amber-500 disabled:opacity-50"
        >
          {loading ? "Préparation de la scène du crime…" : "Commencer l'enquête"}
        </button>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>
    </main>
  );
}
