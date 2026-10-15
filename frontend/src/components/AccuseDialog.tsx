import { useState } from "react";
import type { Suspect } from "../types";

interface Props {
  suspects: Suspect[];
  loading: boolean;
  onAccuse: (suspectId: string, reasoning: string) => void;
  onClose: () => void;
}

export function AccuseDialog({ suspects, loading, onAccuse, onClose }: Props) {
  const [suspectId, setSuspectId] = useState(suspects[0].id);
  const [reasoning, setReasoning] = useState("");

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-lg space-y-4 rounded-xl border border-red-900 bg-stone-900 p-6">
        <h2 className="font-serif text-2xl text-red-300">Accuser un suspect</h2>
        <p className="text-sm text-stone-400">Attention : l'accusation est définitive et termine la partie.</p>
        <div className="grid grid-cols-2 gap-2">
          {suspects.map((suspect) => (
            <button
              key={suspect.id}
              onClick={() => setSuspectId(suspect.id)}
              className={`rounded-lg border px-3 py-2 text-left text-sm ${
                suspect.id === suspectId ? "border-red-500 bg-red-950/40" : "border-stone-700"
              }`}
            >
              <span className="block text-stone-100">{suspect.name}</span>
              <span className="text-xs text-stone-500">{suspect.role}</span>
            </button>
          ))}
        </div>
        <textarea
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
          placeholder="Votre raisonnement : mobile, moyen, indices, contradictions…"
          rows={4}
          className="w-full rounded-lg border border-stone-700 bg-stone-950 p-3 text-sm outline-none focus:border-red-500"
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-stone-400 hover:text-stone-200">
            Annuler
          </button>
          <button
            onClick={() => onAccuse(suspectId, reasoning)}
            disabled={loading}
            className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
          >
            {loading ? "…" : "J'accuse !"}
          </button>
        </div>
      </div>
    </div>
  );
}
