'use client';

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, Video, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useJobsStore } from '@/store/jobs';
import { validateVideoFile, formatFileSize } from '@/lib/utils';
import toast from 'react-hot-toast';

interface VideoUploadProps {
  onJobCreated?: (jobId: string) => void;
}

export function VideoUpload({ onJobCreated }: VideoUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadOptions, setUploadOptions] = useState({
    add_captions: true,
    aspect_ratio: '9:16' as '9:16' | '1:1' | '16:9',
  });

  const { createVideoJob, isUploading, uploadProgress, error } = useJobsStore();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    console.log('onDrop called with files:', acceptedFiles);
    const file = acceptedFiles[0];
    if (!file) {
      console.log('No file provided');
      return;
    }

    console.log('File details:', {
      name: file.name,
      size: file.size,
      type: file.type
    });

    const validation = validateVideoFile(file);
    console.log('Validation result:', validation);
    if (!validation.isValid) {
      toast.error(validation.error || 'Invalid file');
      return;
    }

    setSelectedFile(file);
    toast.success(`Selected: ${file.name}`);
  }, []);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    onDragEnter: () => console.log('Drag enter'),
    onDragLeave: () => console.log('Drag leave'),
    onDragOver: () => console.log('Drag over'),
    onDropAccepted: (files) => console.log('Drop accepted:', files),
    onDropRejected: (rejectedFiles) => console.log('Drop rejected:', rejectedFiles),
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      const uploadData = {
        file: selectedFile,
        ...uploadOptions
      };
      const jobId = await createVideoJob(uploadData);
      toast.success('Video processing started!');
      onJobCreated?.(jobId);
      setSelectedFile(null);
    } catch (error) {
      console.error('Video upload error:', error);
      
      let errorMessage = 'Upload failed';
      if (error instanceof Error) {
        if (error.message.includes('401') || error.message.includes('Not authenticated')) {
          errorMessage = 'Authentication required - Please log in';
        } else if (error.message.includes('404') || error.message.includes('Not Found')) {
          errorMessage = 'Service unavailable - Please try again later';
        } else if (error.message.includes('422')) {
          errorMessage = 'Invalid file or missing required fields';
        } else if (error.message.includes('413')) {
          errorMessage = 'File too large - Maximum size is 500MB';
        } else {
          errorMessage = error.message;
        }
      }
      
      toast.error(errorMessage);
    }
  };





  return (
    <div className="space-y-6">

      
      {/* File Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Video className="h-6 w-6" />
            Upload Video
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            {...getRootProps()}
            className={`dropzone ${
              isDragActive ? 'active' : ''
            } ${isDragReject ? 'reject' : ''} ${
              isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
            }`}
          >
            <input {...getInputProps()} />
            <div className="space-y-4">
              <Upload className="mx-auto h-12 w-12 text-green-400" />
              {isDragActive ? (
                <p className="text-lg font-medium text-primary-600">
                  Drop your video here...
                </p>
              ) : (
                <div>
                  <p className="text-lg font-medium terminal-text">
                    Drag & drop your video here
                  </p>
                  <p className="text-sm terminal-text-dim mt-1">
                    or click to browse files
                  </p>
                </div>
              )}
              <p className="text-xs terminal-text-dim">
                Supports MP4, AVI, MOV, WMV, FLV, WebM, MKV (max 500MB)
              </p>
            </div>
          </div>

          {/* Selected File Info */}
          {selectedFile && (
            <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle className="h-5 w-5 text-green-600" />
              <div className="flex-1">
                <p className="font-medium text-green-900">{selectedFile.name}</p>
                <p className="text-sm text-green-700">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
            </div>
          )}

          {/* Upload Progress */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium text-blue-600">
                  {uploadProgress < 100 ? 'Uploading file...' : 'Upload complete - Starting video processing...'}
                </span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-bar-fill bg-blue-500"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              {uploadProgress < 100 && (
                <p className="text-xs text-gray-600">
                  Step 1 of 4: Uploading your video file
                </p>
              )}
              {uploadProgress === 100 && (
                <p className="text-xs text-green-600">
                  ✓ Upload complete! Video processing will begin shortly...
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Processing Options */}
      {selectedFile && !isUploading && (
        <Card>
          <CardHeader>
            <CardTitle>Processing Options</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Captions */}
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={uploadOptions.add_captions}
                  onChange={(e) =>
                    setUploadOptions(prev => ({
                      ...prev,
                      add_captions: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 text-primary-600 rounded border-gray-300 focus:ring-primary-500"
                />
                <span className="font-medium">Add Live Karaoke Captions</span>
              </label>
              <p className="text-sm terminal-text-dim ml-7">
                Automatically transcribe and add animated captions to your clips
              </p>
            </div>

            {/* Aspect Ratio */}
            <div className="space-y-3">
              <label className="block font-medium">Aspect Ratio</label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { value: '9:16', label: 'Vertical', desc: 'TikTok, Reels' },
                  { value: '1:1', label: 'Square', desc: 'Instagram' },
                  { value: '16:9', label: 'Landscape', desc: 'YouTube' },
                ].map((ratio) => (
                  <button
                    key={ratio.value}
                    onClick={() =>
                      setUploadOptions(prev => ({
                        ...prev,
                        aspect_ratio: ratio.value as '9:16' | '1:1' | '16:9',
                      }))
                    }
                    className={`p-3 border rounded-lg text-left transition-colors ${
                      uploadOptions.aspect_ratio === ratio.value
                        ? 'border-primary-500 bg-primary-50 text-primary-700'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-medium">{ratio.label}</div>
                    <div className="text-xs terminal-text-dim">{ratio.desc}</div>
                  </button>
                ))}
              </div>
            </div>



            {/* Upload Button */}
            <Button
              onClick={handleUpload}
              disabled={isUploading || !selectedFile}
              className="w-full"
              size="lg"
            >
              {isUploading ? (
                <>
                  <div className="spinner mr-2" />
                  Processing...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Start Processing
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
      {error && (
        <div className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <p className="text-red-900">{error}</p>
        </div>
      )}
    </div>
  );
}
