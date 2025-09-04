'use client'

import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Plus, X, Target, Users, Building } from 'lucide-react'
import { analysisAPI } from '@/app/services/api'

interface AnalysisConfigStepProps {
  data: any
  onComplete: (data: any) => void
  onBack?: () => void
}

export function AnalysisConfigStep({ data, onComplete, onBack }: AnalysisConfigStepProps) {
  const [personas, setPersonas] = useState(data.personas || [
    { name: 'Marketing Manager', description: 'Responsible for digital marketing strategy and campaigns' },
    { name: 'Content Creator', description: 'Creates and manages content across channels' }
  ])

  const [jtbdPhases, setJtbdPhases] = useState(data.jtbd_phases || [
    { name: 'Awareness', description: 'Customer becomes aware of the problem' },
    { name: 'Consideration', description: 'Customer evaluates potential solutions' },
    { name: 'Decision', description: 'Customer chooses a specific solution' }
  ])

  const [competitors, setCompetitors] = useState<string[]>(data.competitor_domains || [])
  const [newCompetitor, setNewCompetitor] = useState('')

  const [loading, setLoading] = useState(false)

  const addPersona = () => {
    setPersonas([...personas, { name: '', description: '' }])
  }

  const updatePersona = (index: number, field: 'name' | 'description', value: string) => {
    const updated = personas.map((persona, i) => 
      i === index ? { ...persona, [field]: value } : persona
    )
    setPersonas(updated)
  }

  const removePersona = (index: number) => {
    setPersonas(personas.filter((_, i) => i !== index))
  }

  const addJTBDPhase = () => {
    setJtbdPhases([...jtbdPhases, { name: '', description: '' }])
  }

  const updateJTBDPhase = (index: number, field: 'name' | 'description', value: string) => {
    const updated = jtbdPhases.map((phase, i) => 
      i === index ? { ...phase, [field]: value } : phase
    )
    setJtbdPhases(updated)
  }

  const removeJTBDPhase = (index: number) => {
    setJtbdPhases(jtbdPhases.filter((_, i) => i !== index))
  }

  const addCompetitor = () => {
    if (newCompetitor.trim() && !competitors.includes(newCompetitor.trim())) {
      setCompetitors([...competitors, newCompetitor.trim()])
      setNewCompetitor('')
    }
  }

  const removeCompetitor = (domain: string) => {
    setCompetitors(competitors.filter(c => c !== domain))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const configData = {
        personas,
        jtbd_phases: jtbdPhases,
        competitor_domains: competitors
      }

      // Save analysis config
      await analysisAPI.updatePersonas(personas)
      await analysisAPI.updateJTBDPhases(jtbdPhases) 
      await analysisAPI.updateCompetitors(competitors)

      onComplete(configData)
    } catch (err) {
      console.error('Failed to save analysis config:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 bg-transparent">
      <div>
        <h2 className="text-2xl font-bold mb-2 text-cylvy-midnight">Analysis Configuration</h2>
        <p className="text-gray-600">
          Define your target personas, buyer journey phases, and key competitors for focused analysis.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-transparent">
        <Tabs defaultValue="personas" className="space-y-6 bg-transparent">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="personas" className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Personas
            </TabsTrigger>
            <TabsTrigger value="jtbd" className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              Journey Phases
            </TabsTrigger>
            <TabsTrigger value="competitors" className="flex items-center gap-2">
              <Building className="h-4 w-4" />
              Competitors
            </TabsTrigger>
          </TabsList>

          <TabsContent value="personas" className="space-y-4 bg-transparent text-gray-900">
            <div className="flex justify-between items-center bg-transparent">
              <h3 className="text-lg font-semibold">Target Personas</h3>
              <Button type="button" variant="outline" onClick={addPersona}>
                <Plus className="h-4 w-4 mr-2" />
                Add Persona
              </Button>
            </div>

            <div className="space-y-4 bg-transparent">
              {personas.map((persona, index) => (
                <div key={index} className="persona-container p-4 border rounded-lg space-y-3 bg-white">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 space-y-3">
                      <div>
                        <Label htmlFor={`persona-name-${index}`}>Persona Name</Label>
                        <Input
                          id={`persona-name-${index}`}
                          value={persona.name}
                          onChange={(e) => updatePersona(index, 'name', e.target.value)}
                          placeholder="e.g., Marketing Manager"
                          className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
                        />
                      </div>
                      <div>
                        <Label htmlFor={`persona-desc-${index}`}>Description</Label>
                        <Textarea
                          id={`persona-desc-${index}`}
                          value={persona.description}
                          onChange={(e) => updatePersona(index, 'description', e.target.value)}
                          placeholder="Describe this persona's role and responsibilities..."
                          rows={2}
                          className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
                        />
                      </div>
                    </div>
                    {personas.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removePersona(index)}
                        className="ml-2 text-red-500 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="jtbd" className="space-y-4 bg-transparent text-gray-900">
            <div className="flex justify-between items-center bg-transparent">
              <h3 className="text-lg font-semibold">Jobs-to-be-Done Phases</h3>
              <Button type="button" variant="outline" onClick={addJTBDPhase}>
                <Plus className="h-4 w-4 mr-2" />
                Add Phase
              </Button>
            </div>

            <div className="space-y-4 bg-transparent">
              {jtbdPhases.map((phase, index) => (
                <div key={index} className="jtbd-container p-4 border rounded-lg space-y-3 bg-white">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 space-y-3">
                      <div>
                        <Label htmlFor={`phase-name-${index}`}>Phase Name</Label>
                        <Input
                          id={`phase-name-${index}`}
                          value={phase.name}
                          onChange={(e) => updateJTBDPhase(index, 'name', e.target.value)}
                          placeholder="e.g., Awareness"
                          className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
                        />
                      </div>
                      <div>
                        <Label htmlFor={`phase-desc-${index}`}>Description</Label>
                        <Textarea
                          id={`phase-desc-${index}`}
                          value={phase.description}
                          onChange={(e) => updateJTBDPhase(index, 'description', e.target.value)}
                          placeholder="Describe what happens in this phase..."
                          rows={2}
                          className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
                        />
                      </div>
                    </div>
                    {jtbdPhases.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeJTBDPhase(index)}
                        className="ml-2 text-red-500 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="competitors" className="space-y-4 bg-transparent text-gray-900">
            <div className="bg-transparent">
              <h3 className="text-lg font-semibold mb-4">Competitor Domains</h3>
              <div className="flex gap-2 mb-4 bg-transparent">
                <Input
                  value={newCompetitor}
                  onChange={(e) => setNewCompetitor(e.target.value)}
                  placeholder="competitor.com"
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addCompetitor())}
                  className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
                />
                <Button type="button" onClick={addCompetitor}>
                  Add
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                {competitors.map((domain) => (
                  <Badge key={domain} variant="secondary" className="flex items-center gap-1">
                    {domain}
                    <X 
                      className="h-3 w-3 cursor-pointer hover:text-red-500" 
                      onClick={() => removeCompetitor(domain)}
                    />
                  </Badge>
                ))}
              </div>

              {competitors.length === 0 && (
                <p className="text-gray-500 text-sm">
                  Add competitor domains to track their content and performance
                </p>
              )}
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-between pt-6">
          {onBack && (
            <Button type="button" variant="outline" onClick={onBack}>
              Back
            </Button>
          )}
          <Button 
            type="submit" 
            disabled={loading}
            className="cylvy-btn-primary ml-auto"
          >
            {loading ? 'Saving...' : 'Continue to Verification'}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default AnalysisConfigStep
