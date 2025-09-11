import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Settings, Users, ChevronRight } from "lucide-react"

interface DimensionGroup {
  id: string
  group_id: string
  name: string
  description?: string
  selection_strategy: string
  max_primary_dimensions: number
  display_order: number
  color_hex?: string
  icon?: string
  is_active: boolean
  dimension_count: number
  created_at: string
  updated_at: string
}

interface DimensionGroupListProps {
  groups: DimensionGroup[]
  isLoading: boolean
  onGroupSelect?: (groupId: string) => void
}

const strategyLabels: Record<string, string> = {
  highest_score: "Highest Score",
  highest_confidence: "Highest Confidence",
  most_evidence: "Most Evidence",
  manual: "Manual Selection"
}

export function DimensionGroupList({ 
  groups, 
  isLoading, 
  onGroupSelect 
}: DimensionGroupListProps) {
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-32" />
              <Skeleton className="h-4 w-48 mt-2" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-20 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (groups.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">No dimension groups found</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {groups.map((group) => (
        <Card 
          key={group.id} 
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => onGroupSelect?.(group.id)}
        >
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                {group.color_hex && (
                  <div 
                    className="w-4 h-4 rounded"
                    style={{ backgroundColor: group.color_hex }}
                  />
                )}
                <CardTitle className="text-lg">{group.name}</CardTitle>
              </div>
              <Badge variant={group.is_active ? "default" : "secondary"}>
                {group.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            {group.description && (
              <CardDescription className="mt-2">
                {group.description}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Dimensions</span>
                <span className="font-medium">{group.dimension_count}</span>
              </div>
              
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Selection Strategy</span>
                <Badge variant="outline" className="text-xs">
                  {strategyLabels[group.selection_strategy] || group.selection_strategy}
                </Badge>
              </div>
              
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Max Primary</span>
                <span className="font-medium">{group.max_primary_dimensions}</span>
              </div>
              
              <div className="pt-3 flex items-center justify-between">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation()
                    // TODO: Edit group
                  }}
                >
                  <Settings className="h-4 w-4 mr-1" />
                  Edit
                </Button>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

