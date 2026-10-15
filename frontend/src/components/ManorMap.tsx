import type { RoomInspection, RoomSummary } from "../types";
import { Panel } from "./Panel";

interface Props {
  rooms: RoomSummary[];
  inspection: RoomInspection | null;
  crimeScene: string;
  loadingRoom: string | null;
  onInspect: (roomId: string) => void;
}

export function ManorMap({ rooms, inspection, crimeScene, loadingRoom, onInspect }: Props) {
  return (
    <Panel title="Plan du manoir">
      <div className="grid grid-cols-2 gap-2">
        {rooms.map((room) => {
          const selected = inspection?.id === room.id;
          return (
            <button
              key={room.id}
              onClick={() => onInspect(room.id)}
              disabled={loadingRoom !== null}
              className={`rounded-lg border px-3 py-3 text-left text-sm transition ${
                selected ? "border-amber-500 bg-amber-950/40" : "border-stone-700 hover:border-stone-500"
              }`}
            >
              <span className="block font-medium text-stone-100">{room.name}</span>
              <span className="text-xs text-stone-500">
                {loadingRoom === room.id
                  ? "Fouille en cours…"
                  : room.id === crimeScene
                    ? "Scène du crime"
                    : room.visited
                      ? "Fouillée"
                      : "Non fouillée"}
              </span>
            </button>
          );
        })}
      </div>

      {inspection && (
        <div className="mt-4 space-y-3 overflow-y-auto">
          <p className="text-sm leading-relaxed text-stone-300">{inspection.description}</p>
          {inspection.clues.length === 0 ? (
            <p className="text-sm italic text-stone-500">Rien de suspect ici.</p>
          ) : (
            <ul className="space-y-2">
              {inspection.clues.map((clue) => (
                <li key={clue.id} className="rounded-md bg-stone-950/60 p-2 text-sm">
                  <span className="font-medium text-amber-200">🔍 {clue.name}</span>
                  {inspection.new_clues.includes(clue.id) && (
                    <span className="ml-2 rounded bg-amber-600 px-1.5 text-xs text-stone-950">nouveau</span>
                  )}
                  <p className="text-stone-400">{clue.description}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  );
}
