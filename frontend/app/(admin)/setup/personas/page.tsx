'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AdminLayout } from '@/components/layout/AdminLayout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { 
  Users, 
  Plus, 
  Edit, 
  Trash2, 
  Save, 
  AlertCircle,
  CheckCircle,
  Briefcase,
  Target,
  Brain,
  Lightbulb
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface PersonaField {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select'
  placeholder?: string
  required?: boolean
  options?: string[]
}

interface Persona {
  id?: string
  name: string
  title: string
  department: string
  seniority_level: string
  company_size: string
  industry_focus?: string
  goals: string[]
  challenges: string[]
  decision_criteria: string[]
  information_sources: string[]
  buying_journey_involvement: string
  influence_level: string
  typical_objections?: string[]
  preferred_content_types?: string[]
  description?: string
}

const PERSONA_FIELDS: PersonaField[] = [
  { key: 'name', label: 'Persona Name', type: 'text', placeholder: 'e.g., Technical Decision Maker', required: true },
  { key: 'title', label: 'Job Title', type: 'text', placeholder: 'e.g., VP of Engineering, CTO', required: true },
  { key: 'department', label: 'Department', type: 'text', placeholder: 'e.g., IT, Engineering, Operations', required: true },
  { 
    key: 'seniority_level', 
    label: 'Seniority Level', 
    type: 'select', 
    required: true,
    options: ['C-Level', 'VP/Director', 'Manager', 'Individual Contributor', 'Analyst']
  },
  { 
    key: 'company_size', 
    label: 'Target Company Size', 
    type: 'select', 
    required: true,
    options: ['Enterprise (1000+ employees)', 'Mid-Market (100-999)', 'SMB (10-99)', 'Startup (<10)']
  },
  {
    key: 'buying_journey_involvement',
    label: 'Buying Journey Involvement',
    type: 'select',
    required: true,
    options: ['Initiator', 'Influencer', 'Decision Maker', 'Budget Holder', 'End User', 'Technical Evaluator']
  },
  {
    key: 'influence_level',
    label: 'Influence Level',
    type: 'select',
    required: true,
    options: ['High - Final Decision', 'Medium - Strong Voice', 'Low - Advisory Only']
  }
]

// Pre-defined B2B SaaS persona templates
const PERSONA_TEMPLATES = [
  {
    name: 'Technical Decision Maker',
    title: 'VP of Engineering / CTO',
    department: 'Engineering/IT',
    seniority_level: 'VP/Director',
    company_size: 'Enterprise (1000+ employees)',
    goals: ['Ensure technical scalability', 'Reduce technical debt', 'Improve team productivity', 'Maintain security standards'],
    challenges: ['Legacy system integration', 'Resource constraints', 'Keeping up with technology changes', 'Balancing innovation with stability'],
    decision_criteria: ['Technical architecture fit', 'API quality and documentation', 'Security certifications', 'Vendor technical support'],
    information_sources: ['Technical documentation', 'GitHub/Open source', 'Developer communities', 'Peer recommendations'],
    buying_journey_involvement: 'Technical Evaluator',
    influence_level: 'Medium - Strong Voice',
    typical_objections: ['Integration complexity', 'Learning curve for team', 'Vendor lock-in concerns'],
    preferred_content_types: ['Technical whitepapers', 'API documentation', 'Architecture diagrams', 'Case studies']
  },
  {
    name: 'Business Decision Maker',
    title: 'VP of Sales / CRO',
    department: 'Sales/Revenue',
    seniority_level: 'C-Level',
    company_size: 'Enterprise (1000+ employees)',
    goals: ['Increase revenue', 'Improve sales efficiency', 'Reduce customer acquisition cost', 'Scale operations'],
    challenges: ['Long sales cycles', 'Competition', 'Market changes', 'Team performance'],
    decision_criteria: ['ROI and payback period', 'Ease of implementation', 'Proven results', 'Vendor reputation'],
    information_sources: ['Industry analysts (Gartner, Forrester)', 'Peer networks', 'Industry publications', 'Conferences'],
    buying_journey_involvement: 'Decision Maker',
    influence_level: 'High - Final Decision',
    typical_objections: ['Cost justification', 'Implementation timeline', 'Change management concerns'],
    preferred_content_types: ['ROI calculators', 'Customer success stories', 'Industry reports', 'Executive briefs']
  },
  {
    name: 'End User Champion',
    title: 'Senior Manager / Team Lead',
    department: 'Operations',
    seniority_level: 'Manager',
    company_size: 'Mid-Market (100-999)',
    goals: ['Improve team efficiency', 'Reduce manual work', 'Better reporting', 'Career advancement'],
    challenges: ['Current tool limitations', 'Process inefficiencies', 'Data silos', 'Team adoption'],
    decision_criteria: ['Ease of use', 'Feature completeness', 'Training and support', 'Integration with existing tools'],
    information_sources: ['Product reviews', 'Free trials', 'Webinars', 'User communities'],
    buying_journey_involvement: 'Initiator',
    influence_level: 'Low - Advisory Only',
    typical_objections: ['Change resistance from team', 'Training requirements', 'Workflow disruption'],
    preferred_content_types: ['Product demos', 'How-to guides', 'Webinars', 'User testimonials']
  }
]

export default function PersonasSetupPage() {
  const router = useRouter()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Form state
  const [formData, setFormData] = useState<Persona>({
    name: '',
    title: '',
    department: '',
    seniority_level: '',
    company_size: '',
    goals: [],
    challenges: [],
    decision_criteria: [],
    information_sources: [],
    buying_journey_involvement: '',
    influence_level: '',
    typical_objections: [],
    preferred_content_types: []
  })

  useEffect(() => {
    loadPersonas()
  }, [])

  const loadPersonas = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/personas', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setPersonas(data.personas || [])
      } else if (response.status === 404) {
        // No personas yet, that's ok
        setPersonas([])
      }
    } catch (error) {
      console.error('Failed to load personas:', error)
      setError('Failed to load personas')
    } finally {
      setLoading(false)
    }
  }

  const handleUseTemplate = (template: typeof PERSONA_TEMPLATES[0]) => {
    setFormData(template)
    setIsEditing(true)
    setEditingPersona(null)
  }

  const handleEdit = (persona: Persona) => {
    setFormData(persona)
    setEditingPersona(persona)
    setIsEditing(true)
  }

  const handleDelete = async (personaId: string) => {
    if (!confirm('Are you sure you want to delete this persona?')) return

    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch(`/api/v1/personas/${personaId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (response.ok) {
        setSuccess('Persona deleted successfully')
        await loadPersonas()
      } else {
        throw new Error('Failed to delete persona')
      }
    } catch (error) {
      setError('Failed to delete persona')
    }
  }

  const handleArrayInput = (field: string, value: string) => {
    const items = value.split('\n').filter(item => item.trim())
    setFormData({ ...formData, [field]: items })
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      const token = localStorage.getItem('access_token')
      const url = editingPersona?.id 
        ? `/api/v1/personas/${editingPersona.id}`
        : '/api/v1/personas'
      
      const method = editingPersona?.id ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      })

      if (response.ok) {
        setSuccess(editingPersona ? 'Persona updated successfully' : 'Persona created successfully')
        setIsEditing(false)
        setEditingPersona(null)
        setFormData({
          name: '',
          title: '',
          department: '',
          seniority_level: '',
          company_size: '',
          goals: [],
          challenges: [],
          decision_criteria: [],
          information_sources: [],
          buying_journey_involvement: '',
          influence_level: '',
          typical_objections: [],
          preferred_content_types: []
        })
        await loadPersonas()
      } else {
        throw new Error('Failed to save persona')
      }
    } catch (error) {
      setError('Failed to save persona')
    } finally {
      setSaving(false)
    }
  }

  const canProceed = personas.length >= 1

  return (
    <AdminLayout title="Buyer Personas Setup" description="Define your target buyer personas">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header with navigation */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Buyer Personas</h1>
            <p className="text-gray-600 mt-1">
              Define the key stakeholders in your target accounts' buying journey
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => router.push('/setup/company')}
            >
              ← Previous
            </Button>
            <Button
              onClick={() => router.push('/setup/keywords')}
              disabled={!canProceed}
            >
              Next: Keywords →
            </Button>
          </div>
        </div>

        {/* Success/Error Messages */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 text-red-700 rounded-lg">
            <AlertCircle className="h-5 w-5" />
            {error}
          </div>
        )}
        
        {success && (
          <div className="flex items-center gap-2 p-4 bg-green-50 text-green-700 rounded-lg">
            <CheckCircle className="h-5 w-5" />
            {success}
          </div>
        )}

        {/* Templates Section */}
        {!isEditing && personas.length === 0 && (
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
                          <Badge variant="outline" className="text-xs">
                            {template.influence_level}
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
        {!isEditing && personas.length > 0 && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Your Buyer Personas</CardTitle>
                  <CardDescription>
                    {personas.length} persona{personas.length !== 1 ? 's' : ''} defined
                  </CardDescription>
                </div>
                <Button onClick={() => setIsEditing(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Persona
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                {personas.map((persona) => (
                  <div key={persona.id} className="p-4 border rounded-lg">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-cylvy-purple/10 rounded-lg">
                            <Users className="h-5 w-5 text-cylvy-purple" />
                          </div>
                          <div>
                            <h4 className="font-medium text-lg">{persona.name}</h4>
                            <p className="text-gray-600">{persona.title} • {persona.department}</p>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4 mt-4">
                          <div>
                            <p className="text-sm font-medium text-gray-700">Company Size</p>
                            <p className="text-sm text-gray-600">{persona.company_size}</p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-700">Seniority</p>
                            <p className="text-sm text-gray-600">{persona.seniority_level}</p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-700">Buying Role</p>
                            <p className="text-sm text-gray-600">{persona.buying_journey_involvement}</p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-700">Influence</p>
                            <p className="text-sm text-gray-600">{persona.influence_level}</p>
                          </div>
                        </div>

                        {persona.goals && persona.goals.length > 0 && (
                          <div className="mt-4">
                            <p className="text-sm font-medium text-gray-700 mb-1">Key Goals</p>
                            <div className="flex flex-wrap gap-2">
                              {persona.goals.slice(0, 3).map((goal, idx) => (
                                <Badge key={idx} variant="outline" className="text-xs">
                                  {goal}
                                </Badge>
                              ))}
                              {persona.goals.length > 3 && (
                                <Badge variant="outline" className="text-xs">
                                  +{persona.goals.length - 3} more
                                </Badge>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleEdit(persona)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => persona.id && handleDelete(persona.id)}
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
        {isEditing && (
          <Card>
            <CardHeader>
              <CardTitle>
                {editingPersona ? 'Edit Persona' : 'Create New Persona'}
              </CardTitle>
              <CardDescription>
                Define the characteristics and needs of this buyer persona
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Basic Information */}
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
                  <div>
                    <Label htmlFor="department">Department *</Label>
                    <Input
                      id="department"
                      value={formData.department}
                      onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                      placeholder="e.g., Engineering"
                    />
                  </div>
                  <div>
                    <Label htmlFor="seniority">Seniority Level *</Label>
                    <select
                      id="seniority"
                      className="w-full p-2 border rounded-md"
                      value={formData.seniority_level}
                      onChange={(e) => setFormData({ ...formData, seniority_level: e.target.value })}
                    >
                      <option value="">Select level...</option>
                      {PERSONA_FIELDS.find(f => f.key === 'seniority_level')?.options?.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="company_size">Company Size *</Label>
                    <select
                      id="company_size"
                      className="w-full p-2 border rounded-md"
                      value={formData.company_size}
                      onChange={(e) => setFormData({ ...formData, company_size: e.target.value })}
                    >
                      <option value="">Select size...</option>
                      {PERSONA_FIELDS.find(f => f.key === 'company_size')?.options?.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="buying_role">Buying Journey Role *</Label>
                    <select
                      id="buying_role"
                      className="w-full p-2 border rounded-md"
                      value={formData.buying_journey_involvement}
                      onChange={(e) => setFormData({ ...formData, buying_journey_involvement: e.target.value })}
                    >
                      <option value="">Select role...</option>
                      {PERSONA_FIELDS.find(f => f.key === 'buying_journey_involvement')?.options?.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div className="md:col-span-2">
                    <Label htmlFor="influence">Influence Level *</Label>
                    <select
                      id="influence"
                      className="w-full p-2 border rounded-md"
                      value={formData.influence_level}
                      onChange={(e) => setFormData({ ...formData, influence_level: e.target.value })}
                    >
                      <option value="">Select influence level...</option>
                      {PERSONA_FIELDS.find(f => f.key === 'influence_level')?.options?.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Goals & Objectives */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="goals">
                      <Target className="inline h-4 w-4 mr-1" />
                      Goals & Objectives (one per line)
                    </Label>
                    <Textarea
                      id="goals"
                      rows={4}
                      value={formData.goals?.join('\n') || ''}
                      onChange={(e) => handleArrayInput('goals', e.target.value)}
                      placeholder="Improve team efficiency&#10;Reduce operational costs&#10;Scale the business"
                    />
                  </div>
                  <div>
                    <Label htmlFor="challenges">
                      <AlertCircle className="inline h-4 w-4 mr-1" />
                      Pain Points & Challenges (one per line)
                    </Label>
                    <Textarea
                      id="challenges"
                      rows={4}
                      value={formData.challenges?.join('\n') || ''}
                      onChange={(e) => handleArrayInput('challenges', e.target.value)}
                      placeholder="Legacy system limitations&#10;Resource constraints&#10;Compliance requirements"
                    />
                  </div>
                </div>

                {/* Decision Making */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="criteria">
                      <Brain className="inline h-4 w-4 mr-1" />
                      Decision Criteria (one per line)
                    </Label>
                    <Textarea
                      id="criteria"
                      rows={4}
                      value={formData.decision_criteria?.join('\n') || ''}
                      onChange={(e) => handleArrayInput('decision_criteria', e.target.value)}
                      placeholder="ROI and cost&#10;Ease of implementation&#10;Vendor reputation"
                    />
                  </div>
                  <div>
                    <Label htmlFor="sources">
                      <Lightbulb className="inline h-4 w-4 mr-1" />
                      Information Sources (one per line)
                    </Label>
                    <Textarea
                      id="sources"
                      rows={4}
                      value={formData.information_sources?.join('\n') || ''}
                      onChange={(e) => handleArrayInput('information_sources', e.target.value)}
                      placeholder="Industry analysts&#10;Peer recommendations&#10;Online reviews"
                    />
                  </div>
                </div>

                {/* Additional Context */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label htmlFor="objections">Common Objections (one per line)</Label>
                    <Textarea
                      id="objections"
                      rows={3}
                      value={formData.typical_objections?.join('\n') || ''}
                      onChange={(e) => handleArrayInput('typical_objections', e.target.value)}
                      placeholder="Too expensive&#10;Implementation complexity&#10;Change management"
                    />
                  </div>
                  <div>
                    <Label htmlFor="content">Preferred Content Types (one per line)</Label>
                    <Textarea
                      id="content"
                      rows={3}
                      value={formData.preferred_content_types?.join('\n') || ''}
                      onChange={(e) => handleArrayInput('preferred_content_types', e.target.value)}
                      placeholder="Case studies&#10;ROI calculators&#10;Product demos"
                    />
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex justify-end gap-3">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsEditing(false)
                      setEditingPersona(null)
                    }}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleSave} disabled={saving}>
                    {saving ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        Save Persona
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Progress indicator */}
        {!isEditing && (
          <Card className="bg-gray-50">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">
                  {canProceed ? (
                    <span className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      Great! You have {personas.length} persona{personas.length !== 1 ? 's' : ''} defined. You can proceed to the next step.
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
        )}
      </div>
    </AdminLayout>
  )
}

