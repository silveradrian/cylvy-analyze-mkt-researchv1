'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

import CompanyProfileStep from '@/components/setup/CompanyProfileStep';
import PersonasStep from '@/components/setup/PersonasStep';
import { CountriesKeywordsStep } from '@/components/setup/CountriesKeywordsStep';
import VerifyStep from '@/components/setup/VerifyStep';

import { AdminLayout } from '@/components/layout/AdminLayout';

const SETUP_STEPS = [
  { id: 'company', title: 'Company Profile', component: CompanyProfileStep },
  { id: 'personas', title: 'Buyer Personas', component: PersonasStep },
  { id: 'countries', title: 'Countries & Keywords', component: CountriesKeywordsStep },
  { id: 'verify', title: 'Verify & Launch', component: VerifyStep }
];

export default function SetupWizard() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [setupData, setSetupData] = useState<any>({});
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [pipelineHistory, setPipelineHistory] = useState(null);

  useEffect(() => {
    checkAuthAndSetup();
    
    // Check for step parameter in URL
    const params = new URLSearchParams(window.location.search);
    const stepParam = params.get('step');
    if (stepParam) {
      const stepIndex = SETUP_STEPS.findIndex(s => s.id === stepParam);
      if (stepIndex !== -1) {
        setCurrentStep(stepIndex);
      }
    }
  }, []);

  const checkAuthAndSetup = async () => {
    // Check if user has access token
    let token = localStorage.getItem('access_token');
    
    if (token) {
      // Skip validation for test token
      if (token === 'test-token-for-development') {
        console.log('🔑 Test token found - skipping validation');
        setIsAuthenticated(true);
        setIsCheckingAuth(false);
        await loadExistingConfiguration();
        return;
      }
      
      // Verify token is still valid
      try {
        const response = await fetch('/api/v1/auth/me', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
          console.log('🔑 Valid token found - proceeding to setup');
          setIsAuthenticated(true);
          await loadExistingConfiguration();
        } else {
          console.log('🔑 Token expired - attempting auto-login');
          localStorage.removeItem('access_token');
          token = null; // Force auto-login below
        }
      } catch (error) {
        console.log('🔑 Token validation failed - attempting auto-login');
        localStorage.removeItem('access_token');
        token = null; // Force auto-login below
      }
    }
    
    // Auto-login for testing if no valid token
    if (!token) {
      try {
        console.log('🔐 Attempting auto-login with admin@cylvy.com...');
        const loginResponse = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: 'admin@cylvy.com',
            password: 'admin123'
          })
        });
        
        if (loginResponse.ok) {
          const loginData = await loginResponse.json();
          token = loginData.access_token;
          localStorage.setItem('access_token', token);
          console.log('✅ Auto-login successful - loading configuration...');
          setIsAuthenticated(true);
          await loadExistingConfiguration();
        } else {
          const errorText = await loginResponse.text();
          console.log('❌ Auto-login failed:', loginResponse.status, errorText);
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.log('❌ Auto-login error - showing login form');
        setIsAuthenticated(false);
      }
    }
    
    setIsCheckingAuth(false);
  };

  const checkPipelineHistory = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/executions', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const executions = await response.json();
        if (executions && executions.length > 0) {
          console.log(`📈 Found ${executions.length} pipeline execution(s)`);
          setPipelineHistory(executions);
        }
      }
    } catch (error) {
      console.log('ℹ️ Pipeline history check failed (normal for new installations)');
    }
  };

  const loadExistingConfiguration = async () => {
    try {
      // Load existing configuration and mark steps complete
      const existingData: any = {};
      const completedStepIds = new Set<number>();

      // 1. Check company info
      try {
        const token = localStorage.getItem('access_token');
        const configResponse = await fetch('/api/v1/config', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
        console.log('🔍 Config API response:', configResponse.status);
        
        if (configResponse.ok) {
          const config = await configResponse.json();
          console.log('📋 Config data received:', config);
          
          if (config.company_name && config.company_domain) {
            existingData.company_name = config.company_name;
            existingData.company_domain = config.company_domain; 
            existingData.admin_email = config.admin_email;
            existingData.description = config.description;
            existingData.industry = config.industry;
            existingData.legal_name = config.legal_name;
            existingData.additional_domains = config.additional_domains || [];
            existingData.competitors = config.competitors || [];
            completedStepIds.add(0); // Company info step
            console.log('✅ Company info found and pre-populated:', config.company_name);
          }
        } else {
          const errorText = await configResponse.text();
          console.log('❌ Config API error:', configResponse.status, errorText);
        }
      } catch (e) {
        console.log('❌ Config API fetch error:', e);
      }

      // 2. Check analysis config (personas, competitors)
      try {
        const token = localStorage.getItem('access_token');
        const [personasResponse, competitorsResponse] = await Promise.all([
          fetch('/api/v1/analysis/personas', {
            headers: { 'Authorization': `Bearer ${token}` }
          }),
          fetch('/api/v1/analysis/competitors', {
            headers: { 'Authorization': `Bearer ${token}` }
          })
        ]);
        
        let hasAnalysisConfig = false;
        
        console.log('🔍 Personas API response:', personasResponse.status);
        if (personasResponse.ok) {
          const personas = await personasResponse.json();
          if (personas.personas && personas.personas.length > 0) {
            existingData.personas = personas.personas;
            hasAnalysisConfig = true;
            console.log('✅ Personas found and pre-populated');
          }
        } else {
          const personasError = await personasResponse.text();
          console.log('❌ Personas API error:', personasResponse.status, personasError);
        }
        
        console.log('🔍 Competitors API response:', competitorsResponse.status);
        if (competitorsResponse.ok) {
          const competitors = await competitorsResponse.json();
          // Note: Competitors are now configured in the company profile step
        } else {
          const competitorsError = await competitorsResponse.text();
          console.log('❌ Competitors API error:', competitorsResponse.status, competitorsError);
        }

        if (hasAnalysisConfig) {
          completedStepIds.add(2); // Analysis config step (now step 3 in 4-step flow)
        }
      } catch (e) {
        console.log('ℹ️ Analysis config API temporarily unavailable - skipping pre-population');
        console.log('   (This is normal for fresh installations)');
      }

      // 3. Check keywords
      try {
        const token = localStorage.getItem('access_token');
        const keywordsResponse = await fetch('/api/v1/keywords', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        console.log('🔍 Keywords API response:', keywordsResponse.status);
        if (keywordsResponse.ok) {
          const keywordsData = await keywordsResponse.json();
          if (keywordsData.total > 0) {
            existingData.existing_keywords = keywordsData.keywords || [];
            existingData.keywords_count = keywordsData.total;
            existingData.keywords_uploaded = true;
            completedStepIds.add(1); // Countries & Keywords step
            console.log('✅ Keywords found and pre-populated:', keywordsData.total, 'keywords');
          }
        } else {
          const keywordsError = await keywordsResponse.text();
          console.log('❌ Keywords API error:', keywordsResponse.status, keywordsError);
        }
      } catch (e) {
        console.log('ℹ️ Keywords API temporarily unavailable - skipping pre-population');
      }

      // Update state with existing data
      console.log('📊 Configuration Summary:', {
        'Data Keys': Object.keys(existingData),
        'Completed Steps': Array.from(completedStepIds),
        'Setup Data': existingData
      });
      
      if (Object.keys(existingData).length > 0) {
        setSetupData(existingData);
        setCompletedSteps(completedStepIds);
        console.log(`✅ Loaded existing configuration - ${completedStepIds.size} steps pre-populated`);
        console.log('👆 Navigate through steps manually to review or modify settings');
        
        // Check if any pipelines have been run
        await checkPipelineHistory();
      } else {
        console.log('ℹ️ No existing configuration found - starting from step 1');
      }

    } catch (error) {
      console.error('Failed to load existing configuration:', error);
    }
  };

  const checkSetupStatus = async () => {
    try {
      const response = await fetch('/api/v1/config/setup-status');
      const data = await response.json();
      
      if (data.setup_complete) {
        router.push('/dashboard');
      }
    } catch (error) {
      console.error('Failed to check setup status:', error);
    }
  };

  const handleStepComplete = (stepData: any) => {
    console.log('📝 Step completed with data:', stepData);
    console.log('🔄 Current setup data before merge:', setupData);
    
    const newSetupData = { ...setupData, ...stepData };
    console.log('🆕 New setup data after merge:', newSetupData);
    
    setSetupData(newSetupData);
    setCompletedSteps(prev => new Set([...Array.from(prev), currentStep]));
    
    if (currentStep < SETUP_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePreviousStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleFinishSetup = async () => {
    // Mark setup as complete and redirect to homepage
    console.log('🎉 Setup completed! Redirecting to homepage...');
    router.push('/');
  };

  const handleSaveOnly = (stepData: any) => {
    // Save current step data without advancing to next step
    const newSetupData = { ...setupData, ...stepData };
    setSetupData(newSetupData);
  };

  const handleLogin = async (email: string, password: string) => {
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('access_token', data.access_token);
        console.log('✅ Login successful - loading configuration...');
        setIsAuthenticated(true);
        await loadExistingConfiguration();
      } else {
        const error = await response.json();
        alert(`Login failed: ${error.message || 'Invalid credentials'}`);
      }
    } catch (error) {
      alert('Login failed. Please check your connection and try again.');
    }
  };

  const CurrentStepComponent = SETUP_STEPS[currentStep].component as any;
  const currentStepTitle = SETUP_STEPS[currentStep].title;

  // Loading state
  if (isCheckingAuth) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Login form if not authenticated
  if (!isAuthenticated) {
    return <LoginForm onLogin={handleLogin} />;
  }

  // Setup wizard if authenticated
  return (
    <AdminLayout title={currentStepTitle} description="Configure your digital landscape analyzer">
      <div className="max-w-4xl mx-auto">

        {/* Pipeline History Status */}
        {pipelineHistory && pipelineHistory.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-sm font-medium text-blue-800 mb-2">🚀 Pipeline Activity Detected</h3>
                <div className="text-sm text-blue-700 space-y-1">
                  <div>✅ <strong>{pipelineHistory.length} pipeline execution(s) completed</strong></div>
                  <div>📊 Data collection and analysis has been performed</div>
                  <div className="text-xs text-blue-600 mt-2">
                    Your system is operational with collected data. You can review results or run additional analyses.
                  </div>
                </div>
              </div>
              <div className="ml-4 space-y-2">
                <Button
                  onClick={() => router.push('/pipeline')}
                  className="cylvy-btn-primary text-sm px-4 py-2 w-full"
                >
                  📊 View Pipeline Results
                </Button>
                <Button
                  onClick={() => router.push('/landscapes')}
                  variant="outline"
                  className="text-sm px-4 py-2 w-full"
                >
                  🌐 View Digital Landscapes
                </Button>
              </div>
            </div>
          </div>
        )}


        {/* Step Content */}
        <div className="cylvy-card p-8">
          {currentStep === 1 ? (
            // PersonasStep has different props
            <PersonasStep
              data={setupData}
              onUpdate={(data) => setSetupData({ ...setupData, ...data })}
              onNext={() => handleStepComplete(setupData)}
              onPrev={handlePreviousStep}
            />
          ) : (
            currentStep === 2 ? (
              <CountriesKeywordsStep
                data={setupData}
                onComplete={handleSaveOnly}
                onBack={currentStep > 0 ? handlePreviousStep : undefined}
              />
            ) : (
              <CurrentStepComponent
                data={setupData}
                onComplete={handleStepComplete}
                onBack={currentStep > 0 ? handlePreviousStep : undefined}
                onFinish={currentStep === SETUP_STEPS.length - 1 ? handleFinishSetup : undefined}
              />
            )
          )}
        </div>
      </div>
    </AdminLayout>
  );
}

// Login Form Component
function LoginForm({ onLogin }: { onLogin: (email: string, password: string) => void }) {
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await onLogin(email, password);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="cylvy-gradient-primary py-8 mb-8 rounded-t-lg">
          <div className="text-center px-6">
            <img 
              src="/img/cylvy_lolgo_black.svg" 
              alt="Cylvy Logo" 
              className="h-16 w-auto mx-auto mb-4 filter brightness-0 invert"
            />
            <h1 className="text-3xl font-bold text-white mb-2">Setup Wizard</h1>
            <p className="text-white/90">Login to configure your analyzer</p>
          </div>
        </div>

        {/* Login Form */}
        <div className="cylvy-card p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-900 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth outline-none transition-colors"
                placeholder="admin@cylvy.com"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-900 focus:border-cylvy-amaranth focus:ring-cylvy-amaranth outline-none transition-colors"
                placeholder="Enter your password"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full cylvy-btn-primary py-3 text-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2 inline-block"></div>
                  Signing in...
                </>
              ) : (
                'Sign In to Continue'
              )}
            </button>
          </form>

          {/* Quick Login */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-4">Default Admin Credentials:</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Email:</span>
                  <span className="font-medium text-cylvy-grape">admin@cylvy.com</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Password:</span>
                  <span className="font-medium text-cylvy-grape">admin123</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setEmail('admin@cylvy.com');
                  setPassword('admin123');
                }}
                className="cylvy-btn-ghost text-sm mt-4"
              >
                Use Default Login
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

