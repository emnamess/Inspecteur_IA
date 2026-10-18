import { useEffect, useRef, useState } from "react";
import type { ChatMessage, Suspect } from "../types";
import { Panel } from "./Panel";

interface Props {
  suspects: Suspect[];
  activeId: string;
  conversation: ChatMessage[];
  waiting: boolean;
  onSelect: (suspectId: string) => void;
  onAsk: (question: string) => void;
}

function initials(name: string) {
  return name
    .split(" ")
    .filter((part) => part[0] === part[0].toUpperCase())
    .slice(-2)
    .map((part) => part[0])
    .join("");
}

function VerificationBadge({ verified, attempts }: { verified: boolean; attempts: number }) {
  // Montre le travail du Vérificateur : réponse validée, et nombre de régénérations éventuelles.
  if (!verified) return <span className="text-xs text-stone-500">non vérifiée</span>;
  return (
    <span className="text-xs text-emerald-500" title="Contrôlée par l'agent Vérificateur">
      ✓ vérifiée{attempts > 1 ? ` (régénérée ${attempts - 1}×)` : ""}
    </span>
  );
}

export function Interrogation({ suspects, activeId, conversation, waiting, onSelect, onAsk }: Props) {
  const [question, setQuestion] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const active = suspects.find((s) => s.id === activeId)!;

  // Accolades obligatoires : un effet ne doit rien renvoyer (scrollIntoView renvoie une Promise
  // dans les navigateurs récents, que React prendrait pour une fonction de nettoyage).
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.length, waiting]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || waiting) return;
    onAsk(question.trim());
    setQuestion("");
  }

  return (
    <Panel title="Interrogatoire" className="min-h-[32rem]">
      <div className="flex gap-2 overflow-x-auto pb-3">
        {suspects.map((suspect) => (
          <button
            key={suspect.id}
            onClick={() => onSelect(suspect.id)}
            className={`flex shrink-0 items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-sm ${
              suspect.id === activeId ? "border-amber-500 bg-amber-950/40" : "border-stone-700 hover:border-stone-500"
            }`}
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-stone-700 text-xs font-bold">
              {initials(suspect.name)}
            </span>
            {suspect.name}
          </button>
        ))}
      </div>

      <p className="mb-3 text-sm text-stone-400">
        <span className="font-medium text-stone-200">{active.role}.</span> {active.description}
      </p>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto rounded-lg bg-stone-950/60 p-3">
        {conversation.length === 0 && (
          <p className="text-sm italic text-stone-500">Posez votre première question à {active.name}.</p>
        )}
        {conversation.map((message, index) => (
          <div key={index} className="space-y-2">
            <p className="ml-auto max-w-[85%] rounded-lg bg-stone-800 px-3 py-2 text-sm">{message.question}</p>
            {message.answer && (
              <div className="max-w-[85%] rounded-lg border border-stone-700 px-3 py-2 text-sm">
                <p className="font-serif text-stone-100">{message.answer.answer}</p>
                <VerificationBadge verified={message.answer.verified} attempts={message.answer.attempts} />
              </div>
            )}
            {message.error && <p className="text-sm text-red-400">{message.error}</p>}
          </div>
        ))}
        {waiting && <p className="text-sm italic text-stone-500">{active.name} réfléchit…</p>}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`Votre question à ${active.name}…`}
          maxLength={500}
          className="flex-1 rounded-lg border border-stone-700 bg-stone-950 px-3 py-2 text-sm outline-none focus:border-amber-500"
        />
        <button
          type="submit"
          disabled={waiting || !question.trim()}
          className="rounded-lg bg-amber-600 px-4 text-sm font-semibold text-stone-950 hover:bg-amber-500 disabled:opacity-50"
        >
          Demander
        </button>
      </form>
    </Panel>
  );
}
