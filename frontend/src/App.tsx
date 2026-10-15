import { useState } from "react";
import { api } from "./api";
import { AccuseDialog } from "./components/AccuseDialog";
import { Interrogation } from "./components/Interrogation";
import { ManorMap } from "./components/ManorMap";
import { Notebook } from "./components/Notebook";
import { StartScreen } from "./components/StartScreen";
import { VerdictScreen } from "./components/VerdictScreen";
import type { ChatMessage, Clue, GameStart, RoomInspection, RoomSummary, Verdict } from "./types";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [game, setGame] = useState<GameStart | null>(null);
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [inspection, setInspection] = useState<RoomInspection | null>(null);
  const [clues, setClues] = useState<Clue[]>([]);
  const [activeSuspect, setActiveSuspect] = useState("");
  const [conversations, setConversations] = useState<Record<string, ChatMessage[]>>({});
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [showAccuse, setShowAccuse] = useState(false);
  const [loading, setLoading] = useState<string | null>(null); // action en cours : "start", "room:<id>"...
  const [error, setError] = useState<string | null>(null);

  async function startGame(seed?: number) {
    setLoading("start");
    setError(null);
    try {
      const started = await api.startGame(seed);
      setGame(started);
      setRooms(started.rooms);
      setActiveSuspect(started.suspects[0].id);
      setInspection(null);
      setClues([]);
      setConversations({});
      setVerdict(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(null);
    }
  }

  async function inspectRoom(roomId: string) {
    if (!game) return;
    setLoading(`room:${roomId}`);
    setError(null);
    try {
      const result = await api.inspectRoom(game.game_id, roomId);
      setInspection(result);
      setRooms((current) => current.map((room) => (room.id === roomId ? { ...room, visited: true } : room)));
      if (result.new_clues.length > 0) setClues(await api.getClues(game.game_id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(null);
    }
  }

  async function ask(question: string) {
    if (!game) return;
    const suspectId = activeSuspect;
    const update = (change: (messages: ChatMessage[]) => ChatMessage[]) =>
      setConversations((current) => ({ ...current, [suspectId]: change(current[suspectId] ?? []) }));

    update((messages) => [...messages, { question }]);
    setLoading(`ask:${suspectId}`);
    try {
      const answer = await api.interrogate(game.game_id, suspectId, question);
      update((messages) => messages.map((m, i) => (i === messages.length - 1 ? { ...m, answer } : m)));
    } catch (e) {
      update((messages) => messages.map((m, i) => (i === messages.length - 1 ? { ...m, error: errorMessage(e) } : m)));
    } finally {
      setLoading(null);
    }
  }

  async function accuse(suspectId: string, reasoning: string) {
    if (!game) return;
    setLoading("accuse");
    try {
      setVerdict(await api.accuse(game.game_id, suspectId, reasoning));
      setShowAccuse(false);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(null);
    }
  }

  function restart() {
    setGame(null);
    setVerdict(null);
  }

  if (verdict) return <VerdictScreen verdict={verdict} onRestart={restart} />;
  if (!game) return <StartScreen onStart={startGame} loading={loading === "start"} error={error} />;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl text-amber-100">{game.title}</h1>
          <p className="mt-1 max-w-3xl text-sm text-stone-400">{game.intro}</p>
          <p className="mt-2 text-sm text-stone-300">
            Victime : <span className="text-amber-200">{game.victim.name}</span> · {game.victim.cause_of_death} · vers{" "}
            {game.victim.time}
          </p>
        </div>
        <button
          onClick={() => setShowAccuse(true)}
          className="rounded-lg border border-red-800 px-4 py-2 text-sm font-semibold text-red-300 hover:bg-red-950"
        >
          Accuser un suspect
        </button>
      </header>

      {error && <p className="mb-4 rounded-lg bg-red-950/60 px-4 py-2 text-sm text-red-300">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.6fr_1fr]">
        <ManorMap
          rooms={rooms}
          inspection={inspection}
          crimeScene={game.victim.location}
          loadingRoom={loading?.startsWith("room:") ? loading.slice(5) : null}
          onInspect={inspectRoom}
        />
        <Interrogation
          suspects={game.suspects}
          activeId={activeSuspect}
          conversation={conversations[activeSuspect] ?? []}
          waiting={loading === `ask:${activeSuspect}`}
          onSelect={setActiveSuspect}
          onAsk={ask}
        />
        <Notebook clues={clues} rooms={rooms} />
      </div>

      {showAccuse && (
        <AccuseDialog
          suspects={game.suspects}
          loading={loading === "accuse"}
          onAccuse={accuse}
          onClose={() => setShowAccuse(false)}
        />
      )}
    </div>
  );
}
