'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AdminLayout } from '@/components/layout/AdminLayout'
import { SetupChecklist } from '@/components/setup/SetupChecklist'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  Activity, 
  BarChart3, 
  Calendar, 
  Globe, 
  Layers, 
  Settings,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  Play,
  ChevronRight,
  Monitor
} from 'lucide-react'

interface DashboardStats {
  pipelinesRun: number
  lastPipelineDate?: string
  totalKeywords: number
  activeDimensions: number
  activeLandscapes: number
}

interface QuickAction {
  title: string
  description: string
  icon: any
  route: string
  color: string
  badge?: string
}

export default function Dashboard() {
  const router = useRouter()
  const [stats, setStats] = useState<DashboardStats>({
    pipelinesRun: 0,
    totalKeywords: 0,
    activeDimensions: 0,
    activeLandscapes: 0
  })
  const [recentPipelines, setRecentPipelines] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      const token = localStorage.getItem('access_token') || 'test-token-for-development'
      
      // Fetch all data in parallel
      const [
        pipelineData,
        keywordsData,
        dimensionData,
        landscapeData
      ] = await Promise.all([
        fetch('/api/v1/pipeline/recent?limit=5', {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(res => res.ok ? res.json() : { pipelines: [] }),
        
        fetch('/api/v1/keywords', {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(res => res.ok ? res.json() : { total: 0 }),
        
        fetch('/api/v1/dimensions/dimensions', {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(res => res.ok ? res.json() : []),
        
        fetch('/api/v1/landscapes', {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(res => res.ok ? res.json() : [])
      ])

      // Extract pipelines from the response structure
      const pipelines = pipelineData.pipelines || []
      
      setRecentPipelines(pipelines)
      setStats({
        pipelinesRun: pipelines.length,
        lastPipelineDate: pipelines[0]?.completed_at,
        totalKeywords: keywordsData.total || 0,
        activeDimensions: dimensionData.length || 0,
        activeLandscapes: landscapeData.length || 0
      })
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const quickActions: QuickAction[] = [
    {
      title: 'Run Pipeline',
      description: 'Start a new analysis pipeline',
      icon: Play,
      route: '/pipeline',
      color: 'text-green-600 bg-green-100',
      badge: stats.pipelinesRun > 0 ? 'Active' : 'Start'
    },
    {
      title: 'View Monitoring',
      description: 'Check system health and metrics',
      icon: Monitor,
      route: '/monitoring',
      color: 'text-blue-600 bg-blue-100'
    },
    {
      title: 'Manage Landscapes',
      description: 'Configure DSI market views',
      icon: Globe,
      route: '/landscapes',
      color: 'text-purple-600 bg-purple-100',
      badge: `${stats.activeLandscapes} active`
    },
    {
      title: 'Custom Dimensions',
      description: 'Add analysis dimensions',
      icon: Layers,
      route: '/dimensions',
      color: 'text-orange-600 bg-orange-100'
    }
  ]

  const statusCards = [
    {
      title: 'Pipeline Activity',
      value: stats.pipelinesRun,
      subtitle: stats.lastPipelineDate ? `Last run: ${new Date(stats.lastPipelineDate).toLocaleDateString()}` : 'No pipelines run yet',
      icon: Activity,
      color: 'text-green-600'
    },
    {
      title: 'Keywords Tracked',
      value: stats.totalKeywords.toLocaleString(),
      subtitle: 'Across all markets',
      icon: BarChart3,
      color: 'text-blue-600'
    },
    {
      title: 'Analysis Dimensions',
      value: stats.activeDimensions,
      subtitle: 'Active dimensions',
      icon: Layers,
      color: 'text-purple-600'
    },
    {
      title: 'Digital Landscapes',
      value: stats.activeLandscapes,
      subtitle: 'Configured views',
      icon: Globe,
      color: 'text-orange-600'
    }
  ]

  return (
    <AdminLayout title="Dashboard">
      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-white/80 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white p-8 rounded-lg shadow-lg">
            <div className="flex items-center gap-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cylvy-purple"></div>
              <p className="text-lg font-medium">Loading configuration...</p>
            </div>
          </div>
        </div>
      )}
      
      <div className="space-y-6">
        {/* Setup Checklist - Always visible */}
        <SetupChecklist />

        {/* Status Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {statusCards.map((card, index) => {
            const Icon = card.icon
            return (
              <Card key={index}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">
                    {card.title}
                  </CardTitle>
                  <Icon className={`h-4 w-4 ${card.color}`} />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{card.value}</div>
                  <p className="text-xs text-muted-foreground">
                    {card.subtitle}
                  </p>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Quick Actions and Recent Activity */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>
                Common tasks and workflows
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {quickActions.map((action, index) => {
                const Icon = action.icon
                return (
                  <div
                    key={index}
                    className="flex items-center justify-between p-4 rounded-lg border cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => router.push(action.route)}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${action.color}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <h4 className="font-medium">{action.title}</h4>
                        <p className="text-sm text-gray-600">{action.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {action.badge && (
                        <Badge variant="secondary">{action.badge}</Badge>
                      )}
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    </div>
                  </div>
                )
              })}
            </CardContent>
          </Card>

          {/* Recent Pipeline Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Pipeline Activity</CardTitle>
              <CardDescription>
                Latest analysis runs
              </CardDescription>
            </CardHeader>
            <CardContent>
              {recentPipelines.length > 0 ? (
                <div className="space-y-4">
                  {recentPipelines.map((pipeline, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-full ${
                          pipeline.status === 'completed' ? 'bg-green-100' : 'bg-amber-100'
                        }`}>
                          {pipeline.status === 'completed' ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <Clock className="h-4 w-4 text-amber-600" />
                          )}
                        </div>
                        <div>
                          <p className="text-sm font-medium">
                            {pipeline.config?.batch_size || 0} keywords analyzed
                          </p>
                          <p className="text-xs text-gray-500">
                            {new Date(pipeline.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                      <Badge variant={pipeline.status === 'completed' ? 'success' : 'secondary'}>
                        {pipeline.status}
                      </Badge>
                    </div>
                  ))}
                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={() => router.push('/pipeline')}
                  >
                    View All Pipelines
                  </Button>
                </div>
              ) : (
                <div className="text-center py-8">
                  <AlertCircle className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-600 mb-4">No pipeline runs yet</p>
                  <Button 
                    onClick={() => router.push('/pipeline')}
                    className="cylvy-btn-primary"
                  >
                    Run First Pipeline
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* System Status */}
        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
            <CardDescription>
              Current health and performance metrics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm font-medium">API Status</p>
                  <p className="text-xs text-gray-500">All systems operational</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
                  <TrendingUp className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-medium">Data Collection</p>
                  <p className="text-xs text-gray-500">Running smoothly</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
                  <Calendar className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-sm font-medium">Next Scheduled Run</p>
                  <p className="text-xs text-gray-500">Not configured</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  )
}