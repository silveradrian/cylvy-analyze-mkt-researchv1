'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
// import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { 
  Calendar, Clock, Play, Pause, Settings, Plus, Edit, Trash2,
  AlertCircle, CheckCircle, Timer
} from 'lucide-react';

import { AdminLayout } from '@/components/layout/AdminLayout';

interface ContentTypeSchedule {
  content_type: 'organic' | 'news' | 'videos' | 'social' | 'ads';
  frequency: 'daily' | 'weekly' | 'monthly';
  enabled: boolean;
  last_executed?: string;
  next_execution?: string;
}

interface PipelineSchedule {
  id?: string;
  name: string;
  description?: string;
  is_active: boolean;
  content_schedules: ContentTypeSchedule[];
  regions: string[];
  notification_emails?: string[];
  created_at?: string;
  last_executed_at?: string;
  next_execution_at?: string;
}

const CONTENT_TYPES = [
  { 
    key: 'organic' as const, 
    name: 'Organic Content', 
    description: 'SEO content, blog posts, landing pages',
    icon: '🌱',
    recommended_frequency: 'weekly'
  },
  { 
    key: 'news' as const, 
    name: 'News & PR', 
    description: 'Press releases, news articles, announcements',
    icon: '📰',
    recommended_frequency: 'weekly'
  },
  { 
    key: 'videos' as const, 
    name: 'Video Content', 
    description: 'YouTube videos, webinars, product demos',
    icon: '📺',
    recommended_frequency: 'monthly'
  },
  { 
    key: 'social' as const, 
    name: 'Social Media', 
    description: 'LinkedIn posts, Twitter content, social engagement',
    icon: '📱',
    recommended_frequency: 'weekly'
  },
  { 
    key: 'ads' as const, 
    name: 'Paid Advertising', 
    description: 'Google Ads, PPC campaigns, sponsored content',
    icon: '💰',
    recommended_frequency: 'daily'
  }
];

const FREQUENCY_OPTIONS = [
  { value: 'daily', label: 'Daily', description: 'Every day at specified time' },
  { value: 'weekly', label: 'Weekly', description: 'Once per week on specified day' },
  { value: 'monthly', label: 'Monthly', description: 'Once per month on specified date' }
];

export default function PipelineSchedulesPage() {
  const [schedules, setSchedules] = useState<PipelineSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<PipelineSchedule | null>(null);

  // Form state for schedule creation/editing
  const [formData, setFormData] = useState<PipelineSchedule>({
    name: '',
    description: '',
    is_active: true,
    content_schedules: CONTENT_TYPES.map(ct => ({
      content_type: ct.key,
      frequency: ct.recommended_frequency as 'daily' | 'weekly' | 'monthly',
      enabled: true
    })),
    regions: ['US', 'UK', 'DE', 'SA', 'VN'],
    notification_emails: []
  });

  useEffect(() => {
    checkAuthAndLoadData();
  }, []);

  const checkAuthAndLoadData = async () => {
    setIsCheckingAuth(true);
    
    // Check authentication (similar to pipeline page)
    let token = localStorage.getItem('access_token');
    
    if (!token) {
      // Attempt auto-login
      try {
        console.log('🔐 Attempting auto-login for pipeline schedules page...');
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
          console.log('✅ Auto-login successful for pipeline schedules page');
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
          setError('Authentication failed - please login');
          setIsCheckingAuth(false);
          return;
        }
      } catch (error) {
        console.log('❌ Auto-login error:', error);
        setIsAuthenticated(false);
        setError('Authentication failed - please login');
        setIsCheckingAuth(false);
        return;
      }
    } else {
      setIsAuthenticated(true);
    }
    
    setIsCheckingAuth(false);
    await loadSchedules();
  };

  const loadSchedules = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/pipeline/schedules', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setSchedules(data.schedules || []);
        console.log('✅ Loaded pipeline schedules:', data.schedules?.length || 0);
      } else {
        setError(`Failed to load schedules (${response.status})`);
      }
    } catch (err) {
      setError('Failed to load schedules - check connection');
    } finally {
      setLoading(false);
    }
  };

  const createOrUpdateSchedule = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const url = editingSchedule ? `/api/v1/pipeline/schedules/${editingSchedule.id}` : '/api/v1/pipeline/schedules';
      const method = editingSchedule ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      
      if (response.ok) {
        await loadSchedules();
        setShowCreateDialog(false);
        setEditingSchedule(null);
        resetForm();
      } else {
        setError(`Failed to ${editingSchedule ? 'update' : 'create'} schedule`);
      }
    } catch (err) {
      setError(`Schedule ${editingSchedule ? 'update' : 'creation'} failed`);
    }
  };

  const toggleScheduleActive = async (scheduleId: string, isActive: boolean) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/pipeline/schedules/${scheduleId}/toggle`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_active: isActive })
      });
      
      if (response.ok) {
        await loadSchedules();
      }
    } catch (err) {
      setError('Failed to toggle schedule status');
    }
  };

  const deleteSchedule = async (scheduleId: string) => {
    if (!confirm('Are you sure you want to delete this schedule?')) return;
    
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/pipeline/schedules/${scheduleId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        await loadSchedules();
      }
    } catch (err) {
      setError('Failed to delete schedule');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      is_active: true,
      content_schedules: CONTENT_TYPES.map(ct => ({
        content_type: ct.key,
        frequency: ct.recommended_frequency as 'daily' | 'weekly' | 'monthly',
        enabled: true
      })),
      regions: ['US', 'UK', 'DE', 'SA', 'VN'],
      notification_emails: []
    });
  };

  const updateContentSchedule = (contentType: string, field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      content_schedules: prev.content_schedules.map(cs => 
        cs.content_type === contentType ? { ...cs, [field]: value } : cs
      )
    }));
  };

  const getFrequencyBadgeColor = (frequency: string) => {
    switch (frequency) {
      case 'daily': return 'bg-green-100 text-green-800';
      case 'weekly': return 'bg-blue-100 text-blue-800';
      case 'monthly': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (isCheckingAuth) {
    return (
      <AdminLayout title="Pipeline Scheduling" description="Automated pipeline execution management">
        <Card>
          <CardContent className="text-center py-8">
            <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Authenticating...</p>
          </CardContent>
        </Card>
      </AdminLayout>
    );
  }

  if (!isAuthenticated) {
    return (
      <AdminLayout title="Pipeline Scheduling" description="Automated pipeline execution management">
        <Card>
          <CardContent className="text-center py-8">
            <div className="text-red-500 mb-4">Authentication Required</div>
            <p className="text-gray-600">Please refresh the page to login</p>
            <Button onClick={() => window.location.reload()} className="cylvy-btn-primary mt-4">
              Refresh Page
            </Button>
          </CardContent>
        </Card>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Pipeline Scheduling" description="Automated competitive intelligence collection">
      <div className="space-y-6">
        
        {/* Header Actions */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-cylvy-midnight">Pipeline Scheduling</h1>
            <p className="text-gray-600">Configure automated analysis schedules for different content types</p>
          </div>
          
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button className="cylvy-btn-primary" onClick={() => { setEditingSchedule(null); resetForm(); }}>
                <Plus className="h-4 w-4 mr-2" />
                Create Schedule
              </Button>
            </DialogTrigger>
            
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-white">
              <DialogHeader>
                <DialogTitle className="text-cylvy-midnight">
                  {editingSchedule ? 'Edit Schedule' : 'Create New Schedule'}
                </DialogTitle>
                <DialogDescription>
                  Configure automated pipeline execution for different content types with custom frequencies.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-6">
                
                {/* Basic Schedule Info */}
                <div className="space-y-4 bg-white">
                  <div>
                    <Label htmlFor="schedule-name">Schedule Name *</Label>
                    <Input
                      id="schedule-name"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., Weekly Content Monitoring"
                      className="bg-white text-gray-900"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="schedule-description">Description</Label>
                    <Textarea
                      id="schedule-description"
                      value={formData.description}
                      onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Describe the purpose and scope of this schedule..."
                      rows={2}
                      className="bg-white text-gray-900"
                    />
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={formData.is_active}
                      onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_active: checked }))}
                    />
                    <Label>Schedule is active</Label>
                  </div>
                </div>

                {/* Content Type Schedules */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-cylvy-midnight">Content Type Schedules</h3>
                  <p className="text-sm text-gray-600">
                    Configure analysis frequency for each content type. Different content types have different update patterns.
                  </p>
                  
                  <div className="grid gap-4">
                    {CONTENT_TYPES.map((contentType) => {
                      const schedule = formData.content_schedules.find(cs => cs.content_type === contentType.key);
                      return (
                        <Card key={contentType.key} className="bg-white">
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-3 mb-2">
                                  <span className="text-2xl">{contentType.icon}</span>
                                  <div>
                                    <h4 className="font-medium text-gray-900">{contentType.name}</h4>
                                    <p className="text-xs text-gray-500">{contentType.description}</p>
                                  </div>
                                </div>
                                
                                <div className="flex items-center gap-4">
                                  <div className="flex items-center gap-2">
                                    <Switch
                                      checked={schedule?.enabled || false}
                                      onCheckedChange={(checked) => 
                                        updateContentSchedule(contentType.key, 'enabled', checked)
                                      }
                                    />
                                    <span className="text-sm text-gray-700">
                                      {schedule?.enabled ? 'Enabled' : 'Disabled'}
                                    </span>
                                  </div>
                                  
                                  {schedule?.enabled && (
                                    <select
                                      value={schedule.frequency}
                                      onChange={(e) => 
                                        updateContentSchedule(contentType.key, 'frequency', e.target.value)
                                      }
                                      className="w-32 px-3 py-1 bg-white border border-gray-300 rounded-md text-sm"
                                    >
                                      {FREQUENCY_OPTIONS.map(freq => (
                                        <option key={freq.value} value={freq.value}>
                                          {freq.label}
                                        </option>
                                      ))}
                                    </select>
                                  )}
                                  
                                  <Badge className={getFrequencyBadgeColor(schedule?.frequency || 'monthly')}>
                                    {schedule?.frequency || 'monthly'}
                                  </Badge>
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </div>

                {/* Target Regions */}
                <div className="space-y-3 bg-white">
                  <Label>Target Regions</Label>
                  <div className="grid grid-cols-5 gap-2">
                    {['US', 'UK', 'DE', 'SA', 'VN', 'FR', 'ES', 'IT', 'AU', 'JP'].map(country => (
                      <div key={country} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id={country}
                          checked={formData.regions.includes(country)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData(prev => ({
                                ...prev,
                                regions: [...prev.regions, country]
                              }));
                            } else {
                              setFormData(prev => ({
                                ...prev, 
                                regions: prev.regions.filter(r => r !== country)
                              }));
                            }
                          }}
                          className="rounded"
                        />
                        <label htmlFor={country} className="text-sm text-gray-700">{country}</label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex justify-end gap-3 pt-4">
                  <Button 
                    variant="outline" 
                    onClick={() => { setShowCreateDialog(false); setEditingSchedule(null); }}
                  >
                    Cancel
                  </Button>
                  <Button 
                    className="cylvy-btn-primary"
                    onClick={createOrUpdateSchedule}
                    disabled={!formData.name.trim()}
                  >
                    {editingSchedule ? 'Update Schedule' : 'Create Schedule'}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Error Display */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="py-4">
              <div className="flex items-center gap-2 text-red-800">
                <AlertCircle className="h-4 w-4" />
                {error}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Schedules List */}
        {loading ? (
          <Card>
            <CardContent className="text-center py-8">
              <div className="w-8 h-8 border-2 border-cylvy-amaranth border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
              <p className="text-gray-600">Loading schedules...</p>
            </CardContent>
          </Card>
        ) : schedules.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <Calendar className="mx-auto h-16 w-16 text-gray-400 mb-6" />
              <h3 className="text-xl font-bold mb-2 text-cylvy-midnight">No Pipeline Schedules</h3>
              <p className="text-gray-600 mb-6 max-w-md mx-auto">
                Create your first automated pipeline schedule to regularly collect competitive intelligence data.
              </p>
              <Button onClick={() => setShowCreateDialog(true)} className="cylvy-btn-primary">
                🗓️ Create First Schedule
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6">
            {schedules.map((schedule) => (
              <Card key={schedule.id} className="cylvy-card-hover bg-white">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-3 text-cylvy-midnight">
                        {schedule.is_active ? (
                          <CheckCircle className="h-5 w-5 text-green-500" />
                        ) : (
                          <Pause className="h-5 w-5 text-gray-400" />
                        )}
                        {schedule.name}
                      </CardTitle>
                      <CardDescription>{schedule.description}</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={schedule.is_active ? 'success' : 'secondary'}>
                        {schedule.is_active ? 'Active' : 'Paused'}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingSchedule(schedule);
                          setFormData(schedule);
                          setShowCreateDialog(true);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteSchedule(schedule.id!)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-4 bg-white">
                  
                  {/* Content Type Schedules */}
                  <div>
                    <h4 className="font-medium text-sm mb-3 text-gray-900">Content Type Frequencies:</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                      {schedule.content_schedules.map((cs) => {
                        const contentType = CONTENT_TYPES.find(ct => ct.key === cs.content_type);
                        return (
                          <div key={cs.content_type} className="text-center p-3 bg-gray-50 rounded-lg">
                            <div className="text-lg mb-1">{contentType?.icon}</div>
                            <div className="text-xs font-medium text-gray-700">{contentType?.name}</div>
                            <Badge className={`mt-1 ${getFrequencyBadgeColor(cs.frequency)}`} size="sm">
                              {cs.frequency}
                            </Badge>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Schedule Info */}
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Regions:</span>
                      <div className="mt-1">
                        {schedule.regions.join(', ')}
                      </div>
                    </div>
                    <div>
                      <span className="text-gray-500">Next Execution:</span>
                      <div className="mt-1 flex items-center gap-2">
                        <Timer className="h-3 w-3 text-blue-500" />
                        {schedule.next_execution_at ? 
                          new Date(schedule.next_execution_at).toLocaleString() : 
                          'Not scheduled'
                        }
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-3 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleScheduleActive(schedule.id!, !schedule.is_active)}
                    >
                      {schedule.is_active ? (
                        <>
                          <Pause className="h-3 w-3 mr-1" />
                          Pause
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3 mr-1" />
                          Activate
                        </>
                      )}
                    </Button>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Trigger immediate execution
                        console.log('Manual execution triggered for schedule:', schedule.id);
                      }}
                    >
                      <Play className="h-3 w-3 mr-1" />
                      Run Now
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
