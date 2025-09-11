"use client"

import { useState, useEffect } from "react"
import { Plus, Settings, Folder } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/use-toast"
import { AdminLayout } from "@/components/layout/AdminLayout"
import { DimensionGroupList } from "@/components/dimensions/DimensionGroupList"
import { DimensionList } from "@/components/dimensions/DimensionList"
import { CreateDimensionDialog } from "@/components/dimensions/CreateDimensionDialog"
import { CreateGroupDialog } from "@/components/dimensions/CreateGroupDialog"

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

interface Dimension {
  id: string
  client_id: string
  dimension_id: string
  name: string
  description?: string
  ai_context: any
  criteria: any
  scoring_framework: any
  metadata: any
  is_active: boolean
  created_at: string
  updated_at: string
  created_by?: string
  groups: DimensionGroup[]
}

export default function DimensionsPage() {
  const [groups, setGroups] = useState<DimensionGroup[]>([])
  const [dimensions, setDimensions] = useState<Dimension[]>([])
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [isLoadingGroups, setIsLoadingGroups] = useState(true)
  const [isLoadingDimensions, setIsLoadingDimensions] = useState(false)
  const [showCreateDimension, setShowCreateDimension] = useState(false)
  const [showCreateGroup, setShowCreateGroup] = useState(false)
  const { toast } = useToast()

  // Load dimension groups
  const loadGroups = async () => {
    try {
      const token = localStorage.getItem("auth_token") || "test-token-for-development"
      const response = await fetch("/api/v1/dimensions/dimension-groups", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        throw new Error("Failed to load dimension groups")
      }
      
      const data = await response.json()
      setGroups(data)
    } catch (error) {
      console.error("Error loading dimension groups:", error)
      toast({
        title: "Error",
        description: "Failed to load dimension groups",
        variant: "destructive"
      })
    } finally {
      setIsLoadingGroups(false)
    }
  }

  // Load dimensions
  const loadDimensions = async (groupId?: string) => {
    setIsLoadingDimensions(true)
    try {
      const token = localStorage.getItem("auth_token") || "test-token-for-development"
      const url = groupId 
        ? `/api/v1/dimensions/dimensions?group_id=${groupId}`
        : "/api/v1/dimensions/dimensions"
        
      const response = await fetch(url, {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        throw new Error("Failed to load dimensions")
      }
      
      const data = await response.json()
      setDimensions(data)
    } catch (error) {
      console.error("Error loading dimensions:", error)
      toast({
        title: "Error",
        description: "Failed to load dimensions",
        variant: "destructive"
      })
    } finally {
      setIsLoadingDimensions(false)
    }
  }

  useEffect(() => {
    loadGroups()
    loadDimensions()
  }, [])

  const handleGroupSelect = (groupId: string | null) => {
    setSelectedGroup(groupId)
    loadDimensions(groupId || undefined)
  }

  const handleCreateGroup = async (groupData: any) => {
    try {
      const token = localStorage.getItem("auth_token") || "test-token-for-development"
      const response = await fetch("/api/v1/dimensions/dimension-groups", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(groupData)
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "Failed to create group")
      }
      
      toast({
        title: "Success",
        description: "Dimension group created successfully"
      })
      
      setShowCreateGroup(false)
      loadGroups()
    } catch (error: any) {
      console.error("Error creating group:", error)
      toast({
        title: "Error",
        description: error.message || "Failed to create dimension group",
        variant: "destructive"
      })
    }
  }

  const handleCreateDimension = async (dimensionData: any) => {
    try {
      const token = localStorage.getItem("auth_token") || "test-token-for-development"
      const response = await fetch("/api/v1/dimensions/dimensions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(dimensionData)
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "Failed to create dimension")
      }
      
      toast({
        title: "Success",
        description: "Dimension created successfully"
      })
      
      setShowCreateDimension(false)
      loadDimensions(selectedGroup || undefined)
    } catch (error: any) {
      console.error("Error creating dimension:", error)
      toast({
        title: "Error",
        description: error.message || "Failed to create dimension",
        variant: "destructive"
      })
    }
  }

  const handleDeleteDimension = async (dimensionId: string) => {
    try {
      const token = localStorage.getItem("auth_token") || "test-token-for-development"
      const response = await fetch(`/api/v1/dimensions/dimensions/${dimensionId}`, {
        method: "DELETE",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        throw new Error("Failed to delete dimension")
      }
      
      toast({
        title: "Success",
        description: "Dimension deleted successfully"
      })
      
      loadDimensions(selectedGroup || undefined)
    } catch (error) {
      console.error("Error deleting dimension:", error)
      toast({
        title: "Error",
        description: "Failed to delete dimension",
        variant: "destructive"
      })
    }
  }

  return (
    <AdminLayout title="Custom Dimensions">
      <div className="container mx-auto py-8">
        <div className="flex justify-between items-center mb-8">
              <div>
            <h1 className="text-3xl font-bold">Custom Dimensions</h1>
            <p className="text-muted-foreground mt-2">
              Manage analysis dimensions and their groupings
                </p>
              </div>
        <div className="flex gap-4">
          <Button
            onClick={() => setShowCreateGroup(true)}
            variant="outline"
          >
            <Folder className="h-4 w-4 mr-2" />
            Create Group
          </Button>
          <Button
            onClick={() => setShowCreateDimension(true)}
          >
                <Plus className="h-4 w-4 mr-2" />
                Create Dimension
              </Button>
            </div>
      </div>

      <Tabs defaultValue="dimensions" className="space-y-4">
        <TabsList>
          <TabsTrigger value="dimensions">Dimensions</TabsTrigger>
          <TabsTrigger value="groups">Dimension Groups</TabsTrigger>
        </TabsList>

        <TabsContent value="dimensions" className="space-y-4">
              <Card>
                    <CardHeader>
              <CardTitle>Analysis Dimensions</CardTitle>
              <CardDescription>
                {selectedGroup 
                  ? `Showing dimensions in: ${groups.find(g => g.id === selectedGroup)?.name || 'Unknown'}`
                  : "All custom dimensions for content analysis"
                }
              </CardDescription>
                    </CardHeader>
                    <CardContent>
              <DimensionList
                dimensions={dimensions}
                groups={groups}
                selectedGroup={selectedGroup}
                onGroupSelect={handleGroupSelect}
                onDelete={handleDeleteDimension}
                isLoading={isLoadingDimensions}
              />
                    </CardContent>
                  </Card>
          </TabsContent>

        <TabsContent value="groups" className="space-y-4">
          <Card>
                  <CardHeader>
              <CardTitle>Dimension Groups</CardTitle>
              <CardDescription>
                Organize dimensions into logical groups for analysis
              </CardDescription>
                  </CardHeader>
                  <CardContent>
              <DimensionGroupList
                groups={groups}
                isLoading={isLoadingGroups}
                onGroupSelect={handleGroupSelect}
              />
                  </CardContent>
                </Card>
          </TabsContent>
        </Tabs>

      <CreateDimensionDialog
        open={showCreateDimension}
        onOpenChange={setShowCreateDimension}
        onSubmit={handleCreateDimension}
        groups={groups}
      />

      <CreateGroupDialog
        open={showCreateGroup}
        onOpenChange={setShowCreateGroup}
        onSubmit={handleCreateGroup}
      />
      </div>
    </AdminLayout>
  )
}