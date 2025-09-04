'use client'

import React, { useState, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Activity, 
  CheckCircle, 
  Clock, 
  AlertTriangle, 
  Zap,
  Database,
  Globe,
  Video,
  FileText,
  BarChart3,
  Camera,
  Archive,
  Map
} from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'

interface PipelinePhase {
  name: string
  icon: React.ReactNode
  description: string
  status: 'pending' | 'running' | 'completed' | 'error'
  started_at?: string
  completed_at?: string
  items_processed?: number
  total_items?: number
  current_item?: string
  error_message?: string
}

interface RealtimePipelineStatusProps {
  pipelineId?: string
}

export function RealtimePipelineStatus({ pipelineId }: RealtimePipelineStatusProps) {
  const [phases, setPhases] = useState<PipelinePhase[]>([
    {
      name: 'Keyword Metrics Enrichment',
      icon: <BarChart3 className="h-4 w-4" />,
      description: 'Fetching Google Ads historical metrics',
      status: 'pending'
    },
    {
      name: 'SERP Collection',
      icon: <Globe className="h-4 w-4" />,
      description: 'Collecting search engine results',
      status: 'pending'
    },
    {
      name: 'Company Enrichment',
      icon: <Database className="h-4 w-4" />,
      description: 'Enriching company data',
      status: 'pending'
    },
    {
      name: 'Video Enrichment',
      icon: <Video className="h-4 w-4" />,
      description: 'Processing video content',
      status: 'pending'
    },
    {
      name: 'Content Scraping',
      icon: <FileText className="h-4 w-4" />,
      description: 'Scraping page content',
      status: 'pending'
    },
    {
      name: 'Content Analysis',
      icon: <BarChart3 className="h-4 w-4" />,
      description: 'Analyzing content with AI',
      status: 'pending'
    },
    {
      name: 'DSI Calculation',
      icon: <Zap className="h-4 w-4" />,
      description: 'Computing DSI scores',
      status: 'pending'
    },
    {
      name: 'Historical Snapshot',
      icon: <Archive className="h-4 w-4" />,
      description: 'Creating historical record',
      status: 'pending'
    },
    {
      name: 'Landscape DSI Calculation',
      icon: <Map className="h-4 w-4" />,
      description: 'Calculating Digital Landscape DSI metrics',
      status: 'pending'
    }
  ])

  const [overallProgress, setOverallProgress] = useState(0)
  const [currentPhase, setCurrentPhase] = useState<string>('')
  const [totalStats, setTotalStats] = useState({
    keywords_processed: 0,
    serp_results_collected: 0,
    companies_enriched: 0,
    videos_enriched: 0,
    content_analyzed: 0,
    landscapes_calculated: 0
  })

  // WebSocket connection for real-time updates
  const { isConnected, lastMessage } = useWebSocket(`/ws/pipeline${pipelineId ? `/${pipelineId}` : ''}`)

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage && lastMessage.type === 'pipeline_update') {
      updatePipelineStatus(lastMessage.data)
    }
  }, [lastMessage])

  const updatePipelineStatus = (data: any) => {
    if (data.phase) {
      setCurrentPhase(data.phase)
      
      // Update phase status
      setPhases(prevPhases => 
        prevPhases.map(phase => {
          const phaseKey = phase.name.toLowerCase().replace(/\s+/g, '_')
          
          if (phaseKey === data.phase) {
            return {
              ...phase,
              status: data.status || 'running',
              started_at: data.started_at || phase.started_at,
              completed_at: data.completed_at,
              items_processed: data.items_processed,
              total_items: data.total_items,
              current_item: data.current_item,
              error_message: data.error_message
            }
          } else if (data.completed_phases?.includes(phaseKey)) {
            return { ...phase, status: 'completed' }
          }
          
          return phase
        })
      )
    }

    // Update overall progress
    if (data.completed_phases) {
      const progress = (data.completed_phases.length / phases.length) * 100
      setOverallProgress(Math.round(progress))
    }

    // Update total statistics
    if (data.statistics) {
      setTotalStats(prev => ({ ...prev, ...data.statistics }))
    }
  }

  const getPhaseStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-500'
      case 'running':
        return 'text-blue-500'
      case 'error':
        return 'text-red-500'
      default:
        return 'text-gray-400'
    }
  }

  const getPhaseProgress = (phase: PipelinePhase) => {
    if (phase.status === 'completed') return 100
    if (phase.status === 'running' && phase.items_processed && phase.total_items) {
      return Math.round((phase.items_processed / phase.total_items) * 100)
    }
    return 0
  }

  if (!pipelineId) {
    return (
      <Card>
        <CardContent className="text-center py-8">
          <Activity className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium mb-2">No Active Pipeline</h3>
          <p className="text-gray-600">
            Start a pipeline to see real-time progress updates here
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Connection Status */}
      <div className="flex items-center gap-2 text-sm">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-gray-600">
          {isConnected ? 'Live updates connected' : 'Connection lost - retrying...'}
        </span>
      </div>

      {/* Overall Progress */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Pipeline Progress
          </CardTitle>
          <CardDescription>
            Real-time updates from pipeline execution
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">Overall Progress</span>
                <span className="text-sm text-gray-600">{overallProgress}%</span>
              </div>
              <Progress value={overallProgress} className="h-3" />
            </div>

            {/* Current Phase */}
            {currentPhase && (
              <div className="bg-blue-50 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-500" />
                  <span className="font-medium text-blue-900">
                    Currently: {currentPhase.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </span>
                </div>
              </div>
            )}

            {/* Statistics */}
            <div className="grid grid-cols-7 gap-3 text-center">
              <div>
                <div className="text-xl font-bold text-blue-600">
                  {totalStats.keywords_processed}
                </div>
                <div className="text-xs text-gray-600">Keywords</div>
              </div>
              <div>
                <div className="text-xl font-bold text-indigo-600">
                  {totalStats.keywords_with_metrics}
                </div>
                <div className="text-xs text-gray-600">With Metrics</div>
              </div>
              <div>
                <div className="text-xl font-bold text-green-600">
                  {totalStats.serp_results_collected}
                </div>
                <div className="text-xs text-gray-600">SERP Results</div>
              </div>
              <div>
                <div className="text-xl font-bold text-purple-600">
                  {totalStats.companies_enriched}
                </div>
                <div className="text-xs text-gray-600">Companies</div>
              </div>
              <div>
                <div className="text-xl font-bold text-orange-600">
                  {totalStats.videos_enriched}
                </div>
                <div className="text-xs text-gray-600">Videos</div>
              </div>
              <div>
                <div className="text-xl font-bold text-red-600">
                  {totalStats.content_analyzed}
                </div>
                <div className="text-xs text-gray-600">Content</div>
              </div>
              <div>
                <div className="text-xl font-bold text-cylvy-amaranth">
                  {totalStats.landscapes_calculated}
                </div>
                <div className="text-xs text-gray-600">Landscapes</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Phase Details */}
      <Card>
        <CardHeader>
          <CardTitle>Phase Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {phases.map((phase, index) => (
              <div key={phase.name} className="flex items-center gap-4 p-3 rounded-lg hover:bg-gray-50">
                <div className={`${getPhaseStatusColor(phase.status)} flex-shrink-0`}>
                  {phase.status === 'completed' ? <CheckCircle className="h-5 w-5" /> : phase.icon}
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{phase.name}</span>
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant={
                          phase.status === 'completed' ? 'success' :
                          phase.status === 'running' ? 'default' :
                          phase.status === 'error' ? 'destructive' : 'secondary'
                        }
                        className="text-xs"
                      >
                        {phase.status}
                      </Badge>
                      {phase.status === 'running' && phase.items_processed && phase.total_items && (
                        <span className="text-xs text-gray-500">
                          {phase.items_processed}/{phase.total_items}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div className="text-sm text-gray-600 mb-2">{phase.description}</div>
                  
                  {phase.status === 'running' && (
                    <div className="space-y-1">
                      <Progress value={getPhaseProgress(phase)} className="h-1" />
                      {phase.current_item && (
                        <div className="text-xs text-gray-500">
                          Processing: {phase.current_item}
                        </div>
                      )}
                    </div>
                  )}

                  {phase.error_message && (
                    <Alert className="mt-2">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription className="text-xs">
                        {phase.error_message}
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
