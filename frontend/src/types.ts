// Types des réponses de l'API FastAPI (miroir des dictionnaires renvoyés par game/engine.py).

export interface RoomSummary {
  id: string;
  name: string;
  visited: boolean;
}

export interface Suspect {
  id: string;
  name: string;
  role: string;
  description: string;
}

export interface GameStart {
  game_id: string;
  title: string;
  intro: string;
  victim: { name: string; cause_of_death: string; time: string; location: string };
  rooms: RoomSummary[];
  suspects: Suspect[];
}

export interface RoomInspection {
  id: string;
  name: string;
  description: string;
  clues: { id: string; name: string; description: string }[];
  new_clues: string[];
}

export interface Clue {
  id: string;
  name: string;
  description: string;
  analysis: string;
  found_in: string;
}

export interface InterrogationAnswer {
  suspect: string;
  question: string;
  answer: string;
  verified: boolean;
  attempts: number;
}

export interface Verdict {
  correct: boolean;
  accused: string;
  message: string;
  solution: { guilty: string; guilty_name: string; motive: string; method: string };
  clues_found: number;
  clues_total: number;
}

export interface ChatMessage {
  question: string;
  answer?: InterrogationAnswer;
  error?: string;
}
