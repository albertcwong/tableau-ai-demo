'use client';

import { useState, useEffect } from 'react';
import { adminApi, FeedbackDetailResponse } from '@/lib/api';
import { Alert } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ThumbsUp, ThumbsDown, Clock, ChevronDown, ChevronUp, User, Database, MessageSquare, Copy, Check } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { extractErrorMessage } from '@/lib/utils';

export function FeedbackManagement() {
  const [feedback, setFeedback] = useState<FeedbackDetailResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [copiedId, setCopiedId] = useState<number | null>(null);

  useEffect(() => {
    loadFeedback();
  }, [filterType]);

  const loadFeedback = async () => {
    try {
      setLoading(true);
      setError(null);
      const feedbackType = filterType === 'all' ? undefined : (filterType as 'thumbs_up' | 'thumbs_down');
      const feedbackList = await adminApi.listFeedback(feedbackType);
      setFeedback(feedbackList);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Failed to load feedback'));
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (ms: number | null | undefined): string => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const toggleRow = (messageId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(messageId)) {
      newExpanded.delete(messageId);
    } else {
      newExpanded.add(messageId);
    }
    setExpandedRows(newExpanded);
  };

  const copyToClipboard = async (text: string, messageId: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(messageId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const exportConversation = (item: FeedbackDetailResponse) => {
    const exportData = {
      message_id: item.message_id,
      conversation_id: item.conversation_id,
      conversation_name: item.conversation_name,
      user: item.user,
      feedback: item.feedback,
      context_objects: item.context_objects,
      conversation_thread: item.conversation_thread,
      feedback_message: {
        role: item.role,
        content: item.content,
        model_used: item.model_used,
        total_time_ms: item.total_time_ms,
        created_at: item.created_at,
      }
    };
    const jsonStr = JSON.stringify(exportData, null, 2);
    copyToClipboard(jsonStr, item.message_id);
  };

  if (loading) {
    return <div className="text-center py-8">Loading feedback...</div>;
  }

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">{error}</Alert>
      )}

      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Message Feedback</h2>
        <div className="flex items-center gap-2">
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Filter by type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Feedback</SelectItem>
              <SelectItem value="thumbs_up">Thumbs Up</SelectItem>
              <SelectItem value="thumbs_down">Thumbs Down</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-4">
        {feedback.map((item) => {
          const isExpanded = expandedRows.has(item.message_id);
          return (
            <Card key={item.message_id} className="overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <CardTitle className="text-lg">
                        Message #{item.message_id} - {item.conversation_name || `Conversation ${item.conversation_id}`}
                      </CardTitle>
                      <div className="flex items-center gap-2">
                        {item.feedback === 'thumbs_up' ? (
                          <ThumbsUp className="h-5 w-5 text-green-600 dark:text-green-400 fill-current" />
                        ) : (
                          <ThumbsDown className="h-5 w-5 text-red-600 dark:text-red-400 fill-current" />
                        )}
                        <span className={`text-sm font-medium ${item.feedback === 'thumbs_up' ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                          {item.feedback === 'thumbs_up' ? 'Thumbs Up' : 'Thumbs Down'}
                        </span>
                      </div>
                    </div>
                    <CardDescription className="flex items-center gap-4 flex-wrap">
                      <span>Conversation ID: {item.conversation_id}</span>
                      {item.user && (
                        <span className="flex items-center gap-1">
                          <User className="h-3.5 w-3.5" />
                          {item.user.username} ({item.user.role})
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatTime(item.total_time_ms)}
                      </span>
                      <span>{formatDate(item.created_at)}</span>
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => exportConversation(item)}
                      className="flex items-center gap-1"
                    >
                      {copiedId === item.message_id ? (
                        <>
                          <Check className="h-4 w-4" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4" />
                          Export JSON
                        </>
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleRow(item.message_id)}
                      className="flex items-center gap-1"
                    >
                      {isExpanded ? (
                        <>
                          <ChevronUp className="h-4 w-4" />
                          Hide Details
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-4 w-4" />
                          Show Details
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <div className="text-sm font-medium mb-1">
                      {item.agent_type 
                        ? `${item.agent_type === 'multi_agent' ? 'Multi-Agent' : item.agent_type === 'vizql' ? 'VizQL' : item.agent_type.charAt(0).toUpperCase() + item.agent_type.slice(1)} Message` 
                        : 'Feedback Message'}
                    </div>
                    <div className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 p-3 rounded border break-words">
                      {item.content}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      Model: {item.model_used || 'N/A'} • Role: {item.role}
                    </div>
                  </div>
                  
                  {item.feedback_text && (
                    <div>
                      <div className="text-sm font-medium mb-1">
                        <span className="flex items-center gap-1">
                          <User className="h-3.5 w-3.5" />
                          {item.user?.username ? `<${item.user.username}> Feedback` : 'User Feedback'}
                        </span>
                      </div>
                      <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded border break-words whitespace-pre-wrap">
                        {item.feedback_text}
                      </div>
                    </div>
                  )}

                  {isExpanded && (
                    <div className="space-y-4 pt-4 border-t">
                      {/* Context Objects */}
                      {item.context_objects.length > 0 && (
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Database className="h-4 w-4" />
                            <div className="text-sm font-medium">Context Objects ({item.context_objects.length})</div>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {item.context_objects.map((ctx, idx) => (
                              <div key={idx} className="text-sm bg-gray-50 dark:bg-gray-800 p-2 rounded border">
                                <div className="font-medium">{ctx.object_name || ctx.object_id}</div>
                                <div className="text-xs text-gray-500">
                                  Type: {ctx.object_type} • ID: {ctx.object_id}
                                </div>
                                <div className="text-xs text-gray-400">
                                  Added: {formatDate(ctx.added_at)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Full Conversation Thread */}
                      {item.conversation_thread.length > 0 && (
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <MessageSquare className="h-4 w-4" />
                            <div className="text-sm font-medium">Full Conversation Thread ({item.conversation_thread.length} messages)</div>
                          </div>
                          <div className="space-y-2 max-h-96 overflow-y-auto">
                            {item.conversation_thread.map((msg) => (
                              <div
                                key={msg.id}
                                className={`text-sm p-3 rounded border ${
                                  msg.id === item.message_id
                                    ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-300 dark:border-yellow-700'
                                    : msg.role === 'USER'
                                    ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                                    : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                                }`}
                              >
                                <div className="flex items-start justify-between mb-1">
                                  <div className="font-medium text-xs uppercase">
                                    {msg.role}
                                    {msg.id === item.message_id && (
                                      <span className="ml-2 text-yellow-600 dark:text-yellow-400">(Feedback Given)</span>
                                    )}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    {formatDate(msg.created_at)}
                                    {msg.total_time_ms && (
                                      <span className="ml-2">• {formatTime(msg.total_time_ms)}</span>
                                    )}
                                  </div>
                                </div>
                                <div className="break-words whitespace-pre-wrap">{msg.content}</div>
                                {msg.model_used && (
                                  <div className="text-xs text-gray-500 mt-1">
                                    Model: {msg.model_used}
                                    {msg.tokens_used && ` • Tokens: ${msg.tokens_used.toLocaleString()}`}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
        {feedback.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No feedback found{filterType !== 'all' ? ` for ${filterType === 'thumbs_up' ? 'thumbs up' : 'thumbs down'}` : ''}.
          </div>
        )}
      </div>
    </div>
  );
}
