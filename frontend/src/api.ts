const API_BASE = "http://localhost:8000";

export interface Trip {
  trip_id: string;
  name: string;
  destinations: string[];
  start_date: string | null;
  end_date: string | null;
  notes: string | null;
  created_at: string | null;
  research_status: string;
  research_report: string | null;
  research_error: string | null;
  research_updated_at: string | null;
  research_started_at: string | null;
}

export interface ChatResponse {
  thread_id: string;
  langfuse_session_id: string;
  chat_response: string;
  recommendations: string[];
  warnings: string[];
  follow_up: string[];
}

export async function listTrips(): Promise<Trip[]> {
  const res = await fetch(`${API_BASE}/trips`);
  if (!res.ok) throw new Error("failed to load trips");
  return res.json();
}

export async function getTrip(tripId: string): Promise<Trip> {
  const res = await fetch(`${API_BASE}/trip/${tripId}`);
  if (!res.ok) throw new Error("failed to load trip");
  return res.json();
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
}

export async function getTripMessages(tripId: string): Promise<StoredMessage[]> {
  const res = await fetch(`${API_BASE}/trip/${tripId}/messages`);
  if (!res.ok) throw new Error("failed to load trip messages");
  return res.json();
}

export async function sendChatMessage(
  userMessage: string,
  threadId: string,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_message: userMessage,
      thread_id: threadId,
      langfuse_session_id: threadId,
    }),
  });
  if (!res.ok) throw new Error("chat request failed");
  return res.json();
}
