/**
 * Chat component for interacting with the DevSecOps AI assistant.
 * Maintains conversation history in memory (persists across tab switches).
 * Displays tool calls and token usage visually.
 * Supports both streaming and non-streaming responses.
 */

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { chatApi } from '../services/api';
import type { ChatMessage, ToolCall, TokenUsage } from '../services/api';

// Store chat state outside component to persist across tab switches
let persistedMessages: ChatMessage[] = [];
let persistedTotalUsage = { tokens: 0, cost: 0 };

// Toggle for streaming mode
const USE_STREAMING = true;

export default function Chat() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>(persistedMessages);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [loading, setLoading] = useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [traceUrl, setTraceUrl] = useState<string | null>(null);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [totalUsage, setTotalUsage] = useState(persistedTotalUsage);
  const [streamingContent, setStreamingContent] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Sync state changes to persisted storage
  useEffect(() => {
    persistedMessages = messages;
  }, [messages]);

  useEffect(() => {
    persistedTotalUsage = totalUsage;
  }, [totalUsage]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const clearChat = () => {
    setMessages([]);
    setToolCalls([]);
    setTokenUsage(null);
    setTraceUrl(null);
    setTotalUsage({ tokens: 0, cost: 0 });
    setStreamingContent('');
    persistedMessages = [];
    persistedTotalUsage = { tokens: 0, cost: 0 };
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    setToolsExpanded(false);
    setStreamingContent('');
    setToolCalls([]);

    if (USE_STREAMING) {
      // Streaming mode
      let accumulatedContent = '';
      const streamingToolCalls: ToolCall[] = [];

      try {
        await chatApi.sendStream(input, messages, {
          onToken: (token) => {
            accumulatedContent += token;
            setStreamingContent(accumulatedContent);
          },
          onToolCall: (toolCall) => {
            streamingToolCalls.push(toolCall);
            setToolCalls([...streamingToolCalls]);
          },
          onMetadata: (metadata) => {
            if (metadata.trace_url) {
              setTraceUrl(metadata.trace_url);
            }
            if (metadata.token_usage) {
              setTokenUsage(metadata.token_usage);
              setTotalUsage(prev => ({
                tokens: prev.tokens + metadata.token_usage!.total_tokens,
                cost: prev.cost + metadata.token_usage!.cost.total
              }));
            }
            if (metadata.tool_calls && metadata.tool_calls.length > 0) {
              setToolCalls(metadata.tool_calls);
            }
          },
          onError: (error) => {
            setMessages([...newMessages, { role: 'assistant', content: `Error: ${error}` }]);
            setStreamingContent('');
            setLoading(false);
          },
          onDone: () => {
            if (accumulatedContent) {
              setMessages([...newMessages, { role: 'assistant', content: accumulatedContent }]);
              setStreamingContent('');
            }
            setLoading(false);
          }
        });
      } catch (err: unknown) {
        const error = err as Error;
        setMessages([...newMessages, { role: 'assistant', content: `Error: ${error.message}` }]);
        setStreamingContent('');
        setLoading(false);
      }
    } else {
      // Non-streaming mode
      try {
        const { data } = await chatApi.send(input, messages);
        setMessages([...newMessages, { role: 'assistant', content: data.response }]);
        setToolCalls(data.tool_calls);
        if (data.trace_url) {
          setTraceUrl(data.trace_url);
        }
        if (data.token_usage) {
          setTokenUsage(data.token_usage);
          setTotalUsage(prev => ({
            tokens: prev.tokens + data.token_usage!.total_tokens,
            cost: prev.cost + data.token_usage!.cost.total
          }));
        }
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } };
        const errorMessage = error.response?.data?.detail || 'Failed to get response';
        setMessages([...newMessages, { role: 'assistant', content: `Error: ${errorMessage}` }]);
      } finally {
        setLoading(false);
      }
    }
  };

  const formatCost = (cost: number) => {
    if (cost < 0.01) return `$${cost.toFixed(6)}`;
    return `$${cost.toFixed(4)}`;
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        {totalUsage.tokens > 0 && (
          <div className="usage-banner">
            <span>Session: {totalUsage.tokens.toLocaleString()} tokens</span>
            <span className="cost">{formatCost(totalUsage.cost)}</span>
          </div>
        )}
        {messages.length > 0 && (
          <button className="new-chat-button" onClick={clearChat} disabled={loading}>
            New Chat
          </button>
        )}
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">Ask about security scans, policies, or manage tickets</div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-header">{msg.role === 'user' ? 'You' : 'Assistant'}</div>
            <div className="message-content">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-header">Assistant</div>
            <div className="message-content">
              {streamingContent ? (
                <ReactMarkdown>{streamingContent}</ReactMarkdown>
              ) : (
                <span className="loading">Thinking...</span>
              )}
              <span className="cursor">▌</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {(toolCalls.length > 0 || traceUrl || tokenUsage) && (
        <div className={`tool-calls ${toolsExpanded ? 'expanded' : 'collapsed'}`}>
          <div className="tool-calls-header" onClick={() => setToolsExpanded(!toolsExpanded)}>
            <span className="arrow">{toolsExpanded ? '▼' : '▶'}</span>
            <h4>Details ({toolCalls.length} tools, {tokenUsage?.llm_calls || 0} LLM calls)</h4>
            {tokenUsage && (
              <span className="token-badge">
                {tokenUsage.total_tokens.toLocaleString()} tokens · {formatCost(tokenUsage.cost.total)}
              </span>
            )}
            {traceUrl && (
              <a
                href={traceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="trace-link"
                onClick={(e) => e.stopPropagation()}
              >
                LangSmith →
              </a>
            )}
          </div>
          {toolsExpanded && (
            <div className="tool-calls-content">
              {tokenUsage && (
                <div className="token-details">
                  <div className="token-row">
                    <span>Input tokens:</span>
                    <span>{tokenUsage.input_tokens.toLocaleString()} ({formatCost(tokenUsage.cost.input)})</span>
                  </div>
                  <div className="token-row">
                    <span>Output tokens:</span>
                    <span>{tokenUsage.output_tokens.toLocaleString()} ({formatCost(tokenUsage.cost.output)})</span>
                  </div>
                  <div className="token-row total">
                    <span>Total:</span>
                    <span>{tokenUsage.total_tokens.toLocaleString()} ({formatCost(tokenUsage.cost.total)})</span>
                  </div>
                </div>
              )}
              {toolCalls.length > 0 && (
                <div className="tools-section">
                  <h5>Tools Called:</h5>
                  {toolCalls.map((tc, i) => (
                    <div key={i} className="tool-call">
                      <span className="tool-name">{tc.tool_name}</span>
                      <pre>{JSON.stringify(tc.arguments, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <form onSubmit={sendMessage} className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>Send</button>
      </form>
    </div>
  );
}
