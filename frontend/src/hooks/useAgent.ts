import { useState, useCallback, useRef, useEffect } from "react";
import type { ChatMessage, ChatResponse, Conversation, AgentInfo, ToolExecutionResponse, ProviderInfo } from "../types/agent";
import {
  sendChatMessage as apiSendMessage,
  sendChatMessageStream as apiStreamMessage,
  getConversations as apiGetConversations,
  getConversation as apiGetConversation,
  getAgents as apiGetAgents,
  getProviders as apiGetProviders,
} from "../api/agent";

interface UseAgentReturn {
  messages: ChatMessage[];
  conversations: Conversation[];
  agents: AgentInfo[];
  providers: ProviderInfo[];
  activeConversationId: string | null;
  isLoading: boolean;
  toolExecutions: ToolExecutionResponse[];
  agentUsed: string;
  processingTimeMs: number;
  providerUsed: string;
  sendMessage: (message: string) => Promise<void>;
  loadConversations: () => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  loadAgents: () => Promise<void>;
  loadProviders: () => Promise<void>;
  startNewConversation: () => void;
  clearChat: () => void;
  suggestedPrompts: string[];
  retryLastMessage: () => void;
}

function getSuggestedPrompts(roles: string[]): string[] {
  if (roles.includes("admin")) {
    return [
      "Show system health overview",
      "List failed login attempts in the last 7 days",
      "How many active users do we have?",
      "Generate a security audit report",
    ];
  }
  if (roles.includes("hr") || roles.includes("hr_manager") || roles.includes("organization_admin")) {
    return [
      "Generate this month's hiring report",
      "Show hiring pipeline status",
      "Analyze recruitment fairness metrics",
      "What's our time-to-hire average?",
    ];
  }
  if (roles.includes("recruiter")) {
    return [
      "Show the top 10 Python developers for Job ID 15",
      "Compare the best three candidates",
      "Schedule interviews for shortlisted candidates",
      "Search for React developers in New York",
    ];
  }
  return [
    "Why is my resume score only 82?",
    "How can I improve my profile for this job?",
    "What jobs match my skills?",
    "Show my application status",
  ];
}

export function useAgent(userRoles: string[] = []): UseAgentReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [toolExecutions, setToolExecutions] = useState<ToolExecutionResponse[]>([]);
  const [agentUsed, setAgentUsed] = useState("");
  const [processingTimeMs, setProcessingTimeMs] = useState(0);
  const [providerUsed, setProviderUsed] = useState("");
  const lastMessageRef = useRef<string>("");
  const abortRef = useRef<AbortController | null>(null);

  const suggestedPrompts = getSuggestedPrompts(userRoles);

  const sendMessage = useCallback(async (message: string) => {
    setIsLoading(true);
    lastMessageRef.current = message;
    const userMsg: ChatMessage = { role: "user", content: message, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const response: ChatResponse = await apiSendMessage(message, activeConversationId || undefined);
      setActiveConversationId(response.conversation_id);
      setMessages((prev) => [...prev, response.message]);
      setToolExecutions(response.tool_executions);
      setAgentUsed(response.agent_used);
      setProcessingTimeMs(response.processing_time_ms);
      setProviderUsed(response.provider_used || "");
    } catch {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: "I encountered an error processing your request. This might be because no AI provider is configured. Please try again or contact support.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [activeConversationId]);

  const sendMessageStream = useCallback(async (message: string) => {
    setIsLoading(true);
    lastMessageRef.current = message;
    const userMsg: ChatMessage = { role: "user", content: message, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);

    const streamingMsg: ChatMessage = {
      role: "assistant",
      content: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, streamingMsg]);

    let fullContent = "";

    try {
      await apiStreamMessage(
        message,
        activeConversationId || undefined,
        (chunk) => {
          fullContent += chunk;
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = { ...last, content: fullContent };
            }
            return updated;
          });
        },
        (meta) => {
          setActiveConversationId(meta.conversation_id);
          setAgentUsed(meta.agent_type || "");
        },
        (done) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                content: done.content || fullContent,
                isStreaming: false,
                agent_type: done.agent_type || last.agent_type,
                citations: (done.citations as ChatMessage["citations"]) || last.citations,
              };
            }
            return updated;
          });
        },
        (error) => {
          let userFriendlyMessage = "I encountered an error processing your request. Please try again in a moment.";
          if (error && typeof error === "string") {
            const trimmed = error.trim();
            if (trimmed.startsWith("{")) {
              try {
                const parsed = JSON.parse(trimmed);
                if (parsed.error?.code === "validation_error" || JSON.stringify(parsed).includes("authorization")) {
                  userFriendlyMessage = "Authentication required. Please refresh the page or sign in again.";
                } else if (parsed.error?.message && !parsed.error.message.toLowerCase().includes("validation")) {
                  userFriendlyMessage = parsed.error.message;
                } else if (parsed.message && !parsed.message.toLowerCase().includes("validation")) {
                  userFriendlyMessage = parsed.message;
                }
              } catch {
                // keep friendly fallback
              }
            } else {
              userFriendlyMessage = trimmed;
            }
          }
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.isStreaming) {
              updated[updated.length - 1] = {
                ...last,
                content: userFriendlyMessage,
                isStreaming: false,
              };
            }
            return updated;
          });
        },
      );
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last && last.isStreaming) {
          updated[updated.length - 1] = {
            ...last,
            content: "I encountered an error. Please try again.",
            isStreaming: false,
          };
        }
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }, [activeConversationId]);

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiGetConversations();
      setConversations(data.conversations);
    } catch {
      // silently fail
    }
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    try {
      setIsLoading(true);
      const data = await apiGetConversation(id);
      setActiveConversationId(data.id);
      setMessages(data.messages || []);
    } catch {
      // silently fail
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const data = await apiGetAgents();
      setAgents(data.agents);
    } catch {
      // silently fail
    }
  }, []);

  const loadProviders = useCallback(async () => {
    try {
      const data = await apiGetProviders();
      setProviders(data.providers);
    } catch {
      // silently fail
    }
  }, []);

  const startNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setToolExecutions([]);
    setAgentUsed("");
    setProcessingTimeMs(0);
    setProviderUsed("");
  }, []);

  const clearChat = useCallback(() => {
    startNewConversation();
  }, [startNewConversation]);

  const retryLastMessage = useCallback(() => {
    if (lastMessageRef.current) {
      const msg = lastMessageRef.current;
      setMessages((prev) => prev.slice(0, -1));
      sendMessage(msg);
    }
  }, [sendMessage]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return {
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
    sendMessage: sendMessageStream,
    loadConversations,
    loadConversation,
    loadAgents,
    loadProviders,
    startNewConversation,
    clearChat,
    suggestedPrompts,
    retryLastMessage,
  };
}
