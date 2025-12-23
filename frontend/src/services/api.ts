/**
 * API service for communicating with the DevSecOps backend.
 * Handles authentication, chat, tickets, and policies endpoints.
 */

import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' }
});

// Add auth token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses by clearing auth
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export type AuthProvider = 'local' | 'azure_ad';

export interface User {
  id: number;
  username: string;
  email?: string;
  display_name?: string;
  auth_provider: AuthProvider;
  created_at: string;
}

export interface SSOStatus {
  enabled: boolean;
  provider: string;
}

export interface SSOLoginResponse {
  auth_url: string;
  state: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  llm_calls: number;
  cost: {
    input: number;
    output: number;
    total: number;
  };
}

export interface ChatResponse {
  response: string;
  tool_calls: ToolCall[];
  trace_url?: string;
  token_usage?: TokenUsage;
}

export interface Ticket {
  id: number;
  ticket_type: 'jira' | 'servicenow';
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  assignee: string | null;
  created_by: string;
  created_at: string;
  updated_at: string | null;
}

export interface Policy {
  id: string;
  title: string;
  content: string;
  category: string | null;
  severity: string | null;
  created_at: string;
  updated_at: string | null;
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }),
  register: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/register', { username, password }),
  me: () => api.get<User>('/auth/me'),

  // SSO endpoints
  ssoStatus: () => api.get<SSOStatus>('/auth/sso/status'),
  ssoLogin: () => api.get<SSOLoginResponse>('/auth/sso/login')
};

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onToolCall: (toolCall: ToolCall) => void;
  onMetadata: (metadata: { tool_calls: ToolCall[]; trace_url?: string; token_usage?: TokenUsage }) => void;
  onError: (error: string) => void;
  onDone: () => void;
}

export const chatApi = {
  send: (message: string, history: ChatMessage[]) =>
    api.post<ChatResponse>('/chat/', { message, conversation_history: history }),

  /**
   * Send a message with streaming response.
   * Uses Server-Sent Events to stream tokens as they're generated.
   */
  sendStream: async (
    message: string,
    history: ChatMessage[],
    callbacks: StreamCallbacks
  ): Promise<void> => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify({ message, conversation_history: history })
    });

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/';
        return;
      }
      callbacks.onError(`HTTP error: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      callbacks.onError('No response body');
      return;
    }

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          const eventType = line.slice(6).trim();
          continue;
        }
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim();
          if (!data) continue;

          try {
            const parsed = JSON.parse(data);

            // Handle different event types based on data content
            if (parsed.token) {
              callbacks.onToken(parsed.token);
            } else if (parsed.tool_name && parsed.arguments) {
              callbacks.onToolCall(parsed);
            } else if (parsed.token_usage) {
              callbacks.onMetadata(parsed);
            } else if (parsed.error) {
              callbacks.onError(parsed.error);
            } else if (parsed.status === 'complete') {
              callbacks.onDone();
            }
          } catch {
            // Ignore parse errors for partial data
          }
        }
      }
    }

    callbacks.onDone();
  }
};

export const ticketsApi = {
  list: () => api.get<Ticket[]>('/tickets/'),
  get: (id: number) => api.get<Ticket>(`/tickets/${id}`),
  create: (ticket: Omit<Ticket, 'id' | 'status' | 'created_at' | 'updated_at'>) =>
    api.post<Ticket>('/tickets/', ticket)
};

export const policiesApi = {
  list: () => api.get<Policy[]>('/policies/'),
  create: (policy: Omit<Policy, 'created_at' | 'updated_at'>) =>
    api.post<Policy>('/policies/', policy)
};
