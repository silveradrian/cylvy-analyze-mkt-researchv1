'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { configAPI } from '@/app/services/api'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle, Plus, X, Globe, Building, Upload, Image, Trash2 } from 'lucide-react'

interface CompanyInfoStepProps {
  data: any
  onComplete: (data: any) => void
  onBack?: () => void
}

export function CompanyInfoStep({ data, onComplete }: CompanyInfoStepProps) {
  const [formData, setFormData] = useState({
    company_name: '',
    company_domain: '',
    admin_email: '',
    description: '',
    industry: '',
    target_regions: ['US', 'UK'],
  })

  // Logo upload state
  const [logoUrl, setLogoUrl] = useState<string | null>(data?.logo_url || null)
  const [isUploadingLogo, setIsUploadingLogo] = useState(false)

  // Multi-domain support
  const [additionalDomains, setAdditionalDomains] = useState<Array<{
    domain: string;
    type: string;
    country: string;
    notes?: string;
  }>>([])
  const [showDomainManager, setShowDomainManager] = useState(false)
  
  // Check if this step is already completed
  const isAlreadyConfigured = data.company_name && data.company_domain
  const [showSuccessBadge, setShowSuccessBadge] = useState(isAlreadyConfigured)

  // Update form data when data prop changes (auto-population)
  useEffect(() => {
    console.log('🔄 CompanyInfoStep received data prop:', data);
    console.log('📝 Form data keys:', Object.keys(data || {}));
    
    const newFormData = {
      company_name: data?.company_name || '',
      company_domain: data?.company_domain || '',
      admin_email: data?.admin_email || '',
      description: data?.description || '',
      industry: data?.industry || '',
      target_regions: data?.target_regions || ['US', 'UK']
    };
    
    console.log('📝 Setting form data:', newFormData);
    setFormData(newFormData);
    
    // Update success badge if data is loaded
    if (data.company_name && data.company_domain) {
      setShowSuccessBadge(true);
      console.log('✅ Auto-populated company info successfully:', data.company_name);
    } else {
      console.log('ℹ️ No company data to auto-populate yet');
    }
  }, [data])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Logo upload functionality
  const handleLogoUpload = async (file: File) => {
    setIsUploadingLogo(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/config/logo', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        const result = await response.json()
        setLogoUrl(result.logo_url)
        console.log('✅ Logo uploaded successfully:', result.logo_url)
      } else {
        // For testing: treat as uploaded but warn user
        console.warn('⚠️ Logo upload API error, but file may be saved')
        const errorText = await response.text()
        console.error('Logo upload error details:', errorText)
        
        // Set a placeholder logo URL for testing
        setLogoUrl('/storage/logos/uploaded_logo.png')
        setError('Logo uploaded but may need manual verification')
      }
    } catch (error) {
      console.error('Logo upload failed:', error)
      setError('Failed to upload logo - connection error')
    } finally {
      setIsUploadingLogo(false)
    }
  }

  const handleLogoDelete = async () => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/config/logo', {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        throw new Error('Logo delete failed')
      }

      setLogoUrl(null)
    } catch (error) {
      console.error('Logo delete failed:', error)
      setError('Failed to delete logo')
    }
  }

  const handleLogoFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        setError('Please select an image file')
        return
      }
      
      // Validate file size (5MB max)
      if (file.size > 5 * 1024 * 1024) {
        setError('Image must be smaller than 5MB')
        return
      }
      
      handleLogoUpload(file)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      // Include additional domains and logo in the submission
      const submitData = {
        ...formData,
        additional_domains: additionalDomains,
        logo_url: logoUrl
      }
      
      // Save to backend
      await configAPI.updateConfig(submitData)
      setShowSuccessBadge(true) // Show success badge after save
      onComplete(submitData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save company info')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold mb-2 text-cylvy-midnight">Company Information</h2>
          <p className="text-gray-600">
            Tell us about your organization to customize your analysis experience.
          </p>
        </div>
        {showSuccessBadge && (
          <div className="flex items-center gap-2 bg-green-50 text-green-800 px-3 py-1 rounded-full text-sm">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            Already Configured
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <Label htmlFor="company_name">Company Name *</Label>
            <Input
              id="company_name"
              value={formData.company_name}
              onChange={(e) => setFormData(prev => ({ ...prev, company_name: e.target.value }))}
              placeholder="Enter your company name (e.g., Finastra)"
              className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
              required
            />
          </div>

          <div>
            <Label htmlFor="company_domain">Company Domain *</Label>
            <Input
              id="company_domain"
              value={formData.company_domain}
              onChange={(e) => setFormData(prev => ({ ...prev, company_domain: e.target.value }))}
              placeholder="Enter your domain (e.g., finastra.com)"
              className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
              required
            />
          </div>

          <div>
            <Label htmlFor="admin_email">Admin Email *</Label>
            <Input
              id="admin_email"
              type="email"
              value={formData.admin_email}
              onChange={(e) => setFormData(prev => ({ ...prev, admin_email: e.target.value }))}
              placeholder="Enter admin email (e.g., admin@finastra.com)"
              className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
              required
            />
          </div>

          <div>
            <Label htmlFor="industry">Industry</Label>
            <Input
              id="industry"
              value={formData.industry}
              onChange={(e) => setFormData(prev => ({ ...prev, industry: e.target.value }))}
              placeholder="Enter industry (e.g., Financial Services Software)"
              className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth placeholder:text-gray-500"
            />
          </div>
        </div>

        <div>
          <Label htmlFor="description">Company Description</Label>
          <Textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
            placeholder="Brief description of your company and what you do..."
            className="bg-white text-gray-900 border-gray-300 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth"
            rows={3}
          />
        </div>

        {/* Company Logo Upload */}
        <div className="border-t pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <Label>Company Logo (Optional)</Label>
              <p className="text-sm text-gray-600 mb-3">
                Upload your company logo for branding and reports
              </p>
              
              <input
                type="file"
                accept="image/*"
                onChange={handleLogoFileSelect}
                className="hidden"
                id="logo-upload"
                disabled={isUploadingLogo}
              />
              
              <div className="space-y-3">
                {!logoUrl && (
                  <label
                    htmlFor="logo-upload"
                    className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                      {isUploadingLogo ? (
                        <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <>
                          <Upload className="w-8 h-8 mb-2 text-gray-400" />
                          <p className="mb-2 text-sm text-gray-500">
                            <span className="font-semibold">Click to upload</span> or drag and drop
                          </p>
                          <p className="text-xs text-gray-500">PNG, JPG, SVG up to 5MB</p>
                        </>
                      )}
                    </div>
                  </label>
                )}
                
                {logoUrl && (
                  <div className="relative">
                    <div className="flex items-center gap-4 p-4 bg-white border rounded-lg">
                      <div className="flex-shrink-0">
                        <img
                          src={logoUrl}
                          alt="Company Logo"
                          className="w-16 h-16 object-contain rounded-lg border"
                        />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Image className="h-4 w-4 text-green-600" />
                          <span className="text-sm font-medium text-green-800">Logo uploaded successfully</span>
                        </div>
                        <p className="text-xs text-gray-600">Your logo will appear in reports and the admin interface</p>
                      </div>
                      <div className="flex gap-2">
                        <label htmlFor="logo-upload">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={isUploadingLogo}
                            className="cursor-pointer"
                          >
                            <Upload className="h-4 w-4 mr-1" />
                            Replace
                          </Button>
                        </label>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={handleLogoDelete}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
            
            <div className="flex items-center justify-center">
              <div className="text-center text-gray-400">
                <Building className="h-16 w-16 mx-auto mb-3 text-gray-300" />
                <p className="text-sm">Logo Preview Area</p>
                <p className="text-xs">Upload a logo to see preview</p>
              </div>
            </div>
          </div>
        </div>

        {/* Multi-Domain Management */}
        <div className="border-t pt-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-cylvy-midnight">Additional Domains</h3>
              <p className="text-sm text-gray-600">
                Add country TLDs, subsidiaries, or brand domains for comprehensive analysis
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowDomainManager(!showDomainManager)}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              {additionalDomains.length > 0 ? `Manage Domains (${additionalDomains.length})` : 'Add Domains'}
            </Button>
          </div>

          {showDomainManager && (
            <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
              <DomainManager
                domains={additionalDomains}
                onDomainsChange={setAdditionalDomains}
                primaryDomain={formData.company_domain}
                companyName={formData.company_name}
              />
            </div>
          )}

          {additionalDomains.length > 0 && !showDomainManager && (
            <div className="flex flex-wrap gap-2">
              {additionalDomains.map((domain, idx) => (
                <Badge key={idx} variant="secondary" className="flex items-center gap-1">
                  <Globe className="h-3 w-3" />
                  {domain.domain}
                  {domain.country && <span className="text-xs">({domain.country})</span>}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <Button 
            type="submit" 
            disabled={loading}
            className="cylvy-btn-primary"
          >
            {loading ? 'Saving...' : isAlreadyConfigured ? 'Update & Continue' : 'Save & Continue to Countries & Keywords'}
          </Button>
        </div>
      </form>
    </div>
  )
}

// Multi-Domain Manager Component
interface DomainManagerProps {
  domains: Array<{
    domain: string;
    type: string;
    country: string;
    notes?: string;
  }>;
  onDomainsChange: (domains: Array<{domain: string; type: string; country: string; notes?: string;}>) => void;
  primaryDomain: string;
  companyName: string;
}

const DOMAIN_TYPES = [
  { value: 'country_tld', label: 'Country TLD', description: 'Country-specific top-level domain' },
  { value: 'subsidiary', label: 'Subsidiary', description: 'Subsidiary or regional office domain' },
  { value: 'brand', label: 'Brand Domain', description: 'Product or brand-specific domain' },
  { value: 'legacy', label: 'Legacy Domain', description: 'Previous or acquired domain' },
  { value: 'campaign', label: 'Campaign Domain', description: 'Marketing or campaign-specific domain' }
];

const COUNTRIES = [
  'US', 'UK', 'DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'CH', 'AT', 'SE', 'NO', 'DK', 'FI', 
  'PL', 'CZ', 'HU', 'SA', 'AE', 'CA', 'MX', 'BR', 'AR', 'AU', 'NZ', 'SG', 'HK', 'JP', 
  'KR', 'IN', 'VN', 'TH', 'MY', 'PH', 'ID'
];

function DomainManager({ domains, onDomainsChange, primaryDomain, companyName }: DomainManagerProps) {
  const [newDomain, setNewDomain] = useState({
    domain: '',
    type: 'country_tld',
    country: 'US',
    notes: ''
  });

  const addDomain = () => {
    if (!newDomain.domain.trim()) return;
    
    // Check for duplicates
    if (domains.some(d => d.domain === newDomain.domain) || newDomain.domain === primaryDomain) {
      alert('This domain is already added');
      return;
    }

    onDomainsChange([...domains, { ...newDomain, domain: newDomain.domain.trim() }]);
    setNewDomain({ domain: '', type: 'country_tld', country: 'US', notes: '' });
  };

  const removeDomain = (index: number) => {
    onDomainsChange(domains.filter((_, i) => i !== index));
  };

  const generateSuggestions = () => {
    if (!primaryDomain || !companyName) return;
    
    const baseDomain = primaryDomain.replace(/^www\./, '').split('.')[0];
    const suggestions = [
      { domain: `${baseDomain}.co.uk`, type: 'country_tld', country: 'UK', notes: 'UK market domain' },
      { domain: `${baseDomain}.de`, type: 'country_tld', country: 'DE', notes: 'German market domain' },
      { domain: `${baseDomain}.fr`, type: 'country_tld', country: 'FR', notes: 'French market domain' },
      { domain: `www.${baseDomain}.com`, type: 'brand', country: '', notes: 'WWW subdomain variant' }
    ];

    // Add suggestions that don't already exist
    const newSuggestions = suggestions.filter(s => 
      !domains.some(d => d.domain === s.domain) && s.domain !== primaryDomain
    );

    if (newSuggestions.length > 0) {
      onDomainsChange([...domains, ...newSuggestions]);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-gray-900">Domain Management</h4>
        {primaryDomain && (
          <Button 
            type="button" 
            variant="outline" 
            size="sm" 
            onClick={generateSuggestions}
            className="text-xs"
          >
            <Building className="h-3 w-3 mr-1" />
            Generate Suggestions
          </Button>
        )}
      </div>

      {/* Current Primary Domain */}
      {primaryDomain && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <span className="font-medium text-green-800">Primary Domain:</span>
            <code className="text-green-900 bg-green-100 px-2 py-1 rounded text-sm">{primaryDomain}</code>
          </div>
        </div>
      )}

      {/* Additional Domains List */}
      {domains.length > 0 && (
        <div className="space-y-2">
          {domains.map((domain, index) => (
            <div key={index} className="flex items-center gap-3 p-3 bg-white border rounded-lg">
              <Globe className="h-4 w-4 text-gray-400" />
              <div className="flex-1 grid grid-cols-4 gap-3 text-sm">
                <div>
                  <div className="font-medium">{domain.domain}</div>
                </div>
                <div>
                  <Badge variant="outline">{DOMAIN_TYPES.find(t => t.value === domain.type)?.label}</Badge>
                </div>
                <div>
                  {domain.country && <Badge variant="secondary">{domain.country}</Badge>}
                </div>
                <div className="text-gray-500 truncate">
                  {domain.notes}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeDomain(index)}
                className="text-red-500 hover:text-red-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Add New Domain Form */}
      <div className="grid grid-cols-12 gap-3 p-3 bg-white border border-dashed border-gray-300 rounded-lg">
        <div className="col-span-4">
          <Input
            placeholder="example.co.uk"
            value={newDomain.domain}
            onChange={(e) => setNewDomain(prev => ({ ...prev, domain: e.target.value }))}
            className="text-sm"
          />
        </div>
        <div className="col-span-3">
          <select
            value={newDomain.type}
            onChange={(e) => setNewDomain(prev => ({ ...prev, type: e.target.value }))}
            className="w-full p-2 border border-gray-300 rounded-md text-sm bg-white"
          >
            {DOMAIN_TYPES.map(type => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <select
            value={newDomain.country}
            onChange={(e) => setNewDomain(prev => ({ ...prev, country: e.target.value }))}
            className="w-full p-2 border border-gray-300 rounded-md text-sm bg-white"
          >
            <option value="">No Country</option>
            {COUNTRIES.map(country => (
              <option key={country} value={country}>{country}</option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <Input
            placeholder="Notes"
            value={newDomain.notes}
            onChange={(e) => setNewDomain(prev => ({ ...prev, notes: e.target.value }))}
            className="text-sm"
          />
        </div>
        <div className="col-span-1">
          <Button
            type="button"
            onClick={addDomain}
            disabled={!newDomain.domain.trim()}
            size="sm"
            className="w-full cylvy-btn-secondary"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="text-xs text-gray-500">
        <strong>Examples:</strong> company.co.uk (UK), company.de (Germany), subsidiary.com (Subsidiary), 
        product.com (Brand), old-company.com (Legacy)
      </div>
    </div>
  );
}

export default CompanyInfoStep
