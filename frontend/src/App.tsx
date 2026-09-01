import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow, { type ChatMessage } from "./components/ChatWindow";
import { listTrips, getTripMessages, type Trip } from "./api";

function newThreadId() {
  return crypto.randomUUID();
}

export default function App() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [threadId, setThreadId] = useState<string>(newThreadId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTripId, setActiveTripId] = useState<string | null>(null);

  useEffect(() => {
    listTrips().then(setTrips).catch(() => setTrips([]));
  }, []);

  function handleNewChat() {
    setThreadId(newThreadId());
    setMessages([]);
    setActiveTripId(null);
  }

  function handleSelectTrip(tripId: string) {
    setThreadId(tripId);
    setMessages([]);
    setActiveTripId(tripId);
    getTripMessages(tripId)
      .then(setMessages)
      .catch(() => setMessages([]));
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-logo-mark" aria-hidden="true" />
        <h1>Odysee</h1>
      </header>
      <Sidebar
        trips={trips}
        activeTripId={activeTripId}
        onNewChat={handleNewChat}
        onSelectTrip={handleSelectTrip}
      />
      <ChatWindow threadId={threadId} messages={messages} onMessagesChange={setMessages} />
    </div>
  );
}
