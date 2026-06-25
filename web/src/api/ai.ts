import client from "./client"

// SSE event types from /api/ai/chat
export interface SSEEvent {
  type: "token" | "error" | "done"
  content?: string
}

export const aiApi = {
  chat: (conversationId: string, message: string) =>
    client.post("/api/ai/chat", { conversation_id: conversationId, message }) as Promise<{
      reply: string;
      conversation_id: string;
      history: unknown[];
    }>,
  conversations: () =>
    client.get("/api/ai/conversations") as Promise<{
      conversations: { id: string; title: string; created_at: string; message_count: number }[];
    }>,
  clear: (id: string) => client.delete(`/api/ai/conversation/${id}`) as Promise<void>,
  getConversations: () =>
    client.get("/api/ai/conversations") as Promise<{
      conversations: { id: string; title: string; created_at: string; message_count: number }[];
    }>,
  getConversation: (id: string) =>
    client.get(`/api/ai/conversation/${id}`) as Promise<{
      conversation_id: string;
      messages: { role: string; content: string; timestamp: string }[];
    }>,
  saveMessage: (conversationId: string, role: string, content: string) =>
    client.post(`/api/ai/conversation/${conversationId}/message`, { role, content }) as Promise<{
      saved: boolean;
      id: number | null;
    }>,
  deleteConversation: (id: string) =>
    client.delete(`/api/ai/conversation/${id}`) as Promise<{ cleared: boolean }>,
}

export async function* streamChat(
  conversationId: string,
  message: string,
  options?: { mode?: string },
): AsyncGenerator<SSEEvent, void, unknown> {
  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch("/api/ai/chat", {
    method: "POST",
    headers,
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      mode: options?.mode,
    }),
  });
  if (!res.ok || !res.body) throw new Error("Stream failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.slice(6);
        try {
          const event = JSON.parse(jsonStr) as SSEEvent;
          yield event;
        } catch {
          // skip unparseable SSE data
        }
      }
    }
  }
  // flush remaining buffer
  if (buffer.startsWith("data: ")) {
    const jsonStr = buffer.slice(6);
    try {
      const event = JSON.parse(jsonStr) as SSEEvent;
      yield event;
    } catch {
      // skip
    }
  }
}

export interface StructuredInsight {
  summary: string
  overfitRisk: string | null
  alphaDecomposition: string | null
  suggestions: string[]
}

export async function analyzeBacktest(backtestId: string): Promise<{ insight: string | StructuredInsight }> {
  return await client.post(`/api/ai/analyze-backtest/${backtestId}`) as { insight: string | StructuredInsight }
}
