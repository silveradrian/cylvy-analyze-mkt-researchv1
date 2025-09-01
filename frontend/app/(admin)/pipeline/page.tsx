'use client';

import { useState, useEffect } from 'react';
import { PlayCircle, Pause, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';

import { StartPipelineDialog } from '@/components/pipeline/StartPipelineDialog';
import { PipelineHistoryTable } from '@/components/pipeline/PipelineHistoryTable';
import { PipelineSchedules } from '@/components/pipeline/PipelineSchedules';
import { RealtimePipelineStatus } from '@/components/pipeline/RealtimePipelineStatus';
import { useWebSocket } from '@/hooks/useWebSocket';
import { pipelineAPI } from '@/app/services/api';

interface PipelineStatus {
  pipeline_id: string;
  status: string;
  mode: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  current_phase?: string;
  phases_completed: string[];
  phases_remaining: string[];
  keywords_processed: number;
  serp_results_collected: number;
  companies_enriched: number;
  videos_enriched: number;
  content_analyzed: number;
  errors: string[];
  warnings: string[];
}

export default function PipelineManagementPage() {
  const [activePipelines, setActivePipelines] = useState<PipelineStatus[]>([]);
  const [recentPipelines, setRecentPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showStartDialog, setShowStartDialog] = useState(false);

  // WebSocket connection for real-time updates
  const { isConnected, lastMessage } = useWebSocket('/ws/pipeline');

  // Load initial data
  useEffect(() => {
    loadRecentPipelines();
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      handlePipelineUpdate(lastMessage);
    }
  }, [lastMessage]);

  const loadRecentPipelines = async () => {
    try {
      setLoading(true);
      const response = await pipelineAPI.getRecentPipelines();
      setRecentPipelines(response.pipelines);
      
      // Filter active pipelines
      const active = response.pipelines.filter(
        (p: any) => ['pending', 'running'].includes(p.status)
      );
      setActivePipelines(active);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pipelines');
    } finally {
      setLoading(false);
    }
  };

  const handlePipelineUpdate = (message: any) => {
    if (message.type === 'pipeline_update') {
      const pipelineId = message.pipeline_id;
      
      // Update active pipelines
      setActivePipelines(prev => {
        const updated = prev.map(p => 
          p.pipeline_id === pipelineId 
            ? { ...p, current_phase: message.data?.phase, ...message.data }
            : p
        );
        
        // Remove completed/failed pipelines from active list
        return updated.filter(p => ['pending', 'running'].includes(p.status));
      });
      
      // Refresh recent pipelines if a pipeline completes
      if (['completed', 'failed', 'cancelled'].includes(message.data?.status)) {
        loadRecentPipelines();
      }
    }
  };

  const startPipeline = async (config: any) => {
    try {
      const response = await pipelineAPI.startPipeline(config);
      setShowStartDialog(false);
      
      // Add to active pipelines
      const newPipeline = {
        pipeline_id: response.pipeline_id,
        status: 'pending',
        mode: config.mode || 'manual',
        started_at: new Date().toISOString(),
        current_phase: null,
        phases_completed: [],
        phases_remaining: [],
        keywords_processed: 0,
        serp_results_collected: 0,
        companies_enriched: 0,
        videos_enriched: 0,
        content_analyzed: 0,
        errors: [],
        warnings: []
      };
      
      setActivePipelines(prev => [...prev, newPipeline]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline');
    }
  };

  const cancelPipeline = async (pipelineId: string) => {
    try {
      await pipelineAPI.cancelPipeline(pipelineId);
      // Status will be updated via WebSocket
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel pipeline');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'running':
        return <PlayCircle className="h-4 w-4 text-blue-500" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'cancelled':
        return <Pause className="h-4 w-4 text-gray-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-600';
    }
  };

  const calculateProgress = (pipeline: PipelineStatus) => {
    const totalPhases = 7; // SERP, Company, Video, Scraping, Analysis, DSI, Historical
    const completedCount = pipeline.phases_completed?.length || 0;
    return Math.round((completedCount / totalPhases) * 100);
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center">Loading pipeline data...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Pipeline Management</h1>
          <p className="text-gray-600 mt-1">
            Monitor and control digital landscape analysis pipelines
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <Button onClick={() => setShowStartDialog(true)}>
            <PlayCircle className="mr-2 h-4 w-4" />
            Start Pipeline
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => setError(null)}
          >
            Dismiss
          </Button>
        </Alert>
      )}

      <Tabs defaultValue="active" className="space-y-4">
        <TabsList>
          <TabsTrigger value="active">
            Active Pipelines ({activePipelines.length})
          </TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="schedules">Schedules</TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="space-y-4">
          {activePipelines.length === 0 ? (
            <Card>
              <CardContent className="text-center py-8">
                <PlayCircle className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <h3 className="text-lg font-medium mb-2">No Active Pipelines</h3>
                <p className="text-gray-600 mb-4">
                  Start a new pipeline to begin collecting and analyzing data
                </p>
                <Button onClick={() => setShowStartDialog(true)}>
                  Start First Pipeline
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {activePipelines.map((pipeline) => (
                <Card key={pipeline.pipeline_id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(pipeline.status)}
                        <div>
                          <CardTitle className="text-lg">
                            Pipeline {pipeline.pipeline_id.slice(0, 8)}
                          </CardTitle>
                          <CardDescription>
                            Started {new Date(pipeline.started_at).toLocaleString()} • {pipeline.mode}
                          </CardDescription>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={getStatusColor(pipeline.status)}>
                          {pipeline.status}
                        </Badge>
                        {pipeline.status === 'running' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => cancelPipeline(pipeline.pipeline_id)}
                          >
                            Cancel
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  
                  <CardContent>
                    <div className="space-y-4">
                      {/* Progress */}
                      <div>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm font-medium">
                            {pipeline.current_phase ? `Current: ${pipeline.current_phase}` : 'Progress'}
                          </span>
                          <span className="text-sm text-gray-600">
                            {calculateProgress(pipeline)}%
                          </span>
                        </div>
                        <Progress value={calculateProgress(pipeline)} className="h-2" />
                      </div>

                      {/* Phases */}
                      <div className="grid grid-cols-4 gap-2 text-xs">
                        {[
                          'SERP Collection',
                          'Company Enrichment', 
                          'Video Enrichment',
                          'Content Scraping',
                          'Content Analysis',
                          'DSI Calculation',
                          'Historical Snapshot'
                        ].map((phase, index) => {
                          const phaseKey = phase.toLowerCase().replace(/\s+/g, '_');
                          const isCompleted = pipeline.phases_completed?.includes(phaseKey);
                          const isCurrent = pipeline.current_phase === phaseKey;
                          
                          return (
                            <div
                              key={phase}
                              className={`p-2 rounded text-center ${
                                isCompleted 
                                  ? 'bg-green-100 text-green-800'
                                  : isCurrent
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-gray-100 text-gray-600'
                              }`}
                            >
                              {phase}
                            </div>
                          );
                        })}
                      </div>

                      {/* Statistics */}
                      <div className="grid grid-cols-5 gap-4 text-center">
                        <div>
                          <div className="text-2xl font-bold text-blue-600">
                            {pipeline.keywords_processed}
                          </div>
                          <div className="text-xs text-gray-600">Keywords</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-green-600">
                            {pipeline.serp_results_collected}
                          </div>
                          <div className="text-xs text-gray-600">SERP Results</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-purple-600">
                            {pipeline.companies_enriched}
                          </div>
                          <div className="text-xs text-gray-600">Companies</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-orange-600">
                            {pipeline.videos_enriched}
                          </div>
                          <div className="text-xs text-gray-600">Videos</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-red-600">
                            {pipeline.content_analyzed}
                          </div>
                          <div className="text-xs text-gray-600">Content</div>
                        </div>
                      </div>

                      {/* Errors/Warnings */}
                      {(pipeline.errors?.length > 0 || pipeline.warnings?.length > 0) && (
                        <div className="space-y-2">
                          {pipeline.errors?.length > 0 && (
                            <Alert variant="destructive">
                              <AlertCircle className="h-4 w-4" />
                              <AlertDescription>
                                {pipeline.errors.length} error(s): {pipeline.errors[0]}
                                {pipeline.errors.length > 1 && ` (and ${pipeline.errors.length - 1} more)`}
                              </AlertDescription>
                            </Alert>
                          )}
                          {pipeline.warnings?.length > 0 && (
                            <Alert>
                              <AlertCircle className="h-4 w-4" />
                              <AlertDescription>
                                {pipeline.warnings.length} warning(s): {pipeline.warnings[0]}
                                {pipeline.warnings.length > 1 && ` (and ${pipeline.warnings.length - 1} more)`}
                              </AlertDescription>
                            </Alert>
                          )}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="history">
          <PipelineHistoryTable pipelines={recentPipelines} />
        </TabsContent>

        <TabsContent value="schedules">
          <PipelineSchedules />
        </TabsContent>
      </Tabs>

      {/* Start Pipeline Dialog */}
      {showStartDialog && (
        <StartPipelineDialog
          open={showStartDialog}
          onClose={() => setShowStartDialog(false)}
          onStart={startPipeline}
        />
      )}
    </div>
  );
}
