'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { VideoClipJob, JobEvent } from '@/types';
import { getStatusIcon, getStatusColor, formatDate } from '@/lib/utils';
import { Play, Download, RefreshCw } from 'lucide-react';
import { useJobsStore } from '@/store/jobs';
import toast from 'react-hot-toast';

interface JobProgressProps {
  jobId: string;
  onComplete?: (job: VideoClipJob) => void;
}

export function JobProgress({ jobId, onComplete }: JobProgressProps) {
  const { currentJob, fetchJob } = useJobsStore();
  const [isPlaying, setIsPlaying] = useState<string | null>(null);

  useEffect(() => {
    fetchJob(jobId);
  }, [jobId, fetchJob]);

  useEffect(() => {
    if (currentJob?.status === 'COMPLETED' && onComplete) {
      onComplete(currentJob);
    }
  }, [currentJob, onComplete]);

  if (!currentJob) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            <div className="spinner" />
            <span className="ml-2">Loading job details...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const getProgressColor = (status: string) => {
    switch (status) {
      case 'PENDING':
        return 'bg-yellow-500';
      case 'IN_PROGRESS':
        return 'bg-blue-500';
      case 'COMPLETED':
        return 'bg-green-500';
      case 'FAILED':
        return 'bg-red-500';
      default:
        return 'bg-gray-800';
    }
  };

  const getProgressPercentage = () => {
    if (currentJob.status === 'COMPLETED') return 100;
    if (currentJob.status === 'FAILED') return 0;
    return currentJob.progress_details?.percentage || 0;
  };

  const handleDownload = (clipUrl: string, filename: string) => {
    const link = document.createElement('a');
    link.href = clipUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Download started!');
  };

  const handlePlay = (clipUrl: string) => {
    setIsPlaying(clipUrl);
  };

  return (
    <div className="space-y-6">
      {/* Job Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span>{getStatusIcon(currentJob.status)}</span>
            Job Status
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="font-medium">
                {currentJob.progress_details?.description || 'Processing...'}
              </span>
              <span>{getProgressPercentage()}%</span>
            </div>
            <div className="progress-bar">
              <div
                className={`progress-bar-fill ${getProgressColor(currentJob.status)}`}
                style={{ width: `${getProgressPercentage()}%` }}
              />
            </div>
          </div>

          {/* Status Details */}
          <div className={`p-3 rounded-lg border ${getStatusColor(currentJob.status)}`}>
            <div className="flex items-center gap-2">
              <span className="text-lg">{getStatusIcon(currentJob.status)}</span>
              <div>
                <p className="font-medium capitalize">
                  {currentJob.status.toLowerCase().replace('_', ' ')}
                </p>
                {currentJob.progress_details?.stage && (
                  <p className="text-sm opacity-75">
                    Stage: {currentJob.progress_details.stage}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Job Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium">Job ID:</span>
              <p className="font-mono text-xs bg-black border border-green-500 text-green-400 p-1 rounded mt-1">
                {currentJob.id}
              </p>
            </div>
            <div>
              <span className="font-medium">Created:</span>
              <p className="mt-1">{formatDate(currentJob.created_at)}</p>
            </div>
          </div>

          {/* Error Message */}
          {currentJob.error_message && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-900 text-sm">
                <strong>Error:</strong> {currentJob.error_message}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {currentJob.status === 'COMPLETED' && currentJob.results && (
        <Card>
          <CardHeader>
            <CardTitle>Generated Clips</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Processing Details */}
              <div className="p-4 bg-black border border-green-500 rounded-lg">
                <h4 className="font-medium mb-2">Processing Summary</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="terminal-text-dim">Total Clips:</span>
                    <p className="font-medium">{currentJob.results.total_clips}</p>
                  </div>
                  <div>
                    <span className="terminal-text-dim">Video Duration:</span>
                    <p className="font-medium">
                      {Math.round(currentJob.results.video_duration)}s
                    </p>
                  </div>
                  <div>
                    <span className="terminal-text-dim">Captions Added:</span>
                    <p className="font-medium">
                      {currentJob.results.captions_added ? 'Yes' : 'No'}
                    </p>
                  </div>
                  <div>
                    <span className="terminal-text-dim">Processing Method:</span>
                    <p className="font-medium">
                      {currentJob.results.processing_details.processing_method}
                    </p>
                  </div>
                </div>
              </div>

              {/* Clips Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {currentJob.results.clips_by_platform.all.map((clip, index) => (
                  <div
                    key={index}
                    className="border border-gray-200 rounded-lg overflow-hidden"
                  >
                    {/* Video Player */}
                    <div className="relative aspect-video bg-black">
                      {isPlaying === clip.url ? (
                        <video
                          src={clip.url}
                          controls
                          autoPlay
                          className="w-full h-full object-contain"
                          onEnded={() => setIsPlaying(null)}
                        />
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handlePlay(clip.url)}
                            className="bg-black/90 hover:bg-black border border-green-500"
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </div>

                    {/* Clip Info */}
                    <div className="p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">
                          Clip {index + 1}
                        </span>
                        {clip.captions_added && (
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                            Captions
                          </span>
                        )}
                      </div>
                      
                      <div className="text-xs terminal-text-dim space-y-1">
                        <p>Duration: {Math.round(clip.duration)}s</p>
                        <p>Size: {(clip.file_size / 1024 / 1024).toFixed(1)}MB</p>
                        {clip.viral_info && (
                          <p>Viral Score: {clip.viral_info.viral_score}</p>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload(clip.url, `clip_${index + 1}.mp4`)}
                          className="flex-1"
                        >
                          <Download className="h-3 w-3 mr-1" />
                          Download
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Retry Button for Failed Jobs */}
      {currentJob.status === 'FAILED' && (
        <Card>
          <CardContent className="p-6">
            <div className="text-center space-y-4">
              <p className="terminal-text-dim">
                The job failed to complete. You can try again or contact support.
              </p>
              <Button
                onClick={() => fetchJob(jobId)}
                variant="outline"
                className="mx-auto"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Status
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
