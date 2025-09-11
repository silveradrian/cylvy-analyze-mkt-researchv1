"use client"

import React, { useState, useEffect } from 'react'
import { AdminLayout } from '@/components/layout/AdminLayout'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Plus, Settings, Target, Play, Clock, TrendingUp, 
  Search, Check, X, Globe, BarChart3 
} from 'lucide-react'

interface DigitalLandscape {
  id: string
  name: string
  description?: string
  is_active: boolean
  created_at: string
  keyword_count: number
}

interface Keyword {
  id: string
  keyword: string
  search_volume?: number
  competition_level?: string
}

interface LandscapeMetric {
  entity_name: string
  entity_domain: string
  unique_keywords: number
  unique_pages: number
  keyword_coverage: number
  estimated_traffic: number
  traffic_share: number
  dsi_score: number
  rank_in_landscape: number
  market_position: string
  calculation_date: string
}

interface LandscapeSummary {
  landscape_id: string
  calculation_date: string
  total_companies: number
  total_keywords: number
  total_pages: number
  total_traffic: number
  avg_dsi_score: number
  top_dsi_score: number
}

export default function DigitalLandscapeManager() {
  const [landscapes, setLandscapes] = useState<DigitalLandscape[]>([])
  const [selectedLandscape, setSelectedLandscape] = useState<DigitalLandscape | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [loading, setLoading] = useState(true)
  const [calculating, setCalculating] = useState<string | null>(null)
  
  // Create landscape form
  const [createForm, setCreateForm] = useState({
    name: '',
    description: ''
  })
  
  // Keywords management
  const [availableKeywords, setAvailableKeywords] = useState<Keyword[]>([])
  const [assignedKeywords, setAssignedKeywords] = useState<Keyword[]>([])
  const [keywordSearch, setKeywordSearch] = useState('')
  const [selectedKeywordIds, setSelectedKeywordIds] = useState<string[]>([])
  
  // Metrics & results
  const [landscapeMetrics, setLandscapeMetrics] = useState<LandscapeMetric[]>([])
  const [landscapeSummary, setLandscapeSummary] = useState<LandscapeSummary | null>(null)

  useEffect(() => {
    loadLandscapes()
    loadAvailableKeywords()
  }, [])

  useEffect(() => {
    if (selectedLandscape) {
      loadLandscapeKeywords(selectedLandscape.id)
      loadLandscapeMetrics(selectedLandscape.id)
      loadLandscapeSummary(selectedLandscape.id)
    }
  }, [selectedLandscape])

  const loadLandscapes = async () => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/landscapes', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setLandscapes(Array.isArray(data) ? data : data.value || [])
      }
    } catch (error) {
      console.error('Failed to load landscapes:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadAvailableKeywords = async (search?: string) => {
    try {
      const token = localStorage.getItem('access_token')
      const params = new URLSearchParams()
      if (search) params.append('search', search)
      params.append('limit', '200')
      
      const response = await fetch(`/api/v1/landscapes/keywords/available?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setAvailableKeywords(data)
      }
    } catch (error) {
      console.error('Failed to load keywords:', error)
    }
  }

  const loadLandscapeKeywords = async (landscapeId: string) => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/landscapes/${landscapeId}/keywords`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setAssignedKeywords(data)
      }
    } catch (error) {
      console.error('Failed to load landscape keywords:', error)
    }
  }

  const loadLandscapeMetrics = async (landscapeId: string) => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/landscapes/${landscapeId}/metrics?limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setLandscapeMetrics(data.metrics || [])
      }
    } catch (error) {
      console.error('Failed to load landscape metrics:', error)
    }
  }

  const loadLandscapeSummary = async (landscapeId: string) => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/landscapes/${landscapeId}/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setLandscapeSummary(data)
      }
    } catch (error) {
      console.error('Failed to load landscape summary:', error)
    }
  }

  const createLandscape = async () => {
    if (!createForm.name.trim()) return
    
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/landscapes', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(createForm)
      })
      
      if (response.ok) {
        await loadLandscapes()
        setShowCreateDialog(false)
        setCreateForm({ name: '', description: '' })
      }
    } catch (error) {
      console.error('Failed to create landscape:', error)
    }
  }

  const assignKeywords = async () => {
    if (!selectedLandscape || selectedKeywordIds.length === 0) return
    
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/landscapes/${selectedLandscape.id}/keywords`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(selectedKeywordIds)
      })
      
      if (response.ok) {
        await loadLandscapeKeywords(selectedLandscape.id)
        await loadLandscapes() // Refresh keyword counts
        setSelectedKeywordIds([])
      }
    } catch (error) {
      console.error('Failed to assign keywords:', error)
    }
  }

  const calculateDSI = async (landscapeId: string) => {
    setCalculating(landscapeId)
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/landscapes/${landscapeId}/calculate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        await loadLandscapeMetrics(landscapeId)
        await loadLandscapeSummary(landscapeId)
      }
    } catch (error) {
      console.error('Failed to calculate DSI:', error)
    } finally {
      setCalculating(null)
    }
  }

  const searchKeywords = (search: string) => {
    setKeywordSearch(search)
    loadAvailableKeywords(search)
  }

  const toggleKeywordSelection = (keywordId: string) => {
    setSelectedKeywordIds(prev => 
      prev.includes(keywordId) 
        ? prev.filter(id => id !== keywordId)
        : [...prev, keywordId]
    )
  }

  if (loading) {
    return (
      <AdminLayout title="Digital Landscape Manager" description="Loading landscapes...">
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin"></div>
        </div>
      </AdminLayout>
    )
  }

  return (
    <AdminLayout title="Digital Landscape Manager" description="Configure keyword-based digital landscape views and historical metrics">
      <Tabs defaultValue="landscapes" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="landscapes" className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Landscape Definitions
          </TabsTrigger>
          <TabsTrigger value="keywords" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Keyword Assignment
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Historical Results
          </TabsTrigger>
        </TabsList>

        {/* Landscape Definitions Tab */}
        <TabsContent value="landscapes" className="space-y-6 bg-transparent">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-cylvy-midnight">Digital Landscapes</h2>
              <p className="text-gray-600 mt-1">Define your market segments and geographical views</p>
            </div>
            <Button onClick={() => setShowCreateDialog(true)} className="cylvy-btn-primary">
              <Plus className="h-4 w-4 mr-2" />
              Create Landscape
            </Button>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {landscapes.map(landscape => (
              <Card 
                key={landscape.id} 
                className={`cylvy-card-hover cursor-pointer transition-all bg-white ${
                  selectedLandscape?.id === landscape.id ? 'ring-2 ring-cylvy-amaranth' : ''
                }`}
                onClick={() => setSelectedLandscape(landscape)}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-cylvy-midnight text-lg">{landscape.name}</CardTitle>
                      {landscape.description && (
                        <CardDescription className="mt-2">{landscape.description}</CardDescription>
                      )}
                    </div>
                    <Badge variant="secondary" className="ml-2">
                      {landscape.keyword_count} keywords
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-500">
                      Created {new Date(landscape.created_at).toLocaleDateString()}
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        calculateDSI(landscape.id)
                      }}
                      disabled={calculating === landscape.id || landscape.keyword_count === 0}
                      className="cylvy-btn-secondary"
                    >
                      {calculating === landscape.id ? (
                        <div className="w-4 h-4 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                      Calculate
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Keyword Assignment Tab */}
        <TabsContent value="keywords" className="space-y-6 bg-transparent">
          {selectedLandscape ? (
            <>
              <div className="bg-cylvy-amaranth/10 p-4 rounded-lg">
                <h3 className="font-semibold text-cylvy-midnight">
                  Managing Keywords for: {selectedLandscape.name}
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  Currently assigned: {assignedKeywords.length} keywords
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Assigned Keywords */}
                <Card className="bg-white">
                  <CardHeader>
                    <CardTitle className="text-cylvy-midnight">Assigned Keywords</CardTitle>
                    <CardDescription>Keywords currently assigned to this landscape</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {assignedKeywords.length === 0 ? (
                      <p className="text-gray-500 text-center py-8">No keywords assigned</p>
                    ) : (
                      <div className="space-y-2 max-h-80 overflow-y-auto">
                        {assignedKeywords.map(keyword => (
                          <div key={keyword.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                            <span className="font-medium">{keyword.keyword}</span>
                            {keyword.search_volume && (
                              <Badge variant="outline">{keyword.search_volume.toLocaleString()} vol</Badge>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Available Keywords */}
                <Card className="bg-white">
                  <CardHeader>
                    <CardTitle className="text-cylvy-midnight">Available Keywords</CardTitle>
                    <CardDescription>Search and assign keywords to this landscape</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="relative">
                        <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                        <Input
                          placeholder="Search keywords..."
                          value={keywordSearch}
                          onChange={(e) => searchKeywords(e.target.value)}
                          className="pl-10 bg-white text-gray-900 border-gray-300"
                        />
                      </div>

                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {availableKeywords.map(keyword => (
                          <div 
                            key={keyword.id} 
                            className={`flex items-center justify-between p-2 rounded cursor-pointer transition-colors ${
                              selectedKeywordIds.includes(keyword.id) 
                                ? 'bg-cylvy-amaranth/20 border border-cylvy-amaranth' 
                                : 'bg-gray-50 hover:bg-gray-100'
                            }`}
                            onClick={() => toggleKeywordSelection(keyword.id)}
                          >
                            <span className="font-medium">{keyword.keyword}</span>
                            <div className="flex items-center gap-2">
                              {keyword.search_volume && (
                                <Badge variant="outline" className="text-xs">
                                  {keyword.search_volume.toLocaleString()}
                                </Badge>
                              )}
                              {selectedKeywordIds.includes(keyword.id) && (
                                <Check className="h-4 w-4 text-cylvy-amaranth" />
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      {selectedKeywordIds.length > 0 && (
                        <Button 
                          onClick={assignKeywords} 
                          className="w-full cylvy-btn-primary"
                        >
                          Assign {selectedKeywordIds.length} Keywords
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          ) : (
            <div className="text-center py-12">
              <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Landscape</h3>
              <p className="text-gray-600">Choose a landscape from the Definitions tab to manage its keywords</p>
            </div>
          )}
        </TabsContent>

        {/* Historical Results Tab */}
        <TabsContent value="results" className="space-y-6 bg-transparent">
          {selectedLandscape && landscapeSummary ? (
            <>
              {/* Summary Cards */}
              <div className="grid md:grid-cols-4 gap-4">
                <Card className="bg-white">
                  <CardContent className="p-6">
                    <div className="flex items-center">
                      <div>
                        <p className="text-sm font-medium text-gray-600">Companies</p>
                        <p className="text-2xl font-bold text-cylvy-midnight">{landscapeSummary.total_companies}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-white">
                  <CardContent className="p-6">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Keywords</p>
                      <p className="text-2xl font-bold text-cylvy-midnight">{landscapeSummary.total_keywords}</p>
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-white">
                  <CardContent className="p-6">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Total Traffic</p>
                      <p className="text-2xl font-bold text-cylvy-midnight">{landscapeSummary.total_traffic.toLocaleString()}</p>
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-white">
                  <CardContent className="p-6">
                    <div>
                      <p className="text-sm font-medium text-gray-600">Top DSI Score</p>
                      <p className="text-2xl font-bold text-cylvy-midnight">{landscapeSummary.top_dsi_score.toFixed(2)}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Company Rankings */}
              <Card className="bg-white">
                <CardHeader>
                  <CardTitle className="text-cylvy-midnight">Company Rankings</CardTitle>
                  <CardDescription>Latest DSI calculations for {selectedLandscape.name}</CardDescription>
                </CardHeader>
                <CardContent>
                  {landscapeMetrics.length === 0 ? (
                    <div className="text-center py-8">
                      <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 mb-2">No Calculations Yet</h3>
                      <p className="text-gray-600 mb-4">Calculate DSI metrics to see company rankings</p>
                      <Button 
                        onClick={() => calculateDSI(selectedLandscape.id)} 
                        className="cylvy-btn-primary"
                        disabled={assignedKeywords.length === 0}
                      >
                        Calculate DSI Metrics
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {landscapeMetrics.map((metric, idx) => (
                        <div key={`${metric.entity_domain}-${idx}`} className="flex items-center justify-between p-4 border rounded-lg">
                          <div className="flex items-center gap-4">
                            <div className="w-8 h-8 bg-cylvy-amaranth/10 rounded-full flex items-center justify-center">
                              <span className="text-sm font-bold text-cylvy-amaranth">#{metric.rank_in_landscape}</span>
                            </div>
                            <div>
                              <div className="font-semibold text-gray-900">{metric.entity_name}</div>
                              <div className="text-sm text-gray-600">{metric.entity_domain}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-6">
                            <div className="text-center">
                              <div className="text-sm text-gray-500">DSI Score</div>
                              <div className="font-bold text-cylvy-midnight">{metric.dsi_score.toFixed(2)}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-sm text-gray-500">Keywords</div>
                              <div className="font-bold">{metric.unique_keywords}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-sm text-gray-500">Traffic</div>
                              <div className="font-bold">{metric.estimated_traffic.toLocaleString()}</div>
                            </div>
                            <Badge 
                              variant={metric.market_position === 'LEADER' ? 'default' : 'secondary'}
                            >
                              {metric.market_position}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="text-center py-12">
              <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Landscape</h3>
              <p className="text-gray-600">Choose a landscape to view its historical DSI results and metrics</p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Create Landscape Dialog */}
      {showCreateDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md bg-white">
            <CardHeader>
              <CardTitle className="text-cylvy-midnight">Create Digital Landscape</CardTitle>
              <CardDescription>Define a new market segment or geographical view</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
                <Input
                  placeholder="e.g., UK Market, Payments Keywords"
                  value={createForm.name}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                  className="bg-white text-gray-900 border-gray-300"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Description (Optional)</label>
                <Textarea
                  placeholder="Describe this landscape segment..."
                  value={createForm.description}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                  className="bg-white text-gray-900 border-gray-300"
                />
              </div>
            </CardContent>
            <div className="flex gap-3 p-6 pt-0">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)} className="flex-1">
                Cancel
              </Button>
              <Button onClick={createLandscape} className="flex-1 cylvy-btn-primary">
                Create Landscape
              </Button>
            </div>
          </Card>
        </div>
      )}
    </AdminLayout>
  )
}

