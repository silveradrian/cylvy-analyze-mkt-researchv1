'use client';

import React, { useState, useEffect } from 'react';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PipelineLogs } from '@/components/monitoring/PipelineLogs';
import { RestartPhaseDialog } from '@/components/monitoring/RestartPhaseDialog';
import { Progress } from '@/components/ui/progress';
import { 
  RefreshCw, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  Activity,
  ChevronRight,
  Loader2,
  Download,
  Play,
  RotateCcw,
  AlertCircle,
  X
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';

interface Pipeline {
  id: string;
  status: string;
  mode: string;
  started_at: string;
  completed_at?: string;
  current_phase?: string;
  progress_percentage: number;
  phases_completed: number;
  total_phases: number;
  duration_seconds?: number;
  keywords_processed: number;
  serp_results_collected: number;
  companies_enriched: number;
  videos_enriched: number;
  content_analyzed: number;
  is_active: boolean;
}

interface PipelinePhase {
  phase_name: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  progress_percentage?: number;
  error_message?: string;
  eta_seconds?: number;
  metrics?: {
    items_processed: number;
    total_items: number;
    success_rate: number;
    errors_count: number;
    // Phase-specific metrics
    [key: string]: any;
  };
}

const PipelineMonitoring: React.FC = () => {
  const [activePipelines, setActivePipelines] = useState<Pipeline[]>([]);
  const [recentPipelines, setRecentPipelines] = useState<Pipeline[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState<string | null>(null);
  const [pipelinePhases, setPipelinePhases] = useState<PipelinePhase[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  
  // Restart dialog state
  const [restartDialog, setRestartDialog] = useState<{
    open: boolean;
    phaseName: string;
    phaseDisplayName: string;
  }>({
    open: false,
    phaseName: '',
    phaseDisplayName: ''
  });
  const [isRestarting, setIsRestarting] = useState(false);

  // Fetch pipelines
  const fetchPipelines = async () => {
    try {
      const response = await fetch('/api/v1/monitoring/pipelines');
      if (!response.ok) throw new Error('Failed to fetch pipelines');
      const data = await response.json();
      setActivePipelines(data.active_pipelines || []);
      setRecentPipelines(data.recent_pipelines || []);
    } catch (error) {
      console.error('Error fetching pipelines:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Fetch pipeline phases
  const fetchPipelinePhases = async (pipelineId: string) => {
    try {
      const response = await fetch(`/api/v1/monitoring/pipeline/${pipelineId}/phases`);
      if (!response.ok) throw new Error('Failed to fetch pipeline phases');
      const data = await response.json();
      setPipelinePhases(data.phases || []);
    } catch (error) {
      console.error('Error fetching pipeline phases:', error);
    }
  };

  // Auto-refresh for active pipelines
  useEffect(() => {
    fetchPipelines();
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchPipelines();
        if (selectedPipeline) {
          fetchPipelinePhases(selectedPipeline);
        }
      }, 15000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, selectedPipeline]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchPipelines();
    if (selectedPipeline) {
      fetchPipelinePhases(selectedPipeline);
    }
  };

  // Handle restart confirmation
  const handleRestartPhase = async (freshAnalysis: boolean) => {
    if (!selectedPipeline || !restartDialog.phaseName) return;
    
    setIsRestarting(true);
    try {
      const response = await fetch(`/api/v1/pipeline/${selectedPipeline}/restart_phase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          phase: restartDialog.phaseName,
          fresh_analysis: freshAnalysis
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to restart phase');
      }
      
      // Refresh data after restart
      await fetchPipelinePhases(selectedPipeline);
      await fetchPipelines();
      
    } catch (error) {
      console.error('Restart phase failed:', error);
      // You could add a toast notification here
    } finally {
      setIsRestarting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
      case 'processing':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'pending':
      case 'queued':
        return 'bg-yellow-500';
      case 'blocked':
        return 'bg-gray-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'failed':
        return <XCircle className="w-4 h-4" />;
      case 'running':
      case 'processing':
        return <Loader2 className="w-4 h-4 animate-spin" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    }
    return `${minutes}m ${Math.floor(seconds % 60)}s`;
  };

  const phaseDisplayNames: { [key: string]: string } = {
    keyword_metrics: 'Keyword Metrics',
    serp_collection: 'SERP Collection',
    company_enrichment_serp: 'Company Enrichment',
    youtube_enrichment: 'YouTube Metrics',
    content_scraping: 'Content Scraping',
    channel_company_resolver: 'Channel Resolution',
    content_analysis: 'Content Analysis',
    dsi_calculation: 'DSI Calculation'
  };

  const renderPhaseSpecificMetrics = (phase: PipelinePhase) => {
    const m = phase.metrics;
    if (!m) return null;

    switch (phase.phase_name) {
      case 'keyword_metrics':
        return (
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 mt-2 pt-2 border-t">
            {m.keywords && <div><span className="font-medium">{m.keywords}</span> keywords</div>}
            {m.countries && <div><span className="font-medium">{m.countries}</span> countries</div>}
          </div>
        );
        
      case 'serp_collection':
        return (
          <div className="space-y-2 mt-2 pt-2 border-t">
            <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
              {m.keywords && <div><span className="font-medium">{m.keywords}</span> keywords</div>}
              {m.regions && <div><span className="font-medium">{m.regions}</span> regions</div>}
              {m.content_types && <div><span className="font-medium">{m.content_types}</span> types</div>}
            </div>
            {m.batch_status && Object.keys(m.batch_status).length > 0 && (
              <div className="text-xs">
                <div className="font-medium text-gray-600 mb-1">Batch Status:</div>
                <div className="space-y-1">
                  {Object.entries(m.batch_status).map(([type, status]: [string, any]) => (
                    <div key={type} className="flex items-center gap-2">
                      <span className="text-gray-500">{type}:</span>
                      {status.completed && <Badge variant="success" className="text-xs">{status.completed} done</Badge>}
                      {status.running && <Badge variant="default" className="text-xs">{status.running} running</Badge>}
                      {status.failed && <Badge variant="destructive" className="text-xs">{status.failed} failed</Badge>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
        
      case 'company_enrichment_serp':
        return (
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 mt-2 pt-2 border-t">
            {m.enriched_domains && <div><span className="font-medium">{m.enriched_domains}</span> enriched</div>}
            {m.unique_domains && <div><span className="font-medium">{m.unique_domains}</span> unique domains</div>}
          </div>
        );
        
      case 'youtube_enrichment':
        return (
          <div className="space-y-2 mt-2 pt-2 border-t">
            <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
              {m.videos_found && <div><span className="font-medium">{m.videos_found}</span> videos found</div>}
              {m.videos_enriched && <div><span className="font-medium">{m.videos_enriched}</span> enriched</div>}
              {m.unique_channels && <div><span className="font-medium">{m.unique_channels}</span> channels</div>}
            </div>
            {(m.avg_views > 0 || m.avg_engagement > 0) && (
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                {m.avg_views > 0 && <div><span className="font-medium">{m.avg_views.toLocaleString()}</span> avg views</div>}
                {m.avg_engagement > 0 && <div><span className="font-medium">{m.avg_engagement}%</span> avg engagement</div>}
              </div>
            )}
            {m.circuit_breaker === 'quota_exceeded' && (
              <Badge variant="destructive" className="text-xs">YouTube API Quota Exceeded</Badge>
            )}
          </div>
        );
        
      case 'content_scraping':
        return (
          <div className="space-y-2 mt-2 pt-2 border-t">
            <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
              {m.pages_scraped !== undefined && <div><span className="font-medium">{m.pages_scraped}</span> scraped</div>}
              {m.pages_failed !== undefined && <div><span className="font-medium text-red-600">{m.pages_failed}</span> failed</div>}
              {m.pages_pending !== undefined && <div><span className="font-medium text-yellow-600">{m.pages_pending}</span> pending</div>}
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              {m.unique_domains && <div><span className="font-medium">{m.unique_domains}</span> domains</div>}
              {m.avg_word_count && <div><span className="font-medium">{m.avg_word_count}</span> avg words</div>}
            </div>
            {m.scraping_rate && phase.status === 'running' && (
              <div className="text-xs text-gray-500">
                Rate: <span className="font-medium">{m.scraping_rate}</span> pages/sec
              </div>
            )}
          </div>
        );
        
      case 'channel_company_resolver':
        return (
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 mt-2 pt-2 border-t">
            {m.channels_resolved && <div><span className="font-medium">{m.channels_resolved}</span> resolved</div>}
            {m.unique_channels && <div><span className="font-medium">{m.unique_channels}</span> total channels</div>}
          </div>
        );
        
      case 'content_analysis':
        return (
          <div className="space-y-2 mt-2 pt-2 border-t">
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              {m.pending !== undefined && <div><span className="font-medium">{m.pending}</span> pending</div>}
              {m.highly_relevant && <div><span className="font-medium">{m.highly_relevant}</span> highly relevant</div>}
            </div>
            {(m.solution_focused || m.problem_focused) && (
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                {m.solution_focused && <div><span className="font-medium">{m.solution_focused}</span> solution phase</div>}
                {m.problem_focused && <div><span className="font-medium">{m.problem_focused}</span> problem phase</div>}
              </div>
            )}
            {(m.avg_relevance || m.avg_trust) && (
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                {m.avg_relevance && <div>Relevance: <span className="font-medium">{m.avg_relevance}</span></div>}
                {m.avg_trust && <div>Trust: <span className="font-medium">{m.avg_trust}</span></div>}
              </div>
            )}
            {m.analysis_rate && phase.status === 'running' && (
              <div className="text-xs text-gray-500">
                Rate: <span className="font-medium">{m.analysis_rate}</span> pages/sec
              </div>
            )}
          </div>
        );
        
      default:
        return null;
    }
  };

  // Hide deprecated phase "company_enrichment_youtube" from Pipeline Details
  const filteredPipelinePhases = pipelinePhases.filter(
    (p) => p.phase_name !== 'company_enrichment_youtube'
  );

  if (loading) {
    return (
      <AdminLayout
        title="Pipeline Monitoring"
        description="Real-time pipeline execution tracking"
      >
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout
      title="Pipeline Monitoring"
      description="Real-time pipeline execution tracking"
    >
      <div className="space-y-6">
        {/* Header Controls */}
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Badge variant={activePipelines.length > 0 ? "default" : "secondary"}>
              {activePipelines.length} Active Pipeline{activePipelines.length !== 1 ? 's' : ''}
            </Badge>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh
            </label>
          </div>
          <Button 
            onClick={handleRefresh} 
            variant="outline" 
            size="sm"
            disabled={refreshing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Active Pipelines */}
        {activePipelines.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-blue-500" />
                Active Pipelines
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {activePipelines.map((pipeline) => (
                <div
                  key={pipeline.id}
                  className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => {
                    setSelectedPipeline(pipeline.id);
                    fetchPipelinePhases(pipeline.id);
                    // Also refresh the main pipeline list to get latest stats
                    fetchPipelines();
                  }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium">Pipeline #{pipeline.id.slice(0, 8)}</h3>
                      <Badge variant="outline" className="text-xs">
                        {pipeline.mode}
                      </Badge>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">
                        Started {formatDistanceToNow(new Date(pipeline.started_at))} ago
                      </span>
                      <span className="font-medium">
                        {pipeline.current_phase ? phaseDisplayNames[pipeline.current_phase] || pipeline.current_phase : 'Initializing'}
                      </span>
                    </div>
                    
                    <Progress value={pipeline.progress_percentage} className="h-2" />
                    
                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span>{pipeline.phases_completed}/{pipeline.total_phases} phases</span>
                      <span>~{formatDuration(pipeline.duration_seconds)} elapsed</span>
                    </div>

                    <div className="grid grid-cols-5 gap-2 mt-3 text-xs">
                      <div className="text-center">
                        <div className="font-semibold">{pipeline.keywords_processed.toLocaleString()}</div>
                        <div className="text-gray-500">Keywords</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{pipeline.serp_results_collected.toLocaleString()}</div>
                        <div className="text-gray-500">SERPs</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{pipeline.companies_enriched.toLocaleString()}</div>
                        <div className="text-gray-500">Companies</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{pipeline.videos_enriched.toLocaleString()}</div>
                        <div className="text-gray-500">Videos</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold">{pipeline.content_analyzed.toLocaleString()}</div>
                        <div className="text-gray-500">Analyzed</div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Recent Pipelines */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Pipelines</CardTitle>
          </CardHeader>
          <CardContent>
            {recentPipelines.length === 0 && activePipelines.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No pipelines found</p>
            ) : (
              <div className="space-y-2">
                {recentPipelines.slice(0, 10).map((pipeline) => (
                  <div
                    key={pipeline.id}
                    className="flex items-center justify-between py-2 px-3 hover:bg-gray-50 rounded cursor-pointer"
                    onClick={() => {
                      setSelectedPipeline(pipeline.id);
                      fetchPipelinePhases(pipeline.id);
                      // Also refresh the main pipeline list to get latest stats
                      fetchPipelines();
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${getStatusColor(pipeline.status)}`} />
                      <span className="font-medium">#{pipeline.id.slice(0, 8)}</span>
                      <Badge 
                        variant={pipeline.status === 'completed' ? 'success' : 'destructive'}
                        className="text-xs"
                      >
                        {pipeline.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span>{formatDuration(pipeline.duration_seconds)}</span>
                      <span>{formatDistanceToNow(new Date(pipeline.started_at))} ago</span>
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Phase Details Modal/Drawer */}
        {selectedPipeline && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Pipeline Details - #{selectedPipeline.slice(0, 8)}</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    title="Export to Excel"
                    onClick={() => {
                      const url = `/api/v1/export/digital-landscape/${selectedPipeline}`;
                      window.open(url, '_blank');
                    }}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="destructive"
                    size="icon"
                    className="h-8 w-8"
                    title="Mark as Failed"
                    onClick={async () => {
                      try {
                        await fetch(`/api/v1/pipeline/${selectedPipeline}/fail`, {
                          method: 'POST'
                        });
                        // Refresh lists and phases after marking failed
                        await fetchPipelines();
                        await fetchPipelinePhases(selectedPipeline);
                      } catch (e) {
                        console.error('Failed to mark pipeline failed', e);
                      }
                    }}
                  >
                    <AlertCircle className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    title="Close"
                    onClick={() => {
                      setSelectedPipeline(null);
                      setPipelinePhases([]);
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {filteredPipelinePhases.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p>No phase information available for this pipeline.</p>
                  <p className="text-sm mt-2">This pipeline may have failed during initialization.</p>
                </div>
              ) : (
              <div className="space-y-4">
                {/* Overall Pipeline Summary */}
                {(() => {
                  const pipeline = [...activePipelines, ...recentPipelines].find(p => p.id === selectedPipeline);
                  if (!pipeline) return null;
                  
                  const completedPhases = filteredPipelinePhases.filter(p => p.status === 'completed').length;
                  const runningPhases = filteredPipelinePhases.filter(p => p.status === 'running').length;
                  const failedPhases = filteredPipelinePhases.filter(p => p.status === 'failed').length;
                  
                  return (
                    <div className="bg-gray-50 rounded-lg p-4 mb-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <div className="text-gray-500">Status</div>
                          <div className="font-medium flex items-center gap-2 mt-1">
                            <div className={`w-2 h-2 rounded-full ${getStatusColor(pipeline.status)}`} />
                            {pipeline.status}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-500">Progress</div>
                          <div className="font-medium mt-1">
                            {completedPhases}/{filteredPipelinePhases.length} phases
                            {runningPhases > 0 && <span className="text-blue-600 ml-1">({runningPhases} running)</span>}
                            {failedPhases > 0 && <span className="text-red-600 ml-1">({failedPhases} failed)</span>}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-500">Duration</div>
                          <div className="font-medium mt-1">{formatDuration(pipeline.duration_seconds)}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Started</div>
                          <div className="font-medium mt-1">{formatDistanceToNow(new Date(pipeline.started_at))} ago</div>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-5 gap-4 mt-4 pt-4 border-t text-center">
                        <div>
                          <div className="text-2xl font-bold text-gray-900">{pipeline.keywords_processed.toLocaleString()}</div>
                          <div className="text-xs text-gray-500">Keywords</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-gray-900">{pipeline.serp_results_collected.toLocaleString()}</div>
                          <div className="text-xs text-gray-500">SERP Results</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-gray-900">{pipeline.companies_enriched.toLocaleString()}</div>
                          <div className="text-xs text-gray-500">Companies</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-gray-900">{pipeline.videos_enriched.toLocaleString()}</div>
                          <div className="text-xs text-gray-500">Videos</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-gray-900">{pipeline.content_analyzed.toLocaleString()}</div>
                          <div className="text-xs text-gray-500">Pages Analyzed</div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
                {filteredPipelinePhases.map((phase, index) => (
                  <div key={phase.phase_name} className="border-l-4 border-gray-200 pl-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white ${getStatusColor(phase.status)}`}>
                          {getStatusIcon(phase.status)}
                        </div>
                        <div>
                          <h4 className="font-medium">
                            {phaseDisplayNames[phase.phase_name] || phase.phase_name}
                          </h4>
                          {phase.error_message && (
                            <p className="text-sm text-red-600 mt-1">{phase.error_message}</p>
                          )}
                        </div>
                      </div>
                      <div className="text-right text-sm">
                        {phase.duration_seconds && (
                          <div className="text-gray-600">
                            {formatDuration(phase.duration_seconds)}
                          </div>
                        )}
                        {typeof phase.eta_seconds === 'number' && phase.status === 'running' && (
                          <div className="text-gray-500 mt-1">
                            ETA: {formatDuration(phase.eta_seconds)}
                          </div>
                        )}
                        <div className="mt-2 flex items-center gap-2 justify-end">
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            title="Continue phase"
                            onClick={async () => {
                              if (!selectedPipeline) return;
                              try {
                                await fetch(`/api/v1/pipeline/${selectedPipeline}/continue_phase`, {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ phase: phase.phase_name })
                                });
                                await fetchPipelinePhases(selectedPipeline);
                              } catch (e) {
                                console.error('Continue phase failed', e);
                              }
                            }}
                          >
                            <Play className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="secondary"
                            size="icon"
                            className="h-7 w-7"
                            title="Restart phase"
                            onClick={() => {
                              setRestartDialog({
                                open: true,
                                phaseName: phase.phase_name,
                                phaseDisplayName: phaseDisplayNames[phase.phase_name] || phase.phase_name
                              });
                            }}
                          >
                            <RotateCcw className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                    
                    {phase.metrics && (
                      <div className="mt-3 space-y-2">
                        {/* Progress bar for running phases */}
                        {phase.progress_percentage !== null && phase.status === 'running' && (
                          <div className="w-full">
                            <Progress value={phase.progress_percentage} className="h-2" />
                          </div>
                        )}
                        
                        {/* Basic metrics */}
                        <div className="grid grid-cols-4 gap-4 text-xs text-gray-600">
                          <div>
                            <span className="font-medium">{phase.metrics.items_processed}</span>
                            <span className="text-gray-400">/{phase.metrics.total_items} processed</span>
                          </div>
                          <div>
                            <span className="font-medium">{phase.metrics.success_rate}%</span>
                            <span className="text-gray-400"> success</span>
                          </div>
                          {phase.metrics.errors_count > 0 && (
                            <div className="text-red-600">
                              <span className="font-medium">{phase.metrics.errors_count}</span>
                              <span className="text-gray-400"> errors</span>
                            </div>
                          )}
                        </div>
                        
                        {/* Phase-specific detailed metrics */}
                        {renderPhaseSpecificMetrics(phase)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Pipeline Logs */}
        {selectedPipeline && (
          <div className="mt-4">
            <PipelineLogs pipelineId={selectedPipeline} />
          </div>
        )}
      </div>

      {/* Restart Phase Dialog */}
      <RestartPhaseDialog
        open={restartDialog.open}
        onOpenChange={(open) => setRestartDialog(prev => ({ ...prev, open }))}
        phaseName={restartDialog.phaseName}
        phaseDisplayName={restartDialog.phaseDisplayName}
        pipelineId={selectedPipeline || ''}
        onRestart={handleRestartPhase}
        isRestarting={isRestarting}
      />
    </AdminLayout>
  );
};

export default PipelineMonitoring;
