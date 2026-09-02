import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow, { type ChatMessage } from "./components/ChatWindow";
import ReportPanel from "./components/ReportPanel";
import { listTrips, getTripMessages, type Trip } from "./api";
import { useTripWebSocket } from "./lib/useTripWebSocket";

function newThreadId() {
  return crypto.randomUUID();
}

export default function App() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [threadId, setThreadId] = useState<string>(newThreadId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTripId, setActiveTripId] = useState<string | null>(null);
  const tripLive = useTripWebSocket(activeTripId);

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

  function handleTripStarted(tripId: string) {
    setActiveTripId(tripId);
    listTrips().then(setTrips).catch(() => {});
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
      <div className={`main-split ${activeTripId ? "with-report" : ""}`}>
        <ChatWindow
          threadId={threadId}
          messages={messages}
          onMessagesChange={setMessages}
          onTripStarted={handleTripStarted}
        />
        {activeTripId && (
          <ReportPanel
            surfaceId={activeTripId}
            report={tripLive.report}
            sections={tripLive.sections}
            status={tripLive.status ?? "not_started"}
          />
        )}
      </div>
    </div>
  );
}
