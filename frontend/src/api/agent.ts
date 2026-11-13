import apiClient, { getAccessToken, setAccessToken } from "./client";
import { storage } from "../utils/storage";
import type { ChatResponse, ConversationDetail, AgentInfo, WorkflowTemplate, AgentActivity, AgentStats, ProviderInfo } from "../types/agent";

export async function sendChatMessage(
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const { data } = await apiClient.post("/agent/chat", {
    message,
    conversation_id: conversationId || null,
    stream: false,
  });
  return data;
}

export async function sendChatMessageStream(
  message: string,
  conversationId?: string,
  onChunk?: (chunk: string) => void,
  onMetadata?: (meta: { conversation_id: string; agent_type: string; citations: unknown[] }) => void,
  onDone?: (data: { content: string; agent_type: string; citations: unknown[] }) => void,
  onError?: (error: string) => void,
): Promise<void> {
  let token = getAccessToken() || storage.getAccessToken() || localStorage.getItem("access_token") || "";
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

  // Proactive token refresh if token is missing but refresh token exists
  if (!token) {
    const refreshToken = storage.getRefreshToken();
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const tokenData = await refreshRes.json();
          if (tokenData.access_token) {
            token = tokenData.access_token;
            setAccessToken(token);
          }
        }
      } catch {
        // proceed with best effort
      }
    }
  }

  const makeStreamRequest = async (authToken: string) => {
    return fetch(`${API_BASE_URL}/api/v1/agent/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({ message, conversation_id: conversationId || null, stream: true }),
    });
  };

  let response: Response;
  try {
    response = await makeStreamRequest(token);
  } catch (netErr) {
    // Network failure: try non-streaming fallback through apiClient
    try {
      const fallback = await sendChatMessage(message, conversationId);
      if (fallback?.message) {
        onMetadata?.({
          conversation_id: fallback.conversation_id,
          agent_type: fallback.agent_used,
          citations: fallback.message.citations || [],
        });
        onDone?.({
          content: fallback.message.content,
          agent_type: fallback.agent_used,
          citations: fallback.message.citations || [],
        });
        return;
      }
    } catch {
      onError?.("Network connection issue. Please check your connection and try again.");
      return;
    }
    return;
  }

  // Handle 401 or 422 authentication/validation retry
  if ((response.status === 401 || response.status === 422) && storage.getRefreshToken()) {
    try {
      const refreshRes = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: storage.getRefreshToken() }),
      });
      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        if (refreshData.access_token) {
          token = refreshData.access_token;
          setAccessToken(token);
          response = await makeStreamRequest(token);
        }
      }
    } catch {
      // proceed to fallback
    }
  }

  if (!response.ok) {
    // Graceful fallback to non-streaming endpoint via apiClient
    try {
      const fallback = await sendChatMessage(message, conversationId);
      if (fallback?.message) {
        onMetadata?.({
          conversation_id: fallback.conversation_id,
          agent_type: fallback.agent_used,
          citations: fallback.message.citations || [],
        });
        onDone?.({
          content: fallback.message.content,
          agent_type: fallback.agent_used,
          citations: fallback.message.citations || [],
        });
        return;
      }
    } catch {
      onError?.("I encountered an error processing your request. Please try again.");
      return;
    }
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    try {
      const fallback = await sendChatMessage(message, conversationId);
      if (fallback?.message) {
        onDone?.({
          content: fallback.message.content,
          agent_type: fallback.agent_used,
          citations: fallback.message.citations || [],
        });
        return;
      }
    } catch {
      onError?.("No response stream available.");
    }
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const event = JSON.parse(line);
          switch (event.type) {
            case "metadata":
              onMetadata?.(event);
              break;
            case "delta":
              onChunk?.(event.content || "");
              break;
            case "done":
              onDone?.(event);
              break;
            case "error":
              onError?.(event.content || "An error occurred.");
              break;
          }
        } catch {
          // skip malformed line
        }
      }
    }
    // Process any remaining buffer content
    if (buffer.trim()) {
      try {
        const event = JSON.parse(buffer);
        if (event.type === "done") onDone?.(event);
        else if (event.type === "delta") onChunk?.(event.content || "");
      } catch {
        // ignore
      }
    }
  } catch {
    onError?.("Stream interrupted. Please try again.");
  } finally {
    reader.releaseLock();
  }
}

export async function getConversations(): Promise<{ conversations: Array<{ id: string; title?: string; agent_type?: string; created_at: string; updated_at: string }> }> {
  const { data } = await apiClient.get("/agent/conversations");
  return data;
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const { data } = await apiClient.get(`/agent/conversations/${conversationId}`);
  return data;
}

export async function getAgents(): Promise<{ agents: AgentInfo[] }> {
  const { data } = await apiClient.get("/agent/agents");
  return data;
}

export async function getTools(): Promise<{ tools: string[] }> {
  const { data } = await apiClient.get("/agent/tools");
  return data;
}

export async function getProviders(): Promise<{ providers: ProviderInfo[] }> {
  try {
    const { data } = await apiClient.get("/agent/providers");
    return data;
  } catch {
    return { providers: [] };
  }
}

export async function getWorkflows(): Promise<{ workflows: WorkflowTemplate[] }> {
  const { data } = await apiClient.get("/agent/workflows");
  return data;
}

export async function getActivityLogs(): Promise<{ activity: AgentActivity[] }> {
  const { data } = await apiClient.get("/agent/activity");
  return data;
}

export async function getAgentStats(): Promise<AgentStats> {
  const { data } = await apiClient.get("/agent/stats");
  return data;
}

export async function createWorkflow(name: string, steps: Array<{ name: string; tool_name: string; confirmation_required?: boolean }>): Promise<{ workflow_id: string; name: string; status: string; steps_count: number }> {
  const { data } = await apiClient.post("/agent/workflows", { name, description: name, steps });
  return data;
}

export async function executeWorkflow(workflowId: string): Promise<Record<string, unknown>> {
  const { data } = await apiClient.post(`/agent/workflows/${workflowId}/execute`);
  return data;
}

export async function generateReport(reportType: string, title?: string, exportFormat?: string): Promise<Record<string, unknown>> {
  const { data } = await apiClient.post("/agent/reports/generate", {
    report_type: reportType,
    title,
    export_format: exportFormat || "pdf",
  });
  return data;
}

export async function exportReport(reportType: string, format: string): Promise<Record<string, unknown>> {
  const { data } = await apiClient.post("/agent/reports/export", {
    report_type: reportType,
    export_format: format,
  });
  return data;
}
