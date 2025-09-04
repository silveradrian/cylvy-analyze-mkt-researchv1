'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { 
  Plus, 
  Calendar, 
  Clock, 
  Edit,
  Trash2,
  Play,
  Pause,
  AlertCircle
} from 'lucide-react'
import { pipelineAPI } from '@/app/services/api'

interface Schedule {
  schedule_id: string
  name: string
  cron_expression: string
  description: string
  enabled: boolean
  next_run: string
  last_run?: string
  created_at: string
  pipeline_config: any
}

export function PipelineSchedules() {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    cron_expression: '0 9 * * 1', // Default: Every Monday at 9 AM
    enabled: true
  })

  useEffect(() => {
    loadSchedules()
  }, [])

  const loadSchedules = async () => {
    try {
      setLoading(true)
      const response = await pipelineAPI.getSchedules()
      setSchedules(response.schedules || [])
    } catch (error) {
      console.error('Failed to load schedules:', error)
    } finally {
      setLoading(false)
    }
  }

  const createSchedule = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      await pipelineAPI.createSchedule({
        ...formData,
        pipeline_config: {
          mode: 'scheduled',
          collect_serp: true,
          enrich_companies: true,
          scrape_content: true,
          analyze_content: true
        }
      })
      
      setShowCreateDialog(false)
      setFormData({
        name: '',
        description: '',
        cron_expression: '0 9 * * 1',
        enabled: true
      })
      loadSchedules()
    } catch (error) {
      console.error('Failed to create schedule:', error)
    }
  }

  const updateSchedule = async (scheduleId: string, updates: Partial<Schedule>) => {
    try {
      await pipelineAPI.updateSchedule(scheduleId, updates)
      loadSchedules()
    } catch (error) {
      console.error('Failed to update schedule:', error)
    }
  }

  const deleteSchedule = async (scheduleId: string) => {
    if (confirm('Are you sure you want to delete this schedule?')) {
      try {
        await pipelineAPI.deleteSchedule(scheduleId)
        loadSchedules()
      } catch (error) {
        console.error('Failed to delete schedule:', error)
      }
    }
  }

  const toggleSchedule = (schedule: Schedule) => {
    updateSchedule(schedule.schedule_id, { enabled: !schedule.enabled })
  }

  const formatCronExpression = (cron: string) => {
    // Simple cron expression formatter
    const commonPatterns: Record<string, string> = {
      '0 9 * * 1': 'Every Monday at 9:00 AM',
      '0 9 * * 1-5': 'Weekdays at 9:00 AM',
      '0 0 * * 0': 'Every Sunday at midnight',
      '0 12 * * *': 'Daily at noon',
      '0 0 1 * *': 'Monthly on the 1st at midnight',
    }
    
    return commonPatterns[cron] || cron
  }

  const getNextRunBadge = (nextRun: string) => {
    const nextRunDate = new Date(nextRun)
    const now = new Date()
    const diffHours = Math.round((nextRunDate.getTime() - now.getTime()) / (1000 * 60 * 60))
    
    if (diffHours < 1) {
      return <Badge variant="secondary">Soon</Badge>
    } else if (diffHours < 24) {
      return <Badge variant="secondary">{diffHours}h</Badge>
    } else {
      const diffDays = Math.round(diffHours / 24)
      return <Badge variant="secondary">{diffDays}d</Badge>
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="text-center py-8">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p>Loading schedules...</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-start">
            <div>
              <CardTitle>Pipeline Schedules</CardTitle>
              <CardDescription>
                Automate your pipeline execution with scheduled runs
              </CardDescription>
            </div>
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Schedule
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Pipeline Schedule</DialogTitle>
                  <DialogDescription>
                    Set up automated pipeline execution
                  </DialogDescription>
                </DialogHeader>
                
                <form onSubmit={createSchedule} className="space-y-4">
                  <div>
                    <Label htmlFor="name">Schedule Name</Label>
                    <Input
                      id="name"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Weekly Analysis"
                      required
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="description">Description</Label>
                    <Input
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Describe what this schedule does..."
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="cron">Schedule</Label>
                    <Select 
                      value={formData.cron_expression} 
                      onValueChange={(value) => setFormData(prev => ({ ...prev, cron_expression: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="0 9 * * 1">Every Monday at 9:00 AM</SelectItem>
                        <SelectItem value="0 9 * * 1-5">Weekdays at 9:00 AM</SelectItem>
                        <SelectItem value="0 0 * * 0">Every Sunday at midnight</SelectItem>
                        <SelectItem value="0 12 * * *">Daily at noon</SelectItem>
                        <SelectItem value="0 0 1 * *">Monthly on the 1st</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="enabled"
                      checked={formData.enabled}
                      onCheckedChange={(checked) => setFormData(prev => ({ ...prev, enabled: checked }))}
                    />
                    <Label htmlFor="enabled">Enable immediately</Label>
                  </div>
                  
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setShowCreateDialog(false)}>
                      Cancel
                    </Button>
                    <Button type="submit">Create Schedule</Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
      </Card>

      {schedules.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8">
            <Calendar className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium mb-2">No Schedules</h3>
            <p className="text-gray-600 mb-4">
              Create your first automated pipeline schedule to run analysis regularly
            </p>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create First Schedule
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {schedules.map((schedule) => (
            <Card key={schedule.schedule_id} className={`transition-opacity ${!schedule.enabled ? 'opacity-60' : ''}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${schedule.enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
                    <div>
                      <div className="font-medium">{schedule.name}</div>
                      <div className="text-sm text-gray-600">{schedule.description}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge variant={schedule.enabled ? "success" : "secondary"}>
                      {schedule.enabled ? 'Active' : 'Disabled'}
                    </Badge>
                    {schedule.enabled && getNextRunBadge(schedule.next_run)}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
                  <div>
                    <div className="text-gray-500">Schedule</div>
                    <div className="font-medium">{formatCronExpression(schedule.cron_expression)}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Next Run</div>
                    <div className="font-medium">
                      {schedule.enabled ? new Date(schedule.next_run).toLocaleString() : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Last Run</div>
                    <div className="font-medium">
                      {schedule.last_run ? new Date(schedule.last_run).toLocaleString() : 'Never'}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Created</div>
                    <div className="font-medium">
                      {new Date(schedule.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleSchedule(schedule)}
                  >
                    {schedule.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingSchedule(schedule)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteSchedule(schedule.schedule_id)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

