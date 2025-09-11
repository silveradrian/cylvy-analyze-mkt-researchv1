'use client'

import React from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { Check, Circle, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SetupStep {
  id: string
  title: string
  description: string
  route: string
  status: 'not-started' | 'in-progress' | 'completed'
  dependencies?: string[]
}

interface SetupProgressTrackerProps {
  steps: SetupStep[]
  currentStepId?: string
  completedSteps: string[]
  className?: string
}

export function SetupProgressTracker({
  steps,
  currentStepId,
  completedSteps,
  className
}: SetupProgressTrackerProps) {
  const router = useRouter()
  const pathname = usePathname()
  
  // Check if all dependencies are met for a step
  const areDependenciesMet = (step: SetupStep) => {
    if (!step.dependencies || step.dependencies.length === 0) return true
    return step.dependencies.every(dep => completedSteps.includes(dep))
  }
  
  // Get step status
  const getStepStatus = (step: SetupStep) => {
    if (completedSteps.includes(step.id)) return 'completed'
    if (currentStepId === step.id || pathname === step.route) return 'in-progress'
    return 'not-started'
  }
  
  // Navigate to step if allowed
  const handleStepClick = (step: SetupStep) => {
    if (!areDependenciesMet(step)) {
      return // Can't access this step yet
    }
    router.push(step.route)
  }
  
  return (
    <div className={cn("bg-white border-b", className)}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Setup Progress</h2>
          <div className="text-sm text-gray-500">
            {completedSteps.length} of {steps.length} steps completed
          </div>
        </div>
        
        <div className="mt-4">
          {/* Progress bar */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center" aria-hidden="true">
              <div className="h-0.5 w-full bg-gray-200" />
              <div 
                className="absolute h-0.5 bg-cylvy-purple transition-all duration-500"
                style={{ 
                  width: `${(completedSteps.length / steps.length) * 100}%` 
                }}
              />
            </div>
            
            {/* Step indicators */}
            <div className="relative flex justify-between">
              {steps.map((step, index) => {
                const status = getStepStatus(step)
                const isAccessible = areDependenciesMet(step)
                const isActive = pathname === step.route
                
                return (
                  <div 
                    key={step.id}
                    className={cn(
                      "flex flex-col items-center cursor-pointer",
                      !isAccessible && "cursor-not-allowed opacity-50"
                    )}
                    onClick={() => handleStepClick(step)}
                  >
                    {/* Step circle */}
                    <div className={cn(
                      "relative flex h-8 w-8 items-center justify-center rounded-full border-2 bg-white transition-all",
                      status === 'completed' && "border-green-600 bg-green-600",
                      status === 'in-progress' && "border-cylvy-purple bg-cylvy-purple",
                      status === 'not-started' && "border-gray-300",
                      isActive && "ring-4 ring-cylvy-purple/20"
                    )}>
                      {status === 'completed' ? (
                        <Check className="h-4 w-4 text-white" />
                      ) : status === 'in-progress' ? (
                        <Circle className="h-3 w-3 text-white fill-current" />
                      ) : !isAccessible ? (
                        <Lock className="h-3 w-3 text-gray-400" />
                      ) : (
                        <span className="text-xs font-medium text-gray-600">
                          {index + 1}
                        </span>
                      )}
                    </div>
                    
                    {/* Step label */}
                    <div className="mt-2 text-center">
                      <div className={cn(
                        "text-xs font-medium",
                        status === 'completed' && "text-green-600",
                        status === 'in-progress' && "text-cylvy-purple",
                        status === 'not-started' && "text-gray-500"
                      )}>
                        {step.title}
                      </div>
                      {!isAccessible && step.dependencies && (
                        <div className="text-xs text-gray-400 mt-1">
                          Requires: {step.dependencies.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Hook to use setup progress throughout the app
export function useSetupProgress() {
  const [progress, setProgress] = React.useState<{
    currentStep?: string
    completedSteps: string[]
    isComplete: boolean
  }>({
    completedSteps: [],
    isComplete: false
  })
  
  React.useEffect(() => {
    checkSetupProgress()
  }, [])
  
  const checkSetupProgress = async () => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await fetch('/api/v1/setup/progress', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (response.ok) {
        const data = await response.json()
        setProgress(data)
      }
    } catch (error) {
      console.error('Failed to check setup progress:', error)
    }
  }
  
  const markStepComplete = async (stepId: string) => {
    try {
      const token = localStorage.getItem('access_token')
      await fetch(`/api/v1/setup/progress/${stepId}`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: 'completed' })
      })
      
      // Refresh progress
      await checkSetupProgress()
    } catch (error) {
      console.error('Failed to update step progress:', error)
    }
  }
  
  return { 
    ...progress, 
    markStepComplete,
    refresh: checkSetupProgress
  }
}

// Default setup flow configuration
export const DEFAULT_SETUP_FLOW: SetupStep[] = [
  {
    id: 'company',
    title: 'Company Profile',
    description: 'Basic company information and industry',
    route: '/setup/company',
    status: 'not-started'
  },
  {
    id: 'personas',
    title: 'Buyer Personas',
    description: 'Define your target buyer personas',
    route: '/setup/personas',
    status: 'not-started',
    dependencies: ['company']
  },
  {
    id: 'keywords',
    title: 'Keywords & Markets',
    description: 'Target keywords and geographic regions',
    route: '/setup/keywords',
    status: 'not-started',
    dependencies: ['personas']
  },
  {
    id: 'dimensions',
    title: 'Analysis Dimensions',
    description: 'Custom dimensions for competitive analysis',
    route: '/dimensions',
    status: 'not-started',
    dependencies: ['company', 'personas']
  },
  {
    id: 'landscapes',
    title: 'Digital Landscapes',
    description: 'Keyword groupings for landscape analysis',
    route: '/landscapes',
    status: 'not-started',
    dependencies: ['keywords']
  },
  {
    id: 'schedules',
    title: 'Pipeline Schedules',
    description: 'Automated data collection schedules',
    route: '/pipeline-schedules',
    status: 'not-started',
    dependencies: ['keywords']
  },
  {
    id: 'review',
    title: 'Review & Launch',
    description: 'Verify configuration and start first pipeline',
    route: '/setup/review',
    status: 'not-started',
    dependencies: ['company', 'personas', 'keywords']
  }
]
