'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  Globe, Upload, FileText, CheckCircle, 
  AlertTriangle, X, Download 
} from 'lucide-react'

interface CountriesKeywordsStepProps {
  data: any
  onComplete: (data: any) => void
  onBack?: () => void
}

interface Country {
  code: string
  name: string
  flag: string
  serp_code: string // For SERP API
}

const AVAILABLE_COUNTRIES: Country[] = [
  // Your Next Client's Primary Countries
  { code: 'US', name: 'United States', flag: '🇺🇸', serp_code: 'us' },
  { code: 'UK', name: 'United Kingdom', flag: '🇬🇧', serp_code: 'uk' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪', serp_code: 'de' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦', serp_code: 'sa' },
  { code: 'VN', name: 'Vietnam', flag: '🇻🇳', serp_code: 'vn' },
  
  // EMEA Countries
  { code: 'FR', name: 'France', flag: '🇫🇷', serp_code: 'fr' },
  { code: 'ES', name: 'Spain', flag: '🇪🇸', serp_code: 'es' },
  { code: 'IT', name: 'Italy', flag: '🇮🇹', serp_code: 'it' },
  { code: 'NL', name: 'Netherlands', flag: '🇳🇱', serp_code: 'nl' },
  { code: 'BE', name: 'Belgium', flag: '🇧🇪', serp_code: 'be' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭', serp_code: 'ch' },
  { code: 'AT', name: 'Austria', flag: '🇦🇹', serp_code: 'at' },
  { code: 'SE', name: 'Sweden', flag: '🇸🇪', serp_code: 'se' },
  { code: 'NO', name: 'Norway', flag: '🇳🇴', serp_code: 'no' },
  { code: 'DK', name: 'Denmark', flag: '🇩🇰', serp_code: 'dk' },
  { code: 'FI', name: 'Finland', flag: '🇫🇮', serp_code: 'fi' },
  { code: 'PL', name: 'Poland', flag: '🇵🇱', serp_code: 'pl' },
  { code: 'CZ', name: 'Czech Republic', flag: '🇨🇿', serp_code: 'cz' },
  { code: 'HU', name: 'Hungary', flag: '🇭🇺', serp_code: 'hu' },
  { code: 'AE', name: 'UAE', flag: '🇦🇪', serp_code: 'ae' },
  { code: 'ZA', name: 'South Africa', flag: '🇿🇦', serp_code: 'za' },
  
  // North America
  { code: 'CA', name: 'Canada', flag: '🇨🇦', serp_code: 'ca' },
  { code: 'MX', name: 'Mexico', flag: '🇲🇽', serp_code: 'mx' },
  
  // South America
  { code: 'BR', name: 'Brazil', flag: '🇧🇷', serp_code: 'br' },
  { code: 'AR', name: 'Argentina', flag: '🇦🇷', serp_code: 'ar' },
  { code: 'CL', name: 'Chile', flag: '🇨🇱', serp_code: 'cl' },
  { code: 'CO', name: 'Colombia', flag: '🇨🇴', serp_code: 'co' },
  { code: 'PE', name: 'Peru', flag: '🇵🇪', serp_code: 'pe' },
  
  // Asia-Pacific
  { code: 'AU', name: 'Australia', flag: '🇦🇺', serp_code: 'au' },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿', serp_code: 'nz' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬', serp_code: 'sg' },
  { code: 'HK', name: 'Hong Kong', flag: '🇭🇰', serp_code: 'hk' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵', serp_code: 'jp' },
  { code: 'KR', name: 'South Korea', flag: '🇰🇷', serp_code: 'kr' },
  { code: 'IN', name: 'India', flag: '🇮🇳', serp_code: 'in' },
  { code: 'TH', name: 'Thailand', flag: '🇹🇭', serp_code: 'th' },
  { code: 'MY', name: 'Malaysia', flag: '🇲🇾', serp_code: 'my' },
  { code: 'PH', name: 'Philippines', flag: '🇵🇭', serp_code: 'ph' },
  { code: 'ID', name: 'Indonesia', flag: '🇮🇩', serp_code: 'id' }
]

// Regional Groupings for Quick Selection
const REGIONAL_GROUPS = {
  'client_primary': {
    name: 'Your Client Markets',
    countries: ['US', 'UK', 'DE', 'SA', 'VN'],
    description: 'Primary markets for your next client'
  },
  'emea': {
    name: 'EMEA',
    countries: ['UK', 'DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'CH', 'AT', 'SE', 'NO', 'DK', 'FI', 'PL', 'CZ', 'HU', 'AE', 'SA', 'ZA'],
    description: 'Europe, Middle East & Africa'
  },
  'americas': {
    name: 'Americas',
    countries: ['US', 'CA', 'MX', 'BR', 'AR', 'CL', 'CO', 'PE'],
    description: 'North & South America'
  },
  'apac': {
    name: 'Asia-Pacific',
    countries: ['AU', 'NZ', 'SG', 'HK', 'JP', 'KR', 'IN', 'TH', 'MY', 'PH', 'ID', 'VN'],
    description: 'Asia-Pacific region'
  }
}

export function CountriesKeywordsStep({ data, onComplete, onBack }: CountriesKeywordsStepProps) {
  const [selectedCountries, setSelectedCountries] = useState<string[]>(
    data.target_countries || ['US', 'UK', 'DE', 'SA', 'VN']  // Default to client primary markets
  )
  const [keywordFile, setKeywordFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<{
    status: 'idle' | 'uploading' | 'success' | 'error'
    message?: string
    details?: any
  }>({ status: 'idle' })
  const [existingKeywords, setExistingKeywords] = useState<any[]>([])
  const [loadingKeywords, setLoadingKeywords] = useState(false)
  
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load existing keywords on component mount and when data prop changes
  useEffect(() => {
    console.log('📊 CountriesKeywordsStep received data:', data);
    console.log('📋 Data keys:', Object.keys(data || {}));
    
    // Check multiple ways keywords might be passed
    if (data.existing_keywords && data.existing_keywords.length > 0) {
      console.log('✅ Using keywords from setup wizard existing_keywords:', data.existing_keywords.length);
      setExistingKeywords(data.existing_keywords);
      setUploadStatus({
        status: 'success',
        message: `${data.existing_keywords.length} keywords already configured`,
        details: { total: data.existing_keywords.length, existing: true }
      });
    } else if (data.keywords_uploaded || data.keywords_count > 0) {
      console.log('✅ Keywords uploaded flag detected, loading from API...');
      loadExistingKeywords();
    } else {
      console.log('🔍 No keywords in data prop, checking API...');
      loadExistingKeywords();
    }
  }, [data])

  const loadExistingKeywords = async () => {
    setLoadingKeywords(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/keywords', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const keywordData = await response.json()
        console.log('📊 Existing keywords loaded:', keywordData.total || 0)
        setExistingKeywords(keywordData.keywords || [])
        
        // Mark as already uploaded if we have keywords
        if (keywordData.total > 0) {
          setUploadStatus({
            status: 'success',
            message: `${keywordData.total} keywords already configured`,
            details: { total: keywordData.total, existing: true }
          })
        }
      }
    } catch (error) {
      console.error('Failed to load existing keywords:', error)
    } finally {
      setLoadingKeywords(false)
    }
  }

  const toggleCountry = (countryCode: string) => {
    setSelectedCountries(prev => 
      prev.includes(countryCode)
        ? prev.filter(c => c !== countryCode)
        : [...prev, countryCode]
    )
  }

  const selectRegionalGroup = (groupKey: string) => {
    const group = REGIONAL_GROUPS[groupKey]
    if (group) {
      setSelectedCountries(group.countries)
    }
  }

  const clearSelection = () => {
    setSelectedCountries([])
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      if (!file.name.endsWith('.csv')) {
        setUploadStatus({
          status: 'error',
          message: 'Please select a CSV file'
        })
        return
      }
      setKeywordFile(file)
      setUploadStatus({ status: 'idle' })
    }
  }

  const uploadKeywords = async () => {
    if (!keywordFile || selectedCountries.length === 0) return

    setUploadStatus({ status: 'uploading', message: 'Uploading keywords...' })

    try {
      const formData = new FormData()
      formData.append('file', keywordFile)
      formData.append('regions', selectedCountries.join(','))

      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/keywords/upload', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        const result = await response.json()
        console.log('📤 Upload Response:', result)
        
        if (result.keywords_processed > 0) {
          setUploadStatus({
            status: 'success',
            message: `Successfully uploaded ${result.keywords_processed} keywords`,
            details: result
          })
          
          // Reload keywords to update the display
          console.log('🔄 Reloading keywords after successful upload...');
          await loadExistingKeywords();
        } else {
          setUploadStatus({
            status: 'error',
            message: `Upload failed: ${result.errors?.join('; ') || 'No keywords processed'}`,
            details: result
          })
        }
      } else {
        const errorText = await response.text()
        console.error('❌ Upload Error Response:', errorText)
        
        let errorMessage = 'Upload failed'
        try {
          const errorJson = JSON.parse(errorText)
          errorMessage = errorJson.error?.message || errorJson.message || 'Upload failed'
        } catch {
          errorMessage = `Upload failed (${response.status}): ${errorText.substring(0, 100)}`
        }
        
        setUploadStatus({
          status: 'error',
          message: errorMessage,
          details: errorText
        })
      }
    } catch (error) {
      setUploadStatus({
        status: 'error',
        message: 'Upload failed - check your connection'
      })
    }
  }

  const downloadTemplate = () => {
    const csvContent = `Keyword,Category,JTBD Stage,Avg Monthly Searches (US),Client Score,SEO Score,Persona Score,Is Branded
digital banking,Financial Technology,Consideration,5400,8.5,7.2,9.1,false
open banking API,API Technology,Decision,1200,9.2,6.8,8.7,false
fintech solutions,Solutions,Awareness,8900,7.8,8.1,8.9,false
banking software,Technology,Consideration,3200,8.0,7.5,8.5,false
cloud banking,Technology,Decision,2800,8.8,7.8,9.0,false`

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'keyword_template.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  const handleNext = () => {
    if (selectedCountries.length === 0) {
      setUploadStatus({
        status: 'error',
        message: 'Please select at least one country'
      })
      return
    }

    onComplete({
      target_countries: selectedCountries,
      keywords_uploaded: uploadStatus.status === 'success' || existingKeywords.length > 0,
      upload_details: uploadStatus.details || { total: existingKeywords.length, existing: true }
    })
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-cylvy-midnight mb-2">Countries & Keywords</h2>
        <p className="text-gray-600">
          Select target countries for SERP analysis and upload your keyword list
        </p>
      </div>

      {/* Country Selection */}
      <Card className="bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-cylvy-midnight">
            <Globe className="h-5 w-5" />
            Target Countries
          </CardTitle>
          <CardDescription>
            Select countries where you want to analyze SERPs and create digital landscapes.
            Each country will have its own search results and rankings.
          </CardDescription>
        </CardHeader>
        <CardContent className="bg-white">
          {/* Regional Quick Selection */}
          <div className="mb-6 space-y-3 bg-white">
            <Label className="text-sm font-medium text-gray-700">Quick Regional Selection:</Label>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {Object.entries(REGIONAL_GROUPS).map(([key, group]) => (
                <Button
                  key={key}
                  variant="outline"
                  size="sm"
                  onClick={() => selectRegionalGroup(key)}
                  className={`text-left h-auto p-3 bg-white hover:bg-gray-50 ${
                    key === 'client_primary' ? 'border-cylvy-amaranth bg-cylvy-amaranth/5' : 'border-gray-200'
                  }`}
                >
                  <div className="w-full">
                    <div className="font-medium text-sm text-gray-900">{group.name}</div>
                    <div className="text-xs text-gray-500 mt-1 line-clamp-2">{group.description}</div>
                    <div className="text-xs text-gray-400 mt-1">{group.countries.length} countries</div>
                  </div>
                </Button>
              ))}
            </div>
            <div className="flex gap-2 bg-white">
              <Button variant="outline" size="sm" onClick={clearSelection} className="bg-white hover:bg-gray-50">
                Clear All
              </Button>
              <Button variant="outline" size="sm" onClick={() => selectRegionalGroup('client_primary')} className="bg-white hover:bg-gray-50">
                Reset to Primary Markets
              </Button>
            </div>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {AVAILABLE_COUNTRIES.map((country) => (
              <div
                key={country.code}
                className={`flex items-center space-x-3 p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedCountries.includes(country.code)
                    ? 'border-cylvy-amaranth bg-cylvy-amaranth/10'
                    : 'border-gray-200 hover:border-cylvy-amaranth/50'
                }`}
                onClick={() => toggleCountry(country.code)}
              >
                <Checkbox
                  checked={selectedCountries.includes(country.code)}
                  onChange={() => {}} // Handled by div click
                  className="pointer-events-none"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{country.flag}</span>
                    <span className="font-medium text-sm truncate">{country.name}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          
          <div className="mt-4">
            <Label className="text-sm font-medium text-gray-700">
              Selected Countries ({selectedCountries.length}):
            </Label>
            <div className="flex flex-wrap gap-2 mt-2">
              {selectedCountries.map(code => {
                const country = AVAILABLE_COUNTRIES.find(c => c.code === code)
                return country ? (
                  <Badge key={code} variant="secondary" className="flex items-center gap-1">
                    <span>{country.flag}</span>
                    <span>{country.name}</span>
                    <X 
                      className="h-3 w-3 cursor-pointer hover:text-red-500" 
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleCountry(code)
                      }}
                    />
                  </Badge>
                ) : null
              })}
            </div>
            
            {selectedCountries.length > 0 && (
              <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                <div className="text-sm text-blue-800">
                  <strong>SERP Analysis Impact:</strong> Each country will have dedicated search result collection.
                  You'll be able to create separate Digital Landscapes for each market.
                </div>
                <div className="text-xs text-blue-600 mt-1">
                  Pipeline will collect {selectedCountries.length} × [number of keywords] SERP results
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Existing Keywords Status */}
      {loadingKeywords && (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-blue-700">Checking for existing keywords...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {existingKeywords.length > 0 && (
        <Card className="bg-green-50 border-green-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-800">
              <CheckCircle className="h-5 w-5" />
              Existing Keywords Configuration
            </CardTitle>
            <CardDescription className="text-green-700">
              Your project already has {existingKeywords.length} keywords configured.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 bg-white">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 max-h-32 overflow-y-auto">
              {existingKeywords.slice(0, 12).map((keyword: any, index: number) => (
                <Badge key={index} variant="secondary" className="text-xs">
                  {keyword.keyword}
                </Badge>
              ))}
              {existingKeywords.length > 12 && (
                <Badge variant="outline" className="text-xs">
                  +{existingKeywords.length - 12} more
                </Badge>
              )}
            </div>
            <div className="flex justify-between items-center pt-2">
              <span className="text-sm text-green-600">
                ✅ Keywords are configured and ready for analysis
              </span>
              <Button
                onClick={loadExistingKeywords}
                variant="outline"
                size="sm"
                className="text-xs"
              >
                🔄 Refresh
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Keywords Upload */}
      <Card className="bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-cylvy-midnight">
            {existingKeywords.length > 0 ? <CheckCircle className="h-5 w-5 text-green-600" /> : <FileText className="h-5 w-5" />}
            {existingKeywords.length > 0 ? 'Keywords Successfully Uploaded' : 'Keywords Upload'}
          </CardTitle>
          <CardDescription>
            {existingKeywords.length > 0 
              ? `✅ ${existingKeywords.length} keywords are configured and ready for analysis. You can re-upload to update them.`
              : 'Upload your CSV file with keywords, categories, scores, and rationales. These keywords will be analyzed across all selected countries.'
            }
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 bg-white">
          {/* Template Download */}
          <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
            <div>
              <h4 className="font-medium text-blue-900">Need the CSV template?</h4>
              <p className="text-sm text-blue-700">Download the template with required columns and examples</p>
            </div>
            <Button variant="outline" onClick={downloadTemplate} className="flex items-center gap-2">
              <Download className="h-4 w-4" />
              Download Template
            </Button>
          </div>

          {/* File Upload */}
          <div className="space-y-4 bg-white">
            <div className="bg-white">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
              />
              <Button
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                className="w-full h-24 border-2 border-dashed border-gray-300 hover:border-cylvy-amaranth"
              >
                <div className="text-center">
                  <Upload className="h-8 w-8 mx-auto mb-2 text-gray-400" />
                  <p className="text-sm font-medium">
                    {keywordFile ? keywordFile.name : 'Click to select CSV file'}
                  </p>
                  <p className="text-xs text-gray-500">
                    CSV file with keywords, categories, JTBD stages, and scores
                  </p>
                </div>
              </Button>
            </div>

            {keywordFile && (
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium">{keywordFile.name}</span>
                  <Badge variant="outline">{(keywordFile.size / 1024).toFixed(1)} KB</Badge>
                </div>
                <Button
                  onClick={uploadKeywords}
                  disabled={uploadStatus.status === 'uploading' || selectedCountries.length === 0}
                  className="cylvy-btn-primary"
                >
                  {uploadStatus.status === 'uploading' ? 'Uploading...' : 'Upload Keywords'}
                </Button>
              </div>
            )}
          </div>

          {/* Upload Status */}
          {uploadStatus.message && (
            <Alert className={
              uploadStatus.status === 'success' ? 'border-green-200 bg-green-50' :
              uploadStatus.status === 'error' ? 'border-red-200 bg-red-50' :
              'border-blue-200 bg-blue-50'
            }>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {uploadStatus.status === 'success' && <CheckCircle className="h-4 w-4 text-green-600" />}
                  {uploadStatus.status === 'error' && <AlertTriangle className="h-4 w-4 text-red-600" />}
                  <AlertDescription className={
                    uploadStatus.status === 'success' ? 'text-green-800' :
                    uploadStatus.status === 'error' ? 'text-red-800' :
                    'text-blue-800'
                  }>
                    {uploadStatus.message}
                  </AlertDescription>
                </div>
                {existingKeywords.length > 0 && uploadStatus.status === 'success' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setUploadStatus({ status: 'idle' });
                      setKeywordFile(null);
                      if (fileInputRef.current) {
                        fileInputRef.current.value = '';
                      }
                    }}
                    className="text-xs"
                  >
                    🔄 Re-upload Keywords
                  </Button>
                )}
              </div>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Back to Company Info
        </Button>
        <Button 
          onClick={handleNext}
          className="cylvy-btn-primary"
          disabled={selectedCountries.length === 0}
        >
          Continue to Branding
        </Button>
      </div>
    </div>
  )
}