import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface DimensionGroup {
  id: string
  name: string
}

interface CreateDimensionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: any) => void
  groups: DimensionGroup[]
}

export function CreateDimensionDialog({
  open,
  onOpenChange,
  onSubmit,
  groups
}: CreateDimensionDialogProps) {
  const [formData, setFormData] = useState({
    dimension_id: "",
    name: "",
    description: "",
    group_ids: [] as string[],
    ai_context: {
      general_description: "",
      purpose: "",
      scope: "",
      key_focus_areas: [] as string[],
      analysis_approach: ""
    },
    criteria: {
      what_counts: "",
      positive_signals: [] as string[],
      negative_signals: [] as string[],
      exclusions: [] as string[]
    },
    scoring_framework: {
      levels: {} as Record<string, string>,
      evidence_requirements: "",
      contextual_rules: ""
    }
  })

  const [currentSignal, setCurrentSignal] = useState("")
  const [currentFocusArea, setCurrentFocusArea] = useState("")

  const handleSubmit = () => {
    // Generate dimension_id if not provided
    const dimensionId = formData.dimension_id || 
      formData.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')

    onSubmit({
      ...formData,
      dimension_id: dimensionId,
      is_active: true
    })

    // Reset form
    setFormData({
      dimension_id: "",
      name: "",
      description: "",
      group_ids: [],
      ai_context: {
        general_description: "",
        purpose: "",
        scope: "",
        key_focus_areas: [],
        analysis_approach: ""
      },
      criteria: {
        what_counts: "",
        positive_signals: [],
        negative_signals: [],
        exclusions: []
      },
      scoring_framework: {
        levels: {},
        evidence_requirements: "",
        contextual_rules: ""
      }
    })
  }

  const addToList = (field: string, value: string, setter: (v: string) => void) => {
    if (value.trim()) {
      const path = field.split('.')
      const newData = { ...formData }
      let current: any = newData
      
      for (let i = 0; i < path.length - 1; i++) {
        current = current[path[i]]
      }
      
      current[path[path.length - 1]].push(value.trim())
      setFormData(newData)
      setter("")
    }
  }

  const removeFromList = (field: string, index: number) => {
    const path = field.split('.')
    const newData = { ...formData }
    let current: any = newData
    
    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]]
    }
    
    current[path[path.length - 1]].splice(index, 1)
    setFormData(newData)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Custom Dimension</DialogTitle>
          <DialogDescription>
            Define a new dimension for content analysis
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="basic" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="basic">Basic Info</TabsTrigger>
            <TabsTrigger value="ai">AI Context</TabsTrigger>
            <TabsTrigger value="criteria">Criteria</TabsTrigger>
            <TabsTrigger value="scoring">Scoring</TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Dimension Name *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Customer Obsession"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="dimension_id">Dimension ID</Label>
              <Input
                id="dimension_id"
                value={formData.dimension_id}
                onChange={(e) => setFormData({ ...formData, dimension_id: e.target.value })}
                placeholder="e.g., customer_obsession (auto-generated if empty)"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe what this dimension measures..."
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label>Assign to Groups</Label>
              <div className="space-y-2">
                {groups.map((group) => (
                  <div key={group.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`group-${group.id}`}
                      checked={formData.group_ids.includes(group.id)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setFormData({
                            ...formData,
                            group_ids: [...formData.group_ids, group.id]
                          })
                        } else {
                          setFormData({
                            ...formData,
                            group_ids: formData.group_ids.filter(id => id !== group.id)
                          })
                        }
                      }}
                    />
                    <Label htmlFor={`group-${group.id}`} className="cursor-pointer">
                      {group.name}
                    </Label>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="ai" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ai_general">General Description</Label>
              <Textarea
                id="ai_general"
                value={formData.ai_context.general_description}
                onChange={(e) => setFormData({
                  ...formData,
                  ai_context: { ...formData.ai_context, general_description: e.target.value }
                })}
                placeholder="Describe this dimension for the AI analyzer..."
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai_purpose">Purpose</Label>
              <Input
                id="ai_purpose"
                value={formData.ai_context.purpose}
                onChange={(e) => setFormData({
                  ...formData,
                  ai_context: { ...formData.ai_context, purpose: e.target.value }
                })}
                placeholder="e.g., Evaluate content relevance to customer-centric practices"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai_scope">Scope</Label>
              <Input
                id="ai_scope"
                value={formData.ai_context.scope}
                onChange={(e) => setFormData({
                  ...formData,
                  ai_context: { ...formData.ai_context, scope: e.target.value }
                })}
                placeholder="e.g., strategic_pillar, business_unit, capability"
              />
            </div>

            <div className="space-y-2">
              <Label>Key Focus Areas</Label>
              <div className="flex gap-2">
                <Input
                  value={currentFocusArea}
                  onChange={(e) => setCurrentFocusArea(e.target.value)}
                  placeholder="Add a focus area..."
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addToList('ai_context.key_focus_areas', currentFocusArea, setCurrentFocusArea)
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => addToList('ai_context.key_focus_areas', currentFocusArea, setCurrentFocusArea)}
                >
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.ai_context.key_focus_areas.map((area, index) => (
                  <Badge key={index} variant="secondary">
                    {area}
                    <button
                      className="ml-2 text-xs"
                      onClick={() => removeFromList('ai_context.key_focus_areas', index)}
                    >
                      ×
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="criteria" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="what_counts">What Counts</Label>
              <Textarea
                id="what_counts"
                value={formData.criteria.what_counts}
                onChange={(e) => setFormData({
                  ...formData,
                  criteria: { ...formData.criteria, what_counts: e.target.value }
                })}
                placeholder="Describe what evidence counts for this dimension..."
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label>Positive Signals</Label>
              <div className="flex gap-2">
                <Input
                  value={currentSignal}
                  onChange={(e) => setCurrentSignal(e.target.value)}
                  placeholder="Add a positive signal..."
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addToList('criteria.positive_signals', currentSignal, setCurrentSignal)
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => addToList('criteria.positive_signals', currentSignal, setCurrentSignal)}
                >
                  Add
                </Button>
              </div>
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.criteria.positive_signals.map((signal, index) => (
                  <Badge key={index} variant="default">
                    {signal}
                    <button
                      className="ml-2 text-xs"
                      onClick={() => removeFromList('criteria.positive_signals', index)}
                    >
                      ×
                    </button>
                  </Badge>
                ))}
              </div>
            </div>

            {/* Similar sections for negative_signals and exclusions */}
          </TabsContent>

          <TabsContent value="scoring" className="space-y-4">
            <div className="space-y-2">
              <Label>Scoring Levels</Label>
              <div className="space-y-2">
                {["0-2", "3-4", "5-6", "7-8", "9-10"].map((range) => (
                  <div key={range} className="flex gap-2 items-center">
                    <Label className="w-16">{range}:</Label>
                    <Input
                      value={formData.scoring_framework.levels[range] || ""}
                      onChange={(e) => setFormData({
                        ...formData,
                        scoring_framework: {
                          ...formData.scoring_framework,
                          levels: {
                            ...formData.scoring_framework.levels,
                            [range]: e.target.value
                          }
                        }
                      })}
                      placeholder={`Description for score ${range}...`}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="evidence_requirements">Evidence Requirements</Label>
              <Textarea
                id="evidence_requirements"
                value={formData.scoring_framework.evidence_requirements}
                onChange={(e) => setFormData({
                  ...formData,
                  scoring_framework: {
                    ...formData.scoring_framework,
                    evidence_requirements: e.target.value
                  }
                })}
                placeholder="Describe evidence requirements for scoring..."
                rows={3}
              />
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!formData.name}>
            Create Dimension
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Fix the missing Badge import
import { Badge } from "@/components/ui/badge"

