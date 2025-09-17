'use client';

import { useState, useEffect } from 'react';
import { X, Play, Database, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface StartPipelineDialogProps {
  open: boolean;
  onClose: () => void;
  onStart: (config: any) => Promise<void>;
}

interface RecentPipeline {
  pipeline_id: string;
  status: string;
  started_at: string;
  serp_results_collected: number;
  runtime_minutes: number;
}

export function StartPipelineDialog({ open, onClose, onStart }: StartPipelineDialogProps) {
  const [config, setConfig] = useState({
    keywords: null as string[] | null,  // Will be removed from UI but kept for backend compatibility
    regions: null as string[] | null,    // Will use main configuration from backend
    content_types: ['organic', 'news', 'video'],
    
    // Concurrency settings - hardcoded defaults
    max_concurrent_serp: 10,
    max_concurrent_enrichment: 15,
    max_concurrent_analysis: 20,
    
    // Feature flags
    enable_company_enrichment: true,
    enable_video_enrichment: true,
    enable_content_analysis: true,
    enable_historical_tracking: true,
    force_refresh: false,
    
    // SERP reuse option
    reuse_serp_enabled: false,
    reuse_serp_from_pipeline_id: null as string | null,
    
    // Mode
    mode: 'manual'
  });
  const [isStarting, setIsStarting] = useState(false);
  const [recentPipelines, setRecentPipelines] = useState<RecentPipeline[]>([]);
  const [loadingPipelines, setLoadingPipelines] = useState(false);

  // Load recent successful pipelines when dialog opens
  useEffect(() => {
    if (open) {
      loadRecentPipelines();
    }
  }, [open]);

  const loadRecentPipelines = async () => {
    try {
      setLoadingPipelines(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/recent?limit=10', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        // Filter for successful pipelines with SERP results
        const successfulPipelines = (data.pipelines || [])
          .filter((p: any) => p.status === 'completed' && p.serp_results_collected > 0)
          .map((p: any) => ({
            pipeline_id: p.pipeline_id,
            status: p.status,
            started_at: p.started_at,
            serp_results_collected: p.serp_results_collected || 0,
            runtime_minutes: p.runtime_minutes || 0
          }))
          .slice(0, 5); // Only show last 5 successful pipelines
        
        setRecentPipelines(successfulPipelines);
      }
    } catch (err) {
      console.error('Failed to load recent pipelines:', err);
    } finally {
      setLoadingPipelines(false);
    }
  };


  const contentTypes = [
    { id: 'organic', name: 'Organic Results', description: 'Regular search results' },
    { id: 'news', name: 'News Results', description: 'News articles and updates' },
    { id: 'video', name: 'Video Results', description: 'YouTube and video content' }
  ];


  const handleContentTypeChange = (contentType: string, checked: boolean) => {
    setConfig(prev => ({
      ...prev,
      content_types: checked
        ? [...prev.content_types, contentType]
        : prev.content_types.filter(ct => ct !== contentType)
    }));
  };


  const handleStart = async () => {
    setIsStarting(true);
    try {
      // Prepare config for submission
      const submitConfig = { ...config };
      
      // Add SERP reuse parameter if enabled
      if (config.reuse_serp_enabled && config.reuse_serp_from_pipeline_id) {
        submitConfig.reuse_serp_from_pipeline_id = config.reuse_serp_from_pipeline_id;
      }
      
      // Remove frontend-only fields
      const { reuse_serp_enabled, ...finalConfig } = submitConfig;
      
      await onStart(finalConfig);
    } finally {
      setIsStarting(false);
    }
  };


  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Play className="h-5 w-5" />
            Start Pipeline
          </DialogTitle>
          <DialogDescription>
            Configure and start a new digital landscape analysis pipeline
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="scope" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="scope">Scope</TabsTrigger>
            <TabsTrigger value="features">Features</TabsTrigger>
          </TabsList>

          <TabsContent value="scope" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Keywords & Content
                </CardTitle>
                <CardDescription>
                  Select content types to analyze using the main project configuration
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-4">
                  <p className="text-sm text-blue-800">
                    💡 This pipeline will use the keywords and regions defined in your main project configuration.
                  </p>
                </div>
                
                <div>
                  <Label className="text-base font-semibold">Content Types</Label>
                  <div className="grid gap-3 mt-2">
                    {contentTypes.map((ct) => (
                      <div key={ct.id} className="flex items-center space-x-3">
                        <Checkbox
                          id={ct.id}
                          checked={config.content_types.includes(ct.id)}
                          onCheckedChange={(checked) => handleContentTypeChange(ct.id, !!checked)}
                        />
                        <div className="flex-1">
                          <Label htmlFor={ct.id} className="font-medium">
                            {ct.name}
                          </Label>
                          <p className="text-sm text-gray-600">{ct.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* SERP Reuse Option */}
                <div className="border-t pt-4">
                  <div className="flex items-center space-x-3 mb-3">
                    <Checkbox
                      id="reuse-serp"
                      checked={config.reuse_serp_enabled}
                      onCheckedChange={(checked) => 
                        setConfig(prev => ({ 
                          ...prev, 
                          reuse_serp_enabled: !!checked,
                          reuse_serp_from_pipeline_id: checked ? prev.reuse_serp_from_pipeline_id : null
                        }))
                      }
                    />
                    <div className="flex-1">
                      <Label htmlFor="reuse-serp" className="font-medium flex items-center gap-2">
                        <RefreshCw className="h-4 w-4" />
                        Reuse Previous SERP Data
                      </Label>
                      <p className="text-sm text-gray-600">
                        Copy SERP results from a previous pipeline to save API costs
                      </p>
                    </div>
                  </div>

                  {config.reuse_serp_enabled && (
                    <div className="ml-6 space-y-3">
                      <div>
                        <Label htmlFor="source-pipeline">Source Pipeline</Label>
                        <Select
                          value={config.reuse_serp_from_pipeline_id || ''}
                          onValueChange={(value) => 
                            setConfig(prev => ({ ...prev, reuse_serp_from_pipeline_id: value }))
                          }
                        >
                          <SelectTrigger className="mt-1">
                            <SelectValue placeholder={loadingPipelines ? "Loading pipelines..." : "Select a pipeline"} />
                          </SelectTrigger>
                          <SelectContent>
                            {recentPipelines.length === 0 && !loadingPipelines && (
                              <SelectItem value="" disabled>No successful pipelines found</SelectItem>
                            )}
                            {recentPipelines.map((pipeline) => (
                              <SelectItem key={pipeline.pipeline_id} value={pipeline.pipeline_id}>
                                #{pipeline.pipeline_id.slice(0, 8)} • {pipeline.serp_results_collected.toLocaleString()} results • {' '}
                                {new Date(pipeline.started_at).toLocaleDateString()}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {config.reuse_serp_from_pipeline_id && (
                          <p className="text-xs text-green-600 mt-1">
                            💡 This will skip SERP collection and reuse existing data
                          </p>
                        )}
                      </div>
                      
                      {recentPipelines.length === 0 && !loadingPipelines && (
                        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                          <p className="text-sm text-yellow-800">
                            No successful pipelines with SERP data found. Complete a pipeline first to enable this option.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="features" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Pipeline Features</CardTitle>
                <CardDescription>
                  Enable or disable specific pipeline phases
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="company-enrichment" className="font-medium">
                      Company Enrichment
                    </Label>
                    <p className="text-sm text-gray-600">
                      Enrich domains with company data via Cognism API
                    </p>
                  </div>
                  <Switch
                    id="company-enrichment"
                    checked={config.enable_company_enrichment}
                    onCheckedChange={(checked) => 
                      setConfig(prev => ({ ...prev, enable_company_enrichment: checked }))
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="video-enrichment" className="font-medium">
                      Video Enrichment
                    </Label>
                    <p className="text-sm text-gray-600">
                      Fetch video metadata and transcripts from YouTube
                    </p>
                  </div>
                  <Switch
                    id="video-enrichment"
                    checked={config.enable_video_enrichment}
                    onCheckedChange={(checked) => 
                      setConfig(prev => ({ ...prev, enable_video_enrichment: checked }))
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="content-analysis" className="font-medium">
                      AI Content Analysis
                    </Label>
                    <p className="text-sm text-gray-600">
                      Analyze content with GPT-4 for personas, JTBD, and sentiment
                    </p>
                  </div>
                  <Switch
                    id="content-analysis"
                    checked={config.enable_content_analysis}
                    onCheckedChange={(checked) => 
                      setConfig(prev => ({ ...prev, enable_content_analysis: checked }))
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="historical-tracking" className="font-medium">
                      Historical Snapshot
                    </Label>
                    <p className="text-sm text-gray-600">
                      Create monthly snapshots for trend analysis
                    </p>
                  </div>
                  <Switch
                    id="historical-tracking"
                    checked={config.enable_historical_tracking}
                    onCheckedChange={(checked) => 
                      setConfig(prev => ({ ...prev, enable_historical_tracking: checked }))
                    }
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="force-refresh" className="font-medium">
                      Force Refresh
                    </Label>
                    <p className="text-sm text-gray-600">
                      Re-scrape and re-analyze existing content
                    </p>
                  </div>
                  <Switch
                    id="force-refresh"
                    checked={config.force_refresh}
                    onCheckedChange={(checked) => 
                      setConfig(prev => ({ ...prev, force_refresh: checked }))
                    }
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="flex items-center justify-between pt-6">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {config.content_types.length} content types
            </Badge>
            <Badge variant="secondary">
              Using project configuration
            </Badge>
          </div>
          
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button 
              onClick={handleStart} 
              disabled={isStarting || config.content_types.length === 0}
            >
              {isStarting ? 'Starting...' : 'Start Pipeline'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

