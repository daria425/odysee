import { useState } from "react";
import { sendChatMessage } from "../api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatWindowProps {
  threadId: string;
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  onTripStarted?: (tripId: string) => void;
}

export default function ChatWindow({ threadId, messages, onMessagesChange, onTripStarted }: ChatWindowProps) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    const isStart = text.startsWith("/start");
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: text }];
    onMessagesChange(nextMessages);
    setInput("");
    setSending(true);
    // For /start, the trip_id the server creates is exactly this threadId — no need to wait for
    // the response to know it, so open the report panel (and its websocket) immediately, giving
    // the "watch it build" experience rather than a dead panel until the reply comes back.
    if (isStart) onTripStarted?.(threadId);
    try {
      const response = await sendChatMessage(text, threadId);
      onMessagesChange([...nextMessages, { role: "assistant", content: response.chat_response }]);
      if (isStart) onTripStarted?.(threadId);
    } catch {
      onMessagesChange([
        ...nextMessages,
        { role: "assistant", content: "Something went wrong reaching the server." },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSend();
  }

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.length === 0 && !sending && (
          <div className="chat-empty-state">
            <h2>Where are we headed?</h2>
            <p>Ask about a destination, or start a new trip with /start &lt;name&gt; | &lt;destinations&gt; | &lt;date&gt;</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            {m.content}
          </div>
        ))}
        {sending && (
          <div className="typing-indicator" aria-label="Assistant is typing" role="status">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>
      <div className="chat-input-row">
        <label htmlFor="chat-input" className="sr-only">
          Message
        </label>
        <input
          id="chat-input"
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your trip, or /start <name> | <destinations> | <date>"
          disabled={sending}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={sending}
          aria-label="Send message"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M22 2 11 13" />
            <path d="M22 2 15 22l-4-9-9-4 20-7Z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
