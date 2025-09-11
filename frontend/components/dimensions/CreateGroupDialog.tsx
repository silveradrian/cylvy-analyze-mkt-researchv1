import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"

interface CreateGroupDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: any) => void
}

const SELECTION_STRATEGIES = [
  { value: "highest_score", label: "Highest Score", description: "Select dimensions with the highest overall score" },
  { value: "highest_confidence", label: "Highest Confidence", description: "Select dimensions with the highest confidence level" },
  { value: "most_evidence", label: "Most Evidence", description: "Select dimensions with the most supporting evidence" },
  { value: "manual", label: "Manual Selection", description: "Manually prioritize dimensions" }
]

const PRESET_COLORS = [
  "#3B82F6", // Blue
  "#10B981", // Emerald
  "#8B5CF6", // Violet
  "#F59E0B", // Amber
  "#EF4444", // Red
  "#EC4899", // Pink
  "#6366F1", // Indigo
  "#14B8A6", // Teal
]

export function CreateGroupDialog({
  open,
  onOpenChange,
  onSubmit
}: CreateGroupDialogProps) {
  const [formData, setFormData] = useState({
    group_id: "",
    name: "",
    description: "",
    selection_strategy: "highest_score",
    max_primary_dimensions: 1,
    display_order: 0,
    color_hex: "#3B82F6",
    icon: "",
    metadata: {},
    is_active: true
  })

  const handleSubmit = () => {
    // Generate group_id if not provided
    const groupId = formData.group_id || 
      formData.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')

    onSubmit({
      ...formData,
      group_id: groupId
    })

    // Reset form
    setFormData({
      group_id: "",
      name: "",
      description: "",
      selection_strategy: "highest_score",
      max_primary_dimensions: 1,
      display_order: 0,
      color_hex: "#3B82F6",
      icon: "",
      metadata: {},
      is_active: true
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Dimension Group</DialogTitle>
          <DialogDescription>
            Create a new group to organize related dimensions
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Group Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Strategic Pillars"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="group_id">Group ID</Label>
            <Input
              id="group_id"
              value={formData.group_id}
              onChange={(e) => setFormData({ ...formData, group_id: e.target.value })}
              placeholder="e.g., strategic_pillars (auto-generated if empty)"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Describe the purpose of this dimension group..."
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="selection_strategy">Selection Strategy</Label>
            <Select
              value={formData.selection_strategy}
              onValueChange={(value) => setFormData({ ...formData, selection_strategy: value })}
            >
              <SelectTrigger id="selection_strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SELECTION_STRATEGIES.map((strategy) => (
                  <SelectItem key={strategy.value} value={strategy.value}>
                    <div>
                      <div className="font-medium">{strategy.label}</div>
                      <div className="text-xs text-muted-foreground">{strategy.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="max_primary">
              Maximum Primary Dimensions: {formData.max_primary_dimensions}
            </Label>
            <Slider
              id="max_primary"
              value={[formData.max_primary_dimensions]}
              onValueChange={(value) => setFormData({ ...formData, max_primary_dimensions: value[0] })}
              min={1}
              max={5}
              step={1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              How many dimensions can be selected as primary in this group
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="display_order">
              Display Order: {formData.display_order}
            </Label>
            <Slider
              id="display_order"
              value={[formData.display_order]}
              onValueChange={(value) => setFormData({ ...formData, display_order: value[0] })}
              min={0}
              max={10}
              step={1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Lower numbers appear first
            </p>
          </div>

          <div className="space-y-2">
            <Label>Color</Label>
            <div className="flex gap-2">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  className={`w-8 h-8 rounded border-2 ${
                    formData.color_hex === color ? 'border-primary' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: color }}
                  onClick={() => setFormData({ ...formData, color_hex: color })}
                />
              ))}
              <Input
                type="color"
                value={formData.color_hex}
                onChange={(e) => setFormData({ ...formData, color_hex: e.target.value })}
                className="w-8 h-8 p-0 border-2"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="icon">Icon (optional)</Label>
            <Input
              id="icon"
              value={formData.icon}
              onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
              placeholder="e.g., folder, chart-bar, target"
            />
            <p className="text-xs text-muted-foreground">
              Icon identifier for UI display
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!formData.name}>
            Create Group
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

