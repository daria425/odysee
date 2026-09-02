import { useEffect, useMemo, useState } from "react";
import { MessageProcessor } from "@a2ui/web_core/v0_9";
import { A2uiSurface, basicCatalog, type ReactComponentImplementation } from "@a2ui/react/v0_9";
import type { SurfaceModel } from "@a2ui/web_core/v0_9";
import { markdownToA2uiMessages } from "../lib/markdownToA2ui";

interface ReportPanelProps {
  surfaceId: string;
  report: string | null;
  reportUi: string | null;
  status: string;
}

export default function ReportPanel({ surfaceId, report, reportUi, status }: ReportPanelProps) {
  const messages = useMemo(() => {
    if (reportUi) {
      try {
        return JSON.parse(reportUi);
      } catch {
        // Falls through to the markdown-derived rendering below.
      }
    }
    if (report) return markdownToA2uiMessages(report, surfaceId);
    return null;
  }, [surfaceId, report, reportUi]);

  const [surface, setSurface] = useState<SurfaceModel<ReactComponentImplementation> | null>(null);

  useEffect(() => {
    setSurface(null);
    if (!messages) return;
    // A fresh processor per effect run (rather than a memoized/shared one) means React
    // StrictMode's dev-mode double-invoke creates two independent processor instances
    // instead of calling createSurface twice on the same one, which MessageProcessor rejects.
    const processor = new MessageProcessor([basicCatalog]);
    const createdSub = processor.onSurfaceCreated((s) => setSurface(s));
    processor.processMessages(messages);
    return () => createdSub.unsubscribe();
  }, [messages]);

  if (status === "running" || status === "not_started") {
    return (
      <div className="report-panel report-panel-empty">
        <p>Researching this trip — the report will appear here once it's ready.</p>
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

  if (!surface) {
    return (
      <div className="report-panel report-panel-empty">
        <p>No report available for this trip.</p>
      </div>
    );
  }

  return (
    <div className="report-panel">
      <A2uiSurface surface={surface} />
    </div>
  );
}
