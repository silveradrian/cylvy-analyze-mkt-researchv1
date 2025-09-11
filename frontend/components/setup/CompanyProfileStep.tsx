'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Building, 
  Globe,
  Users,
  Plus,
  X,
  Info
} from 'lucide-react'

interface CompanyProfileStepProps {
  data: any
  onComplete: (data: any) => void
  onBack?: () => void
}

interface Competitor {
  name: string
  domains: string[]
}

interface CompanyProfileData {
  // Basic fields
  company_name: string
  company_domain: string  // Primary domain
  description: string
  
  // Additional fields
  legal_name: string
  additional_domains: string[]
  competitors: Competitor[]
}

export default function CompanyProfileStep({ data, onComplete, onBack }: CompanyProfileStepProps) {
  const [activeTab, setActiveTab] = useState('basic')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  
  // Form state
  const [profile, setProfile] = useState<CompanyProfileData>({
    company_name: data?.company_name || '',
    company_domain: data?.company_domain || '',
    description: data?.description || '',
    legal_name: data?.legal_name || '',
    additional_domains: data?.additional_domains || [],
    competitors: data?.competitors || []
  })

  // Domain input state
  const [newDomain, setNewDomain] = useState('')
  
  // Competitor input state
  const [newCompetitor, setNewCompetitor] = useState({ name: '', domain: '' })

  // Update form when data prop changes
  useEffect(() => {
    if (data && Object.keys(data).length > 0) {
      setProfile({
        company_name: data.company_name || '',
        company_domain: data.company_domain || '',
        description: data.description || '',
        legal_name: data.legal_name || '',
        additional_domains: data.additional_domains || [],
        competitors: data.competitors || []
      })
    }
  }, [data])

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    
    if (!profile.company_name.trim()) {
      newErrors.company_name = 'Company name is required'
    }
    
    if (!profile.company_domain.trim()) {
      newErrors.company_domain = 'Primary domain is required'
    } else if (!/^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?(\.[a-zA-Z]{2,})+$/.test(profile.company_domain)) {
      newErrors.company_domain = 'Please enter a valid domain (e.g., example.com)'
    }
    
    if (!profile.legal_name.trim()) {
      newErrors.legal_name = 'Legal name is required'
    }
    
    if (!profile.description.trim()) {
      newErrors.description = 'Company description is required'
    } else if (profile.description.trim().split(/\s+/).length > 1000) {
      newErrors.description = 'Description must be 1000 words or less'
    }
    
    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) {
      console.log('Validation errors:', newErrors)
    }
    return Object.keys(newErrors).length === 0
  }

  const handleFieldChange = (field: string, value: any) => {
    setProfile(prev => ({ ...prev, [field]: value }))
    setTouched(prev => ({ ...prev, [field]: true }))
    setSaveStatus('idle')
  }

  const addDomain = () => {
    if (newDomain && /^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?(\.[a-zA-Z]{2,})+$/.test(newDomain)) {
      if (!profile.additional_domains.includes(newDomain) && newDomain !== profile.company_domain) {
        setProfile(prev => ({
          ...prev,
          additional_domains: [...prev.additional_domains, newDomain]
        }))
        setNewDomain('')
        setSaveStatus('idle')
      }
    }
  }

  const removeDomain = (domain: string) => {
    setProfile(prev => ({
      ...prev,
      additional_domains: prev.additional_domains.filter(d => d !== domain)
    }))
    setSaveStatus('idle')
  }

  const addCompetitor = () => {
    if (newCompetitor.name && newCompetitor.domain) {
      const existingCompetitor = profile.competitors.find(c => c.name === newCompetitor.name)
      
      if (existingCompetitor) {
        // Add domain to existing competitor
        if (!existingCompetitor.domains.includes(newCompetitor.domain)) {
          setProfile(prev => ({
            ...prev,
            competitors: prev.competitors.map(c => 
              c.name === newCompetitor.name
                ? { ...c, domains: [...c.domains, newCompetitor.domain] }
                : c
            )
          }))
        }
      } else {
        // Create new competitor
        setProfile(prev => ({
          ...prev,
          competitors: [...prev.competitors, { name: newCompetitor.name, domains: [newCompetitor.domain] }]
        }))
      }
      
      setNewCompetitor({ name: '', domain: '' })
      setSaveStatus('idle')
    }
  }

  const removeCompetitor = (competitorName: string) => {
    setProfile(prev => ({
      ...prev,
      competitors: prev.competitors.filter(c => c.name !== competitorName)
    }))
    setSaveStatus('idle')
  }

  const removeCompetitorDomain = (competitorName: string, domain: string) => {
    setProfile(prev => ({
      ...prev,
      competitors: prev.competitors.map(c => 
        c.name === competitorName
          ? { ...c, domains: c.domains.filter(d => d !== domain) }
          : c
      ).filter(c => c.domains.length > 0)  // Remove competitor if no domains left
    }))
    setSaveStatus('idle')
  }

  const handleSubmit = async () => {
    console.log('handleSubmit called')
    const isValid = validateForm()
    console.log('Form validation result:', isValid)
    if (isValid) {
      console.log('Form validation passed')
      setIsSaving(true)
      setSaveStatus('saving')
      
      try {
        const token = localStorage.getItem('access_token')
        console.log('Token:', token ? 'exists' : 'missing')
        
        // Prepare data for API
        const apiData = {
          company_name: profile.company_name,
          company_domain: profile.company_domain,
          description: profile.description,
          legal_name: profile.legal_name,
          additional_domains: profile.additional_domains,
          competitors: profile.competitors
        }
        
        console.log('Sending API request to /api/v1/config')
        console.log('API data:', apiData)
        
        const response = await fetch('/api/v1/config', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(apiData)
        })

        console.log('Response status:', response.status)
        
        if (response.ok) {
          setSaveStatus('saved')
          console.log('Calling onComplete callback')
          onComplete(apiData)
        } else {
          const errorText = await response.text()
          console.error('API error:', errorText)
          throw new Error(`Failed to save configuration: ${errorText}`)
        }
      } catch (error) {
        console.error('Error saving configuration:', error)
        setSaveStatus('error')
        setErrors({ submit: 'Failed to save configuration. Please try again.' })
      } finally {
        setIsSaving(false)
      }
    } else {
      console.log('Form validation failed, not submitting')
    }
  }

  // Word count for description
  const wordCount = profile.description.trim() ? profile.description.trim().split(/\s+/).length : 0

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <div className="flex items-center gap-2 mb-2">
          <Building className="w-6 h-6 text-cylvy-purple" />
          <CardTitle>Company Profile</CardTitle>
        </div>
        <CardDescription>
          Provide comprehensive company context for AI analysis
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="basic">Basic Information</TabsTrigger>
            <TabsTrigger value="market">Market & Competition</TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="space-y-6 mt-6">
            <div className="grid gap-6">
              {/* Company Name */}
              <div className="grid gap-2">
                <Label htmlFor="company_name">Company Name *</Label>
                <Input
                  id="company_name"
                  value={profile.company_name}
                  onChange={(e) => handleFieldChange('company_name', e.target.value)}
                  placeholder="e.g., Cylvy Technologies"
                  className={errors.company_name && touched.company_name ? 'border-red-500' : ''}
                />
                {errors.company_name && touched.company_name && (
                  <p className="text-sm text-red-500">{errors.company_name}</p>
                )}
              </div>

              {/* Legal Name */}
              <div className="grid gap-2">
                <Label htmlFor="legal_name">Full Legal Name *</Label>
                <Input
                  id="legal_name"
                  value={profile.legal_name}
                  onChange={(e) => handleFieldChange('legal_name', e.target.value)}
                  placeholder="e.g., Cylvy Technologies Inc."
                  className={errors.legal_name && touched.legal_name ? 'border-red-500' : ''}
                />
                {errors.legal_name && touched.legal_name && (
                  <p className="text-sm text-red-500">{errors.legal_name}</p>
                )}
              </div>

              {/* Primary Domain */}
              <div className="grid gap-2">
                <Label htmlFor="company_domain">Primary Domain *</Label>
                <Input
                  id="company_domain"
                  value={profile.company_domain}
                  onChange={(e) => handleFieldChange('company_domain', e.target.value)}
                  placeholder="e.g., cylvy.com"
                  className={errors.company_domain && touched.company_domain ? 'border-red-500' : ''}
                />
                {errors.company_domain && touched.company_domain && (
                  <p className="text-sm text-red-500">{errors.company_domain}</p>
                )}
              </div>

              {/* Additional Domains */}
              <div className="grid gap-2">
                <Label>Additional Domains</Label>
                <div className="flex gap-2">
                  <Input
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    placeholder="e.g., cylvy.ai"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addDomain())}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={addDomain}
                    disabled={!newDomain}
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {profile.additional_domains.map((domain) => (
                    <Badge key={domain} variant="secondary" className="gap-1">
                      <Globe className="w-3 h-3" />
                      {domain}
                      <button
                        onClick={() => removeDomain(domain)}
                        className="ml-1 hover:text-red-500"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div className="grid gap-2">
                <div className="flex justify-between items-center">
                  <Label htmlFor="description">Company Description *</Label>
                  <span className={`text-sm ${wordCount > 1000 ? 'text-red-500' : 'text-gray-500'}`}>
                    {wordCount}/1000 words
                  </span>
                </div>
                <Textarea
                  id="description"
                  value={profile.description}
                  onChange={(e) => handleFieldChange('description', e.target.value)}
                  placeholder="Provide a comprehensive description of your company, including what you do, your mission, and key value propositions..."
                  rows={8}
                  className={errors.description && touched.description ? 'border-red-500' : ''}
                />
                {errors.description && touched.description && (
                  <p className="text-sm text-red-500">{errors.description}</p>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="market" className="space-y-6 mt-6">
            {/* Competitors */}
            <div className="grid gap-4">
              <div>
                <Label className="text-base font-semibold mb-2 block">Competitors</Label>
                <p className="text-sm text-gray-600 mb-4">
                  Add your competitors and their domains for competitive analysis
                </p>
              </div>

              <div className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    value={newCompetitor.name}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Competitor name"
                    className="flex-1"
                  />
                  <Input
                    value={newCompetitor.domain}
                    onChange={(e) => setNewCompetitor(prev => ({ ...prev, domain: e.target.value }))}
                    placeholder="competitor.com"
                    className="flex-1"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addCompetitor())}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={addCompetitor}
                    disabled={!newCompetitor.name || !newCompetitor.domain}
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>

                <div className="space-y-3">
                  {profile.competitors.map((competitor) => (
                    <Card key={competitor.name} className="p-4">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-medium">{competitor.name}</h4>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeCompetitor(competitor.name)}
                          className="text-red-500 hover:text-red-700"
                        >
                          Remove
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {competitor.domains.map((domain) => (
                          <Badge key={domain} variant="outline" className="gap-1">
                            <Globe className="w-3 h-3" />
                            {domain}
                            <button
                              onClick={() => removeCompetitorDomain(competitor.name, domain)}
                              className="ml-1 hover:text-red-500"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    </Card>
                  ))}
                  
                  {profile.competitors.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Users className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                      <p>No competitors added yet</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Error message */}
        {errors.submit && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {errors.submit}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex justify-between mt-8">
          {onBack && (
            <Button
              type="button"
              variant="outline"
              onClick={onBack}
            >
              Back
            </Button>
          )}
          <Button
            onClick={handleSubmit}
            disabled={isSaving}
            className="ml-auto"
          >
            {isSaving ? 'Saving...' : 'Save & Continue'}
          </Button>
        </div>

        {/* Save status */}
        {saveStatus === 'saved' && (
          <p className="text-sm text-green-600 mt-2 text-center">
            ✓ Configuration saved successfully
          </p>
        )}
      </CardContent>
    </Card>
  )
}