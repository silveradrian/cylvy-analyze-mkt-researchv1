# Frontend Usability Audit & Recommendations

## Executive Summary

The current frontend has several overlapping configuration areas and lacks a clear sequential flow for platform setup. This document provides recommendations to improve usability through better navigation, eliminating duplication, and implementing a setup progress tracker.

### Latest Updates
- **Buyer Personas**: Now a mandatory setup step after Company Profile
- **JTBD Phases**: Pre-configured with Gartner's B2B buying journey phases (optional customization)
- **Setup Flow**: Company → Personas → Keywords → Dimensions/Landscapes → Schedule → Launch

## Current Issues Identified

### 1. Configuration Duplication

**Problem Areas:**
- **Keywords & Regions**: Configured in both `/setup` (Setup Wizard) and `/settings` pages
- **Analysis Settings**: Split between `/setup` (Analysis Config Step) and `/settings` (Advanced Settings)
- **JTBD Phases**: Can be configured in both `/setup` and `/settings`
- **Content Types**: Managed in both `/pipeline-schedules` and indirectly in `/setup`

### 2. Unclear Navigation Flow

- No clear indication of what order pages should be visited
- Missing visual progress indicators
- Setup wizard exists but doesn't integrate with other configuration pages
- No way to know if setup is complete

### 3. Fragmented Configuration

- Company info in `/setup`
- Dimensions in `/dimensions`
- Landscapes in `/landscapes`
- Schedules in `/pipeline-schedules`
- Advanced settings in `/settings`

## Recommended Solution: Sequential Setup Flow with Progress Tracking

### 1. Implement a Setup Progress Component

Create a persistent progress tracker that shows across all admin pages:

```typescript
// components/setup/SetupProgressTracker.tsx
interface SetupStep {
  id: string
  title: string
  description: string
  route: string
  status: 'not-started' | 'in-progress' | 'completed'
  dependencies?: string[] // Other steps that must be completed first
}

const SETUP_FLOW = [
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
    description: 'Define your target buyer personas (REQUIRED)',
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
    id: 'jtbd',
    title: 'JTBD Phases',
    description: 'Customize Gartner buying journey phases (OPTIONAL)',
    route: '/settings#jtbd',
    status: 'not-started',
    dependencies: ['company']
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
    id: 'verify',
    title: 'Review & Launch',
    description: 'Verify configuration and start first pipeline',
    route: '/setup/review',
    status: 'not-started',
    dependencies: ['company', 'personas', 'keywords']
  }
]
```

### 2. Restructure Pages to Eliminate Duplication

#### A. Consolidate Configuration Areas

**Remove from `/settings`:**
- ~JTBD Phases~ (Now optional with Gartner defaults pre-configured)
- Source Types (keep as advanced configuration)

**Create New Structure:**
```
/setup
  /company     - Company info only
  /personas    - Buyer personas (mandatory)
  /keywords    - Keywords & regions (single source of truth)
  /review      - Final review and launch

/dimensions    - All dimension configuration
/landscapes    - Digital landscape management
/pipeline-schedules - Schedule configuration
/settings      - System settings + optional JTBD customization
```

#### B. Single Source of Truth for Each Configuration

1. **Company Info**: Only in `/setup/company`
2. **Buyer Personas**: Only in `/setup/personas` (mandatory)
3. **Keywords & Regions**: Only in `/setup/keywords`
4. **Dimensions**: Only in `/dimensions`
5. **Landscapes**: Only in `/landscapes`
6. **Schedules**: Only in `/pipeline-schedules`
7. **JTBD Phases**: Pre-configured with Gartner defaults, optional customization in `/settings`

### 3. Enhanced Navigation Implementation

#### A. Add Setup Progress to AdminLayout

```typescript
// Update AdminLayout to include setup progress
export function AdminLayout({ children }: { children: React.ReactNode }) {
  const [setupProgress, setSetupProgress] = useState<SetupProgress>()
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Existing header */}
      <Header />
      
      {/* Add Setup Progress Bar */}
      {!setupProgress?.isComplete && (
        <SetupProgressBar 
          steps={SETUP_FLOW}
          currentStep={setupProgress?.currentStep}
          completedSteps={setupProgress?.completedSteps}
        />
      )}
      
      <div className="flex">
        {/* Existing sidebar with updated navigation */}
        <Sidebar setupProgress={setupProgress} />
        
        <main className="flex-1">
          {children}
        </main>
      </div>
    </div>
  )
}
```

#### B. Update Sidebar Navigation

```typescript
const navigationItems = [
  {
    title: 'Setup',
    items: [
      { 
        name: 'Company Profile', 
        href: '/setup/company',
        icon: Building,
        badge: setupProgress?.company === 'completed' ? '✓' : '•'
      },
      { 
        name: 'Keywords & Markets', 
        href: '/setup/keywords',
        icon: Target,
        badge: setupProgress?.keywords === 'completed' ? '✓' : '•'
      },
      { 
        name: 'Review & Launch', 
        href: '/setup/review',
        icon: Rocket,
        disabled: !canAccessReview // Based on dependencies
      }
    ]
  },
  {
    title: 'Configuration',
    items: [
      { 
        name: 'Custom Dimensions', 
        href: '/dimensions',
        icon: Layers,
        badge: dimensionCount > 0 ? dimensionCount : null
      },
      { 
        name: 'Digital Landscapes', 
        href: '/landscapes',
        icon: Globe,
        badge: landscapeCount
      },
      { 
        name: 'Pipeline Schedules', 
        href: '/pipeline-schedules',
        icon: Calendar,
        badge: activeScheduleCount
      }
    ]
  },
  {
    title: 'Operations',
    items: [
      { name: 'Pipeline Management', href: '/pipeline', icon: Activity },
      { name: 'System Monitoring', href: '/monitoring', icon: Monitor }
    ]
  },
  {
    title: 'System',
    items: [
      { name: 'Settings', href: '/settings', icon: Settings }
    ]
  }
]
```

### 4. Implement Smart Routing & Dependencies

```typescript
// hooks/useSetupProgress.ts
export function useSetupProgress() {
  const [progress, setProgress] = useState<SetupProgress>()
  
  useEffect(() => {
    checkSetupProgress()
  }, [])
  
  const checkSetupProgress = async () => {
    const token = localStorage.getItem('access_token')
    const response = await fetch('/api/v1/setup/progress', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    
    if (response.ok) {
      const data = await response.json()
      setProgress(data)
    }
  }
  
  const canAccessStep = (stepId: string) => {
    const step = SETUP_FLOW.find(s => s.id === stepId)
    if (!step?.dependencies) return true
    
    return step.dependencies.every(dep => 
      progress?.completedSteps.includes(dep)
    )
  }
  
  const getNextStep = () => {
    return SETUP_FLOW.find(step => 
      step.status !== 'completed' && canAccessStep(step.id)
    )
  }
  
  return { progress, canAccessStep, getNextStep }
}
```

### 5. Add Visual Cues & Guidance

#### A. Empty State Guidance

```typescript
// For pages with no data
<EmptyState
  icon={<Target className="h-12 w-12 text-gray-400" />}
  title="No keywords configured yet"
  description="Keywords are the foundation of your competitive analysis"
  action={
    <Button onClick={() => router.push('/setup/keywords')}>
      Configure Keywords
    </Button>
  }
  tip="You need at least 5 keywords to start meaningful analysis"
/>
```

#### B. Contextual Help

```typescript
// Add help tooltips to complex settings
<HelpTooltip>
  <p>Digital Landscapes group related keywords for focused analysis.</p>
  <p>Example: "Cloud Security" landscape might include:</p>
  <ul>
    <li>• cloud security platform</li>
    <li>• cloud access security broker</li>
    <li>• cloud workload protection</li>
  </ul>
</HelpTooltip>
```

### 6. Simplify Initial Setup

#### A. Progressive Disclosure

Start with minimal required fields and expand options as needed:

```typescript
// Initial setup shows only essentials
const INITIAL_SETUP_FIELDS = {
  company: ['name', 'domain', 'industry'],
  keywords: ['keywords', 'primary_region'],
  dimensions: [] // Use pre-configured defaults initially
}

// Advanced options available after initial setup
const ADVANCED_OPTIONS = {
  company: ['description', 'competitors', 'target_audience'],
  keywords: ['additional_regions', 'keyword_tags', 'search_volume_threshold'],
  dimensions: ['custom_dimensions', 'scoring_overrides']
}
```

#### B. Smart Defaults

```typescript
// Provide intelligent defaults based on industry
const INDUSTRY_DEFAULTS = {
  'saas': {
    dimensions: ['Cloud Maturity', 'Integration Depth', 'Security & Compliance'],
    content_types: ['organic', 'videos', 'news'],
    schedule_frequency: 'weekly'
  },
  'fintech': {
    dimensions: ['Security & Trust', 'Regulatory Compliance', 'API Ecosystem'],
    content_types: ['organic', 'news', 'ads'],
    schedule_frequency: 'daily'
  }
}
```

### 7. Implementation Priority

1. **Phase 1** (Immediate):
   - Create SetupProgressTracker component
   - Add to AdminLayout
   - Update sidebar navigation with badges

2. **Phase 2** (Next Sprint):
   - Consolidate duplicate configuration pages
   - Implement dependency checking
   - Add empty state guidance

3. **Phase 3** (Following Sprint):
   - Add contextual help system
   - Implement smart defaults
   - Create setup completion celebration

### 8. Success Metrics

- **Time to First Pipeline**: Reduce from current ~30 min to <10 min
- **Setup Completion Rate**: Increase from ~60% to >90%
- **Configuration Errors**: Reduce by 75%
- **User Confusion**: Eliminate "where do I configure X?" questions

### 9. Quick Wins (Can Implement Today)

1. **Add Setup Checklist to Dashboard**:
   ```typescript
   <SetupChecklist>
     ✓ Company profile configured
     ✓ 10 keywords added
     ○ Custom dimensions created (optional)
     ○ Digital landscape defined (optional)
     ✓ Pipeline schedule active
   </SetupChecklist>
   ```

2. **Add "Next Step" Prompts**:
   ```typescript
   // After saving company info
   <SuccessMessage>
     Company profile saved! 
     <Button onClick={() => router.push('/setup/keywords')}>
       Configure Keywords →
     </Button>
   </SuccessMessage>
   ```

3. **Disable Advanced Features Until Basics Complete**:
   ```typescript
   // In pipeline page
   {!setupComplete && (
     <Alert>
       Complete basic setup to unlock pipeline features
       <Link href="/setup/company">Start Setup →</Link>
     </Alert>
   )}
   ```

## Conclusion

By implementing these recommendations, the Cylvy platform will have:
- Clear, sequential setup flow
- No configuration duplication
- Visual progress tracking
- Intelligent dependency management
- Contextual guidance

This will significantly improve the user experience and reduce time to value for new customers.
