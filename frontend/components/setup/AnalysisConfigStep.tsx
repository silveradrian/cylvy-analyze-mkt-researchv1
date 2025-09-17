'use client'

import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Plus, 
  X, 
  Target, 
  Building, 
  Layers,
  AlertCircle,
  CheckCircle,
  Info
} from 'lucide-react'

interface AnalysisConfigStepProps {
  data: any
  onComplete: (data: any) => void
  onBack?: () => void
}

interface CustomDimension {
  name: string
  description: string
  scoring_levels: Array<{
    level: number
    label: string
    description: string
  }>
  evidence_types: string[]
  group_id?: string
}

interface DimensionGroup {
  id: string
  name: string
  description: string
  selection_strategy: 'highest_score' | 'highest_confidence' | 'most_evidence' | 'manual'
  color?: string
  icon?: string
}

// Pre-defined dimension groups (examples - fully customizable)
const DEFAULT_GROUPS: DimensionGroup[] = [
  {
    id: 'content_style',
    name: 'Content Style & Tone',
    description: 'Writing style, tone of voice, and communication approach',
    selection_strategy: 'highest_confidence',
    color: '#8B5CF6',
    icon: 'PenTool'
  },
  {
    id: 'audience_alignment',
    name: 'Audience Targeting',
    description: 'How well content aligns with different audience segments',
    selection_strategy: 'highest_score',
    color: '#3B82F6',
    icon: 'Users'
  },
  {
    id: 'information_quality',
    name: 'Information Quality',
    description: 'Depth, accuracy, and completeness of information',
    selection_strategy: 'most_evidence',
    color: '#10B981',
    icon: 'FileText'
  },
  {
    id: 'engagement_factors',
    name: 'Engagement & Impact',
    description: 'Factors that drive reader engagement and action',
    selection_strategy: 'highest_score',
    color: '#F59E0B',
    icon: 'TrendingUp'
  }
]

// Pre-defined dimension templates showing diverse content attributes
const DIMENSION_TEMPLATES = [
  {
    name: 'Professional Tone',
    description: 'Measures professional and authoritative tone in writing',
    group_id: 'content_style',
    scoring_levels: [
      { level: 0, label: 'Casual/Informal', description: 'Very casual or unprofessional tone' },
      { level: 5, label: 'Business Appropriate', description: 'Standard business communication' },
      { level: 10, label: 'Executive Level', description: 'Highly professional, C-suite appropriate' }
    ],
    evidence_types: ['formal language', 'industry terminology', 'data-backed claims', 'structured arguments', 'professional citations']
  },
  {
    name: 'Technical Depth',
    description: 'Evaluates the technical sophistication and detail level',
    group_id: 'information_quality',
    scoring_levels: [
      { level: 0, label: 'Surface Level', description: 'High-level overview only' },
      { level: 5, label: 'Practitioner Detail', description: 'Good technical detail for practitioners' },
      { level: 10, label: 'Expert Deep Dive', description: 'Comprehensive technical documentation' }
    ],
    evidence_types: ['code examples', 'architecture diagrams', 'performance metrics', 'implementation details', 'edge cases']
  },
  {
    name: 'Storytelling Quality',
    description: 'Assesses narrative structure and engagement techniques',
    group_id: 'engagement_factors',
    scoring_levels: [
      { level: 0, label: 'No Narrative', description: 'Pure facts without story' },
      { level: 5, label: 'Basic Narrative', description: 'Some storytelling elements' },
      { level: 10, label: 'Compelling Story', description: 'Masterful storytelling that captivates' }
    ],
    evidence_types: ['customer stories', 'problem-solution narrative', 'emotional hooks', 'relatable examples', 'journey mapping']
  },
  {
    name: 'Accessibility Level',
    description: 'How accessible the content is to non-experts',
    group_id: 'audience_alignment',
    scoring_levels: [
      { level: 0, label: 'Expert Only', description: 'Requires deep domain knowledge' },
      { level: 5, label: 'Intermediate Friendly', description: 'Accessible with some background' },
      { level: 10, label: 'Beginner Friendly', description: 'Anyone can understand' }
    ],
    evidence_types: ['plain language', 'analogies', 'glossary terms', 'visual aids', 'step-by-step explanations']
  },
  {
    name: 'Emotional Appeal',
    description: 'Measures emotional resonance and human connection',
    group_id: 'content_style',
    scoring_levels: [
      { level: 0, label: 'Purely Logical', description: 'Facts only, no emotion' },
      { level: 5, label: 'Balanced', description: 'Mix of logic and emotion' },
      { level: 10, label: 'Highly Emotional', description: 'Strong emotional connection' }
    ],
    evidence_types: ['empathy statements', 'personal anecdotes', 'inspirational messaging', 'human impact stories', 'aspirational language']
  },
  {
    name: 'Data Richness',
    description: 'Quantity and quality of data, statistics, and evidence',
    group_id: 'information_quality',
    scoring_levels: [
      { level: 0, label: 'Opinion Based', description: 'Mostly opinions without data' },
      { level: 5, label: 'Some Data', description: 'Includes relevant statistics' },
      { level: 10, label: 'Data Driven', description: 'Comprehensive data and research' }
    ],
    evidence_types: ['statistics', 'research citations', 'benchmarks', 'survey results', 'case study metrics', 'ROI data']
  }
]

export default function AnalysisConfigStep({ data, onComplete, onBack }: AnalysisConfigStepProps) {
  const [dimensions, setDimensions] = useState<CustomDimension[]>(data.custom_dimensions || [])
  const [dimensionGroups, setDimensionGroups] = useState<DimensionGroup[]>(data.dimension_groups || DEFAULT_GROUPS)
  const [editingDimension, setEditingDimension] = useState<CustomDimension | null>(null)
  const [showDimensionForm, setShowDimensionForm] = useState(false)

  const useDimensionTemplate = (template: typeof DIMENSION_TEMPLATES[0]) => {
    setEditingDimension({
      ...template,
      evidence_types: [...template.evidence_types],
      group_id: template.group_id
    })
    setShowDimensionForm(true)
  }

  const saveDimension = () => {
    if (editingDimension && editingDimension.name) {
      const existingIndex = dimensions.findIndex(d => d.name === editingDimension.name)
      if (existingIndex >= 0) {
        const updated = [...dimensions]
        updated[existingIndex] = editingDimension
        setDimensions(updated)
      } else {
        setDimensions([...dimensions, editingDimension])
      }
      setEditingDimension(null)
      setShowDimensionForm(false)
    }
  }

  const removeDimension = (name: string) => {
    setDimensions(dimensions.filter(d => d.name !== name))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

      const configData = {
      custom_dimensions: dimensions,
      dimension_groups: dimensionGroups
      }

      onComplete(configData)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Analysis Configuration</h2>
        <p className="text-gray-600">
          Configure optional analysis settings. You can skip this step if you want to use defaults.
        </p>
        <div className="mt-2 flex items-center gap-2 text-sm text-blue-600">
          <Info className="h-4 w-4" />
          <span>Competitors are configured in the Company Profile step</span>
        </div>
      </div>

      <Tabs defaultValue="dimensions" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="dimensions">
            <Layers className="h-4 w-4 mr-2" />
            Custom Dimensions
            </TabsTrigger>
          <TabsTrigger value="groups">
            <Target className="h-4 w-4 mr-2" />
            Dimension Groups
            </TabsTrigger>
          </TabsList>

        {/* Custom Dimensions Tab */}
        <TabsContent value="dimensions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Custom Analysis Dimensions (Optional)</CardTitle>
              <CardDescription>
                Add custom dimensions to analyze ANY content attributes - tone of voice, writing style, emotional appeal, 
                technical depth, or any other traits you want to measure. The AI will evaluate content against your criteria.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Dimension Templates */}
              {dimensions.length === 0 && !showDimensionForm && (
                <div>
                  <p className="text-sm text-gray-600 mb-4">
                    Start with a template or create your own custom dimension:
                  </p>
                  <div className="grid gap-4 md:grid-cols-3">
                    {DIMENSION_TEMPLATES.map((template, index) => (
                      <div
                        key={index}
                        className="p-4 border rounded-lg hover:border-cylvy-purple cursor-pointer transition-colors"
                        onClick={() => useDimensionTemplate(template)}
                      >
                        <h4 className="font-medium mb-1">{template.name}</h4>
                        <p className="text-sm text-gray-600">{template.description}</p>
                        <div className="mt-2">
                          <Badge variant="outline" className="text-xs">
                            3 scoring levels
                          </Badge>
            </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 text-center">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setEditingDimension({
                          name: '',
                          description: '',
                          scoring_levels: [
                            { level: 0, label: 'Basic', description: '' },
                            { level: 5, label: 'Intermediate', description: '' },
                            { level: 10, label: 'Advanced', description: '' }
                          ],
                          evidence_types: []
                        })
                        setShowDimensionForm(true)
                      }}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Create Custom Dimension
                    </Button>
                  </div>
                </div>
              )}

              {/* Existing Dimensions */}
              {dimensions.length > 0 && !showDimensionForm && (
                <div>
                  <div className="space-y-3">
                    {dimensions.map((dimension, index) => (
                      <div key={index} className="p-4 border rounded-lg">
                        <div className="flex items-start justify-between">
                      <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium">{dimension.name}</h4>
                              {dimension.group_id && (
                                <Badge variant="outline" className="text-xs">
                                  {dimensionGroups.find(g => g.id === dimension.group_id)?.name || dimension.group_id}
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-600">{dimension.description}</p>
                            <div className="mt-2 space-y-1">
                              {dimension.scoring_levels.map((level) => (
                                <div key={level.level} className="text-xs">
                                  <span className="font-medium">Level {level.level}:</span> {level.label}
                                </div>
                              ))}
                      </div>
                    </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                            onClick={() => removeDimension(dimension.name)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                  </div>
                </div>
              ))}
            </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="mt-4"
                    onClick={() => {
                      setEditingDimension({
                        name: '',
                        description: '',
                        scoring_levels: [
                          { level: 0, label: 'Basic', description: '' },
                          { level: 5, label: 'Intermediate', description: '' },
                          { level: 10, label: 'Advanced', description: '' }
                        ],
                        evidence_types: []
                      })
                      setShowDimensionForm(true)
                    }}
                  >
                <Plus className="h-4 w-4 mr-2" />
                    Add Another Dimension
              </Button>
            </div>
              )}

              {/* Dimension Form */}
              {showDimensionForm && editingDimension && (
                <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
                      <div>
                    <Label htmlFor="dimension-name">Dimension Name</Label>
                        <Input
                      id="dimension-name"
                      value={editingDimension.name}
                      onChange={(e) => setEditingDimension({ ...editingDimension, name: e.target.value })}
                      placeholder="e.g., API Ecosystem Maturity"
                        />
                      </div>
                      <div>
                    <Label htmlFor="dimension-desc">Description</Label>
                        <Textarea
                      id="dimension-desc"
                      value={editingDimension.description}
                      onChange={(e) => setEditingDimension({ ...editingDimension, description: e.target.value })}
                      placeholder="What this dimension measures..."
                        />
                      </div>
                  <div>
                    <Label htmlFor="dimension-group">Dimension Group</Label>
                    <select
                      id="dimension-group"
                      className="w-full px-3 py-2 border rounded-md"
                      value={editingDimension.group_id || ''}
                      onChange={(e) => setEditingDimension({ ...editingDimension, group_id: e.target.value })}
                    >
                      <option value="">No Group</option>
                      {dimensionGroups.map((group) => (
                        <option key={group.id} value={group.id}>
                          {group.name} ({group.selection_strategy.replace('_', ' ')})
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-600 mt-1">
                      The AI will select the primary dimension from each group based on the group's strategy
                    </p>
                  </div>
                  <div>
                    <Label>Evidence Types (what the AI should look for)</Label>
                    <Textarea
                      value={editingDimension.evidence_types.join('\n')}
                      onChange={(e) => setEditingDimension({ 
                        ...editingDimension, 
                        evidence_types: e.target.value.split('\n').filter(s => s.trim()) 
                      })}
                      placeholder="API documentation&#10;Integration examples&#10;Developer portal"
                      rows={3}
                    />
                    </div>
                  <div className="flex justify-end gap-3">
                      <Button
                        type="button"
                      variant="outline"
                      onClick={() => {
                        setEditingDimension(null)
                        setShowDimensionForm(false)
                      }}
                    >
                      Cancel
                    </Button>
                    <Button type="button" onClick={saveDimension}>
                      Save Dimension
                      </Button>
                  </div>
                </div>
              )}

              {/* Info Box */}
              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <div className="flex gap-3">
                  <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-800">
                    <p className="font-medium mb-1">How Custom Dimensions Work:</p>
                    <ul className="list-disc list-inside space-y-1 text-blue-700">
                      <li>AI scores any content attribute on 0/5/10 scale</li>
                      <li>Analyze tone, style, depth, emotion, credibility, etc.</li>
                      <li>Group related dimensions for organized insights</li>
                      <li>AI selects primary dimension from each group</li>
                    </ul>
                  </div>
                </div>
            </div>
            </CardContent>
          </Card>
          </TabsContent>

        {/* Dimension Groups Tab */}
        <TabsContent value="groups" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Dimension Groups</CardTitle>
              <CardDescription>
                Dimensions are organized into groups. The AI will automatically select the most relevant dimension from each group as the primary indicator.
                Default groups are just examples - you can create groups for any categorization: writing style, SEO factors, 
                emotional tone, credibility signals, or any other way you want to organize your analysis.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                {dimensionGroups.map((group) => {
                  const groupDimensions = dimensions.filter(d => d.group_id === group.id)
                  return (
                    <div
                      key={group.id}
                      className="p-4 border rounded-lg"
                      style={{ borderColor: group.color || '#E5E7EB' }}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <div 
                          className="w-2 h-2 rounded-full" 
                          style={{ backgroundColor: group.color || '#6B7280' }}
                        />
                        <h4 className="font-medium">{group.name}</h4>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{group.description}</p>
                      <div className="space-y-2">
                        <div className="text-xs">
                          <span className="font-medium">Selection Strategy:</span>{' '}
                          <Badge variant="outline" className="text-xs">
                            {group.selection_strategy.replace('_', ' ')}
                          </Badge>
                        </div>
                        <div className="text-xs">
                          <span className="font-medium">Dimensions in group:</span>{' '}
                          {groupDimensions.length > 0 ? (
                            <span className="text-gray-700">
                              {groupDimensions.map(d => d.name).join(', ')}
                            </span>
                          ) : (
                            <span className="text-gray-500">None yet</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Strategy Explanations */}
              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <div className="flex gap-3">
                  <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-800">
                    <p className="font-medium mb-2">Selection Strategies:</p>
                    <ul className="space-y-1 text-blue-700">
                      <li><span className="font-medium">Highest Score:</span> Selects dimension with highest relevance score</li>
                      <li><span className="font-medium">Highest Confidence:</span> Selects dimension AI is most confident about</li>
                      <li><span className="font-medium">Most Evidence:</span> Selects dimension with most supporting evidence</li>
                      <li><span className="font-medium">Manual:</span> Uses predefined priority order</li>
                    </ul>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>

      {/* Summary Card */}
      <Card className="bg-gray-50">
        <CardContent className="py-4">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <div>
              <p className="font-medium">Analysis Configuration Summary</p>
              <p className="text-sm text-gray-600">
                {dimensions.length} custom dimension{dimensions.length !== 1 ? 's' : ''} in {dimensionGroups.length} group{dimensionGroups.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Navigation */}
        <div className="flex justify-between pt-6">
        <Button type="button" onClick={onBack} variant="outline">
          Previous
            </Button>
        <Button type="submit">
          Next: Review & Launch
          </Button>
        </div>
      </form>
  )
}