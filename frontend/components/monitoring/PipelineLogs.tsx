"use client";

import { useEffect, useState, useRef } from 'react';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Terminal, AlertCircle, CheckCircle, Info, Loader2 } from 'lucide-react';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  phase?: string;
}

interface PipelineLogsProps {
  pipelineId: string;
}

export function PipelineLogs({ pipelineId }: PipelineLogsProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Fetch recent logs first
    fetchRecentLogs();
    
    // Then connect to WebSocket for live updates
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [pipelineId]);

  const fetchRecentLogs = async () => {
    try {
      const response = await fetch(`/api/v1/pipeline/${pipelineId}/logs?limit=100`);
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs || []);
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  const connectWebSocket = () => {
    try {
      const wsUrl = `ws://localhost:8001/ws/pipeline/${pipelineId}/logs`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'history') {
          setLogs(data.logs || []);
        } else if (data.type === 'log') {
          setLogs(prev => [...prev, data.entry]);
          // Auto-scroll to bottom
          if (scrollRef.current) {
            scrollRef.current.scrollIntoView({ behavior: 'smooth' });
          }
        }
      };

      ws.onerror = (event) => {
        setError('WebSocket connection failed');
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
      };

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);

      return () => clearInterval(pingInterval);
    } catch (err) {
      setError('Failed to connect to log stream');
      console.error('WebSocket error:', err);
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'WARNING':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'SUCCESS':
      case 'COMPLETED':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'INFO':
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR':
        return 'text-red-500';
      case 'WARNING':
        return 'text-yellow-500';
      case 'SUCCESS':
      case 'COMPLETED':
        return 'text-green-500';
      case 'INFO':
      default:
        return 'text-blue-500';
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Terminal className="h-5 w-5" />
          <h3 className="font-semibold">Pipeline Logs</h3>
        </div>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Badge variant="outline" className="text-green-600">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Live
            </Badge>
          ) : (
            <Badge variant="outline" className="text-gray-500">
              Disconnected
            </Badge>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-md text-sm">
          {error}
        </div>
      )}

      <ScrollArea className="h-[400px] w-full rounded-md border bg-black p-4">
        <div className="font-mono text-xs">
          {logs.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No logs available yet...
            </div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className="flex items-start gap-2 mb-2">
                <span className="text-gray-500 whitespace-nowrap">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                {getLevelIcon(log.level)}
                <span className={getLevelColor(log.level)}>
                  [{log.level}]
                </span>
                {log.phase && (
                  <Badge variant="outline" className="text-xs">
                    {log.phase}
                  </Badge>
                )}
                <span className="text-gray-300 break-all">
                  {log.message}
                </span>
              </div>
            ))
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>
    </Card>
  );
}



