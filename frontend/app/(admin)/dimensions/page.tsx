'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { 
  Plus, 
  Edit, 
  Trash2, 
  Target, 
  Settings,
  CheckCircle,
  AlertCircle
} from 'lucide-react'

import { AdminLayout } from '@/components/layout/AdminLayout'

interface CustomDimension {
  id?: string
  name: string
  description: string
  scoring_levels: Array<{
    level: number
    label: string
    description: string
  }>
  evidence_config: {
    required_evidence_types: string[]
    evidence_weight: number
    minimum_evidence_score: number
  }
}

export default function CustomDimensionsPage() {
  const [dimensions, setDimensions] = useState<CustomDimension[]>([])
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [editingDimension, setEditingDimension] = useState<CustomDimension | null>(null)
  const [loading, setLoading] = useState(true)

  // Generic Custom Dimension Templates
  const genericTemplates = [
    {
      name: 'Customer Focus',
      description: 'Measures how well content demonstrates genuine customer-centric practices and outcomes.',
      scoring_levels: [
        { level: 0, label: 'Generic Claims', description: 'Generic customer language without specific mechanisms or outcomes' },
        { level: 5, label: 'Shows Mechanisms', description: 'Describes specific customer engagement mechanisms and at least one concrete action' },
        { level: 10, label: 'Proven Results', description: 'Documented customer programs with quantified outcomes and continuous improvement' }
      ],
      evidence_config: {
        required_evidence_types: ['customer_programs', 'outcomes', 'mechanisms'],
        evidence_weight: 0.7,
        minimum_evidence_score: 3
      }
    },
    {
      name: 'Security & Trust',
      description: 'Evaluates security practices, compliance certifications, and trustworthiness indicators.',
      scoring_levels: [
        { level: 0, label: 'Security Claims', description: 'General security or trust claims without specifics' },
        { level: 5, label: 'Multiple Controls', description: 'Multiple security controls, certifications, or clear compliance practices' },
        { level: 10, label: 'Comprehensive Program', description: 'Comprehensive security program with certifications and continuous improvement evidence' }
      ],
      evidence_config: {
        required_evidence_types: ['certifications', 'security_controls', 'compliance'],
        evidence_weight: 0.8,
        minimum_evidence_score: 4
      }
    },
    {
      name: 'Innovation & Partnerships',
      description: 'Assesses collaborative innovation practices and partnership ecosystem development.',
      scoring_levels: [
        { level: 0, label: 'Innovation Claims', description: 'General innovation rhetoric without concrete examples' },
        { level: 5, label: 'Concrete Programs', description: 'Specific innovation programs, pilots, or partnership initiatives with details' },
        { level: 10, label: 'Proven Ecosystem', description: 'Established innovation framework with multiple shipped outcomes and active partnerships' }
      ],
      evidence_config: {
        required_evidence_types: ['innovation_programs', 'partnerships', 'shipped_outcomes'],
        evidence_weight: 0.6,
        minimum_evidence_score: 3
      }
    }
  ]

  const [formData, setFormData] = useState<CustomDimension>({
    name: '',
    description: '',
    scoring_levels: [
      { level: 0, label: '', description: '' },
      { level: 5, label: '', description: '' },
      { level: 10, label: '', description: '' }
    ],
    evidence_config: {
      required_evidence_types: [],
      evidence_weight: 0.7,
      minimum_evidence_score: 3
    }
  })

  useEffect(() => {
    loadDimensions()
  }, [])

  const loadDimensions = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/generic-dimensions', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setDimensions(data.dimensions || [])
      }
    } catch (error) {
      console.error('Failed to load dimensions:', error)
    } finally {
      setLoading(false)
    }
  }

  const createFromTemplate = (template: CustomDimension) => {
    setFormData(template)
    setShowCreateDialog(true)
  }

  const saveDimension = async () => {
    try {
      const token = localStorage.getItem('access_token')
      const method = editingDimension ? 'PUT' : 'POST'
      const url = editingDimension 
        ? `/api/v1/generic-dimensions/${editingDimension.id}`
        : '/api/v1/generic-dimensions'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      })

      if (response.ok) {
        await loadDimensions()
        setShowCreateDialog(false)
        setEditingDimension(null)
        resetForm()
      }
    } catch (error) {
      console.error('Failed to save dimension:', error)
    }
  }

  const deleteDimension = async (dimensionId: string) => {
    if (confirm('Are you sure you want to delete this dimension?')) {
      try {
        const token = localStorage.getItem('access_token')
        await fetch(`/api/v1/generic-dimensions/${dimensionId}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        })
        await loadDimensions()
      } catch (error) {
        console.error('Failed to delete dimension:', error)
      }
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      scoring_levels: [
        { level: 0, label: '', description: '' },
        { level: 5, label: '', description: '' },
        { level: 10, label: '', description: '' }
      ],
      evidence_config: {
        required_evidence_types: [],
        evidence_weight: 0.7,
        minimum_evidence_score: 3
      }
    })
  }

  return (
    <AdminLayout title="Custom Dimensions" description="Manage Strategic Pillars and Advanced Analysis Dimensions">
      <div className="max-w-6xl mx-auto">
        <Tabs defaultValue="dimensions" className="space-y-6 bg-transparent">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="dimensions" className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              Custom Dimensions
            </TabsTrigger>
            <TabsTrigger value="templates" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Common Templates
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dimensions" className="space-y-4 bg-transparent">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-cylvy-midnight">Configured Dimensions</h2>
                <p className="text-gray-600 mt-1">
                  Manage your custom analysis dimensions for advanced content scoring
                </p>
              </div>
              <Button onClick={() => setShowCreateDialog(true)} className="cylvy-btn-primary">
                <Plus className="h-4 w-4 mr-2" />
                Create Dimension
              </Button>
            </div>

            {loading ? (
              <Card>
                <CardContent className="text-center py-8">
                  <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                  <p>Loading dimensions...</p>
                </CardContent>
              </Card>
            ) : dimensions.length === 0 ? (
              <Card className="bg-white">
                <CardContent className="text-center py-8 bg-white">
                  <Target className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                  <h3 className="text-lg font-medium mb-2 text-gray-900">No Custom Dimensions</h3>
                  <p className="text-gray-600 mb-4">
                    Create your first custom dimension to enable advanced analysis scoring
                  </p>
                  <div className="space-y-2 bg-white">
                    <Button onClick={() => setShowCreateDialog(true)} className="cylvy-btn-primary">
                      Create First Dimension
                    </Button>
                    <p className="text-sm text-gray-500">
                      Or use a Strategic Pillar template →
                    </p>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4">
                {dimensions.map((dimension) => (
                  <Card key={dimension.id || dimension.name} className="cylvy-card-hover">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <CardTitle className="text-cylvy-midnight">{dimension.name}</CardTitle>
                          <CardDescription>{dimension.description}</CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary">
                            {dimension.scoring_levels.length} levels
                          </Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingDimension(dimension)
                              setFormData(dimension)
                              setShowCreateDialog(true)
                            }}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteDimension(dimension.id!)}
                            className="text-red-500 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    
                    <CardContent>
                      <div className="space-y-3">
                        <div>
                          <h4 className="font-medium text-sm mb-2">Scoring Levels:</h4>
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                            {dimension.scoring_levels.map((level) => (
                              <div key={level.level} className="text-xs p-2 bg-gray-50 rounded">
                                <div className="font-medium">{level.level}/10 - {level.label}</div>
                                <div className="text-gray-600">{level.description}</div>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>
                            <span className="text-gray-500">Evidence Types:</span>
                            <div className="font-medium">
                              {dimension.evidence_config.required_evidence_types.length} types
                            </div>
                          </div>
                          <div>
                            <span className="text-gray-500">Evidence Weight:</span>
                            <div className="font-medium">
                              {(dimension.evidence_config.evidence_weight * 100)}%
                            </div>
                          </div>
                          <div>
                            <span className="text-gray-500">Min Score:</span>
                            <div className="font-medium">
                              {dimension.evidence_config.minimum_evidence_score}/10
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="templates" className="space-y-4 bg-transparent">
            <div>
              <h2 className="text-2xl font-bold text-cylvy-midnight mb-4">Common Dimension Templates</h2>
              <p className="text-gray-600 mb-6">
                Ready-made custom dimensions for common business analysis scenarios. 
                Click to create and customize for your specific analysis needs.
              </p>
            </div>

            <div className="grid gap-4">
              {genericTemplates.map((template, index) => (
                <Card key={template.name} className="cylvy-card-hover">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-cylvy-amaranth">{template.name}</CardTitle>
                        <CardDescription className="mt-2">{template.description}</CardDescription>
                      </div>
                      <Button
                        onClick={() => createFromTemplate(template)}
                        className="cylvy-btn-secondary"
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Use Template
                      </Button>
                    </div>
                  </CardHeader>
                  
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <h4 className="font-medium text-sm mb-2">Scoring Framework:</h4>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                          {template.scoring_levels.slice(0, 3).map((level) => (
                            <div key={level.level} className="text-xs p-2 bg-cylvy-amaranth/5 border border-cylvy-amaranth/20 rounded">
                              <div className="font-medium text-cylvy-amaranth">{level.level}/10 - {level.label}</div>
                              <div className="text-gray-600">{level.description.substring(0, 50)}...</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="flex gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <CheckCircle className="h-4 w-4 text-green-500" />
                          <span>{template.evidence_config.required_evidence_types.length} Evidence Types</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <AlertCircle className="h-4 w-4 text-blue-500" />
                          <span>{(template.evidence_config.evidence_weight * 100)}% Evidence Weight</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>

        {/* Create/Edit Dialog */}
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingDimension ? 'Edit Custom Dimension' : 'Create Custom Dimension'}
              </DialogTitle>
              <DialogDescription>
                Define a custom dimension for advanced content analysis and scoring
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <Label htmlFor="dimension_name">Dimension Name</Label>
                  <Input
                    id="dimension_name"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g., Customer Obsession"
                    className="bg-white text-gray-900"
                  />
                </div>
                
                <div>
                  <Label htmlFor="dimension_description">Description</Label>
                  <Textarea
                    id="dimension_description"
                    value={formData.description}
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe what this dimension measures..."
                    rows={3}
                    className="bg-white text-gray-900"
                  />
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-4">Scoring Levels</h4>
                <div className="space-y-3">
                  {formData.scoring_levels.map((level, index) => (
                    <div key={index} className="grid grid-cols-12 gap-4 items-start p-3 border rounded-lg">
                      <div className="col-span-1">
                        <Label>Score</Label>
                        <Input
                          type="number"
                          min="0"
                          max="10"
                          value={level.level}
                          onChange={(e) => {
                            const updated = [...formData.scoring_levels]
                            updated[index].level = parseInt(e.target.value) || 0
                            setFormData(prev => ({ ...prev, scoring_levels: updated }))
                          }}
                          className="bg-white text-gray-900"
                        />
                      </div>
                      <div className="col-span-3">
                        <Label>Label</Label>
                        <Input
                          value={level.label}
                          onChange={(e) => {
                            const updated = [...formData.scoring_levels]
                            updated[index].label = e.target.value
                            setFormData(prev => ({ ...prev, scoring_levels: updated }))
                          }}
                          placeholder="e.g., Generic Claims"
                          className="bg-white text-gray-900"
                        />
                      </div>
                      <div className="col-span-8">
                        <Label>Description</Label>
                        <Input
                          value={level.description}
                          onChange={(e) => {
                            const updated = [...formData.scoring_levels]
                            updated[index].description = e.target.value
                            setFormData(prev => ({ ...prev, scoring_levels: updated }))
                          }}
                          placeholder="Describe what qualifies for this score level..."
                          className="bg-white text-gray-900"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={saveDimension} className="cylvy-btn-primary">
                  {editingDimension ? 'Update Dimension' : 'Create Dimension'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  )
}
