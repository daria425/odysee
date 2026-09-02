import { useEffect, useState } from "react";
import { MessageProcessor } from "@a2ui/web_core/v0_9";
import { A2uiSurface, basicCatalog, type ReactComponentImplementation } from "@a2ui/react/v0_9";
import type { SurfaceModel } from "@a2ui/web_core/v0_9";
import { markdownToA2uiMessages } from "../lib/markdownToA2ui";
import type { ReportSection } from "../lib/useTripWebSocket";

interface SectionSurfaceProps {
  messages: unknown[];
}

/** One independent A2UI surface for a single section/card. A fresh MessageProcessor per effect
 * run (rather than a memoized/shared one) means React StrictMode's dev-mode double-invoke creates
 * two independent processor instances instead of calling createSurface twice on the same one,
 * which MessageProcessor rejects. */
function SectionSurface({ messages }: SectionSurfaceProps) {
  const [surface, setSurface] = useState<SurfaceModel<ReactComponentImplementation> | null>(null);

  useEffect(() => {
    setSurface(null);
    const processor = new MessageProcessor([basicCatalog]);
    const createdSub = processor.onSurfaceCreated((s) => setSurface(s));
    processor.processMessages(messages);
    return () => createdSub.unsubscribe();
  }, [messages]);

  if (!surface) return null;
  return <A2uiSurface surface={surface} />;
}

interface ReportPanelProps {
  surfaceId: string;
  report: string | null;
  sections: ReportSection[];
  status: string;
}

export default function ReportPanel({ surfaceId, report, sections, status }: ReportPanelProps) {
  if (sections.length > 0) {
    return (
      <div className="report-panel">
        {status === "running" && (
          <p className="report-panel-note">Researching further sections…</p>
        )}
        {[...sections]
          .sort((a, b) => a.question_id - b.question_id)
          .map((s) => (
            <SectionSurface key={s.surface_id} messages={s.messages} />
          ))}
      </div>
    );
  }

  if (status === "running" || status === "not_started") {
    return (
      <div className="report-panel report-panel-empty">
        <p>Researching this trip — sections will appear here as each one is ready.</p>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="report-panel report-panel-empty">
        <p>Trip research failed. Try starting a new trip.</p>
      </div>
    );
  }

  if (report) {
    return (
      <div className="report-panel">
        <SectionSurface messages={markdownToA2uiMessages(report, surfaceId)} />
      </div>
    );
  }

  return (
    <div className="report-panel report-panel-empty">
      <p>No report available for this trip.</p>
    </div>
  );
}
