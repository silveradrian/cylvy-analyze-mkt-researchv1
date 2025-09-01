'use client';

import { useState, useCallback } from 'react';
import { Upload, X, Image as ImageIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface LogoUploaderProps {
  currentLogo?: string | null;
  onUpload: (file: File) => Promise<void>;
  onDelete?: () => Promise<void>;
  maxSizeMB?: number;
}

export function LogoUploader({
  currentLogo,
  onUpload,
  onDelete,
  maxSizeMB = 5
}: LogoUploaderProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(currentLogo || null);
  const [dragActive, setDragActive] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    setError(null);

    // Validate file type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'];
    if (!validTypes.includes(file.type)) {
      setError('Please upload a PNG, JPG, or SVG file');
      return;
    }

    // Validate file size
    const maxSize = maxSizeMB * 1024 * 1024;
    if (file.size > maxSize) {
      setError(`File size must be less than ${maxSizeMB}MB`);
      return;
    }

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);

    // Upload file
    setIsUploading(true);
    try {
      await onUpload(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setPreview(currentLogo || null);
    } finally {
      setIsUploading(false);
    }
  }, [onUpload, currentLogo, maxSizeMB]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  }, [handleFile]);

  const handleDelete = async () => {
    if (!onDelete) return;
    
    setIsUploading(true);
    try {
      await onDelete();
      setPreview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-6 text-center
          ${dragActive ? 'border-primary bg-primary/5' : 'border-gray-300'}
          ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/svg+xml"
          onChange={handleChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />

        {preview ? (
          <div className="space-y-4">
            <div className="mx-auto w-32 h-32 flex items-center justify-center bg-gray-50 rounded-lg overflow-hidden">
              <img
                src={preview}
                alt="Logo preview"
                className="max-w-full max-h-full object-contain"
              />
            </div>
            <div className="flex justify-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={isUploading}
                onClick={(e) => {
                  e.preventDefault();
                  const input = e.currentTarget.parentElement?.parentElement?.querySelector('input');
                  input?.click();
                }}
              >
                Replace
              </Button>
              {onDelete && (
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={isUploading}
                  onClick={(e) => {
                    e.preventDefault();
                    handleDelete();
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="mx-auto w-12 h-12 flex items-center justify-center bg-gray-100 rounded-lg">
              <ImageIcon className="h-6 w-6 text-gray-400" />
            </div>
            <div>
              <p className="text-sm font-medium">
                Drop logo here or click to upload
              </p>
              <p className="text-xs text-gray-500 mt-1">
                PNG, JPG, or SVG up to {maxSizeMB}MB
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
