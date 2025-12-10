'use client';

import { useState, useRef, useEffect, FormEvent } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import { useChatStore } from '@/lib/store';
import { api } from '@/lib/api';
import { ChatMessage } from '@/lib/types';

interface ChatWidgetProps {
  customerId?: string;
}

export function ChatWidget({ customerId }: ChatWidgetProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const {
    messages,
    sessionId,
    isLoading,
    addMessage,
    setSessionId,
    setLoading,
    setCustomerId,
    clearChat,
  } = useChatStore();

  useEffect(() => {
    if (customerId) {
      // If switching to a different customer, clear the chat
      useChatStore.getState().customerId !== customerId && clearChat();
      setCustomerId(customerId);
    }
  }, [customerId, setCustomerId, clearChat]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    addMessage(userMessage);
    setInput('');
    setLoading(true);

    try {
      const response = await api.sendChatMessage({
        customer_id: customerId || 'guest',
        message: input.trim(),
        session_id: sessionId || undefined,
      });

      if (response.session_id && !sessionId) {
        setSessionId(response.session_id);
      }

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        metadata: {
          tool_calls: response.tool_calls,
        },
      };

      addMessage(assistantMessage);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      };
      addMessage(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-primary-600 text-white">
        <div className="flex items-center space-x-2">
          <Bot className="w-5 h-5" />
          <span className="font-medium">Renewal Assistant</span>
        </div>
        <p className="text-xs text-primary-100 mt-1">
          Ask about policies, renewals, or get help with your account
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            <Bot className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>Start a conversation with our AI assistant</p>
            <p className="text-sm mt-2">
              Try asking about your policy details or renewal options
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`chat-message flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`flex items-start space-x-2 max-w-[80%] ${
                message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.role === 'user'
                    ? 'bg-primary-100'
                    : 'bg-gray-100'
                }`}
              >
                {message.role === 'user' ? (
                  <User className="w-4 h-4 text-primary-600" />
                ) : (
                  <Bot className="w-4 h-4 text-gray-600" />
                )}
              </div>
              <div
                className={`px-4 py-2 rounded-2xl ${
                  message.role === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                <p
                  className={`text-xs mt-1 ${
                    message.role === 'user' ? 'text-primary-200' : 'text-gray-400'
                  }`}
                >
                  {new Date(message.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center space-x-2 bg-gray-100 px-4 py-2 rounded-2xl">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full loading-dot"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full loading-dot"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full loading-dot"></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-200">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="p-2 bg-primary-600 text-white rounded-full hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
