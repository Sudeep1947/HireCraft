import { useEffect, useCallback } from "react";
import { Eraser, Download, RotateCcw } from "lucide-react";
import { useAgent } from "../../hooks/useAgent";
import { ChatMessageList } from "../../components/agent/ChatMessageList";
import { ChatInput } from "../../components/agent/ChatInput";
import { SuggestedPrompts } from "../../components/agent/SuggestedPrompts";
import { ToolExecutionPanel } from "../../components/agent/ToolExecutionPanel";
import { ConversationSidebar } from "../../components/agent/ConversationSidebar";
import { AgentInfoPanel } from "../../components/agent/AgentInfoPanel";
import { useAuth } from "../../hooks/useAuth";

export function AIChat() {
  const { user } = useAuth();
  const roles = user?.roles || ["candidate"];
  const {
    messages,
    conversations,
    agents,
    providers,
    activeConversationId,
    isLoading,
    toolExecutions,
    agentUsed,
    processingTimeMs,
    providerUsed,
    sendMessage,
    loadConversations,
    loadConversation,
    loadAgents,
    loadProviders,
    startNewConversation,
    clearChat,
    suggestedPrompts,
    retryLastMessage,
  } = useAgent(roles);

  useEffect(() => {
    loadConversations();
    loadAgents();
    loadProviders();
  }, [loadConversations, loadAgents, loadProviders]);

  const handleSend = useCallback(
    (message: string) => {
      sendMessage(message);
      setTimeout(() => loadConversations(), 500);
    },
    [sendMessage, loadConversations],
  );

  const handleExport = useCallback(() => {
    const text = messages
      .map((m) => {
        const role = m.role === "user" ? "You" : "AI";
        return `[${role}]: ${m.content}`;
      })
      .join("\n\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-export-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [messages]);

  return (
    <div className="flex h-[calc(100vh-4rem)] animate-fade-in overflow-hidden rounded-2xl border border-gray-200/80 bg-white/70 backdrop-blur-xl shadow-card">
      <ConversationSidebar
        conversations={conversations}
        activeId={activeConversationId}
        onSelect={loadConversation}
        onNew={startNewConversation}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-gray-200/80 bg-white/80 px-5 py-3 backdrop-blur-sm">
          <div className="min-w-0">
            <h1 className="truncate font-display text-lg font-semibold tracking-tight text-gray-900">
              AI HR Intelligence Assistant
            </h1>
            <p className="text-xs text-gray-500">
              Ask questions about recruitment, candidates, analytics, and more
              {providerUsed && (
                <span className="ml-2 font-medium text-primary-600">via {providerUsed}</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {agentUsed && (
              <span className="badge-primary mr-1 hidden sm:inline-flex">
                {agentUsed.replace("_", " ")} Agent
              </span>
            )}
            <button
              onClick={retryLastMessage}
              disabled={isLoading || messages.length === 0}
              className="btn-ghost btn-sm"
              title="Retry last message"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Retry
            </button>
            <button
              onClick={handleExport}
              disabled={messages.length === 0}
              className="btn-ghost btn-sm"
              title="Export conversation"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              Export
            </button>
            <button
              onClick={clearChat}
              disabled={messages.length === 0}
              className="btn-ghost btn-sm"
              title="Clear chat"
            >
              <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
              Clear
            </button>
          </div>
        </div>

        <ChatMessageList messages={messages} isLoading={isLoading} />

        {messages.length <= 1 && (
          <SuggestedPrompts prompts={suggestedPrompts} onSelect={handleSend} />
        )}

        {toolExecutions.length > 0 && (
          <ToolExecutionPanel executions={toolExecutions} />
        )}

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>

      <AgentInfoPanel
        agents={agents}
        toolExecutions={toolExecutions}
        agentUsed={agentUsed}
        processingTimeMs={processingTimeMs}
        providers={providers}
      />
    </div>
  );
}
