import type { Clue, RoomSummary } from "../types";
import { Panel } from "./Panel";

export function Notebook({ clues, rooms }: { clues: Clue[]; rooms: RoomSummary[] }) {
  const roomName = (id: string) => rooms.find((room) => room.id === id)?.name ?? id;

  return (
    <Panel title={`Carnet de l'inspecteur (${clues.length})`}>
      {clues.length === 0 ? (
        <p className="text-sm italic text-stone-500">Aucun indice pour l'instant. Fouillez les pièces.</p>
      ) : (
        <ul className="space-y-3 overflow-y-auto">
          {clues.map((clue) => (
            <li key={clue.id} className="border-l-2 border-amber-600 pl-3 text-sm">
              <p className="font-medium text-amber-200">{clue.name}</p>
              <p className="text-xs text-stone-500">{roomName(clue.found_in)}</p>
              <p className="mt-1 text-stone-300">{clue.description}</p>
              <p className="mt-1 italic text-stone-400">→ {clue.analysis}</p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
