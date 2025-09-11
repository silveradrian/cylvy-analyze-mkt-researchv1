'use client';

import React, { useState, useEffect, useRef } from 'react';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Clock, 
  Pause, 
  Play, 
  Trash2, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Loader2,
  Activity,
  Calendar,
  Timer,
  BarChart3,
  AlertCircle,
  FileText,
  Building2,
  Video,
  Brain,
  TrendingUp
} from 'lucide-react';
import { format, formatDistanceToNow, differenceInSeconds } from 'date-fns';

interface PipelinePhase {
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  startTime?: string;
  endTime?: string;
  progress?: number;
  itemsProcessed?: number;
  totalItems?: number;
  error?: string;
}

// Logs Display Component
const LogsDisplay: React.FC<{ pipelineId: string }> = ({ pipelineId }) => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const logsEndRef = useRef<null | HTMLDivElement>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch(`/api/v1/pipeline/monitoring/${pipelineId}/logs`);
        if (response.ok) {
          const data = await response.json();
          setLogs(data.logs || []);
        }
      } catch (error) {
        console.error('Failed to fetch logs:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
    // Refresh logs every 5 seconds
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [pipelineId]);

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getLogColor = (level: string) => {
    switch (level) {
      case 'ERROR': return 'text-red-500';
      case 'WARNING': return 'text-yellow-500';
      case 'INFO': return 'text-blue-500';
      default: return 'text-gray-500';
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading logs...</div>;
  }

  return (
    <div className="bg-slate-900 rounded-lg p-4 font-mono text-xs max-h-96 overflow-y-auto">
      {logs.length === 0 ? (
        <p className="text-gray-400">No logs available yet...</p>
      ) : (
        logs.map((log, index) => (
          <div key={index} className="py-1">
            <span className="text-gray-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
            <span className={`ml-2 ${getLogColor(log.level)}`}>[{log.level}]</span>
            <span className="ml-2 text-gray-300">{log.message}</span>
          </div>
        ))
      )}
      <div ref={logsEndRef} />
    </div>
  );
};

interface Pipeline {
  id: string;
  status: 'running' | 'completed' | 'failed' | 'paused' | 'cancelled';
  mode: 'test' | 'scheduled' | 'manual';
  startTime: string;
  endTime?: string;
  contentTypes: string[];
  regions: string[];
  currentPhase?: string;
  phases: {
    keyword_metrics: PipelinePhase;
    serp_collection: PipelinePhase;
    company_enrichment: PipelinePhase;
    video_enrichment: PipelinePhase;
    content_analysis: PipelinePhase;
    dsi_calculation: PipelinePhase;
  };
  metrics?: {
    totalKeywords: number;
    totalSearches: number;
    resultsCollected: number;
    domainsEnriched: number;
    videosAnalyzed: number;
    contentAnalyzed: number;
  };
}

const phaseIcons = {
  keyword_metrics: BarChart3,
  serp_collection: FileText,
  company_enrichment: Building2,
  video_enrichment: Video,
  content_analysis: Brain,
  dsi_calculation: TrendingUp
};

const phaseDisplayNames = {
  keyword_metrics: 'Keyword Metrics',
  serp_collection: 'SERP Collection',
  company_enrichment: 'Company Enrichment',
  video_enrichment: 'Video Enrichment',
  content_analysis: 'Content Analysis',
  dsi_calculation: 'DSI Calculation'
};

export default function MonitoringPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [showFailed, setShowFailed] = useState(true);
  const detailsRef = useRef<HTMLDivElement>(null);

  // Fetch pipeline data
  const fetchPipelines = async () => {
    try {
      const response = await fetch('/api/v1/pipeline/monitoring');
      if (response.ok) {
        const data = await response.json();
        setPipelines(data.pipelines || []);
        if (data.pipelines?.length > 0 && !selectedPipeline) {
          setSelectedPipeline(data.pipelines[0].id);
        }
      }
    } catch (error) {
      console.error('Failed to fetch pipelines:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-refresh every 2 seconds for active pipelines
  useEffect(() => {
    fetchPipelines();
    
    if (autoRefresh) {
      const interval = setInterval(fetchPipelines, 2000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  // Control pipeline
  const controlPipeline = async (pipelineId: string, action: 'pause' | 'resume' | 'cancel' | 'delete') => {
    try {
      const response = await fetch(`/api/v1/pipeline/${pipelineId}/${action}`, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchPipelines();
      }
    } catch (error) {
      console.error(`Failed to ${action} pipeline:`, error);
    }
  };

  const getPhaseTime = (phase: PipelinePhase) => {
    if (!phase.startTime) return null;
    
    const start = new Date(phase.startTime);
    const end = phase.endTime ? new Date(phase.endTime) : new Date();
    const seconds = differenceInSeconds(end, start);
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    return `${minutes}m ${remainingSeconds}s`;
  };

  const getEstimatedTimeRemaining = (pipeline: Pipeline) => {
    if (pipeline.status !== 'running' || !pipeline.currentPhase) return null;
    
    // Rough estimates based on phase (in seconds)
    const phaseEstimates: Record<string, number> = {
      keyword_metrics: 30,
      serp_collection: 180,
      company_enrichment: 120,
      youtube_enrichment: 240,
      content_analysis: 90,
      dsi_calculation: 60
    };
    
    const remainingPhases = Object.keys(pipeline.phases).filter(phase => {
      const phaseData = pipeline.phases[phase as keyof typeof pipeline.phases];
      return phaseData.status === 'pending' || phaseData.status === 'in_progress';
    });
    
    const totalSeconds = remainingPhases.reduce((sum, phase) => sum + (phaseEstimates[phase] || 60), 0);
    const minutes = Math.floor(totalSeconds / 60);
    
    return `~${minutes} minutes`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      case 'running': 
      case 'in_progress': return 'text-blue-600';
      case 'paused': return 'text-yellow-600';
      case 'cancelled': return 'text-gray-600';
      default: return 'text-gray-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="w-4 h-4" />;
      case 'failed': return <XCircle className="w-4 h-4" />;
      case 'running':
      case 'in_progress': return <Loader2 className="w-4 h-4 animate-spin" />;
      case 'paused': return <Pause className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const currentPipeline = pipelines.find(p => p.id === selectedPipeline);

  if (isLoading) {
    return (
      <AdminLayout title="Pipeline Monitoring" description="Real-time pipeline execution monitoring">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Pipeline Monitoring" description="Real-time pipeline execution monitoring">
      <div className="space-y-6">
        {/* Header Controls */}
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchPipelines()}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh
            </label>
          </div>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {pipelines.filter(p => p.status === 'running').length} active pipelines
            </span>
          </div>
        </div>

        {/* Pipeline List */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle>Pipeline Runs</CardTitle>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowFailed(!showFailed)}
                >
                  {showFailed ? 'Hide' : 'Show'} Failed
                </Button>
                {pipelines.filter(p => p.status === 'failed').length > 0 && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={async () => {
                      const failedPipelines = pipelines.filter(p => p.status === 'failed');
                      for (const pipeline of failedPipelines) {
                        await controlPipeline(pipeline.id, 'delete');
                      }
                      fetchPipelines();
                    }}
                  >
                    Clear All Failed ({pipelines.filter(p => p.status === 'failed').length})
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {pipelines.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No pipeline runs found
                </div>
              ) : (
                pipelines
                  .filter(pipeline => showFailed || pipeline.status !== 'failed')
                  .map(pipeline => (
                  <div
                    key={pipeline.id}
                    className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                      selectedPipeline === pipeline.id ? 'border-primary bg-primary/5' : 'hover:border-gray-300'
                    }`}
                    onClick={() => {
                      setSelectedPipeline(pipeline.id);
                      // Auto-scroll to details after a short delay
                      setTimeout(() => {
                        detailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }, 100);
                    }}
                  >
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className={`flex items-center gap-1 ${getStatusColor(pipeline.status)}`}>
                            {getStatusIcon(pipeline.status)}
                            <span className="font-medium capitalize">{pipeline.status}</span>
                          </span>
                          <Badge variant="outline" className="text-xs">
                            {pipeline.mode}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {pipeline.id.slice(0, 8)}...
                          </span>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Started {formatDistanceToNow(new Date(pipeline.startTime), { addSuffix: true })}
                        </div>
                        <div className="flex gap-2 text-xs">
                          {pipeline.contentTypes.map(type => (
                            <Badge key={type} variant="secondary" className="text-xs">
                              {type}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      {pipeline.status === 'running' && (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              controlPipeline(pipeline.id, 'pause');
                            }}
                          >
                            <Pause className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              controlPipeline(pipeline.id, 'cancel');
                            }}
                          >
                            <XCircle className="w-4 h-4" />
                          </Button>
                        </div>
                      )}
                      {pipeline.status === 'paused' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            controlPipeline(pipeline.id, 'resume');
                          }}
                        >
                          <Play className="w-4 h-4" />
                        </Button>
                      )}
                      {['completed', 'failed', 'cancelled'].includes(pipeline.status) && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            controlPipeline(pipeline.id, 'delete');
                          }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Pipeline Details */}
        {currentPipeline && (
          <Card ref={detailsRef} className="mt-6 border-2 border-primary">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle>Pipeline Details</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    ID: {currentPipeline.id}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">
                    <Calendar className="w-4 h-4 inline mr-1" />
                    {format(new Date(currentPipeline.startTime), 'PPp')}
                  </div>
                  {currentPipeline.status === 'running' && (
                    <div className="text-sm text-muted-foreground mt-1">
                      <Timer className="w-4 h-4 inline mr-1" />
                      Est. time remaining: {getEstimatedTimeRemaining(currentPipeline)}
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="phases" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="phases">Phases</TabsTrigger>
                  <TabsTrigger value="metrics">Metrics</TabsTrigger>
                  <TabsTrigger value="logs">Logs</TabsTrigger>
                </TabsList>

                <TabsContent value="phases" className="space-y-4">
                  {Object.entries(currentPipeline.phases).map(([phaseKey, phase]) => {
                    const Icon = phaseIcons[phaseKey as keyof typeof phaseIcons] || Activity;
                    const displayName = phaseDisplayNames[phaseKey as keyof typeof phaseDisplayNames] || phaseKey;
                    
                    return (
                      <div key={phaseKey} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Icon className="w-5 h-5 text-muted-foreground" />
                            <span className="font-medium">{displayName}</span>
                            <span className={`flex items-center gap-1 text-sm ${getStatusColor(phase.status)}`}>
                              {getStatusIcon(phase.status)}
                              <span className="capitalize">{phase.status.replace('_', ' ')}</span>
                            </span>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {phase.startTime && (
                              <>
                                <Clock className="w-4 h-4 inline mr-1" />
                                {getPhaseTime(phase)}
                              </>
                            )}
                          </div>
                        </div>
                        
                        {phase.status === 'in_progress' && phase.progress !== undefined && (
                          <div className="space-y-1">
                            <Progress value={phase.progress} className="h-2" />
                            <div className="text-xs text-muted-foreground text-right">
                              {phase.itemsProcessed}/{phase.totalItems} items ({phase.progress}%)
                            </div>
                          </div>
                        )}
                        
                        {phase.error && (
                          <Alert>
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{phase.error}</AlertDescription>
                          </Alert>
                        )}
                      </div>
                    );
                  })}
                </TabsContent>

                <TabsContent value="metrics" className="space-y-4">
                  {currentPipeline.metrics && (
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Keywords</p>
                        <p className="text-2xl font-bold">{currentPipeline.metrics.totalKeywords}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Total Searches</p>
                        <p className="text-2xl font-bold">{currentPipeline.metrics.totalSearches}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Results Collected</p>
                        <p className="text-2xl font-bold">{currentPipeline.metrics.resultsCollected}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Domains Enriched</p>
                        <p className="text-2xl font-bold">{currentPipeline.metrics.domainsEnriched}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Videos Analyzed</p>
                        <p className="text-2xl font-bold">{currentPipeline.metrics.videosAnalyzed}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">Content Analyzed</p>
                        <p className="text-2xl font-bold">{currentPipeline.metrics.contentAnalyzed}</p>
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="logs">
                  <LogsDisplay pipelineId={currentPipeline.id} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        )}
      </div>
    </AdminLayout>
  );
}