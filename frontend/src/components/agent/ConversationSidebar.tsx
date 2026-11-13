import type { Conversation } from "../../types/agent";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function ConversationSidebar({ conversations, activeId, onSelect, onNew }: Props) {
  return (
    <div className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200/70 bg-surface-muted/80 backdrop-blur-sm">
      <div className="border-b border-slate-200/70 p-3">
        <button
          onClick={onNew}
          className="btn-primary btn-md w-full"
        >
          + New Chat
        </button>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <div className="mt-8 text-center text-xs text-ink-subtle">No conversations yet</div>
        ) : (
          conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-all duration-200 ${
                activeId === c.id
                  ? "bg-primary-50/80 text-primary-700 shadow-xs ring-1 ring-inset ring-primary-200/60"
                  : "text-ink-muted hover:bg-white hover:text-ink hover:shadow-xs"
              }`}
            >
              <div className="truncate font-medium">{c.title || "New Conversation"}</div>
              <div className="mt-0.5 text-xs text-ink-subtle">
                {c.agent_type && <span className="capitalize">{c.agent_type} Agent</span>}
                {" \u00b7 "}
                {new Date(c.updated_at).toLocaleDateString()}
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
