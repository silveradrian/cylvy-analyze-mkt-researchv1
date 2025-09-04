'use client';

import React, { useState, useEffect } from 'react';
import { PlayCircle, Clock, CheckCircle, XCircle, AlertCircle, Pause } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';

import { AdminLayout } from '@/components/layout/AdminLayout';

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
  const [wsConnected, setWsConnected] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Check authentication and load data
  useEffect(() => {
    checkAuthAndLoadData();
  }, []);

  const checkAuthAndLoadData = async () => {
    setIsCheckingAuth(true);
    
    // Check if user has access token
    let token = localStorage.getItem('access_token');
    
    if (!token) {
      // Attempt auto-login
      try {
        console.log('🔐 Attempting auto-login for pipeline page...');
        const loginResponse = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email: 'admin@cylvy.com',
            password: 'admin123'
          })
        });
        
        if (loginResponse.ok) {
          const loginData = await loginResponse.json();
          token = loginData.access_token;
          localStorage.setItem('access_token', token);
          console.log('✅ Auto-login successful for pipeline page');
          setIsAuthenticated(true);
        } else {
          const errorText = await loginResponse.text();
          console.log('❌ Auto-login failed:', loginResponse.status, errorText);
          setIsAuthenticated(false);
          setError('Authentication failed - please login');
          setIsCheckingAuth(false);
          return;
        }
      } catch (error) {
        console.log('❌ Auto-login error:', error);
        setIsAuthenticated(false);
        setError('Authentication failed - please login');
        setIsCheckingAuth(false);
        return;
      }
    } else {
      setIsAuthenticated(true);
    }
    
    setIsCheckingAuth(false);
    
    // Now load data with valid token
    await loadRecentPipelines();
    initWebSocket();
  };

  const initWebSocket = () => {
    try {
      // Connect to backend WebSocket
      const ws = new WebSocket('ws://localhost:8001/ws/pipeline');
      
      ws.onopen = () => {
        console.log('✅ Pipeline WebSocket connected');
        setWsConnected(true);
      };
      
      ws.onclose = () => {
        console.log('❌ Pipeline WebSocket disconnected');
        setWsConnected(false);
        setTimeout(() => initWebSocket(), 5000);
      };
      
      ws.onerror = (error) => {
        console.log('❌ WebSocket error:', error);
        setWsConnected(false);
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handlePipelineUpdate(message);
      };
      
    } catch (error) {
      console.log('❌ WebSocket initialization failed:', error);
      setWsConnected(false);
    }
  };

  const loadRecentPipelines = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/recent?limit=10', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setRecentPipelines(data.pipelines || []);
        
        const active = (data.pipelines || []).filter(
          (p: any) => ['pending', 'running'].includes(p.status)
        );
        setActivePipelines(active);
        console.log('✅ Loaded pipelines:', data.pipelines?.length || 0);
      } else {
        const errorText = await response.text();
        setError(`Failed to load pipelines (${response.status})`);
        console.log('❌ Pipeline API error:', response.status, errorText);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load pipelines';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handlePipelineUpdate = (message: any) => {
    if (message.type === 'pipeline_update') {
      const pipelineId = message.pipeline_id;
      
      setActivePipelines(prev => {
        const updated = prev.map(p => 
          p.pipeline_id === pipelineId 
            ? { ...p, current_phase: message.data?.phase, ...message.data }
            : p
        );
        
        return updated.filter(p => ['pending', 'running'].includes(p.status));
      });
      
      if (['completed', 'failed', 'cancelled'].includes(message.data?.status)) {
        loadRecentPipelines();
      }
    }
  };

  const startSimplePipeline = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/start', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          collect_serp: true,
          enrich_companies: true,
          scrape_content: false,
          analyze_content: false
        })
      });
      
      if (response.ok) {
        console.log('✅ Pipeline started successfully');
        loadRecentPipelines();
      } else {
        const errorText = await response.text();
        setError(`Failed to start pipeline: ${response.status}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'running': return <PlayCircle className="h-4 w-4 text-blue-500" />;
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed': return <XCircle className="h-4 w-4 text-red-500" />;
      case 'cancelled': return <Pause className="h-4 w-4 text-gray-500" />;
      default: return <AlertCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'running': return 'bg-blue-100 text-blue-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'cancelled': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  const calculateProgress = (pipeline: PipelineStatus) => {
    const totalPhases = 7;
    const completedCount = pipeline.phases_completed?.length || 0;
    return Math.round((completedCount / totalPhases) * 100);
  };

  if (isCheckingAuth) {
    return (
      <AdminLayout title="Pipeline Management" description="Monitor and control competitive intelligence analysis">
        <Card className="cylvy-card">
          <CardContent className="text-center py-8">
            <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Authenticating...</p>
          </CardContent>
        </Card>
      </AdminLayout>
    );
  }

  if (!isAuthenticated) {
    return (
      <AdminLayout title="Pipeline Management" description="Monitor and control competitive intelligence analysis">
        <Card className="cylvy-card">
          <CardContent className="text-center py-8">
            <div className="text-red-500 mb-4">Authentication Required</div>
            <p className="text-gray-600">Please refresh the page to login</p>
            <Button 
              onClick={() => window.location.reload()} 
              className="cylvy-btn-primary mt-4"
            >
              Refresh Page
            </Button>
          </CardContent>
        </Card>
      </AdminLayout>
    );
  }

  if (loading) {
    return (
      <AdminLayout title="Pipeline Management" description="Monitor and control digital landscape analysis">
        <Card className="cylvy-card">
          <CardContent className="text-center py-8">
            <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Loading pipeline data...</p>
          </CardContent>
        </Card>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Pipeline Management" description="Monitor and control competitive intelligence analysis">
      <div className="space-y-6">
        {/* Quick Actions */}
        <div className="flex gap-4 items-center justify-between">
          <div className="flex gap-4">
            <Button onClick={startSimplePipeline} className="cylvy-btn-primary">
              <PlayCircle className="mr-2 h-4 w-4" />
              Start Analysis Pipeline
            </Button>
            <Button onClick={loadRecentPipelines} variant="outline">
              🔄 Refresh Data
            </Button>
          </div>
          
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-gray-600">
              {wsConnected ? 'Live Updates' : 'Reconnecting...'}
            </span>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">
              {error}
              <Button
                variant="ghost"
                size="sm"
                className="ml-2 text-red-600 hover:text-red-800"
                onClick={() => setError(null)}
              >
                Dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue="active" className="space-y-6 bg-transparent">
          <TabsList className="grid w-full grid-cols-2 bg-white/90">
            <TabsTrigger 
              value="active" 
              className="data-[state=active]:bg-cylvy-amaranth data-[state=active]:text-white"
            >
              Active Pipelines ({activePipelines.length})
            </TabsTrigger>
            <TabsTrigger 
              value="history" 
              className="data-[state=active]:bg-cylvy-amaranth data-[state=active]:text-white"
            >
              Pipeline History
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active" className="space-y-4 bg-transparent">
            {activePipelines.length === 0 ? (
              <Card className="cylvy-card bg-white">
                <CardContent className="text-center py-12 bg-white">
                  <PlayCircle className="mx-auto h-16 w-16 text-gray-400 mb-6" />
                  <h3 className="text-xl font-bold mb-2 text-cylvy-midnight">No Active Pipelines</h3>
                  <p className="text-gray-600 mb-6 max-w-md mx-auto">
                    Start your first competitive intelligence analysis to begin collecting 
                    data from your configured competitors.
                  </p>
                  <Button onClick={startSimplePipeline} className="cylvy-btn-primary">
                    🚀 Start Analysis Pipeline
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6">
                {activePipelines.map((pipeline) => (
                  <Card key={pipeline.pipeline_id} className="cylvy-card-hover">
                    <CardHeader className="pb-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {getStatusIcon(pipeline.status)}
                          <div>
                            <CardTitle className="text-xl text-cylvy-midnight">
                              Finastra Analysis #{pipeline.pipeline_id.slice(0, 8)}
                            </CardTitle>
                            <CardDescription>
                              Started {new Date(pipeline.started_at).toLocaleString()} • {pipeline.mode}
                            </CardDescription>
                          </div>
                        </div>
                        <Badge className={`px-3 py-1 ${getStatusBadgeClass(pipeline.status)}`}>
                          {pipeline.status.toUpperCase()}
                        </Badge>
                      </div>
                    </CardHeader>
                    
                    <CardContent className="space-y-6">
                      {/* Progress */}
                      <div>
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm font-medium text-gray-700">
                            {pipeline.current_phase ? 
                              `Current: ${pipeline.current_phase.replace(/_/g, ' ').toUpperCase()}` : 
                              'Pipeline Progress'}
                          </span>
                          <span className="text-sm font-bold text-cylvy-amaranth">
                            {calculateProgress(pipeline)}%
                          </span>
                        </div>
                        <Progress value={calculateProgress(pipeline)} className="h-3 bg-gray-200" />
                      </div>

                      {/* Statistics */}
                      <div className="grid grid-cols-5 gap-4 text-center">
                        <div className="bg-blue-50 p-3 rounded-lg">
                          <div className="text-2xl font-bold text-blue-600">{pipeline.keywords_processed}</div>
                          <div className="text-xs text-blue-700 font-medium">Keywords</div>
                        </div>
                        <div className="bg-green-50 p-3 rounded-lg">
                          <div className="text-2xl font-bold text-green-600">{pipeline.serp_results_collected}</div>
                          <div className="text-xs text-green-700 font-medium">SERP Results</div>
                        </div>
                        <div className="bg-purple-50 p-3 rounded-lg">
                          <div className="text-2xl font-bold text-purple-600">{pipeline.companies_enriched}</div>
                          <div className="text-xs text-purple-700 font-medium">Companies</div>
                        </div>
                        <div className="bg-orange-50 p-3 rounded-lg">
                          <div className="text-2xl font-bold text-orange-600">{pipeline.videos_enriched}</div>
                          <div className="text-xs text-orange-700 font-medium">Videos</div>
                        </div>
                        <div className="bg-red-50 p-3 rounded-lg">
                          <div className="text-2xl font-bold text-red-600">{pipeline.content_analyzed}</div>
                          <div className="text-xs text-red-700 font-medium">Content</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="history" className="space-y-4 bg-transparent">
            <Card className="cylvy-card bg-white shadow-sm">
              <CardHeader className="bg-white">
                <CardTitle className="text-cylvy-midnight">Pipeline History</CardTitle>
                <CardDescription>
                  Recent competitive intelligence analysis runs
                </CardDescription>
              </CardHeader>
              <CardContent className="bg-white">
                {recentPipelines.length === 0 ? (
                  <div className="text-center py-8">
                    <Clock className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                    <h3 className="text-lg font-medium mb-2">No Pipeline History</h3>
                    <p className="text-gray-600">
                      Pipeline execution history will appear here once you start running analyses
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {recentPipelines.slice(0, 10).map((pipeline: any, index) => (
                      <div key={index} className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50">
                        <div className="flex items-center gap-3">
                          {getStatusIcon(pipeline.status)}
                          <div>
                            <div className="font-medium">Pipeline #{(pipeline.id || index).toString().slice(0, 8)}</div>
                            <div className="text-sm text-gray-600">
                              {pipeline.created_at ? new Date(pipeline.created_at).toLocaleString() : 'Recent'}
                            </div>
                          </div>
                        </div>
                        <Badge className={getStatusBadgeClass(pipeline.status)}>
                          {pipeline.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AdminLayout>
  );
}