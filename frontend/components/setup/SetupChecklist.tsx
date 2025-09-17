'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { 
  Check, 
  Circle, 
  AlertCircle, 
  ChevronRight,
  Building,
  Target,
  Layers,
  Globe,
  Calendar,
  Rocket,
  Users,
  Settings
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

// Simple Progress component inline
const Progress = ({ value, className }: { value: number; className?: string }) => (
  <div className={cn("relative h-2 w-full overflow-hidden rounded-full bg-gray-200", className)}>
    <div 
      className="h-full bg-cylvy-purple transition-all duration-300 ease-in-out"
      style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
    />
  </div>
)

interface ChecklistItem {
  id: string
  title: string
  description: string
  icon: React.ElementType
  route: string
  checkFunction: () => Promise<boolean>
  isOptional?: boolean
  status?: 'pending' | 'complete' | 'incomplete'
}

export function SetupChecklist() {
  const router = useRouter()
  const [items, setItems] = useState<ChecklistItem[]>([
    {
      id: 'company',
      title: 'Company Profile',
      description: 'Provide comprehensive company context for AI analysis',
      icon: Building,
      route: '/setup?step=company',
      checkFunction: async () => {
        try {
          const token = localStorage.getItem('access_token')
          const response = await fetch('/api/v1/config', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (response.ok) {
            const data = await response.json()
            return !!(data.company_name && data.company_domain && data.legal_name && data.description)
          }
        } catch {
          return false
        }
        return false
      }
    },
    {
      id: 'personas',
      title: 'Buyer Personas',
      description: 'Define your target buyer personas',
      icon: Users,
      route: '/setup?step=personas',
      checkFunction: async () => {
        try {
          const token = localStorage.getItem('access_token')
          const response = await fetch('/api/v1/analysis/personas', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (response.ok) {
            const data = await response.json()
            return data.personas && data.personas.length >= 1
          }
        } catch {
          return false
        }
        return false
      }
    },
    {
      id: 'keywords',
      title: 'Keywords Configuration',
      description: 'Add at least 5 target keywords',
      icon: Target,
      route: '/setup?step=countries',
      checkFunction: async () => {
        try {
          const token = localStorage.getItem('access_token')
          const response = await fetch('/api/v1/keywords', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (response.ok) {
            const data = await response.json()
            return Array.isArray(data) ? data.length >= 5 : (data.value && data.value.length >= 5)
          }
        } catch {
          return false
        }
        return false
      }
    },
    {
      id: 'dimensions',
      title: 'Custom Dimensions',
      description: 'Create analysis dimensions',
      icon: Layers,
      route: '/dimensions',
      checkFunction: async () => {
        try {
          const token = localStorage.getItem('access_token')
          const response = await fetch('/api/v1/dimensions/dimensions', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (response.ok) {
            const data = await response.json()
            return Array.isArray(data) && data.length > 0
          }
        } catch {
          return false
        }
        return false
      },
      isOptional: true
    },
    {
      id: 'default-dimensions',
      title: 'Default Dimensions',
      description: 'Configure JTBD Phases & Page Types',
      icon: Settings,
      route: '/settings',
      checkFunction: async () => {
        // Default dimensions are pre-populated, so always return true
        return true
      },
      isOptional: true
    },
    {
      id: 'landscapes',
      title: 'Digital Landscapes',
      description: 'Define keyword groupings',
      icon: Globe,
      route: '/landscapes',
      checkFunction: async () => {
        try {
          const token = localStorage.getItem('access_token')
          const response = await fetch('/api/v1/landscapes', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (response.ok) {
            const data = await response.json()
            return Array.isArray(data) && data.length > 0
          }
        } catch {
          return false
        }
        return false
      },
      isOptional: true
    },
    {
      id: 'schedule',
      title: 'Pipeline Schedule',
      description: 'Configure automated collection',
      icon: Calendar,
      route: '/pipeline-schedules',
      checkFunction: async () => {
        try {
          const token = localStorage.getItem('access_token')
          const response = await fetch('/api/v1/pipeline/schedules', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
          if (response.ok) {
            const data = await response.json()
            return data.schedules && Array.isArray(data.schedules) // Schedules exist (even if empty initially)
          }
        } catch {
          return false
        }
        return false
      }
    }
  ])
  
  const [loading, setLoading] = useState(true)
  const [completedCount, setCompletedCount] = useState(0)
  const [requiredCount, setRequiredCount] = useState(0)
  
  useEffect(() => {
    checkAllItems()
    // Re-check every 5 seconds to catch changes
    const interval = setInterval(checkAllItems, 5000)
    return () => clearInterval(interval)
  }, [])
  
  const checkAllItems = async () => {
    setLoading(true)
    let completed = 0
    let required = 0
    
    const updatedItems = await Promise.all(
      items.map(async (item) => {
        const isComplete = await item.checkFunction()
        if (isComplete) completed++
        if (!item.isOptional) required++
        
        return {
          ...item,
          status: isComplete ? 'complete' : 'incomplete'
        }
      })
    )
    
    setItems(updatedItems)
    setCompletedCount(completed)
    setRequiredCount(required)
    setLoading(false)
  }
  
  const getRequiredCompleteCount = () => {
    return items.filter(item => !item.isOptional && item.status === 'complete').length
  }
  
  const isSetupComplete = () => {
    return items.filter(item => !item.isOptional).every(item => item.status === 'complete')
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              {isSetupComplete() ? (
                <>
                  <Check className="h-5 w-5 text-green-600" />
                  Setup Complete!
                </>
              ) : (
                <>
                  <AlertCircle className="h-5 w-5 text-amber-600" />
                  Complete Your Setup
                </>
              )}
            </CardTitle>
            <CardDescription>
              {isSetupComplete() 
                ? "You're ready to start your first pipeline analysis"
                : `Complete ${requiredCount - getRequiredCompleteCount()} more required steps to get started`
              }
            </CardDescription>
          </div>
          {isSetupComplete() && (
            <Button onClick={() => router.push('/pipeline')}>
              <Rocket className="h-4 w-4 mr-2" />
              Launch Pipeline
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>{getRequiredCompleteCount()} of {requiredCount} required steps</span>
            <span>{Math.round((getRequiredCompleteCount() / requiredCount) * 100)}%</span>
          </div>
          <Progress 
            value={(getRequiredCompleteCount() / requiredCount) * 100} 
            className="h-2"
          />
        </div>
        
        {/* Checklist items */}
        <div className="space-y-3">
          {items.map((item) => {
            const Icon = item.icon
            const isComplete = item.status === 'complete'
            
            return (
              <div
                key={item.id}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border transition-all cursor-pointer",
                  isComplete ? "bg-green-50 border-green-200 hover:bg-green-100" : "hover:bg-gray-50"
                )}
                onClick={() => router.push(item.route)}
              >
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full",
                    isComplete ? "bg-green-100" : "bg-gray-100"
                  )}>
                    <Icon className={cn(
                      "h-5 w-5",
                      isComplete ? "text-green-600" : "text-gray-500"
                    )} />
                  </div>
                  
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className={cn(
                        "font-medium",
                        isComplete && "text-green-700"
                      )}>
                        {item.title}
                      </h4>
                      {item.isOptional && (
                        <Badge variant="outline" className="text-xs">
                          Optional
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-600">{item.description}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  {isComplete && (
                    <Check className="h-5 w-5 text-green-600" />
                  )}
                  <Button 
                    variant={isComplete ? "outline" : "ghost"}
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      router.push(item.route)
                    }}
                  >
                    {isComplete ? "View" : "Configure"}
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
        
        {/* Optional items hint */}
        {items.some(item => item.isOptional && item.status !== 'complete') && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-700">
              💡 <strong>Tip:</strong> Optional steps enhance your analysis but aren't required to get started.
              You can configure these anytime.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
