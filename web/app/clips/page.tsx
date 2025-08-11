'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
// Remove unused Badge import since it's not being used in the code
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ArrowLeft, Play, Download, Share2, Copy, Video, ChevronDown, Edit2, Trash2, Save, X } from 'lucide-react';
import toast from 'react-hot-toast';

interface Clip {
  id: string;
  name: string;
  url: string;
  duration: number;
  file_size: number;
  captions_added: boolean;
  viral_info?: {
    viral_score: number;
  };
  created_at: string;
}

interface JobResult {
  id: string;
  status: string;
  total_clips: number;
  video_duration: number;
  captions_added: boolean;
  clips: Clip[];
  created_at: string;
}

export default function ClipsPage() {
  const [jobs, setJobs] = useState<JobResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<JobResult | null>(null);
  const [isPlaying, setIsPlaying] = useState<string | null>(null);
  const [editingClip, setEditingClip] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    fetchCompletedJobs();
  }, []);

  // Auto-select first job when jobs are loaded
  useEffect(() => {
    if (jobs.length > 0 && !selectedJob) {
      setSelectedJob(jobs[0]);
    }
  }, [jobs, selectedJob]);

  const fetchCompletedJobs = async () => {
    try {
      setIsLoading(true);
      
      // Fetch completed jobs from the main jobs API
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/jobs/history', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        const allJobs = data.jobs || [];
        
        // Filter for completed video jobs and process clips
        const completedJobs = allJobs
          .filter((job: any) => job.status === 'COMPLETED' && job.job_type === 'videoclip')
          .map((job: any) => {
            let results;
            try {
              results = typeof job.results === 'string' ? JSON.parse(job.results) : job.results;
            } catch (e: any) {
              console.error('Failed to parse job results:', e);
              return null;
            }

            // Extract clips from results
            const clipsData = results?.clips_by_platform?.all || [];
            
            // Process clips to ensure proper format
            const clips = clipsData.map((clip: any, index: number) => ({
              id: clip.id || `${job.id}_clip_${index + 1}`,
              name: clip.name || `Clip ${index + 1}`,
              url: clip.url || `/static/generated/final_${job.id}_clip_${index + 1}.mp4`,
              duration: clip.duration || 30,
              file_size: clip.file_size || 5000000,
              captions_added: clip.captions_added !== undefined ? clip.captions_added : true,
              viral_info: clip.viral_info || { viral_score: 7 },
              created_at: job.created_at
            }));

            return {
              id: job.id,
              status: job.status,
              total_clips: clips.length,
              video_duration: results?.video_duration || 60,
              captions_added: results?.captions_added !== undefined ? results.captions_added : true,
              clips: clips,
              created_at: job.created_at
            };
          })
          .filter((job: any) => job !== null && job.clips.length > 0);
        
        setJobs(completedJobs);
        if (completedJobs.length > 0) {
          toast.success(`Found ${completedJobs.length} jobs with ${completedJobs.reduce((total: number, job: any) => total + job.clips.length, 0)} clips`);
        } else {
          toast.error('No completed jobs with clips found');
        }
      } else {
        toast.error('Failed to load clips');
      }
    } catch (error: any) {
      console.error('Error fetching clips:', error);
      toast.error('Error loading clips');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePlay = (clipUrl: string) => {
    setIsPlaying(clipUrl);
  };

  const handleUpdateClipName = async (clipId: string, newName: string) => {
    try {
      const response = await fetch('/api/clips/user', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ clipId, name: newName }),
      });

      const result = await response.json();
      
      if (result.success) {
        toast.success('Clip name updated successfully');
        // Refresh the jobs data
        fetchCompletedJobs();
        setEditingClip(null);
        setEditingName('');
      } else {
        toast.error(result.error || 'Failed to update clip name');
      }
    } catch (error: any) {
      console.error('Error updating clip name:', error);
      toast.error('Failed to update clip name');
    }
  };

  const handleDeleteClip = async (clipId: string) => {
    if (!confirm('Are you sure you want to delete this clip? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await fetch('/api/clips/user', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ clipId }),
      });

      const result = await response.json();
      
      if (result.success) {
        toast.success('Clip deleted successfully');
        // Refresh the jobs data
        fetchCompletedJobs();
      } else {
        toast.error(result.error || 'Failed to delete clip');
      }
    } catch (error: any) {
      console.error('Error deleting clip:', error);
      toast.error('Failed to delete clip');
    }
  };

  const startEditing = (clipId: string, currentName: string) => {
    setEditingClip(clipId);
    setEditingName(currentName);
  };

  const cancelEditing = () => {
    setEditingClip(null);
    setEditingName('');
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

  const handleCopyUrl = (clipUrl: string) => {
    const fullUrl = `${window.location.origin}${clipUrl}`;
    navigator.clipboard.writeText(fullUrl);
    toast.success('Clip URL copied to clipboard!');
  };

  const handleShare = (clipUrl: string, index: number) => {
    const fullUrl = `${window.location.origin}${clipUrl}`;
    const shareData = {
      title: `Video Clip ${index + 1}`,
      text: 'Check out this AI-generated video clip!',
      url: fullUrl,
    };

    if (navigator.share) {
      navigator.share(shareData);
    } else {
      handleCopyUrl(clipUrl);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="spinner mb-4" />
            <p className="terminal-text">LOADING SOCIAL MEDIA CONTENT...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" size="sm" onClick={() => router.push('/')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            BACK
          </Button>
          <div>
            <h1 className="alien-league-title-orange-aura">SOCIAL MEDIA CONTENT READY</h1>
            <p className="alien-league-title">AI-Generated Video Clips</p>
          </div>
        </div>
        <div className="text-right">
          <div className="terminal-text text-sm">{jobs.length} JOBS AVAILABLE</div>
          <div className="terminal-text-dim text-xs">CLIPS READY FOR DOWNLOAD</div>
        </div>
      </div>

      {jobs.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <Video className="h-16 w-16 text-green-600 mx-auto mb-4" />
            <h3 className="alien-league-title text-xl mb-2">NO CLIPS AVAILABLE</h3>
            <p className="terminal-text-dim mb-6">Upload and process a video to generate social media clips</p>
            <Button onClick={() => router.push('/video')} className="mx-auto">
              <Video className="mr-2 h-4 w-4" />
              UPLOAD VIDEO
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Job Selector */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle className="alien-league-title">SELECT JOB</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <select
                    value={selectedJob?.id || ''}
                    onChange={(e) => {
                      const job = jobs.find(j => j.id === e.target.value);
                      if (job) setSelectedJob(job);
                    }}
                    className="w-full p-3 bg-black border border-green-500 text-green-400 font-digital text-sm appearance-none cursor-pointer hover:border-green-400 focus:border-green-400 focus:outline-none"
                  >
                    <option value="" disabled>Choose a job...</option>
                    {jobs.map((job, index) => (
                      <option key={job.id || `unknown-${index}`} value={job.id || ''} className="bg-black text-green-400">
                        JOB-{job.id ? job.id.slice(0, 8) : 'UNKNOWN'} • {job.total_clips} clips • {new Date(job.created_at).toLocaleDateString()}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-green-400 pointer-events-none" />
                </div>
                {selectedJob && (
                  <div className="mt-4 p-3 border border-green-500 bg-green-500/5">
                    <div className="font-digital text-sm text-green-400">
                      JOB-{selectedJob.id ? selectedJob.id.slice(0, 8) : 'UNKNOWN'}
                    </div>
                    <div className="text-xs text-green-600 mt-1">
                      {selectedJob.total_clips} clips • {new Date(selectedJob.created_at).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-green-400 mt-1 font-semibold">
                      ✅ READY FOR SOCIAL MEDIA
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Clips Display */}
          <div className="lg:col-span-3">
            {selectedJob && (
              <div className="space-y-6">
                {/* Job Summary */}
                <Card>
                  <CardHeader>
                    <CardTitle className="alien-league-title flex items-center">
                      <Play className="mr-2 h-6 w-6" />
                      CLIPS FROM JOB-{selectedJob.id ? selectedJob.id.slice(0, 8) : 'UNKNOWN'}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div className="border border-green-500 p-3 text-center">
                        <div className="terminal-text-bold text-2xl">{selectedJob.total_clips}</div>
                        <div className="terminal-text-dim text-xs">TOTAL CLIPS</div>
                      </div>
                      <div className="border border-green-500 p-3 text-center">
                        <div className="terminal-text-bold text-2xl">{Math.round(selectedJob.video_duration)}s</div>
                        <div className="terminal-text-dim text-xs">ORIGINAL LENGTH</div>
                      </div>
                      <div className="border border-green-500 p-3 text-center">
                        <div className="terminal-text-bold text-2xl">{selectedJob.captions_added ? 'YES' : 'NO'}</div>
                        <div className="terminal-text-dim text-xs">CAPTIONS</div>
                      </div>
                      <div className="border border-green-500 p-3 text-center">
                        <div className="terminal-text-bold text-2xl">4K</div>
                        <div className="terminal-text-dim text-xs">QUALITY</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Clips Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {selectedJob.clips.map((clip, index) => (
                    <Card key={clip.id} className="overflow-hidden">
                      {/* Video Player */}
                      <div className="relative aspect-video bg-black border border-green-500">
                        {isPlaying === clip.url ? (
                          <video
                            src={clip.url}
                            controls
                            autoPlay
                            className="w-full h-full object-contain"
                            onEnded={() => setIsPlaying(null)}
                            onError={(e) => {
                              console.error('Video playback error:', e);
                              toast.error('Failed to play video');
                              setIsPlaying(null);
                            }}
                          />
                        ) : (
                          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80">
                            <Button
                              variant="secondary"
                              size="lg"
                              onClick={() => {
                                console.log('Playing clip:', clip.url);
                                handlePlay(clip.url);
                              }}
                              className="bg-green-600 hover:bg-green-700 text-white border-0 mb-2"
                            >
                              <Play className="h-8 w-8" />
                            </Button>
                            <div className="text-xs text-green-400 text-center px-2">
                              CLIP {index + 1} • {Math.round(clip.duration)}s
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Clip Info */}
                      <CardContent className="p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          {editingClip === clip.id ? (
                            <div className="flex items-center gap-2 flex-1">
                              <Input
                                value={editingName}
                                onChange={(e) => setEditingName(e.target.value)}
                                className="flex-1 text-xs"
                                placeholder="Enter clip name"
                              />
                              <Button
                                size="sm"
                                onClick={() => handleUpdateClipName(clip.id, editingName)}
                                disabled={!editingName.trim()}
                                className="text-xs"
                              >
                                <Save className="h-3 w-3" />
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={cancelEditing}
                                className="text-xs"
                              >
                                <X className="h-3 w-3" />
                              </Button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 flex-1">
                              <span className="terminal-text-bold text-xs">{clip.name}</span>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => startEditing(clip.id, clip.name)}
                                className="text-xs p-1 h-6 w-6"
                              >
                                <Edit2 className="h-3 w-3" />
                              </Button>
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            {clip.captions_added && (
                              <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                                CAPTIONS
                              </span>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-red-600 hover:text-red-700 hover:bg-red-50 text-xs p-1 h-6 w-6"
                              onClick={() => handleDeleteClip(clip.id)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                        
                        <div className="text-xs terminal-text-dim space-y-1">
                          <p>Duration: {Math.round(clip.duration)}s</p>
                          <p>Size: {(clip.file_size / 1024 / 1024).toFixed(1)}MB</p>
                          {clip.viral_info && (
                            <p>Viral Score: {clip.viral_info.viral_score}/10</p>
                          )}
                          <p>Created: {new Date(clip.created_at).toLocaleDateString()}</p>
                        </div>

                        {/* Action Buttons */}
                        <div className="grid grid-cols-3 gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDownload(clip.url, `${clip.name}.mp4`)}
                            className="text-xs"
                          >
                            <Download className="h-3 w-3 mr-1" />
                            DOWNLOAD
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleCopyUrl(clip.url)}
                            className="text-xs"
                          >
                            <Copy className="h-3 w-3 mr-1" />
                            COPY URL
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleShare(clip.url, index)}
                            className="text-xs"
                          >
                            <Share2 className="h-3 w-3 mr-1" />
                            SHARE
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-green-500 pt-4">
        <div className="flex justify-between items-center text-xs text-green-600">
          <span className="font-digital">SOCIAL MEDIA READY</span>
          <span className="font-digital">AI-OPTIMIZED CLIPS</span>
          <span className="font-digital">INSTANT DOWNLOAD</span>
        </div>
      </div>
    </div>
  );
}