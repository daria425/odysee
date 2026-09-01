import type { Trip } from "../api";

interface SidebarProps {
  trips: Trip[];
  activeTripId: string | null;
  onNewChat: () => void;
  onSelectTrip: (tripId: string) => void;
}

export default function Sidebar({ trips, activeTripId, onNewChat, onSelectTrip }: SidebarProps) {
  return (
    <aside className="sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        New Chat
      </button>
      <div>
        <div className="sidebar-section-label">Trips</div>
        <ul className="trip-list">
          {trips.map((trip) => (
            <li key={trip.trip_id}>
              <button
                className={`trip-item ${trip.trip_id === activeTripId ? "active" : ""}`}
                onClick={() => onSelectTrip(trip.trip_id)}
                aria-current={trip.trip_id === activeTripId ? "true" : undefined}
              >
                {trip.name}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
