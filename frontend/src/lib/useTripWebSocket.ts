import { useEffect, useState } from "react";
import type { A2uiMessage } from "@a2ui/web_core/v0_9";

const WS_BASE = "ws://localhost:8000";

export interface ReportSection {
  question_id: number;
  surface_id: string;
  messages: A2uiMessage[];
}

interface StatusMessage {
  type: "status";
  status: string;
  report: string | null;
  report_ui: string | null;
  error: string | null;
}

interface SectionUiMessage {
  type: "section_ui";
  question_id: number;
  surface_id: string;
  messages: A2uiMessage[];
}

export interface TripWebSocketState {
  status: string | null;
  report: string | null;
  sections: ReportSection[];
  error: string | null;
}

function upsertSection(sections: ReportSection[], section: ReportSection): ReportSection[] {
  const others = sections.filter((s) => s.question_id !== section.question_id);
  return [...others, section];
}

/** Opens the trip status websocket and accumulates progressive report sections as they arrive.
 * The server always sends a "status" message on connect (with whatever section_ui entries have
 * already been persisted) and again once research finishes, plus a "section_ui" message per
 * question the moment reflection confirms it — this hook merges all of that into one live view. */
export function useTripWebSocket(tripId: string | null): TripWebSocketState {
  const [state, setState] = useState<TripWebSocketState>({
    status: null,
    report: null,
    sections: [],
    error: null,
  });

  useEffect(() => {
    setState({ status: null, report: null, sections: [], error: null });
    if (!tripId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/trip/${tripId}`);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data) as StatusMessage | SectionUiMessage;
      if (msg.type === "section_ui") {
        setState((prev) => ({
          ...prev,
          sections: upsertSection(prev.sections, {
            question_id: msg.question_id,
            surface_id: msg.surface_id,
            messages: msg.messages,
          }),
        }));
        return;
      }
      setState((prev) => {
        let sections = prev.sections;
        if (msg.report_ui) {
          try {
            const parsed = JSON.parse(msg.report_ui) as ReportSection[];
            sections = parsed.reduce(upsertSection, prev.sections);
          } catch {
            // Leave whatever sections we already have via live section_ui messages.
          }
        }
        return { ...prev, status: msg.status, report: msg.report, error: msg.error, sections };
      });
    };

    return () => ws.close();
  }, [tripId]);

  return state;
}
