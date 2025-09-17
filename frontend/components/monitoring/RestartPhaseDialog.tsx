"use client";

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { RotateCcw, AlertTriangle, Zap } from 'lucide-react';

interface RestartPhaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  phaseName: string;
  phaseDisplayName: string;
  pipelineId: string;
  onRestart: (freshAnalysis: boolean) => void;
  isRestarting?: boolean;
}

export function RestartPhaseDialog({
  open,
  onOpenChange,
  phaseName,
  phaseDisplayName,
  pipelineId,
  onRestart,
  isRestarting = false
}: RestartPhaseDialogProps) {
  const [freshAnalysis, setFreshAnalysis] = useState(false);

  const handleConfirm = () => {
    onRestart(freshAnalysis);
    onOpenChange(false);
    setFreshAnalysis(false); // Reset for next time
  };

  const handleCancel = () => {
    onOpenChange(false);
    setFreshAnalysis(false); // Reset for next time
  };

  // Show different content based on phase type
  const isContentAnalysis = phaseName === 'content_analysis';
  const isDataIntensivePhase = ['content_analysis', 'company_enrichment_serp', 'youtube_enrichment'].includes(phaseName);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-orange-600" />
            Restart Phase Confirmation
          </DialogTitle>
          <DialogDescription>
            You are about to restart the <strong>{phaseDisplayName}</strong> phase for pipeline #{pipelineId.slice(0, 8)}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Warning for content analysis */}
          {isContentAnalysis && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>Content Analysis Phase:</strong> This will reprocess all scraped content for AI analysis including personas, JTBDs, and Strategic Imperatives.
              </AlertDescription>
            </Alert>
          )}

          {/* Fresh analysis option for data-intensive phases */}
          {isDataIntensivePhase && (
            <div className="space-y-3 border rounded-lg p-4 bg-gray-50">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="fresh-analysis"
                  checked={freshAnalysis}
                  onCheckedChange={(checked) => setFreshAnalysis(checked as boolean)}
                />
                <Label 
                  htmlFor="fresh-analysis" 
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Get fresh analysis
                </Label>
                <Zap className="h-4 w-4 text-blue-500" />
              </div>
              
              <div className="text-sm text-gray-600 pl-6">
                {isContentAnalysis ? (
                  <>
                    <strong>Recommended for missing Strategic Imperatives:</strong>
                    <ul className="list-disc list-inside mt-1 space-y-1">
                      <li>Ignores previously analyzed content and caches</li>
                      <li>Re-analyzes all content with current AI models</li>
                      <li>Ensures all configured dimensions are analyzed</li>
                      <li>Fixes missing Strategic Imperatives analysis</li>
                    </ul>
                  </>
                ) : (
                  <>
                    Clear all previous {phaseDisplayName.toLowerCase()} data and start fresh.
                    This ensures complete reprocessing with current configuration.
                  </>
                )}
              </div>

              {freshAnalysis && (
                <Alert className="border-orange-200 bg-orange-50">
                  <AlertTriangle className="h-4 w-4 text-orange-600" />
                  <AlertDescription className="text-orange-800">
                    <strong>Fresh analysis will:</strong> Clear existing analysis data and reprocess everything. 
                    This may take significant time but ensures complete, up-to-date results.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {/* Regular restart info */}
          {!freshAnalysis && (
            <div className="text-sm text-gray-600">
              This will reset the phase status to "pending" and allow it to resume processing from where it left off.
            </div>
          )}
        </div>

        <DialogFooter className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isRestarting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={isRestarting}
            variant={freshAnalysis ? "destructive" : "default"}
            className={freshAnalysis ? "bg-orange-600 hover:bg-orange-700" : ""}
          >
            {isRestarting ? (
              <>
                <RotateCcw className="h-4 w-4 mr-2 animate-spin" />
                Restarting...
              </>
            ) : (
              <>
                <RotateCcw className="h-4 w-4 mr-2" />
                {freshAnalysis ? 'Start Fresh Analysis' : 'Restart Phase'}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
