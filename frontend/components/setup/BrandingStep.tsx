'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { LogoUploader } from '@/components/LogoUploader';
import { Card } from '@/components/ui/card';

interface BrandingStepProps {
  data: any;
  onComplete: (data: any) => void;
  onBack?: () => void;
}

export function BrandingStep({ data, onComplete, onBack }: BrandingStepProps) {
  const [branding, setBranding] = useState({
    logo_url: data.logo_url || null,
    primary_color: data.primary_color || '#3B82F6',
    secondary_color: data.secondary_color || '#10B981'
  });
  const [isUploading, setIsUploading] = useState(false);

  const handleLogoUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/v1/config/logo', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const result = await response.json();
      setBranding(prev => ({ ...prev, logo_url: result.logo_url }));
    } catch (error) {
      console.error('Logo upload failed:', error);
      throw error;
    } finally {
      setIsUploading(false);
    }
  };

  const handleLogoDelete = async () => {
    try {
      const response = await fetch('/api/v1/config/logo', {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Delete failed');
      }

      setBranding(prev => ({ ...prev, logo_url: null }));
    } catch (error) {
      console.error('Logo delete failed:', error);
      throw error;
    }
  };

  const handleNext = () => {
    onComplete({ branding });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Branding & Customization</h2>
        <p className="text-gray-600 mt-2">
          Customize the appearance of your digital landscape analyzer
        </p>
      </div>

      <div className="space-y-8">
        {/* Logo Upload */}
        <div>
          <Label className="text-base font-semibold mb-4 block">
            Company Logo
          </Label>
          <LogoUploader
            currentLogo={branding.logo_url}
            onUpload={handleLogoUpload}
            onDelete={handleLogoDelete}
          />
        </div>

        {/* Color Customization */}
        <div>
          <Label className="text-base font-semibold mb-4 block">
            Brand Colors
          </Label>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <Label htmlFor="primary-color">Primary Color</Label>
              <div className="flex gap-2 mt-2">
                <Input
                  id="primary-color"
                  type="color"
                  value={branding.primary_color}
                  onChange={(e) => setBranding(prev => ({ 
                    ...prev, 
                    primary_color: e.target.value 
                  }))}
                  className="w-20 h-10 cursor-pointer"
                />
                <Input
                  type="text"
                  value={branding.primary_color}
                  onChange={(e) => setBranding(prev => ({ 
                    ...prev, 
                    primary_color: e.target.value 
                  }))}
                  placeholder="#3B82F6"
                  className="flex-1"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="secondary-color">Secondary Color</Label>
              <div className="flex gap-2 mt-2">
                <Input
                  id="secondary-color"
                  type="color"
                  value={branding.secondary_color}
                  onChange={(e) => setBranding(prev => ({ 
                    ...prev, 
                    secondary_color: e.target.value 
                  }))}
                  className="w-20 h-10 cursor-pointer"
                />
                <Input
                  type="text"
                  value={branding.secondary_color}
                  onChange={(e) => setBranding(prev => ({ 
                    ...prev, 
                    secondary_color: e.target.value 
                  }))}
                  placeholder="#10B981"
                  className="flex-1"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Preview */}
        <div>
          <Label className="text-base font-semibold mb-4 block">
            Preview
          </Label>
          <Card className="p-6">
            <div className="flex items-center gap-4">
              {branding.logo_url ? (
                <img
                  src={branding.logo_url}
                  alt="Logo"
                  className="h-12 w-auto"
                />
              ) : (
                <div 
                  className="h-12 w-12 rounded-lg"
                  style={{ backgroundColor: branding.primary_color }}
                />
              )}
              <div>
                <h3 className="text-lg font-semibold">
                  {data.company_name || 'Your Company'}
                </h3>
                <p className="text-sm text-gray-600">
                  Digital Landscape Analyzer
                </p>
              </div>
            </div>
            <div className="mt-6 flex gap-3">
              <Button 
                style={{ backgroundColor: branding.primary_color }}
                className="text-white"
              >
                Primary Button
              </Button>
              <Button 
                variant="outline"
                style={{ 
                  borderColor: branding.secondary_color,
                  color: branding.secondary_color 
                }}
              >
                Secondary Button
              </Button>
            </div>
          </Card>
        </div>
      </div>

      <div className="flex justify-between pt-6">
        {onBack && (
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
        )}
        <Button 
          onClick={handleNext}
          disabled={isUploading}
          className="ml-auto"
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
