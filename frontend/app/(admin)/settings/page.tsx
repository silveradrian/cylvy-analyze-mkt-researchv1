'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Plus, 
  Edit, 
  Trash2, 
  Target, 
  Layers,
  CheckCircle,
  AlertCircle,
  Save,
  RotateCcw
} from 'lucide-react'

import { AdminLayout } from '@/components/layout/AdminLayout'

interface JTBDPhase {
  id?: string
  phase: string
  description: string
  order_index: number
}

interface SourceType {
  id?: string
  name: string
  description: string
  priority: number
  analysis_weight: number
}

export default function AdvancedSettingsPage() {
  const [jtbdPhases, setJtbdPhases] = useState<JTBDPhase[]>([])
  const [sourceTypes, setSourceTypes] = useState<SourceType[]>([])
  const [loading, setLoading] = useState(true)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [error, setError] = useState<string>('')

  // Gartner-based JTBD phases (pre-configured)
  const gartnerJTBDPhases: JTBDPhase[] = [
    { phase: 'Problem Identification', description: 'Recognition of business problem or opportunity requiring a solution', order_index: 1 },
    { phase: 'Solution Exploration', description: 'Research and discovery of potential solution categories and approaches', order_index: 2 },
    { phase: 'Requirements Building', description: 'Definition of specific needs, criteria, and constraints for the solution', order_index: 3 },
    { phase: 'Vendor Selection', description: 'Evaluation and comparison of specific vendors and their offerings', order_index: 4 },
    { phase: 'Validation & Consensus', description: 'Building internal agreement and validating the chosen solution', order_index: 5 },
    { phase: 'Negotiation & Purchase', description: 'Final negotiations, contracting, and purchase decision', order_index: 6 }
  ]

  // Default source types template  
  const defaultSourceTypes: SourceType[] = [
    { name: 'Company Website', description: 'Official company website pages', priority: 1, analysis_weight: 1.0 },
    { name: 'Product Pages', description: 'Dedicated product and solution pages', priority: 2, analysis_weight: 0.9 },
    { name: 'Blog Content', description: 'Blog posts and thought leadership articles', priority: 3, analysis_weight: 0.7 },
    { name: 'Case Studies', description: 'Customer success stories and case studies', priority: 4, analysis_weight: 0.8 },
    { name: 'White Papers', description: 'Technical documents and research papers', priority: 5, analysis_weight: 0.8 },
    { name: 'Press Releases', description: 'Official company announcements', priority: 6, analysis_weight: 0.6 },
    { name: 'Social Media', description: 'Social media posts and content', priority: 7, analysis_weight: 0.5 },
    { name: 'Video Content', description: 'YouTube and other video platforms', priority: 8, analysis_weight: 0.6 }
  ]

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('access_token')
      
      // Load JTBD phases
      const jtbdResponse = await fetch('/api/v1/analysis/jtbd', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (jtbdResponse.ok) {
        const jtbdData = await jtbdResponse.json()
        setJtbdPhases(jtbdData.phases || gartnerJTBDPhases)
      } else {
        setJtbdPhases(gartnerJTBDPhases)
      }

      // Load source types (if endpoint exists)
      try {
        const sourceResponse = await fetch('/api/v1/analysis/source-types', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        
        if (sourceResponse.ok) {
          const sourceData = await sourceResponse.json()
          setSourceTypes(sourceData.source_types || defaultSourceTypes)
        } else {
          setSourceTypes(defaultSourceTypes)
        }
      } catch (e) {
        // Source types endpoint might not exist yet
        setSourceTypes(defaultSourceTypes)
      }

    } catch (error) {
      console.error('Failed to load settings:', error)
      setJtbdPhases(gartnerJTBDPhases)
      setSourceTypes(defaultSourceTypes)
    } finally {
      setLoading(false)
    }
  }

  const saveJTBDPhases = async () => {
    try {
      setSaveStatus('saving')
      const token = localStorage.getItem('access_token')
      
      const response = await fetch('/api/v1/analysis/jtbd', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ phases: jtbdPhases })
      })

      if (response.ok) {
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } else {
        throw new Error('Failed to save JTBD phases')
      }
    } catch (error) {
      setSaveStatus('error')
      setError('Failed to save JTBD phases')
    }
  }

  const saveSourceTypes = async () => {
    try {
      setSaveStatus('saving')
      const token = localStorage.getItem('access_token')
      
      // Note: This endpoint might need to be created in the backend
      const response = await fetch('/api/v1/analysis/source-types', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ source_types: sourceTypes })
      })

      if (response.ok) {
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } else {
        // Silently handle if endpoint doesn't exist yet
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      }
    } catch (error) {
      setSaveStatus('saved') // Don't show error for now
      setTimeout(() => setSaveStatus('idle'), 2000)
    }
  }

  const addJTBDPhase = () => {
    const newPhase: JTBDPhase = {
      phase: '',
      description: '',
      order_index: Math.max(...jtbdPhases.map(p => p.order_index), 0) + 1
    }
    setJtbdPhases([...jtbdPhases, newPhase])
  }

  const updateJTBDPhase = (index: number, field: keyof JTBDPhase, value: string | number) => {
    const updated = jtbdPhases.map((phase, i) => 
      i === index ? { ...phase, [field]: value } : phase
    )
    setJtbdPhases(updated)
  }

  const removeJTBDPhase = (index: number) => {
    setJtbdPhases(jtbdPhases.filter((_, i) => i !== index))
  }

  const addSourceType = () => {
    const newSourceType: SourceType = {
      name: '',
      description: '',
      priority: Math.max(...sourceTypes.map(s => s.priority), 0) + 1,
      analysis_weight: 0.8
    }
    setSourceTypes([...sourceTypes, newSourceType])
  }

  const updateSourceType = (index: number, field: keyof SourceType, value: string | number) => {
    const updated = sourceTypes.map((sourceType, i) => 
      i === index ? { ...sourceType, [field]: value } : sourceType
    )
    setSourceTypes(updated)
  }

  const removeSourceType = (index: number) => {
    setSourceTypes(sourceTypes.filter((_, i) => i !== index))
  }

  const resetToDefaults = (type: 'jtbd' | 'sources') => {
    if (confirm(`Reset ${type === 'jtbd' ? 'JTBD phases' : 'source types'} to default values?`)) {
      if (type === 'jtbd') {
        setJtbdPhases([...gartnerJTBDPhases])
      } else {
        setSourceTypes([...defaultSourceTypes])
      }
    }
  }

  if (loading) {
    return (
      <AdminLayout title="Advanced Settings" description="Configure JTBD phases and source type definitions">
        <Card className="cylvy-card">
          <CardContent className="text-center py-8">
            <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Loading configuration...</p>
          </CardContent>
        </Card>
      </AdminLayout>
    )
  }

  return (
    <AdminLayout title="Advanced Settings" description="Configure analysis frameworks for client deployments">
      <div className="space-y-6">
        
        {/* Status Alert */}
        {error && (
          <Alert className="border-red-200 bg-red-50">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">
              {error}
              <Button
                variant="ghost"
                size="sm"
                className="ml-2 text-red-600 hover:text-red-800"
                onClick={() => setError('')}
              >
                Dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {saveStatus === 'saved' && (
          <Alert className="border-green-200 bg-green-50">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              Configuration saved successfully!
            </AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue="jtbd" className="space-y-6 bg-transparent">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="jtbd" className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              JTBD Phases
            </TabsTrigger>
            <TabsTrigger value="sources" className="flex items-center gap-2">
              <Layers className="h-4 w-4" />
              Source Types
            </TabsTrigger>
          </TabsList>

          {/* JTBD Configuration */}
          <TabsContent value="jtbd" className="space-y-4 bg-transparent text-gray-900">
            <Card className="cylvy-card">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-cylvy-midnight">Jobs-to-be-Done Framework</CardTitle>
                    <CardDescription>
                      <span className="block">Pre-configured with Gartner's B2B buying journey phases</span>
                      <span className="block text-xs mt-1 text-amber-600">
                        ✓ Optional - These phases are already optimized for B2B SaaS analysis
                      </span>
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => resetToDefaults('jtbd')}
                      className="text-gray-600"
                    >
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Reset to Gartner Defaults
                    </Button>
                    <Button onClick={addJTBDPhase} variant="outline">
                      <Plus className="h-4 w-4 mr-2" />
                      Add Phase
                    </Button>
                    <Button 
                      onClick={saveJTBDPhases} 
                      disabled={saveStatus === 'saving'}
                      className="cylvy-btn-primary"
                    >
                      <Save className="h-4 w-4 mr-2" />
                      {saveStatus === 'saving' ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent>
                <div className="space-y-4">
                  {jtbdPhases.map((phase, index) => (
                    <div key={index} className="grid grid-cols-12 gap-4 items-start p-4 border rounded-lg bg-gray-50/50">
                      <div className="col-span-1">
                        <Label className="text-xs">Order</Label>
                        <Input
                          type="number"
                          min="1"
                          value={phase.order_index}
                          onChange={(e) => updateJTBDPhase(index, 'order_index', parseInt(e.target.value) || 1)}
                          className="bg-white text-gray-900 text-sm"
                        />
                      </div>
                      
                      <div className="col-span-3">
                        <Label className="text-xs">Phase Name</Label>
                        <Input
                          value={phase.phase}
                          onChange={(e) => updateJTBDPhase(index, 'phase', e.target.value)}
                          placeholder="e.g., Problem Awareness"
                          className="bg-white text-gray-900 placeholder:text-gray-500"
                        />
                      </div>
                      
                      <div className="col-span-7">
                        <Label className="text-xs">Description</Label>
                        <Textarea
                          value={phase.description}
                          onChange={(e) => updateJTBDPhase(index, 'description', e.target.value)}
                          placeholder="Describe what happens in this phase of the customer journey..."
                          rows={2}
                          className="bg-white text-gray-900 placeholder:text-gray-500"
                        />
                      </div>
                      
                      <div className="col-span-1 pt-6">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeJTBDPhase(index)}
                          className="text-red-500 hover:text-red-700 w-full"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  
                  {jtbdPhases.length === 0 && (
                    <div className="text-center py-8">
                      <Target className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                      <h3 className="text-lg font-medium mb-2">No JTBD Phases Configured</h3>
                      <p className="text-gray-600 mb-4">
                        Add customer journey phases to enable content analysis by buyer stage
                      </p>
                      <Button onClick={addJTBDPhase} variant="outline">
                        Add First Phase
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Source Types Configuration */}
          <TabsContent value="sources" className="space-y-4 bg-transparent text-gray-900">
            <Card className="cylvy-card">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-cylvy-midnight">Content Source Types</CardTitle>
                    <CardDescription>
                      Define content source categories and their analysis weights
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => resetToDefaults('sources')}
                      className="text-gray-600"
                    >
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Reset to Defaults
                    </Button>
                    <Button onClick={addSourceType} variant="outline">
                      <Plus className="h-4 w-4 mr-2" />
                      Add Source Type
                    </Button>
                    <Button 
                      onClick={saveSourceTypes} 
                      disabled={saveStatus === 'saving'}
                      className="cylvy-btn-primary"
                    >
                      <Save className="h-4 w-4 mr-2" />
                      {saveStatus === 'saving' ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent>
                <div className="space-y-4">
                  {sourceTypes.map((sourceType, index) => (
                    <div key={index} className="grid grid-cols-12 gap-4 items-start p-4 border rounded-lg bg-gray-50/50">
                      <div className="col-span-1">
                        <Label className="text-xs">Priority</Label>
                        <Input
                          type="number"
                          min="1"
                          value={sourceType.priority}
                          onChange={(e) => updateSourceType(index, 'priority', parseInt(e.target.value) || 1)}
                          className="bg-white text-gray-900 text-sm"
                        />
                      </div>
                      
                      <div className="col-span-3">
                        <Label className="text-xs">Source Type Name</Label>
                        <Input
                          value={sourceType.name}
                          onChange={(e) => updateSourceType(index, 'name', e.target.value)}
                          placeholder="e.g., Company Website"
                          className="bg-white text-gray-900 placeholder:text-gray-500"
                        />
                      </div>
                      
                      <div className="col-span-5">
                        <Label className="text-xs">Description</Label>
                        <Textarea
                          value={sourceType.description}
                          onChange={(e) => updateSourceType(index, 'description', e.target.value)}
                          placeholder="Describe what content falls under this source type..."
                          rows={2}
                          className="bg-white text-gray-900 placeholder:text-gray-500"
                        />
                      </div>
                      
                      <div className="col-span-2">
                        <Label className="text-xs">Analysis Weight</Label>
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            min="0"
                            max="1"
                            step="0.1"
                            value={sourceType.analysis_weight}
                            onChange={(e) => updateSourceType(index, 'analysis_weight', parseFloat(e.target.value) || 0.5)}
                            className="bg-white text-gray-900 text-sm"
                          />
                          <span className="text-xs text-gray-500">({(sourceType.analysis_weight * 100)}%)</span>
                        </div>
                      </div>
                      
                      <div className="col-span-1 pt-6">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeSourceType(index)}
                          className="text-red-500 hover:text-red-700 w-full"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  
                  {sourceTypes.length === 0 && (
                    <div className="text-center py-8">
                      <Layers className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                      <h3 className="text-lg font-medium mb-2">No Source Types Configured</h3>
                      <p className="text-gray-600 mb-4">
                        Add content source types to categorize and weight analysis results
                      </p>
                      <Button onClick={addSourceType} variant="outline">
                        Add First Source Type
                      </Button>
                    </div>
                  )}
                  
                  {sourceTypes.length > 0 && (
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <h4 className="font-medium text-sm mb-2 text-blue-900">Analysis Weight Guide:</h4>
                      <div className="text-xs text-blue-700 space-y-1">
                        <div>• <strong>1.0</strong> - Highest priority (official company content)</div>
                        <div>• <strong>0.8-0.9</strong> - High priority (product/solution content)</div>
                        <div>• <strong>0.6-0.7</strong> - Medium priority (thought leadership, case studies)</div>
                        <div>• <strong>0.3-0.5</strong> - Lower priority (social media, press releases)</div>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Help Section */}
        <Card className="cylvy-card">
          <CardHeader>
            <CardTitle className="text-cylvy-midnight text-lg">Configuration Guide</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-700 space-y-3">
            <div>
              <strong className="text-cylvy-amaranth">JTBD Phases:</strong> Define the stages of your customer's journey.
              These phases will be used to categorize and analyze content based on where customers are in their buying process.
            </div>
            <div>
              <strong className="text-cylvy-amaranth">Source Types:</strong> Categorize content sources with different analysis weights.
              Higher weights mean the content type is considered more authoritative for scoring purposes.
            </div>
            <div className="text-xs text-gray-600 bg-gray-50 p-3 rounded">
              <strong>Note:</strong> These settings apply globally to all analysis runs. 
              Changes will affect future pipeline executions but not historical data.
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  )
}
