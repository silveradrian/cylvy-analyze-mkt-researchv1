'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Calendar, Clock, PlayCircle, CheckCircle, XCircle, 
  AlertCircle, Settings, Activity, Timer, Pause,
  ChevronRight, RefreshCw, Zap
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface ScheduledRun {
  id: string;
  content_type: string;
  frequency: string;
  next_run: string;
  last_run?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

interface PipelineExecution {
  pipeline_id: string;
  status: string;
  mode: string;
  started_at: string;
  completed_at?: string;
  content_types: string[];
  keywords_processed: number;
  current_phase?: string;
  phases_completed?: string[];
}

interface ScheduleConfig {
  organic: string;
  news: string;
  video: string;
  keyword_metrics: string;
}

const CONTENT_TYPE_INFO = {
  organic: { name: 'Organic Search', icon: '🔍', color: 'bg-blue-100 text-blue-800' },
  news: { name: 'News Results', icon: '📰', color: 'bg-green-100 text-green-800' },
  video: { name: 'Video Content', icon: '📺', color: 'bg-purple-100 text-purple-800' },
  keyword_metrics: { name: 'Keyword Metrics', icon: '📊', color: 'bg-orange-100 text-orange-800' }
};

export default function PipelinePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig | null>(null);
  const [recentExecutions, setRecentExecutions] = useState<PipelineExecution[]>([]);
  const [upcomingRuns, setUpcomingRuns] = useState<ScheduledRun[]>([]);
  const [activeTab, setActiveTab] = useState('timeline');
  const [error, setError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    loadPipelineData();
    setupWebSocket();
  }, []);

  const loadPipelineData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      // Load schedule configuration
      const scheduleResponse = await fetch('/api/v1/pipeline/schedules', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (scheduleResponse.ok) {
        const scheduleData = await scheduleResponse.json();
        if (scheduleData.schedules && scheduleData.schedules.length > 0) {
          const schedule = scheduleData.schedules[0];
          const config: ScheduleConfig = {
            organic: 'monthly',
            news: 'weekly',
            video: 'monthly',
            keyword_metrics: 'monthly'
          };
          
          schedule.content_schedules?.forEach((cs: any) => {
            if (cs.content_type in config) {
              config[cs.content_type as keyof ScheduleConfig] = cs.frequency;
            }
          });
          
          setScheduleConfig(config);
          calculateUpcomingRuns(config, schedule);
        }
      }
      
      // Load recent executions
      const executionsResponse = await fetch('/api/v1/pipeline/recent?limit=10', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (executionsResponse.ok) {
        const executionsData = await executionsResponse.json();
        setRecentExecutions(executionsData.pipelines || []);
      }
    } catch (err) {
      console.error('Failed to load pipeline data:', err);
      setError('Failed to load pipeline data');
    } finally {
      setLoading(false);
    }
  };

  const calculateUpcomingRuns = (config: ScheduleConfig, schedule: any) => {
    const now = new Date();
    const runs: ScheduledRun[] = [];
    
    // Calculate next runs for each content type
    Object.entries(config).forEach(([contentType, frequency]) => {
      const lastRun = schedule.last_executed_at ? new Date(schedule.last_executed_at) : new Date();
      let nextRun = new Date(lastRun);
      
      switch (frequency) {
        case 'daily':
          nextRun.setDate(nextRun.getDate() + 1);
          break;
        case 'weekly':
          nextRun.setDate(nextRun.getDate() + 7);
          break;
        case 'monthly':
          nextRun.setMonth(nextRun.getMonth() + 1);
          break;
      }
      
      // If next run is in the past, calculate from now
      if (nextRun < now) {
        nextRun = new Date(now);
        switch (frequency) {
          case 'daily':
            nextRun.setDate(nextRun.getDate() + 1);
            nextRun.setHours(9, 0, 0, 0); // 9 AM
            break;
          case 'weekly':
            nextRun.setDate(nextRun.getDate() + (7 - nextRun.getDay() + 1) % 7); // Next Monday
            nextRun.setHours(9, 0, 0, 0);
            break;
          case 'monthly':
            nextRun.setMonth(nextRun.getMonth() + 1);
            nextRun.setDate(1); // First of month
            nextRun.setHours(9, 0, 0, 0);
            break;
        }
      }
      
      runs.push({
        id: `${contentType}-next`,
        content_type: contentType,
        frequency: frequency,
        next_run: nextRun.toISOString(),
        last_run: schedule.last_executed_at,
        status: 'pending'
      });
    });
    
    setUpcomingRuns(runs.sort((a, b) => 
      new Date(a.next_run).getTime() - new Date(b.next_run).getTime()
    ));
  };

  const setupWebSocket = () => {
    // WebSocket setup for live updates
    try {
      const ws = new WebSocket(process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001/ws');
      
      ws.onopen = () => {
        setWsConnected(true);
        console.log('WebSocket connected for pipeline updates');
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'pipeline_update') {
          loadPipelineData(); // Reload data on updates
        }
      };
      
      ws.onclose = () => {
        setWsConnected(false);
        // Retry connection after 5 seconds
        setTimeout(setupWebSocket, 5000);
      };
      
      return () => ws.close();
    } catch (err) {
      console.error('WebSocket error:', err);
    }
  };

  const startManualPipeline = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/start', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content_types: ['organic', 'news', 'video'],
          regions: ['US', 'UK', 'DE', 'SA', 'VN']
        })
      });
      
      if (response.ok) {
        await loadPipelineData();
        setError(null);
      } else {
        setError('Failed to start pipeline');
      }
    } catch (err) {
      setError('Failed to start pipeline');
    }
  };

  const startTestPipeline = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/test-mode', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          batch_size: 5,
          skip_delays: true,
          regions: ['US'], // Backend will use regions from active schedule
          content_types: ['organic', 'news', 'video']
        })
      });
      
      if (response.ok) {
        await loadPipelineData();
        setError(null);
      } else {
        setError('Failed to start test pipeline');
      }
    } catch (err) {
      setError('Failed to start test pipeline');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Clock className="h-4 w-4 text-yellow-600" />;
      case 'running': return <Activity className="h-4 w-4 text-blue-600 animate-pulse" />;
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'failed': return <XCircle className="h-4 w-4 text-red-600" />;
      default: return <AlertCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  const formatTimeUntil = (date: string) => {
    const future = new Date(date);
    const now = new Date();
    const diff = future.getTime() - now.getTime();
    
    if (diff < 0) return 'Overdue';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `in ${days} day${days > 1 ? 's' : ''}`;
    if (hours > 0) return `in ${hours} hour${hours > 1 ? 's' : ''}`;
    return 'in less than an hour';
  };

  if (loading) {
    return (
      <AdminLayout title="Pipeline Timeline" description="Automated data collection schedule and execution history">
        <div className="flex items-center justify-center h-64">
          <Clock className="h-8 w-8 animate-spin text-cylvy-sage" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Pipeline Timeline" description="Automated data collection schedule and execution history">
      <div className="space-y-6">
        {/* Header Actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button onClick={() => router.push('/pipeline-schedules')} variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              Configure Schedule
            </Button>
            <Button onClick={startManualPipeline} variant="outline">
              <PlayCircle className="h-4 w-4 mr-2" />
              Run Now (All Types)
            </Button>
            <Button onClick={startTestPipeline} variant="outline" className="text-purple-600">
              <Zap className="h-4 w-4 mr-2" />
              Test Mode
            </Button>
          </div>
          
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-gray-600">
              {wsConnected ? 'Live Updates' : 'Connecting...'}
            </span>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">{error}</AlertDescription>
          </Alert>
        )}

        {/* Main Content Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="timeline">Timeline View</TabsTrigger>
            <TabsTrigger value="schedule">Schedule Status</TabsTrigger>
            <TabsTrigger value="history">Execution History</TabsTrigger>
          </TabsList>

          {/* Timeline View */}
          <TabsContent value="timeline" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Upcoming Scheduled Runs</CardTitle>
                <CardDescription>Next automated data collection times</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {upcomingRuns.map((run) => {
                    const info = CONTENT_TYPE_INFO[run.content_type as keyof typeof CONTENT_TYPE_INFO];
                    return (
                      <div key={run.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{info.icon}</span>
                          <div>
                            <h4 className="font-medium">{info.name}</h4>
                            <p className="text-sm text-gray-600">
                              {run.frequency} collection • {formatTimeUntil(run.next_run)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge className={info.color}>
                            {new Date(run.next_run).toLocaleDateString('en-US', { 
                              weekday: 'short', 
                              month: 'short', 
                              day: 'numeric',
                              hour: 'numeric',
                              minute: '2-digit'
                            })}
                          </Badge>
                          {getStatusIcon(run.status)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Timeline Visualization */}
            <Card>
              <CardHeader>
                <CardTitle>Collection Timeline</CardTitle>
                <CardDescription>Visual representation of your data collection schedule</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  {/* Timeline line */}
                  <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-200"></div>
                  
                  {/* Timeline items */}
                  <div className="space-y-6">
                    {[...upcomingRuns, ...recentExecutions.slice(0, 3).map(exec => ({
                      id: exec.pipeline_id,
                      content_type: Array.isArray(exec.content_types) ? exec.content_types.join(', ') : 'Unknown',
                      frequency: 'manual',
                      next_run: exec.started_at,
                      status: exec.status,
                      isPast: true
                    }))].sort((a, b) => 
                      new Date(b.next_run).getTime() - new Date(a.next_run).getTime()
                    ).map((item, index) => (
                      <div key={item.id} className="relative flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center z-10 ${
                          'isPast' in item && item.isPast 
                            ? 'bg-gray-100 border-2 border-gray-300' 
                            : 'bg-white border-2 border-cylvy-sage'
                        }`}>
                          {getStatusIcon(item.status)}
                        </div>
                        <div className={`flex-1 p-3 rounded-lg ${
                          'isPast' in item && item.isPast ? 'bg-gray-50' : 'bg-blue-50'
                        }`}>
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium">
                                {'isPast' in item && item.isPast ? 'Completed' : 'Scheduled'}: {
                                  item.content_type.includes(',') 
                                    ? 'All Content Types' 
                                    : CONTENT_TYPE_INFO[item.content_type as keyof typeof CONTENT_TYPE_INFO]?.name
                                }
                              </p>
                              <p className="text-sm text-gray-600">
                                {new Date(item.next_run).toLocaleString()}
                              </p>
                            </div>
                            {'isPast' in item && item.isPast ? null : (
                              <Badge variant="outline">{item.frequency}</Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Schedule Status */}
          <TabsContent value="schedule" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Current Schedule Configuration</CardTitle>
                <CardDescription>Active data collection frequencies</CardDescription>
              </CardHeader>
              <CardContent>
                {scheduleConfig ? (
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(scheduleConfig).map(([type, frequency]) => {
                      const info = CONTENT_TYPE_INFO[type as keyof typeof CONTENT_TYPE_INFO];
                      return (
                        <div key={type} className="p-4 border rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xl">{info.icon}</span>
                            <h4 className="font-medium">{info.name}</h4>
                          </div>
                          <Badge className={info.color}>{frequency}</Badge>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Calendar className="h-12 w-12 mx-auto mb-3 text-gray-400" />
                    <p>No schedule configured yet</p>
                    <Button 
                      onClick={() => router.push('/pipeline-schedules')} 
                      className="mt-4"
                      variant="outline"
                    >
                      Configure Schedule
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Execution History */}
          <TabsContent value="history" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Recent Pipeline Executions</CardTitle>
                <CardDescription>Last 10 pipeline runs</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {recentExecutions.map((execution) => (
                    <div key={execution.pipeline_id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {getStatusIcon(execution.status)}
                          <div>
                            <p className="font-medium">
                              {Array.isArray(execution.content_types) ? execution.content_types.join(', ') : 'Unknown'} • {execution.mode} mode
                            </p>
                            <p className="text-sm text-gray-600">
                              Started {formatDistanceToNow(new Date(execution.started_at))} ago
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge variant={
                            execution.status === 'completed' ? 'default' : 
                            execution.status === 'running' ? 'secondary' : 
                            'destructive'
                          }>
                            {execution.status}
                          </Badge>
                          {execution.keywords_processed > 0 && (
                            <p className="text-sm text-gray-600 mt-1">
                              {execution.keywords_processed} keywords
                            </p>
                          )}
                        </div>
                      </div>
                      {execution.current_phase && execution.status === 'running' && (
                        <div className="mt-3 pt-3 border-t">
                          <p className="text-sm text-gray-600">
                            Current: {execution.current_phase}
                          </p>
                          <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                            <div 
                              className="bg-cylvy-sage h-2 rounded-full transition-all"
                              style={{ width: `${(execution.phases_completed?.length || 0) / 7 * 100}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {recentExecutions.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Timer className="h-12 w-12 mx-auto mb-3 text-gray-400" />
                      <p>No pipeline executions yet</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}