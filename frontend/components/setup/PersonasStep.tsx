'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { 
  Users, 
  Plus, 
  Trash2, 
  CheckCircle,
  AlertCircle,
  Briefcase
} from 'lucide-react'

interface PersonaData {
  id?: string
  name: string
  title: string
  department: string
  seniority_level: string
  company_size: string
  goals: string[]
  challenges: string[]
  decision_criteria: string[]
  buying_journey_involvement: string
  influence_level: string
}

interface PersonasStepProps {
  data: {
    personas?: PersonaData[]
  }
  onUpdate: (data: any) => void
  onNext: () => void
  onPrev: () => void
}

// Pre-defined B2B SaaS persona templates
const PERSONA_TEMPLATES = [
  {
    name: 'Technical Decision Maker',
    title: 'VP of Engineering / CTO',
    department: 'Engineering/IT',
    seniority_level: 'VP/Director',
    company_size: 'Enterprise (1000+ employees)',
    goals: ['Ensure technical scalability', 'Reduce technical debt', 'Improve team productivity'],
    challenges: ['Legacy system integration', 'Resource constraints', 'Keeping up with technology changes'],
    decision_criteria: ['Technical architecture fit', 'API quality', 'Security certifications'],
    buying_journey_involvement: 'Technical Evaluator',
    influence_level: 'Medium - Strong Voice'
  },
  {
    name: 'Business Decision Maker',
    title: 'VP of Sales / CRO',
    department: 'Sales/Revenue',
    seniority_level: 'C-Level',
    company_size: 'Enterprise (1000+ employees)',
    goals: ['Increase revenue', 'Improve sales efficiency', 'Scale operations'],
    challenges: ['Long sales cycles', 'Competition', 'Market changes'],
    decision_criteria: ['ROI and payback period', 'Ease of implementation', 'Proven results'],
    buying_journey_involvement: 'Decision Maker',
    influence_level: 'High - Final Decision'
  },
  {
    name: 'End User Champion',
    title: 'Senior Manager / Team Lead',
    department: 'Operations',
    seniority_level: 'Manager',
    company_size: 'Mid-Market (100-999)',
    goals: ['Improve team efficiency', 'Reduce manual work', 'Better reporting'],
    challenges: ['Current tool limitations', 'Process inefficiencies', 'Data silos'],
    decision_criteria: ['Ease of use', 'Feature completeness', 'Training and support'],
    buying_journey_involvement: 'Initiator',
    influence_level: 'Low - Advisory Only'
  }
]

export default function PersonasStep({ data, onUpdate, onNext, onPrev }: PersonasStepProps) {
  const [personas, setPersonas] = useState<PersonaData[]>(data.personas || [])
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [formData, setFormData] = useState<PersonaData>({
    name: '',
    title: '',
    department: '',
    seniority_level: '',
    company_size: '',
    goals: [],
    challenges: [],
    decision_criteria: [],
    buying_journey_involvement: '',
    influence_level: ''
  })

  useEffect(() => {
    onUpdate({ personas })
  }, [personas])

  const handleUseTemplate = (template: typeof PERSONA_TEMPLATES[0]) => {
    setFormData(template)
    setEditingIndex(personas.length)
  }

  const handleSavePersona = () => {
    if (!formData.name || !formData.title) {
      alert('Please provide at least a name and title for the persona')
      return
    }

    const newPersonas = [...personas]
    if (editingIndex !== null && editingIndex < personas.length) {
      newPersonas[editingIndex] = formData
    } else {
      newPersonas.push(formData)
    }
    
    setPersonas(newPersonas)
    setEditingIndex(null)
    setFormData({
      name: '',
      title: '',
      department: '',
      seniority_level: '',
      company_size: '',
      goals: [],
      challenges: [],
      decision_criteria: [],
      buying_journey_involvement: '',
      influence_level: ''
    })
  }

  const handleDeletePersona = (index: number) => {
    setPersonas(personas.filter((_, i) => i !== index))
  }

  const handleEditPersona = (index: number) => {
    setFormData(personas[index])
    setEditingIndex(index)
  }

  const handleArrayInput = (field: keyof PersonaData, value: string) => {
    const items = value.split('\n').filter(item => item.trim())
    setFormData({ ...formData, [field]: items })
  }

  const canProceed = personas.length >= 1

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Define Your Buyer Personas</h2>
        <p className="text-gray-600">
          Create at least one buyer persona to help the AI understand your target audience.
          These personas will be used to score and analyze content relevance.
        </p>
      </div>

      {/* Templates */}
      {personas.length === 0 && editingIndex === null && (
        <Card>
          <CardHeader>
            <CardTitle>Start with a Template</CardTitle>
            <CardDescription>
              Choose a pre-defined persona template to get started quickly
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              {PERSONA_TEMPLATES.map((template, index) => (
                <div
                  key={index}
                  className="p-4 border rounded-lg hover:border-cylvy-purple cursor-pointer transition-colors"
                  onClick={() => handleUseTemplate(template)}
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-cylvy-purple/10 rounded-lg">
                      <Briefcase className="h-5 w-5 text-cylvy-purple" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium">{template.name}</h4>
                      <p className="text-sm text-gray-600 mt-1">{template.title}</p>
                      <div className="flex gap-2 mt-2">
                        <Badge variant="outline" className="text-xs">
                          {template.buying_journey_involvement}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Existing Personas */}
      {personas.length > 0 && editingIndex === null && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Your Personas</CardTitle>
                <CardDescription>
                  {personas.length} persona{personas.length !== 1 ? 's' : ''} defined
                </CardDescription>
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setEditingIndex(personas.length)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Persona
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {personas.map((persona, index) => (
                <div key={index} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-cylvy-purple/10 rounded-lg">
                          <Users className="h-4 w-4 text-cylvy-purple" />
                        </div>
                        <div>
                          <h4 className="font-medium">{persona.name}</h4>
                          <p className="text-sm text-gray-600">{persona.title}</p>
                        </div>
                      </div>
                      {persona.goals && persona.goals.length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs font-medium text-gray-700 mb-1">Key Goals:</p>
                          <div className="flex flex-wrap gap-1">
                            {persona.goals.slice(0, 3).map((goal, idx) => (
                              <Badge key={idx} variant="outline" className="text-xs">
                                {goal}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEditPersona(index)}
                      >
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDeletePersona(index)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Edit/Create Form */}
      {editingIndex !== null && (
        <Card>
          <CardHeader>
            <CardTitle>
              {editingIndex < personas.length ? 'Edit Persona' : 'Create New Persona'}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="name">Persona Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Technical Decision Maker"
                />
              </div>
              <div>
                <Label htmlFor="title">Job Title *</Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder="e.g., VP of Engineering"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="goals">Goals (one per line)</Label>
                <Textarea
                  id="goals"
                  rows={3}
                  value={formData.goals?.join('\n') || ''}
                  onChange={(e) => handleArrayInput('goals', e.target.value)}
                  placeholder="Improve efficiency&#10;Reduce costs&#10;Scale operations"
                />
              </div>
              <div>
                <Label htmlFor="challenges">Pain Points (one per line)</Label>
                <Textarea
                  id="challenges"
                  rows={3}
                  value={formData.challenges?.join('\n') || ''}
                  onChange={(e) => handleArrayInput('challenges', e.target.value)}
                  placeholder="Legacy systems&#10;Resource constraints&#10;Data silos"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="decision_criteria">Decision Criteria (one per line)</Label>
              <Textarea
                id="decision_criteria"
                rows={2}
                value={formData.decision_criteria?.join('\n') || ''}
                onChange={(e) => handleArrayInput('decision_criteria', e.target.value)}
                placeholder="ROI and cost&#10;Ease of use&#10;Integration capabilities"
              />
            </div>

            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  setEditingIndex(null)
                  setFormData({
                    name: '',
                    title: '',
                    department: '',
                    seniority_level: '',
                    company_size: '',
                    goals: [],
                    challenges: [],
                    decision_criteria: [],
                    buying_journey_involvement: '',
                    influence_level: ''
                  })
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleSavePersona}>
                Save Persona
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress indicator */}
      <Card className="bg-gray-50">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {canProceed ? (
                <span className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  Great! You have {personas.length} persona{personas.length !== 1 ? 's' : ''} defined.
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                  Please define at least one buyer persona to continue.
                </span>
              )}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between pt-6">
        <Button onClick={onPrev} variant="outline">
          Previous
        </Button>
        <Button onClick={onNext} disabled={!canProceed}>
          Next: Keywords & Markets
        </Button>
      </div>
    </div>
  )
}

