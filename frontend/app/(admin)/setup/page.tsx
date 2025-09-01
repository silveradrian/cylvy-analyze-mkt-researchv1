'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';

import { CompanyInfoStep } from '@/components/setup/CompanyInfoStep';
import { BrandingStep } from '@/components/setup/BrandingStep';
import { APIKeysStep } from '@/components/setup/APIKeysStep';
import { AnalysisConfigStep } from '@/components/setup/AnalysisConfigStep';
import { VerifyStep } from '@/components/setup/VerifyStep';

const SETUP_STEPS = [
  { id: 'company', title: 'Company Information', component: CompanyInfoStep },
  { id: 'branding', title: 'Branding & Logo', component: BrandingStep },
  { id: 'api-keys', title: 'API Configuration', component: APIKeysStep },
  { id: 'analysis', title: 'Analysis Settings', component: AnalysisConfigStep },
  { id: 'verify', title: 'Verify & Launch', component: VerifyStep }
];

export default function SetupWizard() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [setupData, setSetupData] = useState({});

  useEffect(() => {
    // Check if setup is already complete
    checkSetupStatus();
  }, []);

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
    setSetupData(prev => ({ ...prev, ...stepData }));
    setCompletedSteps(prev => new Set([...prev, currentStep]));
    
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
    // Mark setup as complete and redirect to dashboard
    router.push('/dashboard');
  };

  const CurrentStepComponent = SETUP_STEPS[currentStep].component;
  const progress = ((currentStep + 1) / SETUP_STEPS.length) * 100;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <h1 className="text-2xl font-bold">Cylvy Setup Wizard</h1>
          <p className="text-sm text-gray-600 mt-1">
            Let's configure your digital landscape analyzer
          </p>
        </div>
      </div>

      {/* Progress */}
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <Progress value={progress} className="h-2" />
          <div className="flex justify-between mt-4">
            {SETUP_STEPS.map((step, index) => (
              <div
                key={step.id}
                className={`flex items-center ${
                  index <= currentStep ? 'text-primary' : 'text-gray-400'
                }`}
              >
                <div
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                    ${index === currentStep ? 'bg-primary text-white' : ''}
                    ${index < currentStep ? 'bg-primary/20' : 'bg-gray-200'}
                    ${completedSteps.has(index) ? 'bg-green-500 text-white' : ''}
                  `}
                >
                  {completedSteps.has(index) ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    index + 1
                  )}
                </div>
                <span className="ml-2 text-sm hidden sm:inline">
                  {step.title}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="bg-white rounded-lg shadow-sm border p-8">
          <CurrentStepComponent
            data={setupData}
            onComplete={handleStepComplete}
            onBack={currentStep > 0 ? handlePreviousStep : undefined}
            onFinish={currentStep === SETUP_STEPS.length - 1 ? handleFinishSetup : undefined}
          />
        </div>
      </div>
    </div>
  );
}

