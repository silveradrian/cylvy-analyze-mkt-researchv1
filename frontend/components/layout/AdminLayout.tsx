'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { 
  Home, 
  Settings, 
  BarChart3, 
  Target, 
  Users,
  LogOut,
  Menu,
  X,
  ChevronRight,
  Globe,
  Layers,
  Activity,
  Monitor,
  Calendar
} from 'lucide-react'

interface AdminLayoutProps {
  children: React.ReactNode
  title: string
  description?: string
}

const navigationItems = [
  { 
    name: 'Dashboard', 
    href: '/', 
    icon: Home,
    description: 'Overview and setup status'
  },
  // Configuration Section
  { 
    name: 'Company Profile', 
    href: '/setup?step=company', 
    icon: Settings,
    description: 'Company configuration'
  },
  { 
    name: 'Buyer Personas', 
    href: '/setup?step=personas', 
    icon: Users,
    description: 'Target audience profiles'
  },
  { 
    name: 'Keywords', 
    href: '/setup?step=countries', 
    icon: Target,
    description: 'Countries & Keywords'
  },
  { 
    name: 'Analysis Settings', 
    href: '/setup?step=analysis', 
    icon: Settings,
    description: 'Configure analysis'
  },
  // Operations Section
  { 
    name: 'Pipeline', 
    href: '/pipeline', 
    icon: BarChart3,
    description: 'Run and monitor analysis'
  },
  { 
    name: 'Pipeline Schedules', 
    href: '/pipeline-schedules', 
    icon: Calendar,
    description: 'Configure schedules'
  },
  { 
    name: 'Digital Landscapes', 
    href: '/landscapes', 
    icon: Globe,
    description: 'DSI market views'
  },
  { 
    name: 'Custom Dimensions', 
    href: '/dimensions', 
    icon: Layers,
    description: 'Analysis dimensions'
  },
  { 
    name: 'Monitoring', 
    href: '/monitoring', 
    icon: Monitor,
    description: 'System health'
  }
]

export function AdminLayout({ children, title, description }: AdminLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const pathname = usePathname()
  const router = useRouter()

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    router.push('/')
  }

  const isActivePath = (href: string) => {
    if (href === '/') {
      return pathname === '/' || pathname === '/dashboard'
    }
    return pathname.startsWith(href)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Top Masthead */}
      <div className="cylvy-gradient-primary shadow-lg relative z-10">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
            >
              {sidebarOpen ? <X className="h-5 w-5 text-white" /> : <Menu className="h-5 w-5 text-white" />}
            </button>
            
            <div className="flex items-center gap-3">
              <img 
                src="/img/cylvy_lolgo_black.svg" 
                alt="Cylvy Logo" 
                className="h-8 w-auto filter brightness-0 invert"
              />
              <div>
                <h1 className="text-xl font-bold text-white">{title}</h1>
                {description && (
                  <p className="text-white/80 text-sm">{description}</p>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 bg-white/10 px-3 py-1 rounded-full">
              <div className="w-2 h-2 bg-green-400 rounded-full"></div>
              <span className="text-white/90 text-sm">System Healthy</span>
            </div>
            
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg transition-colors"
            >
              <LogOut className="h-4 w-4 text-white" />
              <span className="text-white text-sm">Logout</span>
            </button>
          </div>
        </div>
      </div>

      <div className="flex">
        {/* Left Sidebar Navigation */}
        <div className={`${sidebarOpen ? 'w-64' : 'w-16'} transition-all duration-300 bg-white shadow-lg border-r border-gray-200 min-h-[calc(100vh-72px)] relative z-0`}>
          <div className="p-4">
            <nav className="space-y-2">
              {navigationItems.map((item) => {
                const Icon = item.icon
                const isActive = isActivePath(item.href)
                
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                      isActive 
                        ? 'bg-red-600 shadow-lg border-2 border-red-500 font-semibold' 
                        : 'text-gray-700 hover:bg-red-50 hover:text-red-600'
                    }`}
                    style={isActive ? {
                      backgroundColor: '#dc2626',
                      color: '#ffffff',
                      fontWeight: '600'
                    } : {}}
                  >
                    <Icon 
                      className={`h-5 w-5 flex-shrink-0 font-bold ${
                        isActive ? 'text-white drop-shadow-sm' : 'text-gray-500 group-hover:text-red-600'
                      }`}
                      style={isActive ? { color: '#ffffff' } : {}}
                    />
                    
                    {sidebarOpen && (
                      <div className="flex-1 min-w-0">
                        <div 
                          className={`font-semibold text-sm ${
                            isActive ? 'text-white drop-shadow-sm' : 'text-gray-900'
                          }`}
                          style={isActive ? { color: '#ffffff', fontWeight: '600' } : {}}
                        >
                          {item.name}
                        </div>
                        <div 
                          className={`text-xs mt-0.5 ${
                            isActive ? 'text-white/90 drop-shadow-sm' : 'text-gray-500'
                          }`}
                          style={isActive ? { color: '#ffffff', opacity: '0.9' } : {}}
                        >
                          {item.description}
                        </div>
                      </div>
                    )}
                    
                    {sidebarOpen && isActive && (
                      <ChevronRight 
                        className="h-4 w-4 text-white" 
                        style={{ color: '#ffffff' }}
                      />
                    )}
                  </Link>
                )
              })}
            </nav>

            {/* Compact User Info */}
            {sidebarOpen && (
              <div className="mt-8 pt-6 border-t border-gray-200">
                <div className="px-3 py-2 bg-gray-50 rounded-lg">
                  <div className="text-sm font-medium text-gray-900">Admin User</div>
                  <div className="text-xs text-gray-500">admin@cylvy.com</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 min-h-[calc(100vh-72px)] overflow-auto bg-gradient-to-br from-gray-50 to-gray-100">
          <div className="p-6">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}
