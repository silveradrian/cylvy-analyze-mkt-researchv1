'use client'

import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { 
  PlayCircle, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Pause, 
  AlertCircle,
  Search,
  Filter,
  Download,
  Eye
} from 'lucide-react'

interface Pipeline {
  pipeline_id: string
  status: string
  mode: string
  started_at: string
  completed_at?: string
  duration_seconds?: number
  keywords_processed: number
  serp_results_collected: number
  companies_enriched: number
  videos_enriched: number
  content_analyzed: number
  errors: string[]
  warnings: string[]
}

interface PipelineHistoryTableProps {
  pipelines: Pipeline[]
}

export function PipelineHistoryTable({ pipelines }: PipelineHistoryTableProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [modeFilter, setModeFilter] = useState('all')

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4" style={{ color: 'rgb(var(--color-warning))' }} />
      case 'running':
        return <PlayCircle className="h-4 w-4" style={{ color: 'rgb(var(--status-info-fg))' }} />
      case 'completed':
        return <CheckCircle className="h-4 w-4" style={{ color: 'rgb(var(--status-success-fg))' }} />
      case 'failed':
        return <XCircle className="h-4 w-4" style={{ color: 'rgb(var(--status-error-fg))' }} />
      case 'cancelled':
        return <Pause className="h-4 w-4 text-gray-500" />
      default:
        return <AlertCircle className="h-4 w-4 text-gray-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'text-[rgb(var(--color-warning))]'
      case 'running':
        return 'bg-[rgb(var(--status-info-bg))] text-[rgb(var(--status-info-fg))]'
      case 'completed':
        return 'bg-[rgb(var(--status-success-bg))] text-[rgb(var(--status-success-fg))]'
      case 'failed':
        return 'bg-[rgb(var(--status-error-bg))] text-[rgb(var(--status-error-fg))]'
      case 'cancelled':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-600'
    }
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const remainingSeconds = seconds % 60
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${remainingSeconds}s`
    } else if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`
    } else {
      return `${remainingSeconds}s`
    }
  }

  const filteredPipelines = pipelines.filter(pipeline => {
    const matchesSearch = pipeline.pipeline_id.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || pipeline.status === statusFilter
    const matchesMode = modeFilter === 'all' || pipeline.mode === modeFilter
    return matchesSearch && matchesStatus && matchesMode
  })

  if (pipelines.length === 0) {
    return (
      <Card>
        <CardContent className="text-center py-8">
          <Clock className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium mb-2">No Pipeline History</h3>
          <p className="text-gray-600">
            Pipeline execution history will appear here once you start running pipelines
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Pipeline History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 mb-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  placeholder="Search by pipeline ID..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>

            <Select value={modeFilter} onValueChange={setModeFilter}>
              <SelectTrigger className="w-[150px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Modes</SelectItem>
                <SelectItem value="manual">Manual</SelectItem>
                <SelectItem value="scheduled">Scheduled</SelectItem>
                <SelectItem value="api">API</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Cards */}
      <div className="space-y-3">
        {filteredPipelines.map((pipeline) => (
          <Card key={pipeline.pipeline_id} className="hover:shadow-md transition-shadow">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  {getStatusIcon(pipeline.status)}
                  <div>
                    <div className="font-medium">
                      Pipeline {pipeline.pipeline_id.slice(0, 12)}...
                    </div>
                    <div className="text-sm text-gray-600">
                      {new Date(pipeline.started_at).toLocaleString()}
                      {pipeline.completed_at && (
                        <span> → {new Date(pipeline.completed_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge className={getStatusColor(pipeline.status)}>
                    {pipeline.status}
                  </Badge>
                  <Badge variant="outline">
                    {pipeline.mode}
                  </Badge>
                  <Button variant="ghost" size="sm">
                    <Eye className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-sm">
                <div className="text-center">
                  <div className="font-semibold text-blue-600">{pipeline.keywords_processed}</div>
                  <div className="text-gray-600">Keywords</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-green-600">{pipeline.serp_results_collected}</div>
                  <div className="text-gray-600">SERP Results</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-purple-600">{pipeline.companies_enriched}</div>
                  <div className="text-gray-600">Companies</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-orange-600">{pipeline.videos_enriched}</div>
                  <div className="text-gray-600">Videos</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-red-600">{pipeline.content_analyzed}</div>
                  <div className="text-gray-600">Content</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-gray-600">{formatDuration(pipeline.duration_seconds)}</div>
                  <div className="text-gray-600">Duration</div>
                </div>
              </div>

              {(pipeline.errors?.length > 0 || pipeline.warnings?.length > 0) && (
                <div className="mt-3 pt-3 border-t">
                  <div className="flex gap-4 text-xs">
                    {pipeline.errors?.length > 0 && (
                      <span className="text-red-600">
                        {pipeline.errors.length} error(s)
                      </span>
                    )}
                    {pipeline.warnings?.length > 0 && (
                      <span className="text-yellow-600">
                        {pipeline.warnings.length} warning(s)
                      </span>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredPipelines.length === 0 && (
        <Card>
          <CardContent className="text-center py-8">
            <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium mb-2">No Matching Pipelines</h3>
            <p className="text-gray-600">
              Try adjusting your search or filter criteria
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

