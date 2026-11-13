import { useRef, useEffect, useState } from "react";
import { Bot, User } from "lucide-react";
import type { ChatMessage } from "../../types/agent";
import { formatTime } from "../../utils/dateTime";

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
}

export function ChatMessageList({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-ink-subtle">
        <div className="animate-fade-up text-center">
          <span className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-violet-500 text-white shadow-glow">
            <Bot className="h-8 w-8" aria-hidden="true" />
          </span>
          <h3 className="mb-2 font-display text-lg font-semibold text-ink">
            AI HR Intelligence Assistant
          </h3>
          <p className="text-sm">
            Ask me anything about recruitment, candidates, interviews, or analytics.
          </p>
          <p className="mt-2 text-xs text-ink-subtle">
            Powered by multi-LLM routing with automatic fallback
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} />
      ))}
      {isLoading && !messages.some((m) => m.isStreaming) && (
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-violet-500 text-white shadow-soft">
            <Bot className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="rounded-2xl rounded-bl-md border border-slate-200/70 bg-white px-4 py-3 shadow-soft">
            <div className="flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-primary-400" style={{ animationDelay: "0ms" }} />
              <span className="h-2 w-2 animate-bounce rounded-full bg-primary-400" style={{ animationDelay: "150ms" }} />
              <span className="h-2 w-2 animate-bounce rounded-full bg-primary-400" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}

function renderMarkdown(text: string): string {
  let html = text;
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-ink text-slate-100 rounded-lg p-3 text-xs overflow-x-auto my-2"><code>$2</code></pre>');
  html = html.replace(/`([^`]+)`/g, '<code class="bg-surface-muted text-ink rounded px-1 py-0.5 text-xs">$1</code>');
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/\n/g, "<br/>");
  return html;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const agentLabel: Record<string, string> = {
    candidate: "Career Agent",
    recruiter: "Recruiter Agent",
    hr: "HR Agent",
    admin: "Admin Agent",
    resume: "Resume Agent",
    interview: "Interview Agent",
    analytics: "Analytics Agent",
    fairness: "Fairness Agent",
    report: "Report Agent",
    job_matching: "Matching Agent",
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex animate-fade-up items-start gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-violet-500 text-xs font-bold text-white shadow-soft">
          {message.agent_type
            ? (agentLabel[message.agent_type] || "AI").charAt(0)
            : "AI"}
        </div>
      )}
      <div className={`max-w-[75%] ${isUser ? "order-first" : ""}`}>
        {!isUser && message.agent_type && (
          <div className="mb-1 text-xs font-semibold text-primary-600">
            {agentLabel[message.agent_type] || "AI Agent"}
          </div>
        )}
        <div
          className={`px-4 py-2.5 text-sm shadow-xs ${
            isUser
              ? "rounded-2xl rounded-br-md bg-gradient-to-br from-primary-500 to-violet-500 text-white"
              : "rounded-2xl rounded-bl-md border border-slate-200/70 bg-white text-ink"
          } ${message.isStreaming ? "animate-pulse-soft border-l-2 border-l-primary-400" : ""}`}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <div
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
            />
          )}
          {message.isStreaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary-400 align-middle" />
          )}
        </div>
        {!isUser && !message.isStreaming && message.content && (
          <div className="mt-1 flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="text-xs text-ink-subtle transition-colors hover:text-primary-600"
              title="Copy response"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        )}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.citations.map((c, ci) => (
              <div
                key={ci}
                className="rounded-lg border border-sky-100 bg-sky-50/80 px-2.5 py-1.5 text-xs text-sky-700"
              >
                <span className="font-semibold">{c.source_type}:</span> {c.title}
                <span className="ml-1 font-semibold text-sky-500">
                  ({(c.relevance_score * 100).toFixed(0)}% match)
                </span>
              </div>
            ))}
          </div>
        )}
        {message.timestamp && (
          <div className={`mt-1 text-xs text-ink-subtle ${isUser ? "text-right" : ""}`}>
            {formatTime(message.timestamp)}
          </div>
        )}
      </div>
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-muted text-ink-muted shadow-soft">
          <User className="h-4 w-4" aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
