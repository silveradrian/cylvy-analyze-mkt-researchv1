'use client';

import { useState } from 'react';
import { X, Play, Settings, Database, Globe } from 'lucide-react';
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

export function StartPipelineDialog({ open, onClose, onStart }: StartPipelineDialogProps) {
  const [config, setConfig] = useState({
    keywords: null as string[] | null,
    regions: ['US', 'UK'],
    content_types: ['organic', 'news', 'video'],
    
    // Concurrency settings
    max_concurrent_serp: 10,
    max_concurrent_enrichment: 15,
    max_concurrent_analysis: 20,
    
    // Feature flags
    enable_company_enrichment: true,
    enable_video_enrichment: true,
    enable_content_analysis: true,
    enable_historical_tracking: true,
    force_refresh: false,
    
    // Mode
    mode: 'manual'
  });
  
  const [keywordInput, setKeywordInput] = useState('');
  const [isStarting, setIsStarting] = useState(false);

  const availableRegions = [
    { code: 'US', name: 'United States' },
    { code: 'UK', name: 'United Kingdom' },
    { code: 'CA', name: 'Canada' },
    { code: 'AU', name: 'Australia' },
    { code: 'DE', name: 'Germany' },
    { code: 'FR', name: 'France' },
    { code: 'IN', name: 'India' },
    { code: 'BR', name: 'Brazil' },
    { code: 'JP', name: 'Japan' },
    { code: 'SG', name: 'Singapore' }
  ];

  const contentTypes = [
    { id: 'organic', name: 'Organic Results', description: 'Regular search results' },
    { id: 'news', name: 'News Results', description: 'News articles and updates' },
    { id: 'video', name: 'Video Results', description: 'YouTube and video content' }
  ];

  const handleRegionChange = (regionCode: string, checked: boolean) => {
    setConfig(prev => ({
      ...prev,
      regions: checked 
        ? [...prev.regions, regionCode]
        : prev.regions.filter(r => r !== regionCode)
    }));
  };

  const handleContentTypeChange = (contentType: string, checked: boolean) => {
    setConfig(prev => ({
      ...prev,
      content_types: checked
        ? [...prev.content_types, contentType]
        : prev.content_types.filter(ct => ct !== contentType)
    }));
  };

  const handleKeywordsChange = (value: string) => {
    setKeywordInput(value);
    if (value.trim()) {
      const keywords = value.split('\n').map(k => k.trim()).filter(k => k);
      setConfig(prev => ({ ...prev, keywords }));
    } else {
      setConfig(prev => ({ ...prev, keywords: null }));
    }
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await onStart(config);
    } finally {
      setIsStarting(false);
    }
  };

  const estimatedDuration = () => {
    // Rough estimation based on settings
    const keywordCount = config.keywords?.length || 50; // Assume 50 if all keywords
    const regionCount = config.regions.length;
    const contentTypeCount = config.content_types.length;
    
    const totalRequests = keywordCount * regionCount * contentTypeCount;
    const estimatedMinutes = Math.ceil(totalRequests / config.max_concurrent_serp * 0.5);
    
    if (estimatedMinutes < 60) {
      return `~${estimatedMinutes} minutes`;
    } else {
      const hours = Math.floor(estimatedMinutes / 60);
      const mins = estimatedMinutes % 60;
      return `~${hours}h ${mins}m`;
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
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="scope">Scope</TabsTrigger>
            <TabsTrigger value="regions">Regions</TabsTrigger>
            <TabsTrigger value="features">Features</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
          </TabsList>

          <TabsContent value="scope" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Keywords & Content
                </CardTitle>
                <CardDescription>
                  Define the scope of your analysis
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="keywords">Keywords (optional)</Label>
                  <Textarea
                    id="keywords"
                    placeholder="Enter keywords, one per line. Leave empty to process all keywords."
                    value={keywordInput}
                    onChange={(e) => handleKeywordsChange(e.target.value)}
                    rows={4}
                  />
                  <p className="text-xs text-gray-600 mt-1">
                    {config.keywords ? `${config.keywords.length} keywords specified` : 'Will process all keywords in database'}
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
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="regions" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Geographic Regions
                </CardTitle>
                <CardDescription>
                  Select regions for SERP collection
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  {availableRegions.map((region) => (
                    <div key={region.code} className="flex items-center space-x-3">
                      <Checkbox
                        id={region.code}
                        checked={config.regions.includes(region.code)}
                        onCheckedChange={(checked) => handleRegionChange(region.code, !!checked)}
                      />
                      <Label htmlFor={region.code}>
                        {region.name} ({region.code})
                      </Label>
                    </div>
                  ))}
                </div>
                <div className="mt-4">
                  <p className="text-sm text-gray-600">
                    Selected: {config.regions.join(', ')}
                  </p>
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

          <TabsContent value="performance" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  Performance Settings
                </CardTitle>
                <CardDescription>
                  Adjust concurrency limits for optimal performance
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <Label htmlFor="serp-concurrency">
                    SERP Collection Concurrency: {config.max_concurrent_serp}
                  </Label>
                  <Input
                    id="serp-concurrency"
                    type="range"
                    min="1"
                    max="50"
                    value={config.max_concurrent_serp}
                    onChange={(e) => 
                      setConfig(prev => ({ ...prev, max_concurrent_serp: parseInt(e.target.value) }))
                    }
                    className="mt-2"
                  />
                  <p className="text-xs text-gray-600 mt-1">
                    Higher values = faster SERP collection but may hit rate limits
                  </p>
                </div>

                <div>
                  <Label htmlFor="enrichment-concurrency">
                    Company Enrichment Concurrency: {config.max_concurrent_enrichment}
                  </Label>
                  <Input
                    id="enrichment-concurrency"
                    type="range"
                    min="1"
                    max="30"
                    value={config.max_concurrent_enrichment}
                    onChange={(e) => 
                      setConfig(prev => ({ ...prev, max_concurrent_enrichment: parseInt(e.target.value) }))
                    }
                    className="mt-2"
                  />
                  <p className="text-xs text-gray-600 mt-1">
                    Limited by Cognism API rate limits
                  </p>
                </div>

                <div>
                  <Label htmlFor="analysis-concurrency">
                    Content Analysis Concurrency: {config.max_concurrent_analysis}
                  </Label>
                  <Input
                    id="analysis-concurrency"
                    type="range"
                    min="1"
                    max="50"
                    value={config.max_concurrent_analysis}
                    onChange={(e) => 
                      setConfig(prev => ({ ...prev, max_concurrent_analysis: parseInt(e.target.value) }))
                    }
                    className="mt-2"
                  />
                  <p className="text-xs text-gray-600 mt-1">
                    Higher values = faster AI analysis but higher OpenAI costs
                  </p>
                </div>

                {/* Estimation */}
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h4 className="font-medium text-blue-900">Estimated Duration</h4>
                  <p className="text-blue-700 text-lg font-semibold">{estimatedDuration()}</p>
                  <p className="text-xs text-blue-600 mt-1">
                    Based on {config.keywords?.length || 'all'} keywords × {config.regions.length} regions × {config.content_types.length} content types
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="flex items-center justify-between pt-6">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {config.regions.length} regions
            </Badge>
            <Badge variant="secondary">
              {config.content_types.length} content types
            </Badge>
            <Badge variant="secondary">
              {config.keywords?.length || 'All'} keywords
            </Badge>
          </div>
          
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button 
              onClick={handleStart} 
              disabled={isStarting || config.regions.length === 0 || config.content_types.length === 0}
            >
              {isStarting ? 'Starting...' : 'Start Pipeline'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
