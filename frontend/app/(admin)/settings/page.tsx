'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
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


interface PageType {
  id: string
  name: string
  category: string
  description: string
  indicators: string[]
  buyer_journey_stage: string
}

export default function DefaultDimensionsPage() {
  const [jtbdPhases, setJtbdPhases] = useState<JTBDPhase[]>([])
  const [pageTypes, setPageTypes] = useState<PageType[]>([])
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


  // Default B2B page types
  const defaultPageTypes: PageType[] = [
    {
      id: 'homepage',
      name: 'Homepage',
      category: 'Core Website Pages',
      description: 'Main landing page with hero sections and value propositions',
      indicators: ['hero section', 'value proposition', 'main navigation', 'company overview'],
      buyer_journey_stage: 'awareness'
    },
    {
      id: 'product_landing',
      name: 'Product/Solution Landing',
      category: 'Product & Solution Pages',
      description: 'Main product or solution overview pages',
      indicators: ['product features', 'benefits list', 'pricing tiers', 'demo CTA'],
      buyer_journey_stage: 'consideration'
    },
    {
      id: 'feature_page',
      name: 'Feature/Capability Page',
      category: 'Product & Solution Pages',
      description: 'Detailed pages about specific features or capabilities',
      indicators: ['feature details', 'use cases', 'technical specs', 'integration info'],
      buyer_journey_stage: 'evaluation'
    },
    {
      id: 'pricing',
      name: 'Pricing Page',
      category: 'Conversion Pages',
      description: 'Pricing tiers, plans, and purchasing options',
      indicators: ['pricing tables', 'plan comparison', 'calculator', 'contact sales'],
      buyer_journey_stage: 'decision'
    },
    {
      id: 'case_study',
      name: 'Case Study',
      category: 'Trust & Proof Content',
      description: 'Customer success stories and implementation examples',
      indicators: ['customer quotes', 'results metrics', 'challenge-solution', 'ROI data'],
      buyer_journey_stage: 'validation'
    },
    {
      id: 'blog_post',
      name: 'Blog Post',
      category: 'Educational Content',
      description: 'Thought leadership and educational articles',
      indicators: ['publish date', 'author bio', 'related posts', 'comments section'],
      buyer_journey_stage: 'awareness'
    },
    {
      id: 'resource_hub',
      name: 'Resource Hub/Library',
      category: 'Content Hubs',
      description: 'Central repository for downloadable content',
      indicators: ['content filters', 'download gates', 'resource cards', 'search functionality'],
      buyer_journey_stage: 'research'
    },
    {
      id: 'comparison',
      name: 'Comparison/Vs Page',
      category: 'Competitive Content',
      description: 'Direct comparisons with competitors or alternatives',
      indicators: ['comparison table', 'differentiators', 'switching guide', 'competitor names'],
      buyer_journey_stage: 'evaluation'
    },
    {
      id: 'landing_page',
      name: 'Campaign Landing Page',
      category: 'Conversion Pages',
      description: 'Focused pages for specific campaigns or offers',
      indicators: ['single offer', 'form above fold', 'limited navigation', 'urgency elements'],
      buyer_journey_stage: 'conversion'
    },
    {
      id: 'demo_request',
      name: 'Demo/Trial Request',
      category: 'Conversion Pages',
      description: 'Pages focused on demo or trial sign-ups',
      indicators: ['demo form', 'calendar booking', 'trial benefits', 'qualification questions'],
      buyer_journey_stage: 'decision'
    }
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


      // Load page types from analysis config
      try {
        const configResponse = await fetch('/api/v1/analysis/config', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        
        if (configResponse.ok) {
          const configData = await configResponse.json()
          setPageTypes(configData.page_types || defaultPageTypes)
        } else {
          setPageTypes(defaultPageTypes)
        }
      } catch (e) {
        setPageTypes(defaultPageTypes)
      }

    } catch (error) {
      console.error('Failed to load settings:', error)
      setJtbdPhases(gartnerJTBDPhases)
      setPageTypes(defaultPageTypes)
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


  const savePageTypes = async () => {
    try {
      setSaveStatus('saving')
      setError('')
      const token = localStorage.getItem('access_token')
      
      // Save page types as part of the analysis config
      const response = await fetch('/api/v1/analysis/config', {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ page_types: pageTypes })
      })

      if (response.ok) {
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } else {
        throw new Error('Failed to save page types')
      }
    } catch (error) {
      console.error('Failed to save page types:', error)
      setError('Failed to save page types. Please try again.')
      setSaveStatus('error')
    }
  }

  const resetToDefaults = () => {
    if (confirm('Reset JTBD phases to default values?')) {
      setJtbdPhases([...gartnerJTBDPhases])
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
    <AdminLayout title="Default Dimensions" description="Configure JTBD phases and B2B page types">
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
            <TabsTrigger value="page-types" className="flex items-center gap-2">
              <Layers className="h-4 w-4" />
              B2B Page Types
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
                      onClick={() => resetToDefaults()}
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


          {/* Page Types Configuration */}
          <TabsContent value="page-types" className="space-y-4 bg-transparent text-gray-900">
            <Card className="cylvy-card">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-cylvy-midnight">B2B Page Types</CardTitle>
                    <CardDescription>
                      Define the primary B2B content and page types for analysis
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      onClick={() => setPageTypes(defaultPageTypes)}
                      className="text-gray-600"
                    >
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Reset to Defaults
                    </Button>
                    <Button 
                      onClick={savePageTypes} 
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
                <div className="space-y-6">
                  {Object.entries(
                    pageTypes.reduce((acc, pageType) => {
                      if (!acc[pageType.category]) acc[pageType.category] = []
                      acc[pageType.category].push(pageType)
                      return acc
                    }, {} as Record<string, PageType[]>)
                  ).map(([category, types]) => (
                    <div key={category} className="space-y-3">
                      <h4 className="font-medium text-sm text-gray-700 uppercase tracking-wider">{category}</h4>
                      <div className="space-y-3">
                        {types.map((pageType) => (
                          <div key={pageType.id} className="p-4 border rounded-lg bg-gray-50/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1 space-y-2">
                                <div>
                                  <h5 className="font-medium text-gray-900">{pageType.name}</h5>
                                  <p className="text-sm text-gray-600">{pageType.description}</p>
                                </div>
                                <div className="flex items-center gap-4 text-xs">
                                  <span className="text-gray-500">Buyer Stage:</span>
                                  <Badge variant="outline" className="capitalize">
                                    {pageType.buyer_journey_stage}
                                  </Badge>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">Key Indicators:</p>
                                  <div className="flex flex-wrap gap-1">
                                    {pageType.indicators.map((indicator, idx) => (
                                      <Badge key={idx} variant="secondary" className="text-xs">
                                        {indicator}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                  <h4 className="font-medium text-sm mb-2 text-blue-900">About Page Types</h4>
                  <div className="text-xs text-blue-700 space-y-1">
                    <div>• Page types help the AI identify and classify B2B content</div>
                    <div>• Each type is aligned with specific buyer journey stages</div>
                    <div>• Key indicators are used to recognize page patterns</div>
                    <div>• These are used alongside JTBD phases for comprehensive analysis</div>
                  </div>
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
              <strong className="text-cylvy-amaranth">B2B Page Types:</strong> Identify and classify different types of B2B content.
              The AI uses these definitions to understand page structure and purpose, aligned with buyer journey stages.
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
