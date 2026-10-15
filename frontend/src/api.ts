import type { Clue, GameStart, InterrogationAnswer, RoomInspection, Verdict } from "./types";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail ?? `Erreur ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  startGame: (seed?: number) => request<GameStart>("/games", { seed: seed ?? null }),
  inspectRoom: (gameId: string, roomId: string) =>
    request<RoomInspection>(`/games/${gameId}/rooms/${roomId}/inspect`, {}),
  interrogate: (gameId: string, suspect: string, question: string) =>
    request<InterrogationAnswer>(`/games/${gameId}/interrogate`, { suspect, question }),
  getClues: (gameId: string) => request<Clue[]>(`/games/${gameId}/clues`),
  accuse: (gameId: string, suspect: string, reasoning: string) =>
    request<Verdict>(`/games/${gameId}/accuse`, { suspect, reasoning }),
};
