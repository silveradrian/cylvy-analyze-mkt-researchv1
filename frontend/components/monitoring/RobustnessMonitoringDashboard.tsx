'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Activity, 
  Shield, 
  Zap, 
  Database, 
  Clock, 
  AlertTriangle, 
  CheckCircle,
  RefreshCw,
  Globe,
  TrendingUp,
  BarChart3
} from 'lucide-react'

interface CircuitBreakerStatus {
  service_name: string
  current_state: string
  failure_count: number
  success_count: number
  total_requests: number
  success_rate: number
  last_failure_at?: string
  last_success_at?: string
}

interface SerpBatch {
  id: string
  name: string
  status: string
  searches_total_count: number
  results_count: number
  created_at: string
  last_run?: string
}

interface SystemHealth {
  status: string
  timestamp: string
  circuit_breakers: Record<string, string>
  job_queues: Record<string, number>
  error_rate_1h: number
  api_quota_usage: Record<string, any>
}

interface JobQueueStatus {
  queue_name: string
  pending_count: number
  processing_count: number
  completed_count: number
  failed_count: number
  dead_letter_count: number
}

export function RobustnessMonitoringDashboard() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null)
  const [circuitBreakers, setCircuitBreakers] = useState<CircuitBreakerStatus[]>([])
  const [serpBatches, setSerpBatches] = useState<SerpBatch[]>([])
  const [jobQueues, setJobQueues] = useState<JobQueueStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const handleResendWebhook = async (batchId: string, resultSetId: number) => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/webhooks/resend/${batchId}/${resultSetId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const result = await response.json()
        console.log('✅ Webhook resent successfully:', result)
        // Optionally show a success notification
        alert(`Webhook resent successfully for batch ${batchId}`)
      } else {
        const error = await response.text()
        console.error('❌ Failed to resend webhook:', error)
        alert(`Failed to resend webhook: ${error}`)
      }
    } catch (err) {
      console.error('❌ Error resending webhook:', err)
      alert('Error resending webhook')
    }
  }

  const fetchMonitoringData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch all monitoring data in parallel
      const [healthRes, circuitRes, serpRes, queuesRes] = await Promise.all([
        fetch('/api/v1/monitoring/health'),
        fetch('/api/v1/monitoring/circuit-breakers'),
        fetch('/api/v1/monitoring/serp-batches'),
        fetch('/api/v1/monitoring/job-queues')
      ])

      if (healthRes.ok) {
        setSystemHealth(await healthRes.json())
      }

      if (circuitRes.ok) {
        setCircuitBreakers(await circuitRes.json())
      }

      if (serpRes.ok) {
        const serpData = await serpRes.json()
        setSerpBatches(serpData.cylvy_batches || [])
      }

      if (queuesRes.ok) {
        setJobQueues(await queuesRes.json())
      }

      setLastRefresh(new Date())

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch monitoring data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMonitoringData()
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchMonitoringData, 30000)
    return () => clearInterval(interval)
  }, [])

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-500'
      case 'degraded': return 'bg-yellow-500' 
      case 'unhealthy': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getCircuitBreakerColor = (state: string) => {
    switch (state) {
      case 'closed': return 'text-green-500'
      case 'half_open': return 'text-yellow-500'
      case 'open': return 'text-red-500'
      default: return 'text-gray-500'
    }
  }

  const getSerpBatchStatusColor = (status: string) => {
    switch (status) {
      case 'completed': 
      case 'idle': return 'text-green-500'
      case 'running':
      case 'queued': return 'text-blue-500'
      case 'failed': return 'text-red-500'
      default: return 'text-gray-500'
    }
  }

  if (loading && !systemHealth) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Loading monitoring data...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">System Monitoring</h2>
          <p className="text-gray-600">Real-time pipeline robustness and performance monitoring</p>
        </div>
        
        <div className="flex items-center gap-4">
          {lastRefresh && (
            <span className="text-sm text-gray-500">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          
          <Button onClick={fetchMonitoringData} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* System Health Overview */}
      {systemHealth && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              System Health
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${getHealthStatusColor(systemHealth.status)}`} />
                <div>
                  <div className="font-medium capitalize">{systemHealth.status}</div>
                  <div className="text-sm text-gray-600">Overall Status</div>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                <div>
                  <div className="font-medium">{systemHealth.error_rate_1h.toFixed(1)}%</div>
                  <div className="text-sm text-gray-600">Error Rate (1h)</div>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-blue-500" />
                <div>
                  <div className="font-medium">{Object.keys(systemHealth.circuit_breakers).length}</div>
                  <div className="text-sm text-gray-600">Circuit Breakers</div>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-purple-500" />
                <div>
                  <div className="font-medium">{Object.values(systemHealth.job_queues).reduce((a, b) => a + b, 0)}</div>
                  <div className="text-sm text-gray-600">Queued Jobs</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="circuit-breakers" className="w-full">
        <TabsList className="grid grid-cols-4 lg:grid-cols-4">
          <TabsTrigger value="circuit-breakers">Circuit Breakers</TabsTrigger>
          <TabsTrigger value="serp-batches">Scale SERP Batches</TabsTrigger>
          <TabsTrigger value="job-queues">Job Queues</TabsTrigger>
          <TabsTrigger value="api-quotas">API Quotas</TabsTrigger>
        </TabsList>

        {/* Circuit Breakers Tab */}
        <TabsContent value="circuit-breakers">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Circuit Breakers
              </CardTitle>
              <CardDescription>
                Automatic failure protection for external services
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {circuitBreakers.length > 0 ? (
                  circuitBreakers.map((breaker) => (
                    <div key={breaker.service_name} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${
                          breaker.current_state === 'closed' ? 'bg-green-500' :
                          breaker.current_state === 'half_open' ? 'bg-yellow-500' : 'bg-red-500'
                        }`} />
                        
                        <div>
                          <div className="font-medium capitalize">{breaker.service_name.replace('_', ' ')}</div>
                          <div className="text-sm text-gray-600">
                            {breaker.total_requests} requests • {breaker.success_rate.toFixed(1)}% success rate
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <Badge className={getCircuitBreakerColor(breaker.current_state)}>
                          {breaker.current_state}
                        </Badge>
                        {breaker.current_state === 'open' && (
                          <div className="text-sm text-red-600 mt-1">
                            {breaker.failure_count} failures
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    No circuit breakers configured
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scale SERP Batches Tab */}
        <TabsContent value="serp-batches">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Scale SERP Batches
              </CardTitle>
              <CardDescription>
                Active and recent Scale SERP batch processing status
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {serpBatches.length > 0 ? (
                  serpBatches.map((batch) => (
                    <div key={batch.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${getSerpBatchStatusColor(batch.status)}`} />
                        
                        <div>
                          <div className="font-medium">{batch.name}</div>
                          <div className="text-sm text-gray-600">
                            ID: {batch.id} • {batch.searches_total_count} searches
                          </div>
                          <div className="text-xs text-gray-500">
                            Created: {new Date(batch.created_at).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <Badge className={getSerpBatchStatusColor(batch.status)}>
                          {batch.status}
                        </Badge>
                        
                        <div className="text-sm text-gray-600 mt-1">
                          {batch.results_count}/{batch.searches_total_count} results
                        </div>
                        
                        {batch.results_count > 0 && (
                          <Progress 
                            value={(batch.results_count / batch.searches_total_count) * 100} 
                            className="w-24 mt-2"
                          />
                        )}
                        
                        {batch.status === 'idle' && batch.result_sets && batch.result_sets.length > 0 && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="mt-2"
                            onClick={() => handleResendWebhook(batch.id, batch.result_sets[0].id)}
                          >
                            <RefreshCw className="h-3 w-3 mr-1" />
                            Resend Webhook
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    No recent Scale SERP batches found
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Job Queues Tab */}
        <TabsContent value="job-queues">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Job Queues
              </CardTitle>
              <CardDescription>
                Background job processing status and health
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                {jobQueues.length > 0 ? (
                  jobQueues.map((queue) => (
                    <div key={queue.queue_name} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium capitalize">{queue.queue_name.replace('_', ' ')}</h4>
                        <Badge variant="outline">
                          {queue.pending_count + queue.processing_count} active
                        </Badge>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                        <div>
                          <div className="font-medium text-blue-600">{queue.pending_count}</div>
                          <div className="text-gray-600">Pending</div>
                        </div>
                        <div>
                          <div className="font-medium text-yellow-600">{queue.processing_count}</div>
                          <div className="text-gray-600">Processing</div>
                        </div>
                        <div>
                          <div className="font-medium text-green-600">{queue.completed_count}</div>
                          <div className="text-gray-600">Completed</div>
                        </div>
                        <div>
                          <div className="font-medium text-red-600">{queue.failed_count}</div>
                          <div className="text-gray-600">Failed</div>
                        </div>
                        <div>
                          <div className="font-medium text-purple-600">{queue.dead_letter_count}</div>
                          <div className="text-gray-600">Dead Letter</div>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    No job queues active
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* API Quotas Tab */}
        <TabsContent value="api-quotas">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                API Quota Usage
              </CardTitle>
              <CardDescription>
                External API usage and remaining quotas
              </CardDescription>
            </CardHeader>
            <CardContent>
              {systemHealth?.api_quota_usage ? (
                <div className="space-y-4">
                  {Object.entries(systemHealth.api_quota_usage).map(([service, quota]: [string, any]) => (
                    <div key={service} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium capitalize">{service.replace('_', ' ')}</h4>
                        <Badge className={
                          quota.usage_percentage > 90 ? 'bg-red-100 text-red-800' :
                          quota.usage_percentage > 75 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-green-100 text-green-800'
                        }>
                          {quota.usage_percentage?.toFixed(1)}% used
                        </Badge>
                      </div>
                      
                      <div className="space-y-2">
                        <Progress value={quota.usage_percentage || 0} className="w-full" />
                        
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <div className="font-medium">{quota.current_usage?.toLocaleString() || 0}</div>
                            <div className="text-gray-600">Used</div>
                          </div>
                          <div>
                            <div className="font-medium">{quota.remaining?.toLocaleString() || 0}</div>
                            <div className="text-gray-600">Remaining</div>
                          </div>
                          <div>
                            <div className="font-medium">{quota.monthly_limit?.toLocaleString() || 0}</div>
                            <div className="text-gray-600">Limit</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  No API quota data available
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Quick Actions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Button 
              onClick={() => fetch('/api/v1/monitoring/circuit-breakers/scale_serp_api/reset', { method: 'POST' })}
              variant="outline" 
              size="sm"
            >
              Reset SERP Circuit Breaker
            </Button>
            
            <Button 
              onClick={() => fetch('/api/v1/monitoring/job-queues/serp_collection/retry-dead-letter', { method: 'POST' })}
              variant="outline" 
              size="sm"
            >
              Retry Dead Letter Jobs
            </Button>
            
            <Button onClick={fetchMonitoringData} variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Force Refresh
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
