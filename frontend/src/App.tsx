import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow, { type ChatMessage } from "./components/ChatWindow";
import ReportPanel from "./components/ReportPanel";
import { listTrips, getTrip, getTripMessages, type Trip } from "./api";

function newThreadId() {
  return crypto.randomUUID();
}

export default function App() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [threadId, setThreadId] = useState<string>(newThreadId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTripId, setActiveTripId] = useState<string | null>(null);
  const [activeTrip, setActiveTrip] = useState<Trip | null>(null);

  useEffect(() => {
    listTrips().then(setTrips).catch(() => setTrips([]));
  }, []);

  function handleNewChat() {
    setThreadId(newThreadId());
    setMessages([]);
    setActiveTripId(null);
    setActiveTrip(null);
  }

  function handleSelectTrip(tripId: string) {
    setThreadId(tripId);
    setMessages([]);
    setActiveTripId(tripId);
    setActiveTrip(null);
    getTripMessages(tripId)
      .then(setMessages)
      .catch(() => setMessages([]));
    getTrip(tripId)
      .then(setActiveTrip)
      .catch(() => setActiveTrip(null));
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
      <div className={`main-split ${activeTrip ? "with-report" : ""}`}>
        <ChatWindow threadId={threadId} messages={messages} onMessagesChange={setMessages} />
        {activeTrip && (
          <ReportPanel
            surfaceId={activeTrip.trip_id}
            report={activeTrip.research_report}
            reportUi={activeTrip.research_report_ui}
            status={activeTrip.research_status}
          />
        )}
      </div>
    </div>
  );
}
