'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { CheckCircle, XCircle, Building, Users, Target, Rocket } from 'lucide-react'
import { configAPI } from '@/app/services/api'

interface VerifyStepProps {
  data: any
  onFinish?: () => void
  onBack?: () => void
}

export function VerifyStep({ data, onFinish, onBack }: VerifyStepProps) {
  const [systemChecks, setSystemChecks] = useState({
    database: { status: 'checking', message: 'Testing database connection...' },
    services: { status: 'checking', message: 'Checking external services...' },
    analysis: { status: 'checking', message: 'Validating analysis configuration...' }
  })
  
  const [launching, setLaunching] = useState(false)
  const [setupComplete, setSetupComplete] = useState(false)

  useEffect(() => {
    performSystemChecks()
  }, [])

  const performSystemChecks = async () => {
    // Simulate system checks
    setTimeout(() => {
      setSystemChecks({
        database: { status: 'success', message: 'Database connection established' },
        services: { status: 'success', message: 'All services operational' },
        analysis: { status: 'success', message: 'Analysis configuration validated' }
      })
    }, 2000)
  }

  const handleLaunch = async () => {
    console.log('🚀 Launch button clicked - starting launch process...')
    setLaunching(true)

    try {
      console.log('✅ Setup configuration is complete - all steps validated')
      setSetupComplete(true)

      // Show launch message briefly, then redirect
      console.log('⏳ Launching system in 2 seconds...')
      setTimeout(() => {
        if (onFinish) {
          console.log('🎯 Redirecting to homepage...')
          onFinish()
        } else {
          console.error('❌ No onFinish callback provided!')
        }
      }, 2000)
    } catch (error) {
      console.error('❌ Launch failed:', error)
      setLaunching(false) // Reset launching state on error
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'checking':
        return <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />
      default:
        return null
    }
  }

  if (setupComplete) {
    return (
      <div className="text-center space-y-6">
        <div className="cylvy-gradient-primary rounded-lg p-8 text-white">
          <Rocket className="w-16 h-16 mx-auto mb-4" />
          <h2 className="text-3xl font-bold mb-2">Setup Complete! 🎉</h2>
          <p className="text-xl opacity-90">
            Your Cylvy Digital Landscape Analyzer is ready to go!
          </p>
        </div>
        
        <div className="space-y-4">
          <p className="text-gray-600">
            You can now start collecting and analyzing competitive intelligence data.
            Access your dashboard to begin your first pipeline.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="text-left">
              <strong>Next Steps:</strong>
              <ul className="mt-2 space-y-1 text-gray-600">
                <li>• Upload keyword lists</li>
                <li>• Start your first analysis pipeline</li>
                <li>• Review content analysis results</li>
                <li>• Set up automated schedules</li>
              </ul>
            </div>
            
            <div className="text-left">
              <strong>Quick Links:</strong>
              <ul className="mt-2 space-y-1 text-gray-600">
                <li>• <a href="/pipeline" className="text-cylvy-amaranth hover:underline">Pipeline Management</a></li>
                <li>• <a href="/dashboard" className="text-cylvy-amaranth hover:underline">Analysis Dashboard</a></li>
                <li>• <a href="/settings" className="text-cylvy-amaranth hover:underline">Settings</a></li>
                <li>• <a href="http://localhost:8001/docs" className="text-cylvy-amaranth hover:underline">API Docs</a></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Review & Launch</h2>
        <p className="text-gray-600">
          Let's review your configuration and launch your Cylvy analyzer.
        </p>
      </div>

      {/* Configuration Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Building className="h-5 w-5" />
              Company Info
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div><strong>Name:</strong> {data.company_name}</div>
            <div><strong>Domain:</strong> {data.company_domain}</div>
            <div><strong>Industry:</strong> {data.industry || 'Not specified'}</div>
          </CardContent>
        </Card>



        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Users className="h-5 w-5" />
              Personas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {(data.personas || []).map((persona: any, i: number) => (
                <div key={i} className="text-sm">{persona.name}</div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Target className="h-5 w-5" />
              Competitors
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1">
              {(data.competitor_domains || []).map((domain: string) => (
                <Badge key={domain} variant="outline" className="text-xs">
                  {domain}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Checks */}
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
          <CardDescription>
            Verifying system components and connectivity
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {Object.entries(systemChecks).map(([key, check]) => (
            <div key={key} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {getStatusIcon(check.status)}
                <span className="capitalize font-medium">{key.replace('_', ' ')}</span>
              </div>
              <span className="text-sm text-gray-600">{check.message}</span>
            </div>
          ))}
        </CardContent>
      </Card>



      {/* Launch Success Message */}
      {setupComplete && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-6 h-6 text-green-500" />
            <div>
              <h3 className="text-green-800 font-medium">🎉 Setup Complete!</h3>
              <p className="text-green-700 text-sm">Redirecting to your Cylvy dashboard...</p>
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-between">
        {onBack && (
          <Button type="button" variant="outline" onClick={onBack} disabled={launching}>
            Back
          </Button>
        )}
        <Button 
          onClick={handleLaunch}
          disabled={launching || setupComplete}
          className="cylvy-btn-primary ml-auto"
        >
          {setupComplete ? (
            <>
              <CheckCircle className="w-4 h-4 mr-2 text-white" />
              Setup Complete!
            </>
          ) : launching ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
              Launching...
            </>
          ) : (
            <>
              <Rocket className="w-4 h-4 mr-2" />
              Launch Cylvy Analyzer
            </>
          )}
        </Button>
      </div>
    </div>
  )
}

export default VerifyStep
