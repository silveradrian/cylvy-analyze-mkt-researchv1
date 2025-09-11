'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Calendar, Clock, CheckCircle, AlertCircle, Save } from 'lucide-react';
import { AdminLayout } from '@/components/layout/AdminLayout';

interface ScheduleConfig {
  organic: 'daily' | 'weekly' | 'monthly';
  news: 'daily' | 'weekly' | 'monthly';
  video: 'daily' | 'weekly' | 'monthly';
  keywordMetrics: 'weekly' | 'monthly';
}

const CONTENT_TYPES = [
  {
    key: 'organic',
    name: 'Organic Search',
    description: 'Regular Google search results',
    icon: '🔍',
    defaultFrequency: 'monthly'
  },
  {
    key: 'news',
    name: 'News Results',
    description: 'News articles and press coverage',
    icon: '📰',
    defaultFrequency: 'weekly'
  },
  {
    key: 'video',
    name: 'Video Content',
    description: 'YouTube videos',
    icon: '📺',
    defaultFrequency: 'monthly'
  }
];

export default function PipelineSchedulesPage() {
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>({
    organic: 'monthly',
    news: 'weekly',
    video: 'monthly',
    keywordMetrics: 'monthly'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadScheduleConfig();
  }, []);

  const loadScheduleConfig = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/schedules', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // If there's an existing schedule, load its configuration
        if (data.schedules && data.schedules.length > 0) {
          const schedule = data.schedules[0];
          const config: ScheduleConfig = {
            organic: 'monthly',
            news: 'weekly', 
            video: 'monthly',
            keywordMetrics: 'monthly'
          };
          
          // Extract frequencies from content_schedules
          schedule.content_schedules?.forEach((cs: any) => {
            if (cs.content_type && cs.frequency) {
              if (cs.content_type === 'keyword_metrics') {
                config.keywordMetrics = cs.frequency;
              } else if (cs.content_type in config) {
                config[cs.content_type as keyof ScheduleConfig] = cs.frequency;
              }
            }
          });
          
          setScheduleConfig(config);
        }
      }
    } catch (err) {
      console.error('Failed to load schedule config:', err);
    } finally {
      setLoading(false);
    }
  };

  const saveScheduleConfig = async () => {
    try {
      setSaving(true);
      setMessage(null);
      
      const token = localStorage.getItem('access_token');
      
      // Convert simple config to API format
      const scheduleData = {
        name: 'Project SERP Collection Schedule',
        description: 'Automated SERP data collection and keyword metrics update schedule',
        is_active: true,
        content_schedules: [
          ...CONTENT_TYPES.map(ct => ({
            content_type: ct.key,
            frequency: scheduleConfig[ct.key as keyof ScheduleConfig],
            enabled: true
          })),
          // Add keyword metrics schedule
          {
            content_type: 'keyword_metrics',
            frequency: scheduleConfig.keywordMetrics,
            enabled: true
          }
        ],
        regions: ['US', 'UK', 'DE', 'SA', 'VN'], // All configured regions
        notification_emails: [],
        notify_on_completion: false,
        notify_on_error: true
      };

      // Check if we need to create or update
      const schedulesResponse = await fetch('/api/v1/pipeline/schedules', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      let response;
      if (schedulesResponse.ok) {
        const data = await schedulesResponse.json();
        if (data.schedules && data.schedules.length > 0) {
          // Update existing schedule
          response = await fetch(`/api/v1/pipeline/schedules/${data.schedules[0].id}`, {
            method: 'PUT',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(scheduleData)
          });
        } else {
          // Create new schedule
          response = await fetch('/api/v1/pipeline/schedules', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(scheduleData)
          });
        }
      } else {
        // Create new schedule
        response = await fetch('/api/v1/pipeline/schedules', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(scheduleData)
        });
      }
      
      if (response && response.ok) {
        setMessage({ type: 'success', text: 'Schedule configuration saved successfully!' });
      } else {
        setMessage({ type: 'error', text: 'Failed to save schedule configuration' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Error saving configuration' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AdminLayout title="Collection Schedule" description="Configure data collection frequency for SERP and keyword metrics">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Clock className="h-8 w-8 animate-spin mx-auto mb-4 text-cylvy-sage" />
            <p className="text-gray-600">Loading schedule configuration...</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Collection Schedule" description="Configure data collection frequency for SERP and keyword metrics">
      <div className="max-w-4xl">
        {message && (
          <Alert className={message.type === 'success' ? 'border-green-200 mb-6' : 'border-red-200 mb-6'}>
            {message.type === 'success' ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <AlertCircle className="h-4 w-4 text-red-600" />
            )}
            <AlertDescription className={message.type === 'success' ? 'text-green-800' : 'text-red-800'}>
              {message.text}
            </AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Data Collection Frequency</CardTitle>
            <CardDescription>
              Configure how often to collect SERP data and update keyword metrics. 
              Collection runs automatically based on these schedules.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {CONTENT_TYPES.map((contentType) => (
              <div key={contentType.key} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{contentType.icon}</span>
                  <div>
                    <h4 className="font-medium text-gray-900">{contentType.name}</h4>
                    <p className="text-sm text-gray-600">{contentType.description}</p>
                  </div>
                </div>
                <div className="w-40">
                  <Select
                    value={scheduleConfig[contentType.key as keyof ScheduleConfig]}
                    onValueChange={(value) => 
                      setScheduleConfig(prev => ({
                        ...prev,
                        [contentType.key]: value
                      }))
                    }
                  >
                    <SelectTrigger className="bg-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="monthly">Monthly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            ))}

            {/* Keyword Metrics Update Frequency */}
            <div className="border-t pt-4">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">📊</span>
                  <div>
                    <h4 className="font-medium text-gray-900">Keyword Metrics</h4>
                    <p className="text-sm text-gray-600">Google Ads search volume and competition data</p>
                  </div>
                </div>
                <div className="w-40">
                  <Select
                    value={scheduleConfig.keywordMetrics}
                    onValueChange={(value: 'weekly' | 'monthly') => 
                      setScheduleConfig(prev => ({
                        ...prev,
                        keywordMetrics: value
                      }))
                    }
                  >
                    <SelectTrigger className="bg-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="monthly">Monthly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  <p>💡 Recommendations:</p>
                  <ul className="mt-1 space-y-1">
                    <li>• <strong>News:</strong> Weekly or daily for time-sensitive content</li>
                    <li>• <strong>Organic:</strong> Monthly for stable search results</li>
                    <li>• <strong>Video:</strong> Monthly for YouTube content</li>
                    <li>• <strong>Keywords:</strong> Monthly for stable metrics, weekly for dynamic markets</li>
                  </ul>
                </div>
                <Button 
                  onClick={saveScheduleConfig} 
                  disabled={saving}
                  className="cylvy-btn-primary"
                >
                  {saving ? (
                    <>
                      <Clock className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Configuration
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <h3 className="flex items-center gap-2 font-medium text-blue-900 mb-2">
            <Calendar className="h-4 w-4" />
            How Scheduling Works
          </h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• ScaleSERP batches are created with the configured frequency</li>
            <li>• When batches complete, the pipeline automatically processes the results</li>
            <li>• Each content type runs independently on its own schedule</li>
            <li>• Keyword metrics (Google Ads data) update based on your selected frequency</li>
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}