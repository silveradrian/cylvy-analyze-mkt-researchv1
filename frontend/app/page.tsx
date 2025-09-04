import React from 'react'
import Link from 'next/link'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Consistent Masthead */}
      <div className="cylvy-gradient-primary shadow-lg">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <img 
                src="/img/cylvy_lolgo_black.svg" 
                alt="Cylvy Logo" 
                className="h-8 w-auto filter brightness-0 invert"
              />
              <div>
                <h1 className="text-2xl font-bold text-white">Market Intelligence Agent</h1>
                <p className="text-white/80 text-sm">
                  AI-powered competitive intelligence platform for B2B content analysis
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 bg-white/10 px-3 py-1 rounded-full">
              <div className="w-2 h-2 bg-green-400 rounded-full"></div>
              <span className="text-white/90 text-sm">System Ready</span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="container mx-auto px-6 py-12 mt-8">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex gap-6 justify-center flex-wrap mb-16">
            <Link href="/setup">
              <button className="cylvy-btn-primary text-lg">
                🏗️ Client Setup Wizard
              </button>
            </Link>
            
            <Link href="/pipeline">
              <button className="cylvy-btn-secondary text-lg">
                📊 Pipeline Management
              </button>
            </Link>
            
            <Link href="/pipeline-schedules">
              <button className="cylvy-btn-secondary text-lg">
                🗓️ Pipeline Scheduling
              </button>
            </Link>
            
            <Link href="/landscapes">
              <button className="cylvy-btn-secondary text-lg">
                🌐 Digital Landscapes
              </button>
            </Link>
            
            <Link href="/dimensions">
              <button className="cylvy-btn-ghost text-lg">
                🎯 Custom Dimensions
              </button>
            </Link>
            
            <Link href="/settings">
              <button className="cylvy-btn-ghost text-lg">
                ⚙️ Advanced Settings
              </button>
            </Link>
            
            <Link href="http://localhost:8001/docs" target="_blank">
              <button className="cylvy-btn-ghost text-lg">
                📚 API Documentation
              </button>
            </Link>
          </div>
          
          <div className="cylvy-card max-w-md mx-auto">
            <div className="cylvy-card-header">
              <h3 className="text-lg font-semibold text-cylvy-amaranth text-center">🔐 Admin Access</h3>
            </div>
            <div className="cylvy-card-body text-center">
              <div className="space-y-2">
                <p className="text-gray-700">
                  <strong className="text-cylvy-grape">Email:</strong> admin@cylvy.com
                </p>
                <p className="text-gray-700">
                  <strong className="text-cylvy-grape">Password:</strong> admin123
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}